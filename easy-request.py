#!/usr/bin/env python3
import sys
import json
import argparse
import socket
import ssl
from urllib.parse import urlparse
from typing import Tuple, Optional


DEFAULT_TIMEOUT = 10
VALID_METHODS = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
METHODS_WITH_BODY = {'POST', 'PUT', 'PATCH'}


def read_data_from_arg(data_arg: str | None) -> str:
    if data_arg and data_arg.startswith('@'):
        filepath = data_arg[1:]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except OSError as e:
            print(f"错误: 无法读取文件 {filepath} - {e}")
            sys.exit(1)
    return data_arg or ''


def parse_headers(headers_arg: str | None) -> dict[str, str]:
    if not headers_arg:
        return {}

    try:
        parsed = json.loads(headers_arg)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass

    headers = {}
    for pair in headers_arg.split(','):
        if ':' in pair:
            key, value = pair.split(':', 1)
            headers[key.strip()] = value.strip()
    return headers


def ensure_url_scheme(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        print(f"提示: URL缺少协议，已自动添加 http://")
        return 'http://' + url
    return url


def parse_url(url: str) -> Tuple[str, int, str, bool]:
    """解析URL，返回 (host, port, path, is_https)"""
    parsed = urlparse(url)
    host = parsed.hostname or ''
    is_https = parsed.scheme == 'https'
    port = parsed.port or (443 if is_https else 80)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query
    return host, port, path, is_https


def create_ssl_context(ca_file: str | None) -> ssl.SSLContext:
    """创建SSL上下文，支持自定义CA证书"""
    if ca_file:
        context = ssl.create_default_context(cafile=ca_file)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
    else:
        context = ssl.create_default_context()
    return context


def build_request(method: str, path: str, headers: dict[str, str], data: str) -> bytes:
    """构建HTTP请求字节流"""
    lines = [f"{method} {path} HTTP/1.1"]

    host_header = headers.get('Host') or headers.get('host')
    if not host_header:
        pass

    if data and 'Content-Length' not in headers and 'content-length' not in headers:
        headers['Content-Length'] = str(len(data.encode('utf-8')))

    for key, value in headers.items():
        lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("")
    request = "\r\n".join(lines)

    if data:
        request += data

    return request.encode('utf-8')


def parse_response(response_bytes: bytes) -> Tuple[int, dict[str, str], str]:
    """解析HTTP响应，返回 (status_code, headers, body)"""
    header_end = response_bytes.find(b'\r\n\r\n')
    if header_end == -1:
        header_end = response_bytes.find(b'\n\n')
        if header_end == -1:
            return 0, {}, response_bytes.decode('utf-8', errors='replace')

    header_bytes = response_bytes[:header_end]
    body_bytes = response_bytes[header_end + 4:]

    header_lines = header_bytes.decode('utf-8', errors='replace').split('\r\n')
    if not header_lines:
        return 0, {}, body_bytes.decode('utf-8', errors='replace')

    status_line = header_lines[0]
    try:
        status_code = int(status_line.split(' ')[1])
    except (IndexError, ValueError):
        status_code = 0

    headers = {}
    for line in header_lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()

    body = body_bytes.decode('utf-8', errors='replace')
    return status_code, headers, body


def recv_all(sock: socket.socket, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """接收完整的HTTP响应"""
    sock.settimeout(timeout)

    header_chunks = []
    header_end = -1
    while header_end == -1:
        chunk = sock.recv(4096)
        if not chunk:
            break
        header_chunks.append(chunk)
        combined = b''.join(header_chunks)
        header_end = combined.find(b'\r\n\r\n')
        if header_end == -1:
            header_end = combined.find(b'\n\n')

    if header_end == -1:
        return b''.join(header_chunks)

    header_bytes = b''.join(header_chunks)[:header_end + 4]
    body_start = header_end + 4
    remaining_body = b''.join(header_chunks)[body_start:]

    header_text = header_bytes.decode('utf-8', errors='replace')
    content_length = None
    chunked = False
    connection_close = False

    for line in header_text.split('\r\n'):
        line_lower = line.lower()
        if line_lower.startswith('content-length:'):
            try:
                content_length = int(line.split(':', 1)[1].strip())
            except (ValueError, IndexError):
                pass
        elif line_lower.startswith('transfer-encoding:') and 'chunked' in line_lower:
            chunked = True
        elif line_lower.startswith('connection:') and 'close' in line_lower:
            connection_close = True

    body_chunks = [remaining_body] if remaining_body else []
    total_body_len = len(remaining_body)

    if chunked:
        while True:
            combined = b''.join(body_chunks)
            while True:
                chunk_end = combined.find(b'\r\n')
                if chunk_end == -1:
                    break
                size_line = combined[:chunk_end]
                try:
                    chunk_size = int(size_line.strip(), 16)
                except ValueError:
                    chunk_size = 0

                if chunk_size == 0:
                    if len(combined) >= chunk_end + 4:
                        return header_bytes + combined[:chunk_end + 4]
                    break

                chunk_data_start = chunk_end + 2
                chunk_data_end = chunk_data_start + chunk_size
                if len(combined) >= chunk_data_end + 2:
                    combined = combined[chunk_data_end + 2:]
                    continue
                break

            chunk = sock.recv(4096)
            if not chunk:
                break
            body_chunks.append(chunk)

    elif content_length is not None:
        while total_body_len < content_length:
            chunk = sock.recv(4096)
            if not chunk:
                break
            body_chunks.append(chunk)
            total_body_len += len(chunk)

    else:
        if connection_close:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                body_chunks.append(chunk)
        else:
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    body_chunks.append(chunk)
            except socket.timeout:
                pass

    return header_bytes + b''.join(body_chunks)


def send_request(url: str, method: str, headers: dict[str, str], data: str, ca_file: str | None = None) -> bool:
    url = ensure_url_scheme(url)
    method = method.upper()

    if method not in VALID_METHODS:
        print(f"错误: 不支持的请求类型 '{method}'")
        print(f"支持的请求类型: {', '.join(sorted(VALID_METHODS))}")
        return False

    host, port, path, is_https = parse_url(url)

    if ca_file and not is_https:
        print("错误: 使用 --ca 参数时，URL 必须使用 HTTPS 协议")
        return False

    if 'Host' not in headers and 'host' not in headers:
        headers['Host'] = host

    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'easy-request/1.0'

    if 'Connection' not in headers and 'connection' not in headers:
        headers['Connection'] = 'close'

    print(f"发送 {method} 请求到: {url}")
    print(f"请求头: {headers}")
    preview = data[:200] + ('...' if len(data) > 200 else '')
    print(f"请求内容: {preview}")

    try:
        sock = socket.create_connection((host, port), timeout=DEFAULT_TIMEOUT)

        if is_https:
            context = create_ssl_context(ca_file)
            sock = context.wrap_socket(sock, server_hostname=host)

        request_bytes = build_request(method, path, headers, data)
        sock.sendall(request_bytes)

        response_bytes = recv_all(sock)
        sock.close()

        status_code, resp_headers, body = parse_response(response_bytes)

        print(f"\n响应状态码: {status_code}")
        print("响应头:")
        for key, value in resp_headers.items():
            print(f"  {key}: {value}")
        print("\n响应内容:")
        try:
            print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(body[:1000])

        return True

    except socket.timeout:
        print("错误: 请求超时。")
    except ConnectionRefusedError:
        print("错误: 连接被拒绝。")
    except socket.gaierror:
        print("错误: 域名解析失败。")
    except ssl.SSLError as e:
        print(f"错误: SSL/TLS错误 - {e}")
    except Exception as e:
        print(f"错误: 请求失败 - {e}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description='向指定URL发送HTTP请求（支持自定义请求类型、请求头和内容）',
        add_help=False
    )
    parser.add_argument('url', nargs='?', help='目标URL（可省略协议，默认添加http://）')
    parser.add_argument('method', nargs='?', help='请求类型（GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS）')
    parser.add_argument('headers', nargs='?', help='请求头（JSON格式或键值对，如 "Content-Type: application/json"）')
    parser.add_argument('data', nargs='?', help='请求内容。可使用 @文件名 从文件读取，或通过标准输入传递')
    parser.add_argument('--ca', metavar='FILE', help='自定义CA证书文件路径（PEM格式），要求URL使用HTTPS')
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')

    args = parser.parse_args()

    if args.help or len(sys.argv) == 1:
        print("""
easy-request - 自定义HTTP请求工具

格式:
  easy-request <URL*> <请求类型*> <请求头*> <请求内容*>（带*为必须）

参数说明:
  URL      目标地址（可省略协议，默认添加 http://）
  请求类型  HTTP方法：GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
  请求头    自定义请求头，支持格式：
            - JSON格式：'{"Content-Type":"application/json","Authorization":"Bearer token"}'
            - 键值对：'Content-Type: application/json, User-Agent: test'
  请求内容  要发送的数据。支持：
            - 直接作为参数传递
            - 以 @ 开头表示文件路径
            - 省略时自动从标准输入读取（如果存在）

选项:
  --ca FILE  自定义CA证书文件（PEM格式），要求URL使用HTTPS

示例:
  1. 发送GET请求:
     easy-request https://httpbin.org/get GET '{"Accept":"application/json"}' ''

  2. 发送POST请求（JSON数据）:
     easy-request https://httpbin.org/post POST '{"Content-Type":"application/json"}' '{"name":"test"}'

  3. 发送PUT请求（从文件读取数据）:
     easy-request https://httpbin.org/put PUT 'Content-Type: application/json' @data.json

  4. 发送DELETE请求:
     easy-request https://httpbin.org/delete DELETE '{}' ''

  5. 使用自定义CA证书:
     easy-request https://internal-api.example.com GET '{}' '' --ca /path/to/ca.pem

  6. 查看帮助:
     easy-request -h
        """)
        return 0

    if not args.url or not args.method or not args.headers:
        print("错误: 需要4个必需参数：URL、请求类型、请求头、请求内容")
        print("使用 'easy-request -h' 查看帮助")
        return 1

    headers = parse_headers(args.headers)
    data = read_data_from_arg(args.data)
    if not data and not sys.stdin.isatty():
        data = sys.stdin.read().strip()

    return 0 if send_request(args.url, args.method, headers, data, args.ca) else 1


if __name__ == "__main__":
    sys.exit(main())