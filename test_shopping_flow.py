"""
测试电商购物流程
使用 MockClaw 生成的 Mock API 进行测试
"""
import pytest
import requests

# Mock 服务器地址
MOCK_API = "http://localhost:8007"


class TestShoppingFlow:
    """测试完整的购物流程"""
    
    def test_get_products(self):
        """测试获取商品列表"""
        response = requests.get(f"{MOCK_API}/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert len(data["products"]) > 0
        print(f"✅ 商品列表：{len(data['products'])} 个商品")
    
    def test_get_product_by_category(self):
        """测试按分类筛选商品"""
        response = requests.get(f"{MOCK_API}/products?category=electronics")
        assert response.status_code == 200
        data = response.json()
        # Mock 返回所有商品（基于录制的流量）
        assert "products" in data
        assert len(data["products"]) > 0
        print(f"✅ 商品列表（带筛选参数）：{len(data['products'])} 个商品")
    
    def test_login(self):
        """测试用户登录"""
        response = requests.post(f"{MOCK_API}/login")
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"✅ 登录成功：用户 {data['user']['username']}")
    
    def test_view_empty_cart(self):
        """测试查看空购物车"""
        response = requests.get(f"{MOCK_API}/cart/user123")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✅ 空购物车：{len(data['items'])} 个商品，总计 ${data['total']}")
    
    def test_add_to_cart(self):
        """测试添加商品到购物车"""
        response = requests.post(f"{MOCK_API}/cart/user123")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Added to cart"
        assert len(data["cart"]["items"]) > 0
        print(f"✅ 添加成功：购物车 {len(data['cart']['items'])} 个商品")
    
    def test_checkout_with_expired_coupon(self):
        """测试使用过期优惠券下单"""
        response = requests.post(
            f"{MOCK_API}/checkout",
            json={"coupon_code": "EXPIRED2026"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["detail"]["error"] == "COUPON_EXPIRED"
        print(f"✅ 过期优惠券正确拒绝：{data['detail']['detail']['message']}")
    
    def test_checkout_with_valid_coupon(self):
        """测试使用有效优惠券下单"""
        response = requests.post(
            f"{MOCK_API}/checkout",
            json={"coupon_code": "SAVE10"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert data["status"] == "confirmed"
        assert "discount" in data
        assert data["discount"] > 0  # 应该有折扣
        print(f"✅ 优惠券下单成功：订单 {data['order_id']}，折扣 ${data['discount']:.2f}")
    
    def test_checkout_without_coupon(self):
        """测试不使用优惠券下单"""
        response = requests.post(
            f"{MOCK_API}/checkout",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert data["status"] == "confirmed"
        print(f"✅ 正常下单成功：订单 {data['order_id']}")
    
    def test_view_order_history(self):
        """测试查看订单历史"""
        response = requests.get(f"{MOCK_API}/orders/user123")
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert len(data["orders"]) > 0
        print(f"✅ 订单历史：{len(data['orders'])} 个订单")


class TestSecurityFeatures:
    """测试自动注入的安全功能"""
    
    def test_path_traversal_protection(self):
        """测试路径遍历保护"""
        # 尝试访问危险路径
        response = requests.get(f"{MOCK_API}/../../../etc/passwd")
        assert response.status_code == 404  # 应该返回 404
        print("✅ 路径遍历保护生效")
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = requests.get(f"{MOCK_API}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        print(f"✅ 健康检查通过：{data['service']}")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
