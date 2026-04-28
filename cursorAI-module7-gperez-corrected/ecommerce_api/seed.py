"""
Database seeder – run once after `flask db create` to populate
development data: admin/user accounts, sample products and discount codes.

Usage:
    python seed.py
"""
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models import User, Product, DiscountCode

app = create_app(os.environ.get("FLASK_ENV", "development"))


def seed():
    with app.app_context():
        db.create_all()

        # ── Users ──────────────────────────────────────────────────────────────
        if not User.query.filter_by(email=os.environ.get("ADMIN_EMAIL", "admin@example.com")).first():
            admin = User(email=os.environ.get("ADMIN_EMAIL", "admin@example.com"), role="admin")
            admin.set_password(os.environ.get("ADMIN_PASSWORD", "Admin1234!"))
            db.session.add(admin)
            print("✓ Admin user created")

        if not User.query.filter_by(email=os.environ.get("USER_EMAIL", "user@example.com")).first():
            user = User(email=os.environ.get("USER_EMAIL", "user@example.com"), role="user")
            user.set_password(os.environ.get("USER_PASSWORD", "User1234!"))
            db.session.add(user)
            print("✓ Regular user created")

        # ── Products ───────────────────────────────────────────────────────────
        sample_products = [
            {
                "name": "Wireless Headphones Pro",
                "description": "Premium noise-cancelling headphones with 30h battery life.",
                "price": 149.99,
                "stock": 50,
                "category": "Electronics",
                "rating": 4.5,
                "review_count": 312,
                "badge": "Best Seller",
            },
            {
                "name": "USB-C Hub 7-in-1",
                "description": "Expand your laptop ports with HDMI, USB-A, SD card and more.",
                "price": 49.99,
                "stock": 120,
                "category": "Electronics",
                "rating": 4.2,
                "review_count": 88,
            },
            {
                "name": "Leather Wallet",
                "description": "Slim genuine leather bifold wallet with RFID protection.",
                "price": 34.99,
                "stock": 200,
                "category": "Accessories",
                "rating": 4.7,
                "review_count": 540,
                "badge": "Top Rated",
            },
            {
                "name": "Running Shoes X200",
                "description": "Lightweight and responsive for daily runs and gym workouts.",
                "price": 89.99,
                "stock": 75,
                "category": "Footwear",
                "rating": 4.3,
                "review_count": 201,
            },
            {
                "name": "Ergonomic Office Chair",
                "description": "Adjustable lumbar support and armrests for long work days.",
                "price": 299.99,
                "stock": 20,
                "category": "Office",
                "rating": 4.6,
                "review_count": 95,
                "badge": "Premium",
            },
            {
                "name": "Mechanical Keyboard",
                "description": "Tactile clicky switches with RGB backlighting.",
                "price": 129.99,
                "stock": 60,
                "category": "Electronics",
                "rating": 4.4,
                "review_count": 178,
            },
        ]

        for p_data in sample_products:
            if not Product.query.filter_by(name=p_data["name"]).first():
                product = Product(**p_data)
                db.session.add(product)
        print(f"✓ {len(sample_products)} products seeded")

        # ── Discount Codes ─────────────────────────────────────────────────────
        discount_codes = [
            {
                "code": "SAVE10",
                "type": "percentage",
                "value": 10,
                "expires_at": None,
                "is_single_use": False,
            },
            {
                "code": "FLAT5",
                "type": "fixed",
                "value": 5,
                "expires_at": None,
                "is_single_use": False,
            },
            {
                "code": "NEWUSER",
                "type": "fixed",
                "value": 15,
                "expires_at": None,
                "is_single_use": True,
            },
            {
                "code": "TWENTY_OFF",
                "type": "fixed",
                "value": 20,
                "expires_at": None,
                "is_single_use": False,
            },
            {
                "code": "SUMMER21",
                "type": "percentage",
                "value": 20,
                "expires_at": datetime(2021, 9, 1),  # intentionally expired
                "is_single_use": False,
            },
        ]

        for dc_data in discount_codes:
            if not DiscountCode.query.filter_by(code=dc_data["code"]).first():
                dc = DiscountCode(**dc_data)
                db.session.add(dc)
        print(f"✓ {len(discount_codes)} discount codes seeded")

        db.session.commit()
        print("\n✅ Seed complete. Run the app with: python run.py")


if __name__ == "__main__":
    seed()
