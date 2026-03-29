# MockClaw 核心原理详解

## 🔍 问题 1：为什么不配置 API Key 也能跑？

### **答案：MockClaw 有三种运行模式！**

#### **模式 1：LLM 模式（需要 API Key）**
```bash
# 配置 .env 文件
LLM_API_KEY=sk-your-key-here

# 生成 Mock（会使用 LLM）
mockclaw generate traffic.har
```

**特点**：
- ✅ 使用 AI 分析接口，生成更智能的 Mock
- ✅ 能理解业务逻辑，生成更真实的数据
- ✅ 能推断字段含义（如 email、phone、address）
- ❌ 需要 API Key
- ❌ 有 API 调用成本
- ❌ 速度较慢（每个接口需要调用 LLM）

**示例**：
```python
# LLM 模式生成的代码
@app.get("/users/{user_id}")
async def get_user(user_id: str):
    """LLM 理解这是一个用户接口"""
    from faker import Faker
    fake = Faker()
    return {
        "id": user_id,
        "name": fake.name(),        # AI 知道这是姓名
        "email": fake.email(),      # AI 知道这是邮箱
        "phone": fake.phone_number() # AI 知道这是电话
    }
```

---

#### **模式 2：智能回退模式（不需要 API Key）** ⭐ 推荐
```bash
# 不配置 API Key，使用智能回退
mockclaw generate traffic.har --no-llm

# 或
mockclaw generate traffic.har --smart-fallback
```

**特点**：
- ✅ **不需要 API Key**
- ✅ 完全免费
- ✅ 速度极快（毫秒级生成）
- ✅ 能学习业务逻辑（如优惠券判断）
- ✅ 自动注入安全中间件
- ⚠️ 数据基于录制的 HAR 文件（不会生成新数据）

**示例**：
```python
# 智能回退模式生成的代码
@app.post("/checkout")
async def checkout(request: Request):
    """智能路由：根据请求体返回不同响应"""
    body = await request.json()
    
    # 自动学习：如果 coupon_code == "EXPIRED2026" → 返回 400
    if body.get("coupon_code") == "EXPIRED2026":
        raise HTTPException(400, detail={"error": "COUPON_EXPIRED"})
    
    # 自动学习：如果 coupon_code == "SAVE10" → 返回成功
    elif body.get("coupon_code") == "SAVE10":
        return {"order_id": "ORD-123", "discount": 149.99}
    
    # 默认返回
    else:
        return {"order_id": "ORD-123"}
```

**工作原理**：
1. 分析 HAR 文件中的多个请求/响应对
2. 找出区分点（如不同的 coupon_code）
3. 自动生成 if/elif 条件逻辑
4. 返回对应的响应数据

---

#### **模式 3：模板模式（最简单）**
```bash
mockclaw generate traffic.har
# 如果没有 API Key，自动降级到模板模式
```

**特点**：
- ✅ 不需要 API Key
- ✅ 速度最快
- ⚠️ 只是简单回放录制的响应
- ⚠️ 不理解业务逻辑

**示例**：
```python
# 模板模式生成的代码
@app.get("/products")
async def get_products():
    """直接返回录制的响应"""
    return {"products": [...]}  # 录制时的数据
```

---

### **对比表格**

| 特性 | LLM 模式 | 智能回退模式 | 模板模式 |
|------|---------|------------|---------|
| 需要 API Key | ✅ 是 | ❌ 否 | ❌ 否 |
| 成本 | 💰 有 | 🆓 免费 | 🆓 免费 |
| 速度 | 🐢 慢（秒级） | 🚀 快（毫秒级） | ⚡ 最快 |
| 数据质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 业务逻辑理解 | ✅ 强 | ✅ 中 | ❌ 弱 |
| 推荐场景 | 生产环境 | 日常开发 | 快速原型 |

---

### **我刚才演示用的是哪种模式？**

**答案：智能回退模式（--no-llm）**

```bash
python -m src.cli generate tests/gauntlet/flow.har --no-llm
```

所以：
- ✅ 不需要 API Key
- ✅ 能学习优惠券逻辑
- ✅ 速度很快
- ✅ 完全免费

---

## 📌 问题 2：为什么全程没涉及 CLI 操作？

### **答案：其实全程都在用 CLI！**

#### **我刚才用的命令**

