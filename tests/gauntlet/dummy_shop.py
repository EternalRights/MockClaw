"""
MockClaw Gauntlet - Dummy Shop API
A test API server with intentional complexity for adversarial testing.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import random

app = FastAPI(title="Dummy Shop API", version="1.0.0")

# In-memory database
cart_db = {}
users_db = {
    "testuser": {"id": 1, "username": "testuser", "password": "password123"}
}


class LoginRequest(BaseModel):
    username: str
    password: str


class CartItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int = 1


class CheckoutRequest(BaseModel):
    user_id: str
    coupon_code: Optional[str] = None
    shipping_address: Optional[str] = None


# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "service": "dummy-shop"}


# Login endpoint
@app.post("/login")
async def login(request: LoginRequest):
    """User login - returns token."""
    user = users_db.get(request.username)
    if not user or user["password"] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "token": f"jwt_token_{user['id']}_{datetime.now().timestamp()}",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": f"{user['username']}@example.com"
        }
    }


# Products endpoint
@app.get("/products")
async def list_products(category: Optional[str] = None):
    """List products with optional filter."""
    products = [
        {"id": "iphone15", "name": "iPhone 15 Pro", "price": 999.99, "category": "electronics"},
        {"id": "macbook", "name": "MacBook Pro 16\"", "price": 2499.99, "category": "electronics"},
        {"id": "airpods", "name": "AirPods Pro", "price": 249.99, "category": "electronics"},
        {"id": "watch", "name": "Apple Watch Ultra", "price": 799.99, "category": "accessories"},
    ]
    
    if category:
        products = [p for p in products if p["category"] == category]
    
    return {"products": products, "total": len(products)}


# Cart endpoints
@app.get("/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart."""
    if user_id not in cart_db:
        cart_db[user_id] = {"items": [], "total": 0.0}
    return cart_db[user_id]


@app.post("/cart/{user_id}")
async def add_to_cart(user_id: str, item: CartItem):
    """Add item to cart."""
    if user_id not in cart_db:
        cart_db[user_id] = {"items": [], "total": 0.0}
    
    cart_db[user_id]["items"].append(item.model_dump())
    cart_db[user_id]["total"] = sum(
        i["price"] * i["quantity"] for i in cart_db[user_id]["items"]
    )
    
    return {"message": "Added to cart", "cart": cart_db[user_id]}


@app.delete("/cart/{user_id}/{item_index}")
async def remove_from_cart(user_id: str, item_index: int):
    """Remove item from cart."""
    if user_id not in cart_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    if item_index >= len(cart_db[user_id]["items"]):
        raise HTTPException(status_code=404, detail="Item not found")
    
    cart_db[user_id]["items"].pop(item_index)
    cart_db[user_id]["total"] = sum(
        i["price"] * i["quantity"] for i in cart_db[user_id]["items"]
    )
    
    return {"message": "Removed from cart", "cart": cart_db[user_id]}


# Checkout endpoint - THE CRITICAL ONE
@app.post("/checkout")
async def checkout(request: CheckoutRequest):
    """
    Process checkout.
    IMPORTANT: Coupon "EXPIRED2026" should return 400 error.
    """
    user_id = request.user_id
    
    # Check cart exists
    if user_id not in cart_db or not cart_db[user_id]["items"]:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Coupon validation - THE TEST CASE
    expired_coupons = ["EXPIRED2026", "OLD_DEAL_2025", "DEPRECATED"]
    
    if request.coupon_code and request.coupon_code in expired_coupons:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "COUPON_EXPIRED",
                "message": f"Coupon '{request.coupon_code}' has expired",
                "valid_coupons": ["SAVE10", "SUMMER2026"]
            }
        )
    
    # Calculate total
    cart = cart_db[user_id]
    total = cart["total"]
    
    # Apply valid coupon
    discount = 0
    if request.coupon_code:
        if request.coupon_code == "SAVE10":
            discount = total * 0.1
        elif request.coupon_code == "SUMMER2026":
            discount = total * 0.15
    
    final_total = total - discount
    
    # Create order
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
    
    # Clear cart
    cart_db[user_id] = {"items": [], "total": 0.0}
    
    return {
        "order_id": order_id,
        "status": "confirmed",
        "items": cart["items"],
        "subtotal": total,
        "discount": discount,
        "total": final_total,
        "estimated_delivery": "2026-04-05",
        "tracking_url": f"https://tracking.example.com/{order_id}"
    }


# Order history
@app.get("/orders/{user_id}")
async def get_orders(user_id: str):
    """Get order history (mock)."""
    return {
        "orders": [
            {
                "order_id": "ORD-20260328001",
                "status": "delivered",
                "total": 999.99,
                "date": "2026-03-15"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
