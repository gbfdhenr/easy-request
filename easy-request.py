#!/usr/bin/env python3
"""
easy-request - 自定义HTTP请求工具 / Custom HTTP Request Tool

基于 httpx 库，支持 HTTP/1.1 和 HTTP/2，处理压缩、多值头、大小限制、二进制上传/下载、重定向等。
Based on httpx library, supports HTTP/1.1 and HTTP/2, compression, multi-value headers, size limits, binary upload/download, redirects.
"""
import sys
import json
import argparse
import os
import ssl
from typing import Tuple, Optional, Dict, List, Union, BinaryIO
from urllib.parse import urlparse

import httpx

DEFAULT_TIMEOUT = 10.0
MAX_RESPONSE_SIZE = 10 * 1024 * 1024
MAX_REDIRECTS = 10
VALID_METHODS = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
NO_BODY_METHODS = {'HEAD'}
NO_BODY_STATUS = {100, 101, 204, 304}
REDIRECT_STATUS = {301, 302, 303, 307, 308}
SENSITIVE_HEADERS = {'authorization', 'cookie', 'set-cookie', 'proxy-authorization',
                     'www-authenticate', 'proxy-authenticate', 'x-api-key', 'x-auth-token'}
TEXT_MIME_PREFIXES = ('text/', 'application/json', 'application/xml', 'application/javascript',
                      'application/x-www-form-urlencoded', 'application/ld+json')

Headers = Dict[str, str]
MultiHeaders = Dict[str, List[str]]
HeaderCaseMap = Dict[str, str]

