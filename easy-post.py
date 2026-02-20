import sys
import json
import requests
import argparse
from urllib.parse import urlparse
def read_data_from_arg(data_arg):
    if data_arg and data_arg.startswith('@'):
        filepath = data_arg[1:]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"错误: 无法读取文件 {filepath} - {e}")
            sys.exit(1)
    return data_arg
def send_request(url, data):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            suggested_url = 'http://' + url
            print(f"提示: URL缺少协议，已自动添加 http://")
            url = suggested_url
        print(f"发送 POST 请求到: {url}")
        print(f"请求内容: {data[:200]}{'...' if len(data) > 200 else ''}")  # 预览
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'easy-post/1.0'
        }
        try:
            json_data = json.loads(data)
            response = requests.post(url, headers=headers, json=json_data, timeout=10)
        except json.JSONDecodeError:
            headers['Content-Type'] = 'text/plain'
            response = requests.post(url, headers=headers, data=data, timeout=10)
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        print(f"\n响应内容:")
        try:
            json_response = response.json()
            print(json.dumps(json_response, indent=2, ensure_ascii=False))
        except:
            print(response.text[:1000])
        return True
    except requests.exceptions.Timeout:
        print("错误: 请求超时。")
        return False
    except requests.exceptions.ConnectionError:
        print("错误: 连接失败。")
        return False
    except requests.exceptions.RequestException as e:
        print(f"错误: 请求失败 - {e}")
        return False
    except Exception as e:
        print(f"错误: 发生未知错误 - {e}")
        return False
def main():
    parser = argparse.ArgumentParser(
        description='向指定URL发送HTTP POST请求（支持从文件或标准输入读取数据）',
        add_help=False
    )
    parser.add_argument('url', nargs='?', help='目标URL（可省略协议，默认添加http://）')
    parser.add_argument('data', nargs='?', help='请求内容。可使用 @文件名 从文件读取，或通过标准输入传递')
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    args = parser.parse_args()
    if args.help or len(sys.argv) == 1:
        print("""
easy-post - 极简的HTTP POST工具

使用方法:
  easy-post <URL> [data]                 # 直接提供数据
  echo '{"key":"value"}' | easy-post <URL>   # 从标准输入读取数据
  easy-post <URL> @data.json              # 从文件读取数据

参数说明:
  URL   目标地址（可省略协议，默认添加 http://）
  data  要发送的数据。支持：
          - 直接作为参数传递
          - 以 @ 开头表示文件路径
          - 省略时自动从标准输入读取（如果存在）

示例:
  1. 发送JSON数据:
     easy-post https://httpbin.org/post '{"name":"test","value":123}'
  
  2. 发送文本数据（从标准输入）:
     echo "Hello, world!" | easy-post https://httpbin.org/post
  
  3. 从文件读取数据:
     easy-post https://httpbin.org/post @payload.json

  4. 查看帮助:
     easy-post -h
        """)
        return 0
    if not args.url:
        print("错误: 必须提供URL参数")
        print("使用 'easy-post -h' 查看帮助")
        return 1
    data = None
    if args.data:
        data = read_data_from_arg(args.data)
    elif not sys.stdin.isatty():
        data = sys.stdin.read().strip()
    if data is None:
        print("错误: 必须提供请求内容（可通过参数、文件或标准输入提供）")
        print("使用 'easy-post -h' 查看帮助")
        return 1
    success = send_request(args.url, data)
    return 0 if success else 1
if __name__ == "__main__":
    sys.exit(main())
