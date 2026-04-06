# MockClaw 工程化测试项目生成提示词

## 📋 项目背景

你是一个资深的测试开发工程师，正在为一个名为 **CloudToken Exchange（云代币交易所）** 的项目设计测试方案。该项目是一个真实的微服务架构应用，包含多个第三方 API 集成，需要使用 MockClaw 来创建稳定的测试环境。

---

## 🎯 项目需求

### 项目名称：CloudToken Exchange（云代币交易所）

**项目描述：**
一个基于微服务架构的数字代币交易平台，提供代币交易、钱包管理、订单系统等功能。项目集成了多个第三方服务（支付网关、区块链节点、短信服务、邮件服务、KYC 验证等），需要对这些第三方服务进行 Mock 以实现稳定、可控的测试环境。

### 技术栈
- **后端：** Python FastAPI + 微服务架构
- **前端：** React + TypeScript
- **数据库：** PostgreSQL + Redis
- **消息队列：** RabbitMQ
- **第三方服务：** 
  - 支付网关（Stripe-like API）
  - 区块链节点（Ethereum JSON-RPC）
  - 短信服务（Twilio-like API）
  - 邮件服务（SendGrid-like API）
  - KYC 验证服务（Jumio-like API）

---

## 🏗️ 项目结构要求

请生成以下完整的项目结构：

```
cloudtoken-exchange-test/
├── README.md                          # 项目说明文档
├── requirements.txt                   # Python 依赖
├── pytest.ini                         # Pytest 配置
├── docker-compose.yml                 # Docker 编排
├── .github/
│   └── workflows/
│       └── test.yml                   # CI/CD 工作流
├── config/
│   ├── settings.py                    # 配置文件
│   └── test_config.py                 # 测试配置
├── src/
│   ├── __init__.py
│   ├── models/                        # 数据模型
│   │   ├── user.py
│   │   ├── wallet.py
│   │   ├── order.py
│   │   └── transaction.py
│   ├── services/                      # 业务服务
│   │   ├── auth_service.py
│   │   ├── wallet_service.py
│   │   ├── order_service.py
│   │   └── payment_service.py
│   └── api/                           # API 端点
│       ├── auth.py
│       ├── wallet.py
│       ├── orders.py
│       └── health.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_auth.py                   # 认证测试
│   ├── test_wallet.py                 # 钱包测试
│   ├── test_orders.py                 # 订单测试
│   ├── test_payment.py                # 支付测试
│   ├── test_security.py               # 安全测试
│   └── test_performance.py            # 性能测试
├── mocks/                             # MockClaw 生成的 Mock
│   ├── payment_gateway/               # 支付网关 Mock
│   ├── blockchain_node/               # 区块链节点 Mock
│   ├── sms_service/                   # 短信服务 Mock
│   ├── email_service/                 # 邮件服务 Mock
│   └── kyc_service/                   # KYC 验证 Mock
├── har_files/                         # 录制的 HAR 文件
│   ├── payment_gateway_flow.har
│   ├── blockchain_flow.har
│   ├── sms_flow.har
│   ├── email_flow.har
│   └── kyc_flow.har
├── scripts/
│   ├── record_apis.py                 # 录制 API 流量脚本
│   ├── generate_mocks.py              # 批量生成 Mock 脚本
│   ├── start_all_mocks.py             # 启动所有 Mock 服务
│   └── run_tests.sh                   # 运行测试脚本
└── docs/
    ├── API_DOCUMENTATION.md           # API 文档
    ├── MOCK_USAGE_GUIDE.md            # Mock 使用指南
    └── TEST_STRATEGY.md               # 测试策略文档
```

---

## 📝 具体实现要求

### 1. 核心业务功能（必须实现）

#### 1.1 用户认证模块
- 用户注册（邮箱/手机号）
- 用户登录（JWT Token）
- 双因素认证（2FA）
- 密码重置
- Session 管理

#### 1.2 钱包管理模块
- 创建钱包地址
- 查询余额
- 充值（区块链交易）
- 提现（区块链交易）
- 交易历史

#### 1.3 订单系统模块
- 创建买单/卖单
- 订单撮合
- 订单状态追踪（Pending, Filled, Cancelled, Expired）
- 订单历史查询
- 价格计算

#### 1.4 支付集成模块
- 法币充值（信用卡/借记卡）
- 法币提现
- 支付状态回调
- 退款处理