```bash
# 1. 生成 Mock（CLI）
python -m src.cli generate tests/gauntlet/flow.har --no-llm

# 2. 启动 Mock 服务器（CLI）
python -m src.cli serve generated_mocks --port 8007

# 3. 录制流量（CLI）
python scripts/gauntlet_recorder.py

# 4. 运行测试（CLI）
python -m pytest test_shopping_flow.py -v

# 5. 混沌测试（CLI）
python scripts/enhanced_chaos_test.py
```

#### **为什么用 `python -m src.cli` 而不是 `mockclaw`？**

因为 `mockclaw` 命令需要安装：

```bash
# 安装 CLI 工具
pip install -e .

# 然后就可以直接用
mockclaw generate traffic.har
mockclaw serve generated_mocks
```

#### **前后端界面是做什么的？**

**前端界面（http://localhost:3000）**：
- 🎨 可视化操作界面
- 📤 拖放上传 HAR 文件
- 📊 查看解析结果
- 🎯 一键生成 Mock
- 📖 查看 API 文档

**后端服务（http://localhost:8000）**：
- 🔌 提供 REST API
- 📝 解析 HAR 文件
- 🤖 调用 LLM 生成 Mock
- 💾 保存生成的代码

**CLI 工具**：
- ⚡ 命令行操作
- 🚀 更快速、更灵活
- 🔧 适合自动化脚本
- 🤖 适合 CI/CD 集成

---

### **三种使用方式对比**

#### **方式 1：CLI（推荐）** ⭐
```bash
# 最快速、最灵活
mockclaw generate traffic.har --no-llm
mockclaw serve generated_mocks --port 8000
```

**优点**：
- ✅ 速度快
- ✅ 可脚本化
- ✅ 适合自动化
- ✅ 功能最全

---

#### **方式 2：前端界面**
```
1. 访问 http://localhost:3000
2. 拖放 HAR 文件
3. 点击 "Generate All"
4. 查看结果
```

**优点**：
- ✅ 可视化
- ✅ 易于理解
- ✅ 适合新手

---

#### **方式 3：Python API**
```python
from src.core.parser import HARParser
from src.core.generator import MockGenerator

# 解析 HAR
parser = HARParser("traffic.har")
endpoints = parser.get_endpoints()

# 生成 Mock
generator = MockGenerator(use_smart_fallback=True)
results = generator.generate_all(endpoints, "output_dir")
```

**优点**：
- ✅ 最灵活
- ✅ 可集成到自己的代码
- ✅ 适合高级用户

---

## 📌 问题 3：日常测试开发如何使用？

### **真实场景演示**

#### **场景 1：前端开发 - 后端接口还没好**

**问题**：
- 后端接口还在开发
- 前端需要开始写页面
- 等待后端会延误进度

**解决方案**：

```bash
# 步骤 1：找后端要一个测试环境的 HAR 文件
# 或者自己录制一次真实 API 调用

# 步骤 2：生成 Mock
mockclaw generate backend_api.har --no-llm

# 步骤 3：启动 Mock 服务器
mockclaw serve generated_mocks --port 8000

# 步骤 4：修改前端代码
```

```javascript
// 前端代码
// const API_BASE = 'http://real-backend:8080'  // 真实后端
const API_BASE = 'http://localhost:8000'        // Mock 服务器

// 其他代码无需修改！
fetch(`${API_BASE}/api/users`)
  .then(res => res.json())
  .then(data => console.log(data))
```

**效果**：
- ✅ 前端可以立即开始开发
- ✅ 不依赖后端进度
- ✅ 接口格式和真实后端一致
- ✅ 后端完成后只需改一行代码

---

#### **场景 2：测试开发 - 编写自动化测试**

**问题**：
- 测试环境不稳定
- 第三方 API 有限流
- 有些边界情况难以触发

**解决方案**：

```bash
# 步骤 1：录制真实流量
# 浏览器 F12 → Network → 操作 → Save as HAR

# 步骤 2：生成 Mock
mockclaw generate real_traffic.har --no-llm

# 步骤 3：启动 Mock 服务器
mockclaw serve generated_mocks --port 8000
```

```python
# 步骤 4：编写测试
import pytest
import requests

MOCK_API = "http://localhost:8000"

def test_user_login():
    """测试用户登录"""
    response = requests.post(f"{MOCK_API}/api/login", 
                            json={"username": "test", "password": "123"})
    assert response.status_code == 200
    assert "token" in response.json()

def test_create_order():
    """测试创建订单"""
    response = requests.post(f"{MOCK_API}/api/orders",
                            json={"product_id": "123", "quantity": 2})
    assert response.status_code == 200
    assert "order_id" in response.json()

# 步骤 5：运行测试
# pytest test_api.py -v
```

