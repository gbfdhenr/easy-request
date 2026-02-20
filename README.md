# easy-post

> 极简的 HTTP POST 工具，让发送数据像说话一样简单。

## ✨ 特性

- 🚀 **极简设计**：一条命令完成 POST 请求，零学习成本。
- 📦 **灵活的数据输入**：直接参数、文件（`@文件名`）、标准输入（管道/重定向）。
- 🤖 **智能类型识别**：自动检测 JSON 并设置正确的 `Content-Type`。
- 💡 **友好错误提示**：URL 缺协议自动补全，网络错误给出具体建议。

---

## 🔧 使用方法

```bash
easy-post <URL> [data]
```

- **URL**：目标地址（可省略协议，默认添加 `http://`）
- **data**：要发送的数据（可选），支持三种方式：

### 1. 直接提供
```bash
easy-post https://httpbin.org/post '{"hello":"world"}'
```

### 2. 从文件读取
```bash
easy-post https://httpbin.org/post @data.json
```

### 3. 从标准输入读取
```bash
echo 'Hello, world!' | easy-post https://httpbin.org/post
```

如果未提供 data 且没有标准输入，工具会提示错误。

---

## 📚 更多示例

```bash
# 发送纯文本
easy-post https://httpbin.org/post '这是一条文本'

# 自动补全 http://
easy-post httpbin.org/post 'hello'

# 查看帮助
easy-post -h
```