---

### 2. 第三方 API Mock 场景（必须实现）

#### 2.1 支付网关 Mock（Stripe-like）
**需要 Mock 的场景：**
- 创建支付意图（成功/失败/需要验证）
- 确认支付（成功/失败/3D Secure）
- 退款（全额/部分退款）
- Webhook 回调（支付成功/失败/争议）
- 限流测试（429 Too Many Requests）
- 错误场景（卡片过期、余额不足、欺诈检测）

**关键测试点：**
```python
# 测试支付成功场景
def test_payment_success():
    response = payment_service.create_payment(
        amount=100.00,
        currency="USD",
        card_token="card_valid"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"

# 测试卡片过期场景
def test_payment_card_expired():
    response = payment_service.create_payment(
        amount=100.00,
        currency="USD",
        card_token="card_expired"
    )
    assert response.status_code == 400
    assert "card_expired" in response.json()["error"]["code"]

# 测试限流场景
def test_payment_rate_limit():
    for i in range(100):
        response = payment_service.create_payment(...)
        if i >= 60:
            assert response.status_code == 429
```

#### 2.2 区块链节点 Mock（Ethereum JSON-RPC）
**需要 Mock 的场景：**
- 获取账户余额（正常/零余额/合约地址）
- 发送交易（成功/失败/Gas 不足）
- 获取交易收据（成功/失败/Pending）
- 获取 Gas 价格（动态价格）
- 智能合约调用（成功/Revert/Out of Gas）

**关键测试点：**
```python
# 测试交易成功场景
def test_blockchain_transaction_success():
    tx_hash = blockchain_service.send_transaction(
        from_address="0x123...",
        to_address="0x456...",
        value=1.0
    )
    receipt = blockchain_service.get_transaction_receipt(tx_hash)
    assert receipt["status"] == 1  # Success

# 测试 Gas 不足场景
def test_blockchain_out_of_gas():
    tx_hash = blockchain_service.send_transaction(
        from_address="0x123...",
        to_address="0x456...",
        value=1.0,
        gas=21000  # Insufficient gas
    )
    receipt = blockchain_service.get_transaction_receipt(tx_hash)
    assert receipt["status"] == 0  # Failed
```

#### 2.3 短信服务 Mock（Twilio-like）
**需要 Mock 的场景：**
- 发送验证码（成功/失败/无效号码）
- 验证码校验（正确/错误/过期）
- 发送营销短信（成功/被拦截）
- 号码格式验证

#### 2.4 邮件服务 Mock（SendGrid-like）
**需要 Mock 的场景：**
- 发送验证邮件（成功/失败/邮箱不存在）
- 发送交易通知邮件
- 发送营销邮件（成功/被标记为垃圾邮件）
- 邮件模板渲染

#### 2.5 KYC 验证 Mock（Jumio-like）
**需要 Mock 的场景：**
- 提交身份验证（成功/失败/需要人工审核）
- 人脸识别验证（通过/失败/需要重拍）
- 文档验证（护照/身份证/驾照）
- 验证状态查询（Pending/Approved/Rejected）

---

### 3. 测试场景设计（必须实现）

#### 3.1 单元测试
- 每个服务模块的核心功能测试
- Mock 数据验证
- 异常处理测试

#### 3.2 集成测试
- 完整业务流程测试（注册 → 充值 → 交易 → 提现）
- 第三方 API 集成测试
- 数据库事务测试

#### 3.3 端到端测试（E2E）
- 用户完整交易流程
- 多用户并发交易
- 订单撮合流程

#### 3.4 安全测试
- SQL 注入测试
- XSS 攻击测试
- CSRF 防护测试
- JWT Token 安全性测试
- 限流测试
- 路径遍历攻击测试

#### 3.5 性能测试
- 并发用户测试（100/500/1000 并发）
- 响应时间测试（< 200ms）
- 吞吐量测试（> 1000 QPS）
- 压力测试

---

### 4. MockClaw 集成要求（必须实现）

