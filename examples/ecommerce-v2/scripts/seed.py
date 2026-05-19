#!/usr/bin/env python
"""Seed the ecommerce-v2 database with sample data."""
import os
import sys
import django

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from apps.catalog.models import Category, Product
from apps.stores.models import Store

User = get_user_model()


def seed():
    print("Seeding database...")

    # Admin user
    admin, created = User.objects.get_or_create(
        email="admin@example.com",
        defaults={"username": "admin", "is_staff": True, "is_superuser": True},
    )
    if created:
        admin.set_password("admin123")
        admin.save()
        print(f"  Created admin: admin@example.com / admin123")
    else:
        print(f"  Admin already exists")

    # Test user
    user, created = User.objects.get_or_create(
        email="user@example.com",
        defaults={"username": "testuser"},
    )
    if created:
        user.set_password("password123")
        user.save()
        print(f"  Created user: user@example.com / password123")

    # Store
    store, _ = Store.objects.get_or_create(
        slug="demo-store",
        defaults={
            "owner": admin,
            "name": "Demo Store",
            "description": "The best demo store on the internet.",
            "is_active": True,
        },
    )
    print(f"  Store: {store.name}")

    # Categories
    categories_data = [
        ("Electronics", "electronics", "Gadgets and tech"),
        ("Clothing", "clothing", "Apparel and accessories"),
        ("Books", "books", "Physical and digital books"),
        ("Home & Garden", "home-garden", "Everything for your home"),
    ]
    categories = {}
    for name, slug, desc in categories_data:
        cat, _ = Category.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": desc}
        )
        categories[slug] = cat
    print(f"  Categories: {len(categories)}")

    # Products
    products_data = [
        {
            "name": "Wireless Headphones",
            "slug": "wireless-headphones",
            "description": "Premium noise-cancelling wireless headphones with 30-hour battery life.",
            "price": "149.99",
            "compare_at_price": "199.99",
            "category": "electronics",
            "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400",
        },
        {
            "name": "Mechanical Keyboard",
            "slug": "mechanical-keyboard",
            "description": "TKL mechanical keyboard with Cherry MX switches and RGB backlight.",
            "price": "89.99",
            "compare_at_price": "119.99",
            "category": "electronics",
            "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400",
        },
        {
            "name": "USB-C Hub",
            "slug": "usb-c-hub",
            "description": "7-in-1 USB-C hub with HDMI, 4K support, 100W PD charging.",
            "price": "49.99",
            "category": "electronics",
            "image_url": "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400",
        },
        {
            "name": "Classic White T-Shirt",
            "slug": "classic-white-tshirt",
            "description": "100% organic cotton, relaxed fit, pre-shrunk.",
            "price": "24.99",
            "category": "clothing",
            "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400",
        },
        {
            "name": "Slim Fit Chinos",
            "slug": "slim-fit-chinos",
            "description": "Stretch twill chinos, slim fit, available in multiple colors.",
            "price": "59.99",
            "compare_at_price": "79.99",
            "category": "clothing",
            "image_url": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=400",
        },
        {
            "name": "Clean Code",
            "slug": "clean-code-book",
            "description": "A handbook of agile software craftsmanship by Robert C. Martin.",
            "price": "34.99",
            "category": "books",
            "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400",
        },
        {
            "name": "The Pragmatic Programmer",
            "slug": "pragmatic-programmer",
            "description": "Your journey to mastery, 20th Anniversary Edition.",
            "price": "39.99",
            "category": "books",
            "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=400",
        },
        {
            "name": "Ceramic Plant Pot",
            "slug": "ceramic-plant-pot",
            "description": "Minimalist ceramic pot with drainage hole, 6-inch diameter.",
            "price": "18.99",
            "category": "home-garden",
            "image_url": "https://images.unsplash.com/photo-1485955900006-10f4d324d411?w=400",
        },
        {
            "name": "Bamboo Cutting Board",
            "slug": "bamboo-cutting-board",
            "description": "Large bamboo cutting board with juice groove, 18x12 inches.",
            "price": "29.99",
            "compare_at_price": "39.99",
            "category": "home-garden",
            "image_url": "https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=400",
        },
        {
            "name": "Smart LED Bulb",
            "slug": "smart-led-bulb",
            "description": "WiFi-enabled dimmable LED bulb, 16 million colors, voice control.",
            "price": "14.99",
            "category": "electronics",
            "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400",
        },
    ]

    count = 0
    for data in products_data:
        cat_slug = data.pop("category")
        data["store"] = store
        data["category"] = categories[cat_slug]
        data["is_active"] = True
        Product.objects.get_or_create(slug=data["slug"], defaults=data)
        count += 1

    print(f"  Products: {count}")
    print("Done!")


if __name__ == "__main__":
    seed()
