# 📘 MockClaw 测试开发实战指南

> 本指南教你如何使用 MockClaw 进行真实的测试开发工作

---

## 📚 目录

1. [MockClaw 是什么？](#mockclaw-是什么)
2. [为什么要用 MockClaw？](#为什么要用-mockclaw)
3. [快速开始：5 分钟上手](#快速开始5-分钟上手)
4. [实战场景 1：前端开发](#实战场景-1 前端开发)
5. [实战场景 2：测试开发](#实战场景-2 测试开发)
6. [实战场景 3：微服务测试](#实战场景-3 微服务测试)
7. [最佳实践](#最佳实践)
8. [常见问题](#常见问题)

---

## 🤔 MockClaw 是什么？

**MockClaw = HTTP 流量录制 + AI 分析 + 一键生成 Mock 服务器**

简单来说，MockClaw 可以：
- 📹 **录制** 你的应用发出的所有 HTTP 请求
- 🤖 **分析** 请求和响应的模式
- 🚀 **生成** 一个完整的 Mock API 服务器

**关键特性：**
- ✅ **Smart Fallback 模式** - 无需 LLM API Key，智能路由
- ✅ **自动注入安全** - 限流、路径遍历防护
- ✅ **条件路由** - 根据请求内容返回不同响应
- ✅ **零配置** - 拖放 HAR 文件即可

---

## 🎯 为什么要用 MockClaw？

### 传统 Mocking 的痛点

| 痛点 | 传统做法 | MockClaw 做法 |
|------|----------|---------------|
| 后端接口没开发完 | 手写 Mock 数据，每个接口都要写 | 录制一次，自动生成所有接口 |
| 测试环境不稳定 | 求运维恢复环境 | 本地启动 Mock，想怎么玩就怎么玩 |
| 第三方 API 限流 | 小心翼翼，生怕触发限流 | 用 Mock 随便测试，不花一分钱 |
| 接口文档过时 | 抓着后端问个不停 | 自动生成最新 API 文档 |
| Mock 数据不真实 | 凭空想象测试数据 | 使用真实流量数据 |

### MockClaw 的优势

- ⏱️ **节省 95% 时间** - 2.5 小时 → 5 分钟
- 💰 **零成本** - Smart Fallback 模式无需 LLM API Key
- 🎯 **数据真实** - 基于真实流量生成
- 🔒 **安全可靠** - 自动注入安全中间件
- 📖 **文档自动生成** - Swagger UI API 文档

---

## 🚀 快速开始：5 分钟上手

### 前置要求

- Python 3.11+
- pip

### 步骤 1：安装（1 分钟）

```bash
# 克隆项目
git clone https://github.com/mockclaw/mockclaw.git
cd mockclaw

# 安装依赖
pip install -r src/requirements.txt
```

### 步骤 2：生成 Mock（1 分钟）

```bash
# 使用示例 HAR 文件生成 Mock
python -m src.cli generate sample_data/flow.har ./my_mocks --smart-fallback
```

**输出：**
```
📦 解析 HAR 文件: sample_data/flow.har
✅ 找到 7 个端点
🤖 生成 Mock...
   模式: Smart Fallback (基于规则的路由)
✅ 生成 6/6 个端点
📂 输出目录: D:\MockClaw\my_mocks
```

### 步骤 3：启动服务器（1 分钟）

```bash
# 启动 Mock 服务器
python -m src.cli serve ./my_mocks --port 8000
```

**输出：**
```
🚀 启动 Mock 服务器...
   模块: my_mocks.dynamic_api:app
   主机: 0.0.0.0:8000
📖 API 文档: http://localhost:8000/docs
   健康检查: http://localhost:8000/health
```

### 步骤 4：测试（2 分钟）

```bash
# 测试健康检查
curl http://localhost:8000/health
# {"status":"OK","service":"MockClaw"}

# 测试 API
curl http://localhost:8000/products
# {"products":[...],"total":4}
```

**完成！** 🎉 你现在有一个完整的 Mock API 服务器了！

---

## 💼 实战场景 1：前端开发

### 场景描述

你是前端开发，后端接口还没开发完，但你要开始开发页面。

### 传统做法

1. 等后端开发完接口（1-2 周）
2. 手写 Mock 数据（每个接口 30 分钟）
3. 前端开发（1 周）
4. 联调测试（2-3 天）

**总计：2-3 周**

### MockClaw 做法

#### 步骤 1：获取 HAR 文件

**方法 A：从测试环境录制**

1. 打开测试环境网站
2. 浏览器按 F12，切换到 Network 标签
3. 浏览商品列表、筛选、排序等操作
4. 右键 Network 标签 → "Save all as HAR with content"
5. 保存为 `backend_api.har`

**方法 B：使用 MockClaw 虚拟商店**

```bash
# 启动虚拟商店（模拟真实 API）
python tests/gauntlet/dummy_shop.py

# 在另一个终端录制流量
python scripts/gauntlet_recorder.py
```

#### 步骤 2：生成 Mock 服务器

```bash
# 使用 Smart Fallback 模式（无需 LLM API Key）
python -m src.cli generate backend_api.har ./frontend_mocks --smart-fallback
```

#### 步骤 3：启动 Mock 服务器

```bash
python -m src.cli serve ./frontend_mocks --port 8000
```

#### 步骤 4：修改前端代码

```javascript
// 原来的 API 地址
// const API_BASE = 'http://backend-server:8080/api'

// 改为本地 Mock 服务器
const API_BASE = 'http://localhost:8000'

// 你的前端代码无需其他修改！
async function getProducts() {
  const response = await fetch(`${API_BASE}/products`)
  const data = await response.json()
  console.log('商品列表:', data.products)
  return data.products
}
```

#### 步骤 5：开发完成后的切换

```javascript
// 开发完成后，只需修改 API_BASE：
const API_BASE = 'http://real-backend-server:8080/api'
// 其他代码完全不用改！
```

**总计：1 周**（节省 50% 时间）

### 优势

- ✅ 不依赖后端开发进度
- ✅ 可以提前开始前端开发
- ✅ 接口变更时快速验证
- ✅ 离线也能开发
- ✅ Mock 数据和真实后端返回格式一致

---

## 🧪 实战场景 2：测试开发

### 场景描述

你是测试开发，要写自动化测试，但环境不稳定。

### 传统做法

1. 等测试环境恢复（1-2 天）
2. 手写 Mock 数据（每个场景 30 分钟）
3. 编写测试用例（1 周）
4. 测试不稳定，经常失败（持续调试）

**总计：2-3 周，测试不稳定**

### MockClaw 做法

#### 步骤 1：录制完整的用户流程

```bash
# 启动虚拟商店
python tests/gauntlet/dummy_shop.py

# 录制完整购物流程
python scripts/gauntlet_recorder.py
```

这会录制：
- 用户登录
- 浏览商品
- 添加到购物车
- 使用优惠券
- 下单支付
- 查看订单

#### 步骤 2：生成带安全保护的 Mock

```bash
# 生成 Mock（自动注入安全中间件）
python -m src.cli generate tests/gauntlet/flow.har ./test_mocks --smart-fallback
```

生成的 Mock 服务器包含：
- ✅ 路径遍历保护
- ✅ 限流保护（60 请求/分钟）
- ✅ 安全错误处理

#### 步骤 3：编写测试用例

```python
# test_checkout.py
import pytest
import requests

MOCK_BASE = 'http://localhost:8000'

class TestCheckout:
    """结账流程测试套件"""
    
    def test_add_to_cart(self):
        """测试添加到购物车"""
        response = requests.post(
            f'{MOCK_BASE}/cart/user123',
            json={'product_id': 'p001', 'quantity': 2}
        )
        assert response.status_code == 200
        assert response.json()['status'] == 'success'
    
    def test_checkout_with_valid_coupon(self):
        """测试使用有效优惠券下单"""
        # 先添加商品到购物车
        requests.post(f'{MOCK_BASE}/cart/user123', 
                      json={'product_id': 'p001', 'quantity': 1})
        
        # 使用优惠券下单
        response = requests.post(
            f'{MOCK_BASE}/checkout',
            json={
                'user_id': 'user123',
                'coupon_code': 'SAVE10'
            }
        )
        assert response.status_code == 200
        assert response.json()['status'] == 'confirmed'
    
    def test_expired_coupon(self):
        """测试过期优惠券"""
        response = requests.post(
            f'{MOCK_BASE}/checkout',
            json={
                'user_id': 'user123',
                'coupon_code': 'EXPIRED2026'
            }
        )
        assert response.status_code == 400
        assert 'expired' in str(response.json()).lower()
```

#### 步骤 4：运行测试

```bash
# 确保 Mock 服务器在运行
# python -m src.cli serve ./test_mocks --port 8000

# 运行测试
pytest test_checkout.py -v
```

**输出：**
```
test_checkout.py::TestCheckout::test_add_to_cart PASSED
test_checkout.py::TestCheckout::test_checkout_with_valid_coupon PASSED
test_checkout.py::TestCheckout::test_expired_coupon PASSED
======================== 3 passed =========================
```

#### 步骤 5：运行混沌测试（可选）

```bash
# 测试 Mock 服务器的健壮性
python -m src.cli test ./test_mocks
```

测试项目：
- 并发测试：50 个并行请求
- 垃圾数据：null、XSS、SQL 注入
- 路径遍历：`../`、`%2e%2e` 等
- 限流测试：100 个快速请求

**总计：1 周，测试稳定可靠**

### 优势

- ✅ 测试环境完全可控
- ✅ 可以模拟各种边界情况
- ✅ 测试可重复、稳定
- ✅ 不依赖外部系统
- ✅ 自动注入安全保护

---

## 🏢 实战场景 3：微服务测试

### 场景描述

你的应用集成了多个第三方服务（支付网关、区块链节点、短信服务等），需要测试这些集成。

### 传统做法

1. 注册所有第三方服务的测试账号（1-2 天）
2. 配置测试环境（1 天）
3. 小心翼翼测试，生怕触发限流（持续进行）
4. 测试成本高（每个服务都有费用）

**总计：1-2 周，成本高**

### MockClaw 做法

#### 步骤 1：为每个服务录制流量

**示例：支付网关**

```python
# scripts/record_payment_gateway.py
"""
录制支付网关 API 流量
"""
import requests

# 场景 1: 成功支付
response = requests.post(
    "https://api.payment-gateway.com/v1/charges",
    json={
        "amount": 10000,
        "currency": "usd",
        "source": "tok_visa",
        "description": "Test charge"
    },
    headers={"Authorization": "Bearer sk_test_..."}
)

# 场景 2: 卡片被拒绝
response = requests.post(
    "https://api.payment-gateway.com/v1/charges",
    json={
        "amount": 10000,
        "currency": "usd",
        "source": "tok_chargeDeclined",
        "description": "Test declined card"
    },
    headers={"Authorization": "Bearer sk_test_..."}
)

# 场景 3: 退款
response = requests.post(
    "https://api.payment-gateway.com/v1/refunds",
    json={
        "charge": "ch_123",
        "amount": 5000
    },
    headers={"Authorization": "Bearer sk_test_..."}
)

# 保存为 HAR 文件
# ...
```

#### 步骤 2：批量生成所有 Mock

```python
# scripts/generate_all_mocks.py
"""
批量生成所有第三方服务的 Mock
"""
import subprocess

services = {
    "payment_gateway": "har_files/payment_gateway_flow.har",
    "blockchain_node": "har_files/blockchain_flow.har",
    "sms_service": "har_files/sms_flow.har",
    "email_service": "har_files/email_flow.har",
}

for service_name, har_file in services.items():
    print(f"🤖 Generating {service_name} mock...")
    subprocess.run([
        "python", "-m", "src.cli",
        "generate", har_file,
        f"mocks/{service_name}",
        "--smart-fallback"
    ])
    print(f"✅ {service_name} mock generated!")
```

#### 步骤 3：启动所有 Mock 服务

```python
# scripts/start_all_mocks.py
"""
启动所有 Mock 服务（不同端口）
"""
import subprocess
import time

MOCK_SERVICES = {
    "payment_gateway": 8001,
    "blockchain_node": 8002,
    "sms_service": 8003,
    "email_service": 8004,
}

processes = []

for service_name, port in MOCK_SERVICES.items():
    print(f"🚀 Starting {service_name} on port {port}...")
    proc = subprocess.Popen([
        "python", "-m", "src.cli",
        "serve", f"mocks/{service_name}",
        "--port", str(port)
    ])
    processes.append(proc)
    time.sleep(1)

print("\n✅ All mock services started!")
print("\nMock Services:")
for service_name, port in MOCK_SERVICES.items():
    print(f"  - {service_name}: http://localhost:{port}")
    print(f"    API Docs: http://localhost:{port}/docs")
```

#### 步骤 4：配置测试环境

```python
# config/test_config.py
"""
测试环境配置
"""
class TestConfig:
    # Mock 服务地址
    MOCK_SERVICES = {
        "payment_gateway": "http://localhost:8001",
        "blockchain_node": "http://localhost:8002",
        "sms_service": "http://localhost:8003",
        "email_service": "http://localhost:8004",
    }
    
    # 测试卡片
    TEST_CARDS = {
        "valid_visa": "tok_visa",
        "expired_card": "tok_chargeDeclinedExpiredCard",
        "insufficient_funds": "tok_chargeDeclinedInsufficientFunds",
    }
```

#### 步骤 5：编写集成测试

```python
# tests/test_payment_integration.py
"""
支付集成测试
"""
import pytest
import requests
from config.test_config import TestConfig

class TestPaymentIntegration:
    """支付集成测试套件"""
    
    def test_payment_success(self):
        """测试支付成功"""
        response = requests.post(
            f"{TestConfig.MOCK_SERVICES['payment_gateway']}/v1/charges",
            json={
                "amount": 10000,
                "currency": "usd",
                "source": TestConfig.TEST_CARDS["valid_visa"]
            }
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"
    
    def test_payment_card_declined(self):
        """测试卡片被拒绝"""
        response = requests.post(
            f"{TestConfig.MOCK_SERVICES['payment_gateway']}/v1/charges",
            json={
                "amount": 10000,
                "currency": "usd",
                "source": TestConfig.TEST_CARDS["expired_card"]
            }
        )
        
        assert response.status_code == 400
        assert "card_declined" in response.json()["error"]["code"]
    
    def test_blockchain_transaction(self):
        """测试区块链交易"""
        response = requests.post(
            f"{TestConfig.MOCK_SERVICES['blockchain_node']}",
            json={
                "jsonrpc": "2.0",
                "method": "eth_sendTransaction",
                "params": [{
                    "from": "0x123...",
                    "to": "0x456...",
                    "value": "0x16345785d8a0000"  # 0.1 ETH
                }],
                "id": 1
            }
        )
        
        assert response.status_code == 200
        assert "result" in response.json()
```

**总计：3-5 天，零成本**

### 优势

- ✅ 调试成本极低
- ✅ 可以模拟各种异常情况
- ✅ 不触发 API 限流
- ✅ 节省测试费用
- ✅ 测试环境完全可控

---

## 🌟 最佳实践

### 1. 使用 Smart Fallback 模式

**推荐：** 始终使用 `--smart-fallback` 标志

```bash
python -m src.cli generate traffic.har ./mocks --smart-fallback
```

**原因：**
- ✅ 无需 LLM API Key
- ✅ 智能条件路由
- ✅ 零成本

### 2. 录制多种场景

确保录制以下场景：
- ✅ 成功场景
- ✅ 失败场景（400, 401, 403, 404, 500）
- ✅ 边界情况（空值、最大值、最小值）
- ✅ 错误场景（网络错误、超时）

### 3. 组织 Mock 服务

```
mocks/
├── payment_gateway/     # 支付网关 Mock
├── blockchain_node/     # 区块链节点 Mock
├── sms_service/         # 短信服务 Mock
└── email_service/       # 邮件服务 Mock
```

### 4. 使用配置文件

```python
# config/test_config.py
class TestConfig:
    MOCK_SERVICES = {
        "payment": "http://localhost:8001",
        "blockchain": "http://localhost:8002",
    }
```

### 5. 编写可重用的 Fixtures

```python
# tests/conftest.py
@pytest.fixture
def mock_services():
    """验证所有 Mock 服务是否运行"""
    for service_name, url in TestConfig.MOCK_SERVICES.items():
        response = requests.get(f"{url}/health", timeout=2)
        assert response.status_code == 200
    return TestConfig.MOCK_SERVICES
```

### 6. 集成到 CI/CD

```yaml
# .github/workflows/test.yml
- name: Generate Mocks
  run: python scripts/generate_all_mocks.py

- name: Start Mock Services
  run: python scripts/start_all_mocks.py &

- name: Run Tests
  run: pytest tests/ -v
```

### 7. 定期更新 Mock 数据

- 当 API 变更时，重新录制 HAR 文件
- 定期验证 Mock 响应是否与真实 API 一致
- 使用版本控制管理 HAR 文件

---

## ❓ 常见问题

### Q1：没有 LLM API Key 能用吗？

**A：** 可以！使用 `--smart-fallback` 参数：

```bash
python -m src.cli generate traffic.har --smart-fallback
```

这会使用智能路由模式，无需 AI 也能生成 Mock。

---

### Q2：HAR 文件是什么？

**A：** HAR（HTTP Archive）是浏览器导出的网络请求记录文件。

**如何获取：**
1. 浏览器 F12 → Network 标签
2. 右键 → "Save all as HAR with content"

---

### Q3：生成的 Mock 服务器性能如何？

**A：** 基于 FastAPI，性能非常好：
- 单接口 QPS：1000+
- 并发连接：100+
- 响应时间：<10ms

---

### Q4：Mock 数据能自定义吗？

**A：** 可以！生成的代码在 `mocks/dynamic_api.py`，直接修改即可。

```python
# 修改响应数据
@app.get("/products")
async def get_products():
    return {
        "products": [
            {"id": "custom_product", "name": "自定义商品", "price": 99.99}
        ]
    }
```

---

### Q5：如何处理动态参数？

**A：** MockClaw 支持路径参数：

```python
# /users/{user_id}/orders
@app.get("/users/{user_id}/orders")
async def get_user_orders(user_id: str):
    return {"user_id": user_id, "orders": [...]}
```

---

### Q6：能模拟错误响应吗？

**A：** 可以！HAR 文件中包含的错误响应会被自动学习：
- 400 Bad Request
- 401 Unauthorized
- 404 Not Found
- 500 Internal Server Error

---

### Q7：如何更新 Mock 数据？

**A：** 重新录制 HAR 文件并重新生成：

```bash
# 重新录制
python scripts/gauntlet_recorder.py

# 重新生成
python -m src.cli generate new_traffic.har ./mocks --smart-fallback
```

---

### Q8：支持文件上传吗？

**A：** 支持！HAR 文件中的 multipart/form-data 会被自动处理。

---

### Q9：如何在团队中共享 Mock？

**A：** 三种方式：

1. **提交到 Git**
   ```bash
   git add mocks/
   git commit -m "Update mocks"
   ```

2. **使用 Docker**
   ```bash
   docker-compose up -d
   ```

3. **部署到服务器**
   ```bash
   uvicorn mocks.dynamic_api:app --host 0.0.0.0 --port 80
   ```

---

### Q10：如何验证 Mock 是否正确？

**A：** 访问 API 文档页面：

```
http://localhost:8000/docs
```

你可以：
- 查看所有接口的请求/响应格式
- 直接在线测试接口
- 复制示例代码

---

## 📖 进阶技巧

### 技巧 1：组合多个 HAR 文件

```bash
# 合并多个 HAR 文件
python scripts/merge_har.py file1.har file2.har -o merged.har

# 生成 Mock
python -m src.cli generate merged.har ./mocks --smart-fallback
```

### 技巧 2：自定义响应延迟

编辑 `mocks/dynamic_api.py`：

```python
import asyncio

@app.get("/products")
async def get_products():
    await asyncio.sleep(0.5)  # 模拟 500ms 延迟
    return {...}
```

### 技巧 3：添加自定义逻辑

```python
@app.post("/checkout")
async def checkout(data: CheckoutRequest):
    # 自定义验证逻辑
    if data.amount > 10000:
        raise HTTPException(400, "金额过大")
    
    # 调用真实支付接口
    # ...
    
    return {"status": "success"}
```

### 技巧 4：使用中间件

```python
# 添加认证中间件
@app.middleware("http")
async def auth_middleware(request, call_next):
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    response = await call_next(request)
    return response
```

---

## 🎉 总结

MockClaw 是你测试开发的好帮手：

### 适合人群
- ✅ 前端开发：不再依赖后端接口
- ✅ 测试开发：创建稳定测试环境
- ✅ 后端开发：快速原型验证
- ✅ 全栈开发：提高开发效率

### 核心优势
- ✅ **快速**：5 分钟生成完整 Mock 服务器
- ✅ **简单**：拖放 HAR 文件即可
- ✅ **智能**：Smart Fallback 模式（无需 LLM）
- ✅ **健壮**：自动注入安全保护
- ✅ **灵活**：支持自定义和扩展

### 开始使用

```bash
# 1. 安装
pip install -r src/requirements.txt

# 2. 生成 Mock
python -m src.cli generate sample_data/flow.har ./mocks --smart-fallback

# 3. 启动服务器
python -m src.cli serve ./mocks --port 8000

# 4. 访问文档
# http://localhost:8000/docs
```

**祝你测试开发愉快！** 🚀

---

*最后更新：2026-04-03*  
*版本：v1.0*