**效果**：
- ✅ 测试环境完全可控
- ✅ 测试稳定、可重复
- ✅ 不触发第三方 API 限流
- ✅ 可以模拟各种边界情况

---

#### **场景 3：本地调试 - 调用第三方 API**

**问题**：
- 第三方 API 有调用限制
- 调试成本高（每次都发真实请求）
- 无法测试异常情况

**解决方案**：

```bash
# 步骤 1：录制一次真实调用
# 执行一次真实请求，保存为 HAR

# 步骤 2：生成 Mock
mockclaw generate third_party.har --no-llm

# 步骤 3：启动 Mock 服务器
mockclaw serve generated_mocks --port 8000

# 步骤 4：修改代码或 hosts
```

**方法 A：修改代码**
```python
# 原来
# API_URL = "https://api.weixin.qq.com"

# 改为
API_URL = "http://localhost:8000"
```

**方法 B：修改 hosts**
```
# C:\Windows\System32\drivers\etc\hosts
127.0.0.1 api.weixin.qq.com
```

**效果**：
- ✅ 随意调试，不触发限流
- ✅ 不花钱
- ✅ 可以模拟异常情况（修改 Mock 数据）
- ✅ 调试速度快

---

#### **场景 4：团队协作 - 共享 Mock 数据**

**问题**：
- 前后端联调困难
- 接口文档过时
- 测试数据不一致

**解决方案**：

```bash
# 步骤 1：后端生成 Mock
mockclaw generate backend_api.har --no-llm

# 步骤 2：提交到 Git
git add generated_mocks/
git commit -m "feat: add mock APIs"

# 步骤 3：前端拉取并使用
git pull
mockclaw serve generated_mocks --port 8000
```

**效果**：
- ✅ 前后端使用相同的 Mock 数据
- ✅ 接口格式一致
- ✅ 文档自动生成（/docs）
- ✅ 减少沟通成本

---

### **日常工作流总结**

```
早上到公司
├─ 启动 MockClaw
│  └─ mockclaw serve generated_mocks --port 8000
│
开发/测试中
├─ 前端：使用 http://localhost:8000 作为 API
├─ 测试：在 Mock 上运行测试
└─ 调试：随意修改 Mock 数据
│
需要新接口
├─ 录制新流量
│  └─ 浏览器 F12 → Save as HAR
├─ 重新生成 Mock
│  └─ mockclaw generate new_api.har --no-llm
└─ 重启服务器
   └─ mockclaw serve generated_mocks --port 8000 --reload
│
下班前
└─ 提交 Mock 配置
   └─ git add generated_mocks/
```

---

## 🎯 总结

### **核心要点**

1. **不需要 API Key 也能用**
   - 使用智能回退模式：`--no-llm`
   - 完全免费、速度极快
   - 能学习业务逻辑

2. **CLI 是核心工具**
   - 前端界面只是可视化
   - CLI 更快速、更灵活
   - 适合自动化和 CI/CD

3. **日常使用很简单**
   - 录制流量 → 生成 Mock → 启动服务器
   - 修改 API 地址指向 Mock
   - 其他代码无需修改

### **推荐配置**

```bash
# 安装 CLI 工具
pip install -e .

# 添加别名（Windows PowerShell）
function New-Mock { mockclaw generate $args --no-llm }
function Run-Mock { mockclaw serve generated_mocks --port 8000 }

# 添加别名（Linux/Mac）
alias newmock='mockclaw generate $1 --no-llm'
alias runmock='mockclaw serve generated_mocks --port 8000'
```

### **快速开始**

```bash
# 1. 录制流量
# 浏览器 F12 → Network → 操作 → Save as HAR

# 2. 生成 Mock
mockclaw generate traffic.har --no-llm

# 3. 启动服务器
mockclaw serve generated_mocks --port 8000

# 4. 访问文档
# http://localhost:8000/docs
```

---

**就是这样！MockClaw 的核心价值是：**
- 🚀 快速生成 Mock API
- 🆓 不需要 API Key（智能回退模式）
- 🔒 自动注入安全保护
- 📖 自动生成 API 文档
- 🧪 支持混沌测试

**让你的开发和测试更高效！**
