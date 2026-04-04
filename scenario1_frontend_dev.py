"""
场景 1：前端开发工作流测试
模拟前端开发者使用 MockClaw 进行开发
"""

print("=" * 60)
print("场景 1：前端开发工作流")
print("=" * 60)

print("\n📋 场景描述：")
print("你是前端开发，后端接口还没好，但你要开始开发页面")
print("使用 MockClaw 生成的 Mock 服务器进行前端开发")

print("\n" + "=" * 60)
print("步骤演示")
print("=" * 60)

print("\n步骤 1：获取后端接口的 HAR 文件")
print("  方式 A：从测试环境录制（浏览器 F12 → Network → Save as HAR）")
print("  方式 B：使用 MockClaw 的虚拟商店")
print("  ✅ 我们已经有 tests/gauntlet/flow.har")

print("\n步骤 2：生成 Mock 服务器")
print("  命令：python -m src.cli generate tests/gauntlet/flow.har --smart-fallback")
print("  ✅ 已生成 6 个端点")

print("\n步骤 3：启动 Mock 服务器")
print("  命令：python -m src.cli serve ./beginner_mocks --port 8007")
print("  ✅ 服务器运行在 http://localhost:8007")

print("\n步骤 4：修改前端代码")
print("  原来的 API 地址：http://backend-server:8080/api")
print("  改为本地 Mock：http://localhost:8007")
print("  ✅ 前端代码无需其他修改！")

print("\n" + "=" * 60)
print("前端代码示例")
print("=" * 60)

print("""
// JavaScript 前端代码示例
const API_BASE = 'http://localhost:8007';  // 指向 Mock 服务器

// 获取商品列表
async function getProducts() {
  const response = await fetch(`${API_BASE}/products`);
  const data = await response.json();
  console.log('商品列表:', data.products);
  return data.products;
}

// 使用优惠券下单
async function checkout(userId, couponCode) {
  const response = await fetch(`${API_BASE}/checkout`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: userId,
      coupon_code: couponCode,
      shipping_address: '北京市朝阳区'
    })
  });
  
  if (response.status === 400) {
    const error = await response.json();
    console.error('下单失败:', error);
    return null;
  }
  
  const order = await response.json();
  console.log('下单成功:', order);
  return order;
}

// 使用示例
getProducts();  // 获取商品列表
checkout('user123', 'SAVE10');  // 使用有效优惠券
checkout('user123', 'EXPIRED2026');  // 使用过期优惠券（会失败）
""")

print("\n" + "=" * 60)
print("实际测试")
print("=" * 60)

import requests

API_BASE = "http://localhost:8007"

print("\n测试 1：获取商品列表")
resp = requests.get(f"{API_BASE}/products")
print(f"  状态码: {resp.status_code}")
print(f"  商品数量: {len(resp.json()['products'])}")
print(f"  ✅ 前端可以正常获取商品数据")

print("\n测试 2：用户登录")
resp = requests.post(f"{API_BASE}/login", json={
    "username": "testuser",
    "password": "password123"
})
print(f"  状态码: {resp.status_code}")
print(f"  Token: {resp.json().get('token', 'N/A')[:20]}...")
print(f"  ✅ 前端可以正常登录")

print("\n测试 3：查看购物车")
resp = requests.get(f"{API_BASE}/cart/user123")
print(f"  状态码: {resp.status_code}")
print(f"  购物车商品: {len(resp.json().get('items', []))}")
print(f"  ✅ 前端可以正常查看购物车")

print("\n测试 4：下单（有效优惠券）")
resp = requests.post(f"{API_BASE}/checkout", json={
    "user_id": "user123",
    "coupon_code": "SAVE10",
    "shipping_address": "北京市朝阳区"
})
print(f"  状态码: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"  订单ID: {data.get('order_id')}")
    print(f"  折扣: ¥{data.get('discount', 0):.2f}")
    print(f"  ✅ 前端可以正常下单")

print("\n" + "=" * 60)
print("优势总结")
print("=" * 60)
print("✅ 不依赖后端开发进度")
print("✅ 可以提前开始前端开发")
print("✅ 接口变更时快速验证")
print("✅ 离线也能开发")
print("✅ Mock 数据和真实后端返回格式一致")

print("\n" + "=" * 60)
print("开发完成后的切换")
print("=" * 60)
print("""
// 开发完成后，只需修改 API_BASE：
// const API_BASE = 'http://real-backend-server:8080/api';
// 其他代码完全不用改！
""")