# =============================================================================
# 翻译字典 / Translation Dictionary
# =============================================================================
TRANSLATIONS = {
    'zh': {
        'app_name': 'easy-request - 自定义HTTP请求工具',
        'usage': '格式: easy-request <URL*> <请求类型*> [请求头] [请求内容] [选项]',
        'url_desc': '目标地址（可省略协议，默认添加 http://）',
        'method_desc': 'HTTP方法：GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS',
        'headers_desc': '自定义请求头（可选），支持格式：',
        'headers_json': '  - JSON格式（推荐复杂头）：\'{"Content-Type":"application/json","Authorization":"Bearer token"}\'',
        'headers_kv': '  - 键值对：\'Content-Type: application/json, User-Agent: test\'',
        'headers_empty': '  - 省略或空字符串表示无自定义头',
        'data_desc': '要发送的数据（可选）。支持：',
        'data_direct': '  - 直接作为参数传递',
        'data_file': '  - 以 @ 开头表示文件路径',
        'data_stdin': '  - - 表示从标准输入读取',
        'data_auto': '  - 省略时自动从标准输入读取（如果存在）',
        'opt_binary': '  -b, --binary       以二进制模式读取文件/标准输入，用于上传图片等二进制数据',
        'opt_location': '  -L, --location     自动跟随重定向 (301/302/303/307/308)',
        'opt_max_redirects': '  --max-redirects N  最大重定向次数 (默认 {max_redirects})',
        'opt_ca': '  --ca FILE          自定义CA证书文件（PEM格式），要求URL使用HTTPS',
        'opt_help': '  -h, --help         显示帮助信息',
        'examples': '示例:',
        'ex_get': '  1. 发送GET请求:',
        'ex_get_cmd': '     easy-request https://httpbin.org/get GET \'{"Accept":"application/json"}\' \'\'',
        'ex_post': '  2. 发送POST请求（JSON数据）:',
        'ex_post_cmd': '     easy-request https://httpbin.org/post POST \'{"Content-Type":"application/json"}\' \'{"name":"test"}\'',
        'ex_put': '  3. 发送PUT请求（从文件读取数据）:',
        'ex_put_cmd': '     easy-request https://httpbin.org/put PUT \'Content-Type: application/json\' @data.json',
        'ex_delete': '  4. 发送DELETE请求:',
        'ex_delete_cmd': '     easy-request https://httpbin.org/delete DELETE \'{}\' \'\'',
        'ex_ca': '  5. 使用自定义CA证书:',
        'ex_ca_cmd': '     easy-request https://internal-api.example.com GET \'{}\' \'\' --ca /path/to/ca.pem',
        'ex_binary': '  6. 上传二进制文件（图片等）:',
        'ex_binary_cmd': '     easy-request https://httpbin.org/post POST \'Content-Type: image/png\' @image.png -b',
        'ex_stdin': '  7. 从stdin读取二进制数据:',
        'ex_stdin_cmd': '     cat image.png | easy-request https://httpbin.org/post POST \'Content-Type: image/png\' - -b',
        'ex_redirect': '  8. 自动跟随重定向:',
        'ex_redirect_cmd': '     easy-request https://httpbin.org/redirect/3 GET \'\' \'\' -L',
        'ex_help': '  9. 查看帮助:',
        'ex_help_cmd': '     easy-request -h',

        'url_scheme_hint': '提示: URL缺少协议，已自动添加 http://',
        'sending_request': '发送 {method} 请求到: {url}',
        'request_headers': '请求头:',
        'request_body_binary': '请求内容: <二进制数据 {length} 字节>',
        'request_body_text': '请求内容: {preview}',
        'err_unsupported_method': '不支持的请求类型 \'{method}\'',
        'err_valid_methods': '支持的请求类型: {methods}',
        'err_ca_requires_https': '使用 --ca 参数时，URL 必须使用 HTTPS 协议',
        'err_invalid_port': '无效端口: {port}',
        'err_read_file': '无法读取文件 {filepath} - {error}',
        'err_timeout': '请求超时。',
        'err_connection_refused': '连接被拒绝。',
        'err_dns_failed': '域名解析失败。',
        'err_ssl': 'SSL/TLS错误 - {error}',
        'err_network': '网络错误 - {error}',
        'err_request_failed': '请求失败 - {error}',
        'err_missing_url_method': '需要URL和请求类型参数',
        'err_help_hint': '使用 \'easy-request -h\' 查看帮助',
        'err_max_redirects': '--max-redirects 必须为非负整数',
        'err_redirect_limit': '重定向次数超过限制 ({max_redirects})',
        'err_response_too_large': '响应过大，超过 {max_size} 字节限制',
        'err_prefix': '错误: ',
        'redirect_msg': '重定向 ({status_code}) -> {location}',
        'response_status': '响应状态码: {status_code}',
        'response_headers': '响应头:',
    },
    'en': {
        'app_name': 'easy-request - Custom HTTP Request Tool',
        'usage': 'Usage: easy-request <URL*> <METHOD*> [HEADERS] [DATA] [OPTIONS]',
        'url_desc': 'Target URL (protocol optional, defaults to http://)',
        'method_desc': 'HTTP method: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS',
        'headers_desc': 'Custom headers (optional). Supported formats:',
        'headers_json': '  - JSON (recommended for complex headers): \'{"Content-Type":"application/json","Authorization":"Bearer token"}\'',
        'headers_kv': '  - Key-value pairs: \'Content-Type: application/json, User-Agent: test\'',
        'headers_empty': '  - Omit or empty string for no custom headers',
        'data_desc': 'Request data (optional). Supports:',
        'data_direct': '  - Direct argument',
        'data_file': '  - @ prefix for file path',
        'data_stdin': '  - - for stdin',
        'data_auto': '  - Omit to auto-read from stdin (if available)',
        'opt_binary': '  -b, --binary       Read file/stdin as binary (for images, etc.)',
        'opt_location': '  -L, --location     Follow redirects (301/302/303/307/308)',
        'opt_max_redirects': '  --max-redirects N  Max redirects (default {max_redirects})',
        'opt_ca': '  --ca FILE          Custom CA certificate (PEM), requires HTTPS',
        'opt_help': '  -h, --help         Show help',
        'examples': 'Examples:',
        'ex_get': '  1. GET request:',
        'ex_get_cmd': '     easy-request https://httpbin.org/get GET \'{"Accept":"application/json"}\' \'\'',
        'ex_post': '  2. POST request (JSON):',
        'ex_post_cmd': '     easy-request https://httpbin.org/post POST \'{"Content-Type":"application/json"}\' \'{"name":"test"}\'',
        'ex_put': '  3. PUT request (from file):',
        'ex_put_cmd': '     easy-request https://httpbin.org/put PUT \'Content-Type: application/json\' @data.json',
        'ex_delete': '  4. DELETE request:',
        'ex_delete_cmd': '     easy-request https://httpbin.org/delete DELETE \'{}\' \'\'',
        'ex_ca': '  5. Custom CA certificate:',
        'ex_ca_cmd': '     easy-request https://internal-api.example.com GET \'{}\' \'\' --ca /path/to/ca.pem',
        'ex_binary': '  6. Upload binary file (image, etc.):',
        'ex_binary_cmd': '     easy-request https://httpbin.org/post POST \'Content-Type: image/png\' @image.png -b',
        'ex_stdin': '  7. Read binary from stdin:',
        'ex_stdin_cmd': '     cat image.png | easy-request https://httpbin.org/post POST \'Content-Type: image/png\' - -b',
        'ex_redirect': '  8. Follow redirects:',
        'ex_redirect_cmd': '     easy-request https://httpbin.org/redirect/3 GET \'\' \'\' -L',
        'ex_help': '  9. Show help:',
        'ex_help_cmd': '     easy-request -h',

        'url_scheme_hint': 'Note: URL missing scheme, defaulting to http://',
        'sending_request': 'Sending {method} request to: {url}',
        'request_headers': 'Request headers:',
        'request_body_binary': 'Request body: <binary data {length} bytes>',
        'request_body_text': 'Request body: {preview}',
        'err_unsupported_method': 'Unsupported method \'{method}\'',
        'err_valid_methods': 'Supported methods: {methods}',
        'err_ca_requires_https': 'When using --ca, URL must use HTTPS',
        'err_invalid_port': 'Invalid port: {port}',
        'err_read_file': 'Cannot read file {filepath} - {error}',
        'err_timeout': 'Request timeout.',
        'err_connection_refused': 'Connection refused.',
        'err_dns_failed': 'DNS resolution failed.',
        'err_ssl': 'SSL/TLS error - {error}',
        'err_network': 'Network error - {error}',
        'err_request_failed': 'Request failed - {error}',
        'err_missing_url_method': 'URL and method are required',
        'err_help_hint': 'Use \'easy-request -h\' for help',
        'err_max_redirects': '--max-redirects must be a non-negative integer',
        'err_redirect_limit': 'Redirect limit exceeded ({max_redirects})',
        'err_response_too_large': 'Response too large, exceeds {max_size} bytes limit',
        'err_prefix': 'Error: ',
        'redirect_msg': 'Redirect ({status_code}) -> {location}',
        'response_status': 'Response status: {status_code}',
        'response_headers': 'Response headers:',
    }
}