#### 4.1 HAR 文件录制
为每个第三方服务创建录制脚本：
```python
# scripts/record_payment_gateway.py
"""
录制支付网关 API 流量
"""
import requests
from pathlib import Path

def record_payment_scenarios():
    """录制支付网关的各种场景"""
    
    # 场景 1: 成功支付
    response = requests.post(
        "https://api.payment-gateway.com/v1/charges",
        json={
            "amount": 10000,  # $100.00
            "currency": "usd",
            "source": "tok_visa",
            "description": "CloudToken Exchange Deposit"
        },
        headers={"Authorization": "Bearer sk_test_..."}
    )
    
    # 场景 2: 卡片被拒绝
    response = requests.post(
        "https://api.payment-gateway.com/v1/charges",
        json={
            "amount": 10000,
            "currency": "usd",
            "source": "tok_chargeDeclined",  # 特殊测试 Token
            "description": "Test declined card"
        },
        headers={"Authorization": "Bearer sk_test_..."}
    )
    
    # ... 更多场景
```

#### 4.2 Mock 生成脚本
```python
# scripts/generate_all_mocks.py
"""
使用 MockClaw 批量生成所有第三方服务的 Mock
"""
import subprocess
from pathlib import Path

def generate_all_mocks():
    """生成所有 Mock 服务器"""
    
    services = {
        "payment_gateway": "har_files/payment_gateway_flow.har",
        "blockchain_node": "har_files/blockchain_flow.har",
        "sms_service": "har_files/sms_flow.har",
        "email_service": "har_files/email_flow.har",
        "kyc_service": "har_files/kyc_flow.har",
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

#### 4.3 启动所有 Mock 服务
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
    "kyc_service": 8005,
}

def start_all_mocks():
    """启动所有 Mock 服务"""
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
    
    return processes

if __name__ == "__main__":
    processes = start_all_mocks()
    try:
        # Keep running
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping all mock services...")
        for proc in processes:
            proc.terminate()
```

---

### 5. 配置文件示例（必须实现）

#### 5.1 测试配置
```python
# config/test_config.py
"""
测试环境配置
"""
import os

class TestConfig:
    """测试配置类"""
    
    # Mock 服务地址
    MOCK_SERVICES = {
        "payment_gateway": "http://localhost:8001",
        "blockchain_node": "http://localhost:8002",
        "sms_service": "http://localhost:8003",
        "email_service": "http://localhost:8004",
        "kyc_service": "http://localhost:8005",
    }
    
    # 数据库配置（测试数据库）
    DATABASE_URL = "postgresql://test:test@localhost:5432/cloudtoken_test"
    REDIS_URL = "redis://localhost:6379/1"
    
    # JWT 配置
    JWT_SECRET_KEY = "test-secret-key-for-testing-only"
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    
    # 测试用户数据
    TEST_USERS = {
        "user1": {
            "email": "user1@test.com",
            "password": "Test@123456",
            "phone": "+1234567890",
        },
        "user2": {
            "email": "user2@test.com",
            "password": "Test@123456",
            "phone": "+1234567891",
        },
    }
    
    # 测试钱包地址
    TEST_WALLETS = {
        "eth_wallet_1": "0x1234567890abcdef1234567890abcdef12345678",
        "eth_wallet_2": "0xabcdef1234567890abcdef1234567890abcdef12",
    }
    
    # 测试支付卡片
    TEST_CARDS = {
        "valid_visa": "tok_visa",
        "valid_mastercard": "tok_mastercard",
        "expired_card": "tok_chargeDeclinedExpiredCard",
        "insufficient_funds": "tok_chargeDeclinedInsufficientFunds",
        "fraudulent": "tok_chargeDeclinedFraudulent",
    }
```

#### 5.2 Pytest 配置
```python
# tests/conftest.py
"""
Pytest fixtures 和共享配置
"""
import pytest
import requests
from config.test_config import TestConfig

@pytest.fixture(scope="session")
def mock_services():
    """验证所有 Mock 服务是否运行"""
    for service_name, url in TestConfig.MOCK_SERVICES.items():
        try:
            response = requests.get(f"{url}/health", timeout=2)
            assert response.status_code == 200, f"{service_name} not healthy"
        except Exception as e:
            pytest.fail(f"Mock service {service_name} is not running: {e}")
    
    return TestConfig.MOCK_SERVICES

@pytest.fixture
def test_user():
    """测试用户 fixture"""
    return TestConfig.TEST_USERS["user1"]

@pytest.fixture
def auth_token(test_user, mock_services):
    """获取认证 Token"""
    response = requests.post(
        f"{mock_services['auth_service']}/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    return response.json()["token"]

@pytest.fixture
def clean_database():
    """清理测试数据库"""
    # 清理逻辑
    yield
    # 清理逻辑
```

