# easy-request

> 极简的 HTTP 请求工具，支持自定义请求类型、请求头和内容，让 HTTP 请求像说话一样简单。

## ✨ 特性

- 🚀 **全面支持 HTTP 方法**：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS
- 🎯 **自定义请求头**：支持 JSON 格式和键值对格式
- 📦 **灵活的数据输入**：直接参数、文件（`@文件名`）、标准输入（管道/重定向）
- 🤖 **智能类型识别**：自动检测 JSON 并设置正确的 `Content-Type`
- 💡 **友好错误提示**：URL 缺协议自动补全，清晰的错误信息

---

## 🔧 使用方法

### 格式
```bash
easy-request <URL*> <请求类型*> <请求头*> <请求内容*>
```

- **URL**：目标地址（可省略协议，默认添加 `http://`）
- **请求类型**：HTTP 方法（GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS）
- **请求头**：自定义请求头，支持两种格式：
  - JSON 格式：`'{"Content-Type":"application/json","Authorization":"Bearer token"}'`
  - 键值对格式：`'Content-Type: application/json, User-Agent: test'`
- **请求内容**：要发送的数据，支持三种方式：
  - 直接作为参数传递
  - 以 `@` 开头表示文件路径
  - 省略时自动从标准输入读取（如果存在）

---

## 📚 示例

### 格式示例

```bash
# 发送 GET 请求
easy-request https://httpbin.org/get GET '{"Accept":"application/json"}' ''

# 发送 POST 请求（JSON 数据）
easy-request https://httpbin.org/post POST '{"Content-Type":"application/json"}' '{"name":"test"}'

# 发送 PUT 请求（从文件读取数据）
easy-request https://httpbin.org/put PUT 'Content-Type: application/json' @data.json

# 发送 DELETE 请求
easy-request https://httpbin.org/delete DELETE '{}' ''

# 发送 PATCH 请求
easy-request https://httpbin.org/patch PATCH '{"Content-Type":"application/json"}' '{"updated":true}'

# 使用键值对格式的请求头
easy-request https://httpbin.org/get GET 'Accept: application/json, X-Custom-Header: test-value' ''

# 自动补全 http://
easy-request httpbin.org/get GET '{}' ''

# 查看帮助
easy-request -h
```
---
## 📦下载
[从此页面下载最新版本](https://github.com/gbfdhenr/easy-request/releases)

---

## 🐛问题反馈

如果你遇到任何问题或有改进建议，请提交 Issue 或 Pull Request。
