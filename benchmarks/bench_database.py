#!/usr/bin/env python
"""
Database CRUD Benchmarks for Django Matt.

Tests performance of:
- INSERT operations
- SELECT (single and list)
- UPDATE operations
- DELETE operations
- Bulk operations

Uses in-memory SQLite for consistent benchmarking.

Usage:
    python benchmarks/bench_database.py
    python benchmarks/bench_database.py --iterations 500
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import (
    BenchmarkResult,
    print_environment,
    print_table,
    run_benchmark,
)


class DatabaseBenchmark:
    """Database benchmark runner with SQLite backend."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self._setup_database()

    def _setup_database(self):
        """Create test tables."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100),
                email VARCHAR(255),
                active BOOLEAN DEFAULT 1,
                score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON benchmark_test(email)")
        self.conn.commit()

    def cleanup(self):
        """Clean up test data."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM benchmark_test")
        self.conn.commit()

    def seed_data(self, count: int = 1000):
        """Seed test data."""
        cursor = self.conn.cursor()
        data = [(f"User {i}", f"user{i}@example.com", True, i * 1.5) for i in range(count)]
        cursor.executemany(
            "INSERT INTO benchmark_test (name, email, active, score) VALUES (?, ?, ?, ?)",
            data,
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()


def run_database_benchmarks(iterations: int = 500) -> list[BenchmarkResult]:
    """Run all database benchmarks."""
    results = []

    db = DatabaseBenchmark()

    try:
        # --- INSERT ---
        print("Benchmarking INSERT...")

        counter = [0]

        def insert_single():
            counter[0] += 1
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO benchmark_test (name, email, score) VALUES (?, ?, ?)",
                (f"User {counter[0]}", f"user{counter[0]}@example.com", counter[0] * 1.5),
            )
            db.conn.commit()

        results.append(
            run_benchmark(
                "INSERT (single row)",
                insert_single,
                iterations=iterations,
            )
        )

        # --- BULK INSERT ---
        print("Benchmarking BULK INSERT...")

        def bulk_insert():
            cursor = db.conn.cursor()
            data = [(f"Bulk {i}", f"bulk{i}@example.com", i * 1.0) for i in range(100)]
            cursor.executemany(
                "INSERT INTO benchmark_test (name, email, score) VALUES (?, ?, ?)",
                data,
            )
            db.conn.commit()

        results.append(
            run_benchmark(
                "INSERT (bulk 100 rows)",
                bulk_insert,
                iterations=iterations // 10,
            )
        )

        # Seed data for SELECT/UPDATE/DELETE benchmarks
        db.cleanup()
        db.seed_data(1000)

        # --- SELECT single ---
        print("Benchmarking SELECT...")

        def select_by_pk():
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM benchmark_test WHERE id = ?", (500,))
            return cursor.fetchone()

        results.append(
            run_benchmark(
                "SELECT (by primary key)",
                select_by_pk,
                iterations=iterations,
            )
        )

        # --- SELECT by index ---
        def select_by_email():
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM benchmark_test WHERE email = ?", ("user500@example.com",))
            return cursor.fetchone()

        results.append(
            run_benchmark(
                "SELECT (by indexed column)",
                select_by_email,
                iterations=iterations,
            )
        )

        # --- SELECT list ---
        def select_list():
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM benchmark_test LIMIT 20")
            return cursor.fetchall()

        results.append(
            run_benchmark(
                "SELECT (list with LIMIT 20)",
                select_list,
                iterations=iterations,
            )
        )

        # --- SELECT with filtering ---
        def select_filtered():
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT * FROM benchmark_test WHERE score > ? AND active = ? LIMIT 50",
                (500.0, True),
            )
            return cursor.fetchall()

        results.append(
            run_benchmark(
                "SELECT (filtered with LIMIT 50)",
                select_filtered,
                iterations=iterations,
            )
        )

        # --- SELECT count ---
        def select_count():
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM benchmark_test WHERE active = ?", (True,))
            return cursor.fetchone()

        results.append(
            run_benchmark(
                "SELECT COUNT(*)",
                select_count,
                iterations=iterations,
            )
        )

        # --- UPDATE ---
        print("Benchmarking UPDATE...")

        update_counter = [0]

        def update_single():
            update_counter[0] = (update_counter[0] % 1000) + 1
            cursor = db.conn.cursor()
            cursor.execute(
                "UPDATE benchmark_test SET name = ? WHERE id = ?",
                (f"Updated {update_counter[0]}", update_counter[0]),
            )
            db.conn.commit()

        results.append(
            run_benchmark(
                "UPDATE (single row by PK)",
                update_single,
                iterations=iterations,
            )
        )

        # --- UPDATE bulk ---
        def update_bulk():
            cursor = db.conn.cursor()
            cursor.execute("UPDATE benchmark_test SET score = score + 1 WHERE score < ?", (500.0,))
            db.conn.commit()

        results.append(
            run_benchmark(
                "UPDATE (bulk conditional)",
                update_bulk,
                iterations=iterations // 10,
            )
        )

        # --- DELETE ---
        print("Benchmarking DELETE...")

        # Prepare for delete benchmarks
        delete_id = [1001]

        def setup_delete():
            cursor = db.conn.cursor()
            cursor.execute(
                "INSERT INTO benchmark_test (id, name, email) VALUES (?, ?, ?)",
                (delete_id[0], f"Delete {delete_id[0]}", f"delete{delete_id[0]}@example.com"),
            )
            db.conn.commit()

        def delete_single():
            cursor = db.conn.cursor()
            cursor.execute("DELETE FROM benchmark_test WHERE id = ?", (delete_id[0],))
            db.conn.commit()
            delete_id[0] += 1

        # Custom benchmark with setup
        for _ in range(10):  # warmup
            setup_delete()
            delete_single()

        times = []
        import gc
        import time

        gc.collect()
        gc.disable()
        try:
            for _ in range(iterations):
                setup_delete()
                start = time.perf_counter()
                delete_single()
                end = time.perf_counter()
                times.append((end - start) * 1000)
        finally:
            gc.enable()

        import statistics

        results.append(
            BenchmarkResult(
                name="DELETE (single row by PK)",
                iterations=iterations,
                total_time_ms=sum(times),
                mean_time_ms=statistics.mean(times),
                median_time_ms=statistics.median(times),
                min_time_ms=min(times),
                max_time_ms=max(times),
                std_dev_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
                ops_per_second=1000 / statistics.mean(times),
            )
        )

        # --- Transaction benchmarks ---
        print("Benchmarking transactions...")

        def transaction_multiple_ops():
            cursor = db.conn.cursor()
            # Start transaction (implicit in SQLite)
            cursor.execute(
                "INSERT INTO benchmark_test (name, email) VALUES (?, ?)",
                ("Trans User", "trans@example.com"),
            )
            cursor.execute(
                "UPDATE benchmark_test SET score = 100 WHERE email = ?", ("trans@example.com",)
            )
            cursor.execute("SELECT * FROM benchmark_test WHERE email = ?", ("trans@example.com",))
            cursor.execute("DELETE FROM benchmark_test WHERE email = ?", ("trans@example.com",))
            db.conn.commit()

        results.append(
            run_benchmark(
                "Transaction (INSERT+UPDATE+SELECT+DELETE)",
                transaction_multiple_ops,
                iterations=iterations,
            )
        )

    finally:
        db.close()

    return results