---

### 6. 测试用例示例（必须实现）

#### 6.1 认证测试
```python
# tests/test_auth.py
"""
用户认证测试
"""
import pytest
import requests

class TestAuthentication:
    """认证测试套件"""
    
    def test_user_registration_success(self, mock_services):
        """测试用户注册成功"""
        response = requests.post(
            f"{mock_services['auth_service']}/register",
            json={
                "email": "newuser@test.com",
                "password": "Test@123456",
                "phone": "+1234567899"
            }
        )
        assert response.status_code == 201
        assert "user_id" in response.json()
    
    def test_user_registration_duplicate_email(self, mock_services, test_user):
        """测试重复邮箱注册失败"""
        response = requests.post(
            f"{mock_services['auth_service']}/register",
            json={
                "email": test_user["email"],  # 已存在的邮箱
                "password": "Test@123456",
                "phone": "+1234567899"
            }
        )
        assert response.status_code == 400
        assert "email_already_exists" in response.json()["error"]["code"]
    
    def test_login_success(self, mock_services, test_user):
        """测试登录成功"""
        response = requests.post(
            f"{mock_services['auth_service']}/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"]
            }
        )
        assert response.status_code == 200
        assert "token" in response.json()
    
    def test_login_invalid_password(self, mock_services, test_user):
        """测试密码错误登录失败"""
        response = requests.post(
            f"{mock_services['auth_service']}/login",
            json={
                "email": test_user["email"],
                "password": "WrongPassword123"
            }
        )
        assert response.status_code == 401
    
    def test_2fa_verification(self, mock_services, auth_token):
        """测试双因素认证"""
        # 发送 2FA 验证码
        response = requests.post(
            f"{mock_services['auth_service']}/2fa/send",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        # 验证 2FA 验证码（使用 Mock SMS 服务返回的验证码）
        response = requests.post(
            f"{mock_services['auth_service']}/2fa/verify",
            json={"code": "123456"},  # Mock 服务返回的固定验证码
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
```

#### 6.2 支付测试
```python
# tests/test_payment.py
"""
支付集成测试
"""
import pytest
import requests

class TestPayment:
    """支付测试套件"""
    
    def test_payment_success(self, mock_services, auth_token):
        """测试支付成功"""
        response = requests.post(
            f"{mock_services['payment_gateway']}/v1/charges",
            json={
                "amount": 10000,  # $100.00
                "currency": "usd",
                "source": "tok_visa",
                "description": "CloudToken Deposit"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"
        assert data["amount"] == 10000
    
    def test_payment_card_declined(self, mock_services, auth_token):
        """测试卡片被拒绝"""
        response = requests.post(
            f"{mock_services['payment_gateway']}/v1/charges",
            json={
                "amount": 10000,
                "currency": "usd",
                "source": "tok_chargeDeclined",
                "description": "Test declined card"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 400
        assert "card_declined" in response.json()["error"]["code"]
    
    def test_payment_refund(self, mock_services, auth_token):
        """测试退款"""
        # 先创建支付
        charge_response = requests.post(
            f"{mock_services['payment_gateway']}/v1/charges",
            json={
                "amount": 10000,
                "currency": "usd",
                "source": "tok_visa"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        charge_id = charge_response.json()["id"]
        
        # 发起退款
        refund_response = requests.post(
            f"{mock_services['payment_gateway']}/v1/refunds",
            json={
                "charge": charge_id,
                "amount": 5000  # 部分退款 $50
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert refund_response.status_code == 200
        assert refund_response.json()["status"] == "succeeded"
    
    def test_payment_rate_limit(self, mock_services, auth_token):
        """测试支付限流"""
        # 快速发送 100 个请求
        for i in range(100):
            response = requests.post(
                f"{mock_services['payment_gateway']}/v1/charges",
                json={
                    "amount": 100,
                    "currency": "usd",
                    "source": "tok_visa"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            # 第 61 个请求应该被限流
            if i >= 60:
                assert response.status_code == 429
```

---

### 7. Docker 集成（必须实现）

