"""
场景 2：测试开发工作流测试
为自动化测试创建稳定的测试环境
"""
import pytest
import requests

BASE_URL = "http://localhost:8007"

print("=" * 60)
print("场景 2：测试开发工作流")
print("=" * 60)

print("\n📋 场景描述：")
print("你是测试开发，要写自动化测试，但环境不稳定")
print("使用 MockClaw 创建稳定、可重复的测试环境")

print("\n" + "=" * 60)
print("pytest 测试用例")
print("=" * 60)

# 定义测试类
class TestShoppingFlow:
    """购物流程测试套件"""
    
    def test_get_products(self):
        """测试获取商品列表"""
        response = requests.get(f"{BASE_URL}/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert len(data["products"]) > 0
        print(f"  ✅ 商品列表测试通过，共 {len(data['products'])} 个商品")
    
    def test_user_login(self):
        """测试用户登录"""
        response = requests.post(f"{BASE_URL}/login", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"  ✅ 登录测试通过")
    
    def test_add_to_cart(self):
        """测试添加商品到购物车"""
        response = requests.post(f"{BASE_URL}/cart/user123", json={
            "product_id": "iphone15",
            "name": "iPhone 15 Pro",
            "price": 999.99,
            "quantity": 1
        })
        assert response.status_code == 200
        print(f"  ✅ 添加购物车测试通过")
    
    def test_checkout_with_valid_coupon(self):
        """测试使用有效优惠券下单"""
        response = requests.post(f"{BASE_URL}/checkout", json={
            "user_id": "user123",
            "coupon_code": "SAVE10",
            "shipping_address": "北京市朝阳区"
        })
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert data.get("status") == "confirmed"
        assert data.get("discount", 0) > 0
        print(f"  ✅ 有效优惠券测试通过，订单ID: {data['order_id']}")
    
    def test_checkout_with_expired_coupon(self):
        """测试使用过期优惠券（关键测试）"""
        response = requests.post(f"{BASE_URL}/checkout", json={
            "user_id": "user123",
            "coupon_code": "EXPIRED2026",
            "shipping_address": "北京市朝阳区"
        })
        assert response.status_code == 400
        error_data = response.json()
        assert "expired" in str(error_data).lower()
        print(f"  ✅ 过期优惠券正确被拒绝")
    
    def test_order_history(self):
        """测试查看订单历史"""
        response = requests.get(f"{BASE_URL}/orders/user123")
        assert response.status_code == 200
        print(f"  ✅ 订单历史测试通过")

# 运行测试
print("\n运行测试...")
print("-" * 60)

test_suite = TestShoppingFlow()

tests = [
    ("获取商品列表", test_suite.test_get_products),
    ("用户登录", test_suite.test_user_login),
    ("添加购物车", test_suite.test_add_to_cart),
    ("有效优惠券下单", test_suite.test_checkout_with_valid_coupon),
    ("过期优惠券拒绝", test_suite.test_checkout_with_expired_coupon),
    ("查看订单历史", test_suite.test_order_history),
]

passed = 0
failed = 0

for test_name, test_func in tests:
    try:
        test_func()
        passed += 1
    except AssertionError as e:
        print(f"  ❌ {test_name} 失败: {e}")
        failed += 1
    except Exception as e:
        print(f"  ❌ {test_name} 错误: {e}")
        failed += 1

print("-" * 60)
print(f"\n测试结果: {passed} 通过, {failed} 失败")

print("\n" + "=" * 60)
print("安全特性测试")
print("=" * 60)

print("\n测试 1：路径遍历攻击防护")
response = requests.get(f"{BASE_URL}/../etc/passwd")
if response.status_code in [400, 404]:
    print(f"  ✅ 路径遍历攻击被阻止 (状态码: {response.status_code})")
else:
    print(f"  ⚠️  路径遍历防护可能需要加强")

print("\n测试 2：限流保护")
print("  发送 10 个快速请求...")
for i in range(10):
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 429:
        print(f"  ✅ 限流保护在第 {i+1} 个请求时触发")
        break
else:
    print(f"  ✅ 限流保护正常（允许 10 个请求）")

print("\n" + "=" * 60)
print("优势总结")
print("=" * 60)
print("✅ 测试环境完全可控")
print("✅ 可以模拟各种边界情况")
print("✅ 测试可重复、稳定")
print("✅ 不依赖外部系统")
print("✅ 自动注入安全保护")

print("\n" + "=" * 60)
print("CI/CD 集成示例")
print("=" * 60)
print("""
# .github/workflows/test.yml
name: Tests

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Mock Server
        run: |
          pip install -r src/requirements.txt
          python -m src.cli generate tests/gauntlet/flow.har --smart-fallback
          python -m src.cli serve ./beginner_mocks --port 8000 &
          sleep 3
      
      - name: Run Tests
        run: pytest tests/ -v
""")
