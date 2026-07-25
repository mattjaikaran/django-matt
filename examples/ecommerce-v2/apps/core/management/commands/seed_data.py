from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Inventory, Product, Variant
from apps.reviews.models import Review
from apps.stores.models import Store
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed the database with sample ecommerce data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Review.objects.all().delete()
            Inventory.objects.all().delete()
            Variant.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Store.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # Admin
        admin, _ = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "username": "admin",
                "password": make_password("admin123"),
                "is_staff": True,
                "is_superuser": True,
            },
        )

        # Vendors
        alice, _ = User.objects.get_or_create(
            email="alice@example.com",
            defaults={"username": "alice", "password": make_password("password123")},
        )
        bob, _ = User.objects.get_or_create(
            email="bob@example.com",
            defaults={"username": "bob", "password": make_password("password123")},
        )
        customer, _ = User.objects.get_or_create(
            email="customer@example.com",
            defaults={"username": "customer", "password": make_password("password123")},
        )

        # Stores
        alice_store, _ = Store.objects.get_or_create(
            slug="alice-electronics",
            defaults={"owner": alice, "name": "Alice's Electronics", "description": "Tech gear"},
        )
        bob_store, _ = Store.objects.get_or_create(
            slug="bob-books",
            defaults={"owner": bob, "name": "Bob's Books", "description": "Great reads"},
        )

        # Categories
        electronics, _ = Category.objects.get_or_create(
            slug="electronics", defaults={"name": "Electronics"}
        )
        phones, _ = Category.objects.get_or_create(
            slug="phones", defaults={"name": "Phones", "parent": electronics}
        )
        books, _ = Category.objects.get_or_create(slug="books", defaults={"name": "Books"})

        # Products
        products_data = [
            (alice_store, phones, "iPhone 15 Pro", "iphone-15-pro", Decimal("999.99")),
            (alice_store, electronics, "MacBook Air M3", "macbook-air-m3", Decimal("1299.99")),
            (alice_store, electronics, "AirPods Pro", "airpods-pro", Decimal("249.99")),
            (bob_store, books, "Django for Professionals", "django-pros", Decimal("39.99")),
            (bob_store, books, "Python Crash Course", "python-crash", Decimal("29.99")),
        ]
        for store, cat, name, slug, price in products_data:
            product, _ = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "store": store,
                    "category": cat,
                    "name": name,
                    "price": price,
                    "description": f"High quality {name.lower()}",
                },
            )
            # Default variant + inventory
            variant, _ = Variant.objects.get_or_create(
                product=product,
                sku=f"{slug}-default",
                defaults={"name": "Default"},
            )
            Inventory.objects.get_or_create(
                variant=variant,
                defaults={"quantity": 50},
            )

        # Sample reviews
        for product in Product.objects.all()[:3]:
            Review.objects.get_or_create(
                user=customer,
                product=product,
                defaults={
                    "rating": 5,
                    "title": f"Love the {product.name}!",
                    "body": "Exceeded my expectations.",
                },
            )

        self.stdout.write(self.style.SUCCESS("Seed data created!"))
        self.stdout.write(f"  Users: {User.objects.count()}")
        self.stdout.write(f"  Stores: {Store.objects.count()}")
        self.stdout.write(f"  Products: {Product.objects.count()}")
        self.stdout.write(f"  Reviews: {Review.objects.count()}")