#### 7.1 Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  # 测试数据库
  postgres-test:
    image: postgres:14
    environment:
      POSTGRES_DB: cloudtoken_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
  
  # Redis 测试实例
  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"
  
  # Mock 服务
  payment-gateway-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    command: python -m src.cli serve mocks/payment_gateway --port 8001
    ports:
      - "8001:8001"
    volumes:
      - ./mocks:/app/mocks
  
  blockchain-node-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    command: python -m src.cli serve mocks/blockchain_node --port 8002
    ports:
      - "8002:8002"
    volumes:
      - ./mocks:/app/mocks
  
  sms-service-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    command: python -m src.cli serve mocks/sms_service --port 8003
    ports:
      - "8003:8003"
    volumes:
      - ./mocks:/app/mocks
  
  email-service-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    command: python -m src.cli serve mocks/email_service --port 8004
    ports:
      - "8004:8004"
    volumes:
      - ./mocks:/app/mocks
  
  kyc-service-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    command: python -m src.cli serve mocks/kyc_service --port 8005
    ports:
      - "8005:8005"
    volumes:
      - ./mocks:/app/mocks

  # 测试运行器
  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      - postgres-test
      - redis-test
      - payment-gateway-mock
      - blockchain-node-mock
      - sms-service-mock
      - email-service-mock
      - kyc-service-mock
    environment:
      DATABASE_URL: postgresql://test:test@postgres-test:5432/cloudtoken_test
      REDIS_URL: redis://redis-test:6379/0
    volumes:
      - .:/app
    command: pytest tests/ -v --cov=src --cov-report=html
```

---

### 8. CI/CD 集成（必须实现）

#### 8.1 GitHub Actions
```yaml
# .github/workflows/test.yml
name: CloudToken Exchange Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  PYTHON_VERSION: '3.11'

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: cloudtoken_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7-alpine
        ports:
          - 6380:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
        cache: 'pip'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Generate Mocks from HAR files
      run: |
        python scripts/generate_all_mocks.py
    
    - name: Start Mock Services
      run: |
        python scripts/start_all_mocks.py &
        sleep 5
        
        # Verify all mocks are healthy
        for port in 8001 8002 8003 8004 8005; do
          curl -f http://localhost:$port/health || exit 1
        done
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://test:test@localhost:5433/cloudtoken_test
        REDIS_URL: redis://localhost:6380/0
      run: |
        pytest tests/ -v --cov=src --cov-report=xml --cov-report=html
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Upload test results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results
        path: |
          htmlcov/
          .pytest_cache/
```

---

## 📊 项目验收标准

生成的项目必须满足以下标准：

### 功能完整性
- ✅ 实现所有核心业务功能（认证、钱包、订单、支付）
- ✅ 为所有第三方服务创建 Mock
- ✅ 编写完整的测试用例（单元、集成、E2E、安全、性能）
- ✅ 配置文件完整且可用

### 代码质量
- ✅ 代码符合 PEP 8 规范
- ✅ 所有函数都有文档字符串
- ✅ 类型提示完整
- ✅ 测试覆盖率 > 80%

### MockClaw 集成
- ✅ 使用 MockClaw CLI 生成所有 Mock
- ✅ 使用 Smart Fallback 模式
- ✅ Mock 服务能够正确响应各种场景
- ✅ 提供批量生成和启动脚本

### 文档完整性
- ✅ README.md 包含项目说明和快速开始
- ✅ API_DOCUMENTATION.md 包含所有 API 文档
- ✅ MOCK_USAGE_GUIDE.md 包含 Mock 使用指南
- ✅ TEST_STRATEGY.md 包含测试策略

### CI/CD 就绪
- ✅ Docker Compose 配置完整
- ✅ GitHub Actions 工作流配置完整
- ✅ 测试可以自动化运行
- ✅ 代码覆盖率报告自动生成

---

## 🎯 输出要求

请生成完整的项目代码，包括：
1. 所有源代码文件（Python）
2. 所有测试文件（pytest）
3. 所有配置文件（YAML, INI, ENV）
4. 所有文档文件（Markdown）
5. 所有脚本文件（Shell, Python）
6. Docker 相关文件（Dockerfile, docker-compose.yml）
7. CI/CD 配置文件（GitHub Actions）

确保所有代码都是可运行的，测试可以执行，Mock 服务可以启动。

---

## 💡 提示

- 使用 MockClaw 的 `--smart-fallback` 模式生成智能 Mock
- 为每个第三方服务设计多种场景（成功、失败、边界情况）
- 测试用例要覆盖正常流程和异常流程
- 使用 Docker 确保环境一致性
- CI/CD 流程要自动化所有步骤

---

**开始生成项目代码！** 🚀
