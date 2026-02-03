"""Management command to seed the database with sample data."""

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify


class Command(BaseCommand):
    """Seed the database with sample e-commerce data."""

    help = "Seed the database with sample products, categories, and users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )
        parser.add_argument(
            "--products",
            type=int,
            default=50,
            help="Number of products to create (default: 50)",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.clear_data()

        self.stdout.write("Seeding database...")

        # Create categories
        categories = self.create_categories()
        self.stdout.write(f"  Created {len(categories)} categories")

        # Create products
        products = self.create_products(categories, options["products"])
        self.stdout.write(f"  Created {len(products)} products")

        # Create coupons
        coupons = self.create_coupons()
        self.stdout.write(f"  Created {len(coupons)} coupons")

        # Create sample users
        users = self.create_users()
        self.stdout.write(f"  Created {len(users)} users")

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

    def clear_data(self):
        """Clear existing data."""
        from ecommerce.cart.models import Cart, CartItem
        from ecommerce.catalog.models import (
            Category,
            Inventory,
            Product,
            ProductImage,
            ProductVariant,
        )
        from ecommerce.orders.models import Coupon, Order, OrderItem
        from ecommerce.reviews.models import Review
        from ecommerce.users.models import Address, User, Wishlist

        self.stdout.write("Clearing existing data...")

        CartItem.objects.all().delete()
        Cart.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Review.objects.all().delete()
        Inventory.objects.all().delete()
        ProductVariant.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Coupon.objects.all().delete()
        Wishlist.objects.all().delete()
        Address.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def create_categories(self):
        """Create sample categories."""
        from ecommerce.catalog.models import Category

        categories_data = [
            {
                "name": "Electronics",
                "children": [
                    "Smartphones",
                    "Laptops",
                    "Tablets",
                    "Accessories",
                    "Wearables",
                ],
            },
            {
                "name": "Clothing",
                "children": [
                    "Men's Clothing",
                    "Women's Clothing",
                    "Kids' Clothing",
                    "Shoes",
                    "Accessories",
                ],
            },
            {
                "name": "Home & Garden",
                "children": [
                    "Furniture",
                    "Kitchen",
                    "Bedding",
                    "Decor",
                    "Garden",
                ],
            },
            {
                "name": "Sports & Outdoors",
                "children": [
                    "Fitness",
                    "Camping",
                    "Cycling",
                    "Water Sports",
                    "Team Sports",
                ],
            },
            {
                "name": "Books",
                "children": [
                    "Fiction",
                    "Non-Fiction",
                    "Children's Books",
                    "Textbooks",
                    "Comics",
                ],
            },
        ]

        categories = []
        for cat_data in categories_data:
            parent = Category.objects.create(
                name=cat_data["name"],
                slug=slugify(cat_data["name"]),
                description=f"Shop our {cat_data['name'].lower()} collection",
                is_active=True,
            )
            categories.append(parent)

            for child_name in cat_data["children"]:
                child = Category.objects.create(
                    name=child_name,
                    slug=slugify(f"{cat_data['name']}-{child_name}"),
                    parent=parent,
                    description=f"Browse {child_name.lower()}",
                    is_active=True,
                )
                categories.append(child)

        return categories

    def create_products(self, categories, count):
        """Create sample products."""
        from ecommerce.catalog.models import Inventory, Product, ProductVariant

        product_templates = [
            # Electronics
            {
                "name": "Wireless Bluetooth Headphones",
                "price": Decimal("79.99"),
                "compare_at": Decimal("99.99"),
                "desc": "Premium wireless headphones with noise cancellation",
            },
            {
                "name": "Smart Watch Pro",
                "price": Decimal("249.99"),
                "compare_at": None,
                "desc": "Advanced smartwatch with health monitoring",
            },
            {
                "name": "USB-C Hub Adapter",
                "price": Decimal("34.99"),
                "compare_at": Decimal("44.99"),
                "desc": "7-in-1 USB-C hub with HDMI and card reader",
            },
            {
                "name": "Mechanical Keyboard RGB",
                "price": Decimal("89.99"),
                "compare_at": None,
                "desc": "Gaming mechanical keyboard with RGB lighting",
            },
            {
                "name": "Wireless Mouse Ergonomic",
                "price": Decimal("29.99"),
                "compare_at": Decimal("39.99"),
                "desc": "Ergonomic wireless mouse with silent clicks",
            },
            # Clothing
            {
                "name": "Classic Cotton T-Shirt",
                "price": Decimal("24.99"),
                "compare_at": None,
                "desc": "Comfortable 100% cotton t-shirt",
            },
            {
                "name": "Slim Fit Jeans",
                "price": Decimal("59.99"),
                "compare_at": Decimal("79.99"),
                "desc": "Modern slim fit denim jeans",
            },
            {
                "name": "Running Sneakers",
                "price": Decimal("89.99"),
                "compare_at": None,
                "desc": "Lightweight running shoes with cushioning",
            },
            {
                "name": "Winter Jacket",
                "price": Decimal("149.99"),
                "compare_at": Decimal("199.99"),
                "desc": "Warm waterproof winter jacket",
            },
            {
                "name": "Leather Belt",
                "price": Decimal("34.99"),
                "compare_at": None,
                "desc": "Genuine leather belt with classic buckle",
            },
            # Home & Garden
            {
                "name": "Coffee Maker Deluxe",
                "price": Decimal("79.99"),
                "compare_at": Decimal("99.99"),
                "desc": "Programmable coffee maker with thermal carafe",
            },
            {
                "name": "Memory Foam Pillow",
                "price": Decimal("49.99"),
                "compare_at": None,
                "desc": "Cooling memory foam pillow for better sleep",
            },
            {
                "name": "LED Desk Lamp",
                "price": Decimal("39.99"),
                "compare_at": Decimal("54.99"),
                "desc": "Adjustable LED desk lamp with USB charging",
            },
            {
                "name": "Indoor Plant Pot Set",
                "price": Decimal("29.99"),
                "compare_at": None,
                "desc": "Set of 3 ceramic plant pots with drainage",
            },
            {
                "name": "Kitchen Knife Set",
                "price": Decimal("119.99"),
                "compare_at": Decimal("149.99"),
                "desc": "Professional 8-piece kitchen knife set",
            },
            # Sports & Outdoors
            {
                "name": "Yoga Mat Premium",
                "price": Decimal("34.99"),
                "compare_at": None,
                "desc": "Extra thick eco-friendly yoga mat",
            },
            {
                "name": "Camping Tent 4-Person",
                "price": Decimal("179.99"),
                "compare_at": Decimal("229.99"),
                "desc": "Waterproof 4-person camping tent",
            },
            {
                "name": "Water Bottle Insulated",
                "price": Decimal("24.99"),
                "compare_at": None,
                "desc": "32oz insulated stainless steel water bottle",
            },
            {
                "name": "Resistance Bands Set",
                "price": Decimal("19.99"),
                "compare_at": Decimal("29.99"),
                "desc": "Set of 5 resistance bands with handles",
            },
            {
                "name": "Bicycle Helmet",
                "price": Decimal("49.99"),
                "compare_at": None,
                "desc": "Lightweight ventilated bicycle helmet",
            },
        ]

        # Filter to leaf categories only
        leaf_categories = [c for c in categories if not c.get_children()]

        products = []
        for i in range(count):
            template = random.choice(product_templates)
            suffix = f" #{i + 1}" if i >= len(product_templates) else ""

            product = Product.objects.create(
                name=f"{template['name']}{suffix}",
                slug=slugify(f"{template['name']}{suffix}"),
                description=template["desc"],
                short_description=template["desc"][:100],
                price=template["price"],
                compare_at_price=template["compare_at"],
                cost_price=template["price"] * Decimal("0.5"),
                sku=f"SKU-{i + 1:05d}",
                barcode=f"123456789{i + 1:04d}",
                category=random.choice(leaf_categories),
                status="active",
                is_featured=random.random() < 0.2,  # 20% featured
                weight=Decimal(str(random.uniform(0.1, 5.0))),
                weight_unit="kg",
                attributes={
                    "color": random.choice(["Black", "White", "Blue", "Red", "Green"]),
                    "material": random.choice(["Plastic", "Metal", "Cotton", "Leather"]),
                },
                tags=random.sample(
                    ["bestseller", "new", "sale", "limited", "eco-friendly"],
                    k=random.randint(0, 2),
                ),
            )

            # Create inventory
            Inventory.objects.create(
                product=product,
                location="default",
                quantity=random.randint(0, 100),
                reserved_quantity=0,
                reorder_level=10,
                reorder_quantity=50,
            )

            # Create variants for some products
            if random.random() < 0.3:  # 30% have variants
                sizes = ["S", "M", "L", "XL"]
                for size in sizes:
                    variant = ProductVariant.objects.create(
                        product=product,
                        name=f"{product.name} - {size}",
                        sku=f"{product.sku}-{size}",
                        options={"size": size},
                        price=product.price + Decimal(str(random.randint(-10, 10))),
                        is_active=True,
                    )
                    Inventory.objects.create(
                        product=product,
                        variant=variant,
                        location="default",
                        quantity=random.randint(0, 50),
                        reserved_quantity=0,
                        reorder_level=5,
                        reorder_quantity=25,
                    )

            products.append(product)

        return products

    def create_coupons(self):
        """Create sample coupons."""
        from datetime import timedelta

        from django.utils import timezone

        from ecommerce.orders.models import Coupon

        coupons_data = [
            {
                "code": "WELCOME10",
                "description": "10% off your first order",
                "discount_type": "percentage",
                "discount_value": Decimal("10"),
                "minimum_purchase": Decimal("25"),
            },
            {
                "code": "SAVE20",
                "description": "$20 off orders over $100",
                "discount_type": "fixed",
                "discount_value": Decimal("20"),
                "minimum_purchase": Decimal("100"),
            },
            {
                "code": "FREESHIP",
                "description": "Free shipping on all orders",
                "discount_type": "free_shipping",
                "discount_value": Decimal("0"),
                "minimum_purchase": Decimal("0"),
            },
            {
                "code": "SUMMER25",
                "description": "25% off summer collection",
                "discount_type": "percentage",
                "discount_value": Decimal("25"),
                "minimum_purchase": Decimal("50"),
                "maximum_discount": Decimal("100"),
            },
            {
                "code": "FLASH50",
                "description": "50% off flash sale",
                "discount_type": "percentage",
                "discount_value": Decimal("50"),
                "minimum_purchase": Decimal("75"),
                "maximum_discount": Decimal("50"),
                "usage_limit": 100,
            },
        ]

        coupons = []
        for data in coupons_data:
            coupon = Coupon.objects.create(
                code=data["code"],
                description=data["description"],
                discount_type=data["discount_type"],
                discount_value=data["discount_value"],
                minimum_purchase=data["minimum_purchase"],
                maximum_discount=data.get("maximum_discount"),
                usage_limit=data.get("usage_limit"),
                valid_from=timezone.now(),
                valid_until=timezone.now() + timedelta(days=90),
                is_active=True,
            )
            coupons.append(coupon)

        return coupons

    def create_users(self):
        """Create sample users."""
        from ecommerce.users.models import Address, User

        users_data = [
            {
                "email": "customer@example.com",
                "password": "testpass123",
                "first_name": "John",
                "last_name": "Doe",
            },
            {
                "email": "jane@example.com",
                "password": "testpass123",
                "first_name": "Jane",
                "last_name": "Smith",
            },
            {
                "email": "bob@example.com",
                "password": "testpass123",
                "first_name": "Bob",
                "last_name": "Johnson",
            },
        ]

        users = []
        for data in users_data:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                },
            )
            if created:
                user.set_password(data["password"])
                user.save()

                # Create address
                Address.objects.create(
                    user=user,
                    address_type="both",
                    is_default=True,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    address_line_1="123 Main Street",
                    city="San Francisco",
                    state="CA",
                    postal_code="94102",
                    country="US",
                )

            users.append(user)

        return users