def detect_language(args_lang: Optional[str]) -> str:
    if args_lang:
        lang = args_lang.lower()
        if lang in ('zh', 'cn', 'chinese'):
            return 'zh'
        if lang in ('en', 'us', 'english'):
            return 'en'
    env_lang = os.environ.get('EASY_REQUEST_LANG', '').lower()
    if env_lang in ('zh', 'cn', 'chinese'):
        return 'zh'
    if env_lang in ('en', 'us', 'english'):
        return 'en'
    return 'zh'


class I18n:
    def __init__(self, lang: str):
        self.lang = lang if lang in TRANSLATIONS else 'zh'
        self.t = TRANSLATIONS[self.lang]

    def tr(self, key: str, **kwargs) -> str:
        template = self.t.get(key, TRANSLATIONS['zh'].get(key, key))
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except KeyError:
            return template


_i18n: Optional[I18n] = None


def get_i18n() -> I18n:
    global _i18n
    if _i18n is None:
        _i18n = I18n('zh')
    return _i18n


def set_i18n(lang: str) -> None:
    global _i18n
    _i18n = I18n(lang)


def log_info(msg: str) -> None:
    print(msg, file=sys.stderr)


def log_error(msg: str) -> None:
    prefix = get_i18n().t.get('err_prefix', '错误: ')
    print(f"{prefix}{msg}", file=sys.stderr)


