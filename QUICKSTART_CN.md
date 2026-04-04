# MockClaw 快速开始指南

欢迎使用 MockClaw！本指南将帮助你在 2 分钟内快速上手。

## 📋 前置要求

- Python 3.11 或更高版本
- pip (Python 包管理器)

## 🚀 快速开始（3 种方式）

### 方式 1: 一键体验（推荐新手）

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 3. 安装依赖
pip install -r src/requirements.txt

# 4. 运行示例命令（自动生成并启动示例服务器）
python -m src.cli example
```

### 方式 2: 使用示例 HAR 文件

```bash
# 1-3. 同上（创建和激活虚拟环境，安装依赖）

# 4. 从示例 HAR 生成 mock 服务器
python -m src.cli generate examples/sample.har ./my_mocks --smart-fallback

# 5. 启动服务器
python -m src.cli serve ./my_mocks

# 6. 在浏览器打开 API 文档
# http://localhost:8000/docs
```

### 方式 3: 从零开始录制流量

```bash
# 1-3. 同上（创建和激活虚拟环境，安装依赖）

# 4. 启动 Dummy Shop（测试 API）
python tests/gauntlet/dummy_shop.py &

# 5. 录制流量
python -m src.cli record

# 6. 生成 mock 服务器
python -m src.cli generate tests/gauntlet/flow.har ./my_mocks --smart-fallback

# 7. 启动服务器
python -m src.cli serve ./my_mocks
```

## 🎯 测试你的 Mock 服务器

服务器启动后，你可以测试以下场景：

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

### 2. 测试过期优惠券（应返回 400 错误）

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","coupon_code":"EXPIRED2026","shipping_address":"123 Main St"}'
```

### 3. 测试有效优惠券（应返回成功）

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","coupon_code":"SAVE10","shipping_address":"123 Main St"}'
```

### 4. 查看所有产品

```bash
curl http://localhost:8000/products
```

## 📚 CLI 命令参考

### 查看帮助

```bash
python -m src.cli --help
python -m src.cli [command] --help
```

### 常用命令

```bash
# 查看版本
python -m src.cli --version

# 查看系统信息
python -m src.cli info

# 快速体验
python -m src.cli example

# 生成 mock 服务器
python -m src.cli generate <har_file> <output_dir> --smart-fallback

# 启动服务器
python -m src.cli serve <mock_dir> --port 8000

# 录制流量
python -m src.cli record --url http://localhost:9000

# 运行测试
python -m src.cli test <mock_dir>
```

## 🔧 常见问题

### 1. 安装依赖时遇到权限错误

**问题**: `error: externally-managed-environment`

**解决方案**: 使用虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows
```

### 2. 找不到 HAR 文件

**问题**: `HAR file not found`

**解决方案**: 使用示例 HAR 或录制自己的流量

```bash
# 使用示例
python -m src.cli generate examples/sample.har ./my_mocks --smart-fallback

# 或录制
python -m src.cli record
```

### 3. 端口已被占用

**问题**: `Port 8000 is already in use`

**解决方案**: 使用其他端口

```bash
python -m src.cli serve ./my_mocks --port 8001
```

### 4. Python 命令不存在

**问题**: `command not found: python`

**解决方案**: 使用 `python3`

```bash
python3 -m venv venv
python3 -m src.cli --help
```

## 🎨 高级功能

### Smart Fallback 模式

Smart Fallback 可以根据请求内容自动路由到不同的响应：

```bash
python -m src.cli generate examples/sample.har ./my_mocks --smart-fallback
```

这将生成智能路由逻辑，例如：
- 不同的优惠券代码返回不同的结果
- 不同的用户 ID 返回不同的数据
- 自动处理错误场景

### LLM 辅助生成（可选）

如果你有 OpenAI API key，可以使用 LLM 辅助生成更智能的 mock：

```bash
export OPENAI_API_KEY=sk-...
python -m src.cli generate examples/sample.har ./my_mocks
```

### 开发模式（自动重载）

```bash
python -m src.cli serve ./my_mocks --reload
```

## 📖 下一步

- 查看 [API 文档](http://localhost:8000/docs) 了解所有端点
- 阅读 [README.md](README.md) 了解更多功能
- 查看 [examples/](examples/) 目录了解更多示例
- 运行 [tests/](tests/) 了解测试方法

## 💡 提示

1. **首次使用**: 推荐使用 `python -m src.cli example` 快速体验
2. **开发测试**: 使用 `--smart-fallback` 模式，无需 LLM API key
3. **生产部署**: 使用 `--host 0.0.0.0` 允许外部访问
4. **调试**: 使用 `python -m src.cli info` 查看系统信息

## 🆘 获取帮助

- **GitHub Issues**: [报告问题](https://github.com/EternalRights/MockClaw/issues)
- **文档**: [完整文档](https://github.com/EternalRights/MockClaw/docs)
- **示例**: [examples/](examples/) 目录

---

**祝你使用愉快！🎉**
