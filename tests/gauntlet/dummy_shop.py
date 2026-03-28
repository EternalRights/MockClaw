"""
MockClaw Gauntlet - Dummy Shop API
Critical test: /checkout returns 400 for coupon "EXPIRED2026"
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import random

app = FastAPI(title="Dummy Shop", version="1.0.0")

# In-memory DB
carts = {}
orders = {}


class CartItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int = 1


class CheckoutRequest(BaseModel):
    user_id: str
    coupon_code: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "OK", "service": "dummy-shop"}


@app.get("/products")
async def products():
    return {
        "products": [
            {"id": "iphone15", "name": "iPhone 15 Pro", "price": 999.99},
            {"id": "macbook", "name": "MacBook Pro", "price": 2499.99},
            {"id": "airpods", "name": "AirPods Pro", "price": 249.99},
        ]
    }


@app.post("/cart/{user_id}")
async def add_to_cart(user_id: str, item: CartItem):
    if user_id not in carts:
        carts[user_id] = []
    carts[user_id].append(item.dict())
    return {"message": "Added", "cart": carts[user_id]}


@app.get("/cart/{user_id}")
async def get_cart(user_id: str):
    return {"cart": carts.get(user_id, [])}


@app.post("/checkout")
async def checkout(request: CheckoutRequest):
    """
    CRITICAL TEST CASE:
    Coupon "EXPIRED2026" MUST return 400 error.
    This is what the gauntlet validates.
    """
    EXPIRED_COUPONS = ["EXPIRED2026", "OLD_DEAL", "DEPRECATED"]
    
    # THE TEST - Expired coupon check
    if request.coupon_code and request.coupon_code in EXPIRED_COUPONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "COUPON_EXPIRED",
                "message": f"Coupon '{request.coupon_code}' has expired",
                "valid_coupons": ["SAVE10", "SUMMER2026"]
            }
        )
    
    # Valid checkout
    order_id = f"ORD-{random.randint(10000, 99999)}"
    
    return {
        "order_id": order_id,
        "status": "confirmed",
        "total": random.uniform(100, 500),
        "message": "Order placed successfully"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