def sanitize_header_value(value: str) -> str:
    return value.replace('\r', '').replace('\n', '')


def sanitize_path(path: str) -> str:
    return path.replace('\r', '').replace('\n', '')


def mask_sensitive_header(key: str, value: str) -> str:
    if key.lower() in SENSITIVE_HEADERS:
        return '***MASKED***'
    return value


def read_data_from_arg(data_arg: Optional[str], binary: bool = False) -> Union[str, bytes]:
    if data_arg == '-':
        return read_data_from_stdin(binary)
    if data_arg and data_arg.startswith('@'):
        filepath = data_arg[1:]
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            if binary:
                return data
            return data.decode('utf-8', errors='replace')
        except OSError as e:
            log_error(get_i18n().tr('err_read_file', filepath=filepath, error=e))
            sys.exit(1)
    if binary:
        return (data_arg or '').encode('utf-8')
    return data_arg or ''


def read_data_from_stdin(binary: bool = False) -> Union[str, bytes]:
    if not sys.stdin.isatty():
        data = sys.stdin.buffer.read() if binary else sys.stdin.read()
        return data
    return b'' if binary else ''


def parse_headers(headers_arg: Optional[str]) -> Headers:
    if not headers_arg:
        return {}

    try:
        parsed = json.loads(headers_arg)
        if isinstance(parsed, dict):
            return {str(k): sanitize_header_value(str(v)) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass

    headers: Headers = {}
    for pair in headers_arg.split(','):
        if ':' in pair:
            key, value = pair.split(':', 1)
            headers[key.strip()] = sanitize_header_value(value.strip())
    return headers


def ensure_url_scheme(url: str) -> str:
    if '://' not in url:
        log_info(get_i18n().tr('url_scheme_hint'))
        return 'http://' + url
    return url


def build_host_header(host: str, port: int, is_https: bool) -> str:
    default_port = 443 if is_https else 80
    if port != default_port:
        return f"{host}:{port}"
    return host


def is_text_response(headers: httpx.Headers) -> bool:
    ct = headers.get('content-type', '').lower()
    return any(ct.startswith(p) for p in TEXT_MIME_PREFIXES)


def is_redirect(status_code: int) -> bool:
    return status_code in REDIRECT_STATUS


def resolve_redirect_url(base_url: str, location: str) -> str:
    if location.startswith('http://') or location.startswith('https://'):
        return location
    parsed = urlparse(base_url)
    scheme = parsed.scheme or 'http'
    netloc = parsed.netloc
    if location.startswith('/'):
        return f"{scheme}://{netloc}{location}"
    base_path = parsed.path or '/'
    base_dir = base_path.rsplit('/', 1)[0] + '/'
    return f"{scheme}://{netloc}{base_dir}{location}"


def create_client(
    ca_file: Optional[str],
    follow_redirects: bool,
    max_redirects: int,
    timeout: float,
) -> httpx.Client:
    verify = True
    if ca_file:
        verify = ca_file

    return httpx.Client(
        follow_redirects=follow_redirects,
        max_redirects=max_redirects,
        timeout=httpx.Timeout(timeout, connect=timeout, read=timeout),
        verify=verify,
        http2=True,
    )


def send_request(
    url: str,
    method: str,
    headers: Headers,
    data: Union[str, bytes],
    ca_file: Optional[str] = None,
    follow_redirects: bool = False,
    max_redirects: int = MAX_REDIRECTS,
) -> bool:
    i18n = get_i18n()
    method = method.upper()

    if method not in VALID_METHODS:
        log_error(i18n.tr('err_unsupported_method', method=method))
        log_error(i18n.tr('err_valid_methods', methods=', '.join(sorted(VALID_METHODS))))
        return False

    url = ensure_url_scheme(url)

    # httpx 会自动处理 Host 头和重定向，不需要手动设置
    # 但保留 User-Agent 和 Connection 用户可覆盖
    headers_lower = {k.lower(): k for k in headers}
    if 'user-agent' not in headers_lower:
        headers['User-Agent'] = 'easy-request/1.0'

    # 打印请求信息
    log_info(i18n.tr('sending_request', method=method, url=url))
    log_info(i18n.tr('request_headers'))
    for key, value in headers.items():
        log_info(f"  {key}: {mask_sensitive_header(key, value)}")
    if isinstance(data, bytes):
        log_info(i18n.tr('request_body_binary', length=len(data)))
    else:
        preview = data[:200] + ('...' if len(data) > 200 else '')
        log_info(i18n.tr('request_body_text', preview=preview))

    try:
        client = create_client(ca_file, follow_redirects, max_redirects, DEFAULT_TIMEOUT)

        # 准备请求参数
        req_kwargs = {
            'method': method,
            'url': url,
            'headers': headers,
        }

        # 处理请求体
        if data:
            if isinstance(data, bytes):
                req_kwargs['content'] = data
            else:
                req_kwargs['data'] = data

        # 发送请求
        response = client.request(**req_kwargs)

        # 检查响应大小
        content_length = response.headers.get('content-length')
        if content_length:
            try:
                if int(content_length) > MAX_RESPONSE_SIZE:
                    log_error(i18n.tr('err_response_too_large', max_size=MAX_RESPONSE_SIZE))
                    return False
            except ValueError:
                pass

        # 读取响应体（流式，限制大小）
        body_bytes = b''
        total_read = 0
        for chunk in response.iter_bytes(chunk_size=8192):
            total_read += len(chunk)
            if total_read > MAX_RESPONSE_SIZE:
                log_error(i18n.tr('err_response_too_large', max_size=MAX_RESPONSE_SIZE))
                return False
            body_bytes += chunk

        # 输出响应
        print(i18n.tr('response_status', status_code=response.status_code))
        print(i18n.tr('response_headers'))
        for key, value in response.headers.items():
            # httpx 返回的 headers 保留原始大小写
            print(f"  {key}: {value}")
        print()

        if is_text_response(response.headers):
            charset = 'utf-8'
            content_type = response.headers.get('content-type', '')
            if 'charset=' in content_type:
                for part in content_type.split(';'):
                    part = part.strip()
                    if part.lower().startswith('charset='):
                        charset = part[8:].strip(' "\'')
                        break
            try:
                body_text = body_bytes.decode(charset, errors='replace')
            except LookupError:
                body_text = body_bytes.decode('utf-8', errors='replace')
            print(body_text)
        else:
            sys.stdout.buffer.write(body_bytes)
            sys.stdout.buffer.flush()

        return True

    except httpx.TimeoutException:
        log_error(i18n.tr('err_timeout'))
    except httpx.ConnectError as e:
        log_error(i18n.tr('err_connection_refused'))
        log_error(str(e))
    except httpx.NetworkError as e:
        log_error(i18n.tr('err_network', error=e))
    except httpx.TooManyRedirects:
        log_error(i18n.tr('err_redirect_limit', max_redirects=max_redirects))
    except httpx.InvalidURL as e:
        log_error(i18n.tr('err_request_failed', error=e))
    except ssl.SSLError as e:
        log_error(i18n.tr('err_ssl', error=e))
    except Exception as e:
        log_error(i18n.tr('err_request_failed', error=e))
    return False


def print_help(i18n: I18n) -> None:
    max_r = MAX_REDIRECTS
    print(i18n.tr('app_name'))
    print()
    print(i18n.tr('usage'))
    print()
    print(f"  URL        {i18n.tr('url_desc')}")
    print(f"  METHOD     {i18n.tr('method_desc')}")
    print(f"  HEADERS    {i18n.tr('headers_desc')}")
    print(i18n.tr('headers_json'))
    print(i18n.tr('headers_kv'))
    print(i18n.tr('headers_empty'))
    print(f"  DATA       {i18n.tr('data_desc')}")
    print(i18n.tr('data_direct'))
    print(i18n.tr('data_file'))
    print(i18n.tr('data_stdin'))
    print(i18n.tr('data_auto'))
    print()
    print("Options:")
    print(i18n.tr('opt_binary'))
    print(i18n.tr('opt_location'))
    print(i18n.tr('opt_max_redirects').format(max_redirects=max_r))
    print(i18n.tr('opt_ca'))
    print(i18n.tr('opt_help'))
    print()
    print(i18n.tr('examples'))
    print(i18n.tr('ex_get'))
    print(i18n.tr('ex_get_cmd'))
    print(i18n.tr('ex_post'))
    print(i18n.tr('ex_post_cmd'))
    print(i18n.tr('ex_put'))
    print(i18n.tr('ex_put_cmd'))
    print(i18n.tr('ex_delete'))
    print(i18n.tr('ex_delete_cmd'))
    print(i18n.tr('ex_ca'))
    print(i18n.tr('ex_ca_cmd'))
    print(i18n.tr('ex_binary'))
    print(i18n.tr('ex_binary_cmd'))
    print(i18n.tr('ex_stdin'))
    print(i18n.tr('ex_stdin_cmd'))
    print(i18n.tr('ex_redirect'))
    print(i18n.tr('ex_redirect_cmd'))
    print(i18n.tr('ex_help'))
    print(i18n.tr('ex_help_cmd'))


def main() -> int:
    parser = argparse.ArgumentParser(
        description='向指定URL发送HTTP请求（支持自定义请求类型、请求头和内容）',
        add_help=False
    )
    parser.add_argument('url', nargs='?', help='目标URL（可省略协议，默认添加http://）')
    parser.add_argument('method', nargs='?', help='请求类型（GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS）')
    parser.add_argument('headers', nargs='?', default='', help='请求头（JSON格式或键值对，复杂头建议用JSON）')
    parser.add_argument('data', nargs='?', help='请求内容。可使用 @文件名 从文件读取，- 从stdin读取，或通过标准输入传递')
    parser.add_argument('--ca', metavar='FILE', help='自定义CA证书文件路径（PEM格式），要求URL使用HTTPS')
    parser.add_argument('-b', '--binary', action='store_true', help='以二进制模式读取文件/标准输入，用于上传图片等')
    parser.add_argument('-L', '--location', action='store_true', help='自动跟随重定向 (301/302/303/307/308)')
    parser.add_argument('--max-redirects', type=int, default=MAX_REDIRECTS, metavar='N', help=f'最大重定向次数 (默认 {MAX_REDIRECTS})')
    parser.add_argument('--lang', choices=['zh', 'en'], help='界面语言 / UI language (zh/en)')
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息 / Show help')

    args = parser.parse_args()

    lang = detect_language(args.lang)
    set_i18n(lang)
    i18n = get_i18n()

    if args.help or len(sys.argv) == 1:
        print_help(i18n)
        return 0

    if not args.url or not args.method:
        log_error(i18n.tr('err_missing_url_method'))
        log_error(i18n.tr('err_help_hint'))
        return 1

    if args.max_redirects < 0:
        log_error(i18n.tr('err_max_redirects'))
        return 1

    headers = parse_headers(args.headers) if args.headers is not None else {}
    data = read_data_from_arg(args.data, binary=args.binary)
    if (isinstance(data, str) and not data) or (isinstance(data, bytes) and not data):
        data = read_data_from_stdin(binary=args.binary)

    return 0 if send_request(args.url, args.method, headers, data, args.ca,
                             follow_redirects=args.location, max_redirects=args.max_redirects) else 1


if __name__ == "__main__":
    sys.exit(main())