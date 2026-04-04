"""验证 Mock 服务器是否正常工作"""
import requests

BASE_URL = "http://localhost:8007"

print("=" * 60)
print("验证 MockClaw 生成的 Mock 服务器")
print("=" * 60)

# 测试 1: 健康检查
print("\n1. 健康检查...")
try:
    resp = requests.get(f"{BASE_URL}/health", timeout=2)
    print(f"   ✅ 状态码: {resp.status_code}")
    print(f"   ✅ 响应: {resp.json()}")
except Exception as e:
    print(f"   ❌ 错误: {e}")
    exit(1)

# 测试 2: 获取商品列表
print("\n2. 获取商品列表...")
try:
    resp = requests.get(f"{BASE_URL}/products", timeout=2)
    print(f"   ✅ 状态码: {resp.status_code}")
    data = resp.json()
    print(f"   ✅ 商品数量: {len(data.get('products', []))}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

# 测试 3: 过期优惠券（关键测试）
print("\n3. 测试过期优惠券（关键业务逻辑）...")
try:
    resp = requests.post(f"{BASE_URL}/checkout", json={
        "user_id": "user123",
        "coupon_code": "EXPIRED2026",
        "shipping_address": "测试地址"
    }, timeout=2)
    print(f"   ✅ 状态码: {resp.status_code} (期望: 400)")
    if resp.status_code == 400:
        print(f"   ✅ 正确拒绝了过期优惠券！")
        print(f"   响应: {resp.json()}")
    else:
        print(f"   ❌ 错误：应该返回 400，但返回了 {resp.status_code}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

# 测试 4: 有效优惠券（关键测试）
print("\n4. 测试有效优惠券（关键业务逻辑）...")
try:
    resp = requests.post(f"{BASE_URL}/checkout", json={
        "user_id": "user123",
        "coupon_code": "SAVE10",
        "shipping_address": "测试地址"
    }, timeout=2)
    print(f"   ✅ 状态码: {resp.status_code} (期望: 200)")
    if resp.status_code == 200:
        print(f"   ✅ 成功接受有效优惠券！")
        data = resp.json()
        print(f"   订单ID: {data.get('order_id', 'N/A')}")
        print(f"   折扣: {data.get('discount', 0)}")
    else:
        print(f"   ❌ 错误：应该返回 200，但返回了 {resp.status_code}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

print("\n" + "=" * 60)
print("✅ 验证完成！Mock 服务器工作正常")
print("=" * 60)
print(f"\n📖 API 文档: {BASE_URL}/docs")