def run_django_orm_benchmarks(iterations: int = 500) -> list[BenchmarkResult]:
    """Run Django ORM benchmarks if Django is available."""
    results = []

    try:
        import django
        from django.conf import settings

        if not settings.configured:
            settings.configure(
                DEBUG=False,
                DATABASES={
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": ":memory:",
                    }
                },
                INSTALLED_APPS=[
                    "django.contrib.contenttypes",
                ],
                DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            )
            django.setup()

        from django.db import connection

        # Create test table using raw SQL
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS django_benchmark_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100),
                    email VARCHAR(255)
                )
            """)

        print("\nBenchmarking Django ORM...")

        # Django raw cursor
        def django_raw_insert():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO django_benchmark_test (name, email) VALUES (?, ?)",
                    ("Django User", "django@example.com"),
                )

        results.append(
            run_benchmark(
                "Django raw cursor INSERT",
                django_raw_insert,
                iterations=iterations,
            )
        )

        def django_raw_select():
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM django_benchmark_test LIMIT 20")
                return cursor.fetchall()

        results.append(
            run_benchmark(
                "Django raw cursor SELECT",
                django_raw_select,
                iterations=iterations,
            )
        )

    except ImportError:
        print("\nDjango not installed, skipping ORM benchmarks...")
    except Exception as e:
        print(f"\nDjango ORM benchmarks failed: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Database CRUD benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=500,
        help="Number of iterations (default: 500)",
    )
    parser.add_argument(
        "--django",
        action="store_true",
        help="Include Django ORM benchmarks",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Database CRUD Benchmarks")
    print("=" * 70)

    print_environment()
    print("Using: SQLite in-memory database\n")

    results = run_database_benchmarks(iterations=args.iterations)

    if args.django:
        results.extend(run_django_orm_benchmarks(iterations=args.iterations))

    if results:
        print_table(results, "Database Operation Results")

        # Summary
        fastest = min(results, key=lambda r: r.mean_time_ms)
        print(f"Fastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")


if __name__ == "__main__":
    main()
