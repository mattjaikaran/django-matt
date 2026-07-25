# file-length-max: 900
"""
Seed development database with realistic fake data.

Usage:
    python manage.py matt_seed myapp.Product --count 100
    python manage.py matt_seed myapp --count 50          # all models in app
    python manage.py matt_seed --all --count 20          # all models in all apps
    python manage.py matt_seed myapp.Product --count 100 --clear
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.core.management.base import CommandError
from django.db import models

from django_matt.cli import MattCommand

# field name heuristics for generating contextual data
_NAME_HEURISTICS: dict[str, str] = {
    "email": "email",
    "first_name": "first_name",
    "last_name": "last_name",
    "name": "name",
    "full_name": "name",
    "username": "username",
    "phone": "phone",
    "phone_number": "phone",
    "title": "sentence",
    "subject": "sentence",
    "headline": "sentence",
    "description": "paragraph",
    "bio": "paragraph",
    "about": "paragraph",
    "body": "paragraph",
    "content": "paragraph",
    "summary": "paragraph",
    "address": "address",
    "street": "address",
    "city": "city",
    "state": "state",
    "country": "country",
    "zip_code": "zipcode",
    "postal_code": "zipcode",
    "company": "company",
    "organization": "company",
    "website": "url",
    "url": "url",
    "link": "url",
    "image": "url",
    "avatar": "url",
    "price": "price",
    "cost": "price",
    "amount": "price",
}


def _generate_for_field(
    field: models.Field,
    model: type[models.Model],
    rng: random.Random,
) -> Any:
    """Generate a realistic value based on field type and name heuristics."""
    field_name = field.name.lower()

    # Check name heuristics first for CharFields/TextFields
    if isinstance(field, (models.CharField, models.TextField)):
        hint = _NAME_HEURISTICS.get(field_name)
        if hint:
            return _generate_from_hint(hint, field, rng)

    # EmailField
    if isinstance(field, models.EmailField):
        return _fake_email(rng)

    # URLField
    if isinstance(field, models.URLField):
        return _fake_url(rng)

    # SlugField
    if isinstance(field, models.SlugField):
        words = [_random_word(rng) for _ in range(rng.randint(1, 3))]
        slug = "-".join(words)
        max_len = getattr(field, "max_length", 50) or 50
        return slug[:max_len]

    # UUIDField
    if isinstance(field, models.UUIDField):
        return uuid.uuid4()

    # BooleanField
    if isinstance(field, models.BooleanField):
        return rng.choice([True, False])

    # IntegerField variants
    if isinstance(field, (models.SmallIntegerField,)):
        return rng.randint(0, 1000)
    if isinstance(field, (models.IntegerField, models.BigIntegerField)):
        return rng.randint(0, 10000)
    if isinstance(field, models.PositiveIntegerField):
        return rng.randint(0, 10000)
    if isinstance(field, models.PositiveSmallIntegerField):
        return rng.randint(0, 1000)

    # FloatField
    if isinstance(field, models.FloatField):
        return round(rng.uniform(0, 1000), 2)

    # DecimalField
    if isinstance(field, models.DecimalField):
        max_digits = field.max_digits or 10
        decimal_places = field.decimal_places or 2
        int_digits = max_digits - decimal_places
        max_val = 10**int_digits - 1
        val = rng.uniform(0, min(max_val, 99999))
        return Decimal(str(round(val, decimal_places)))

    # DateField
    if isinstance(field, models.DateField):
        today = date.today()
        delta = rng.randint(0, 365)
        return today - timedelta(days=delta)

    # DateTimeField
    if isinstance(field, models.DateTimeField):
        now = datetime.now(tz=UTC)
        delta = rng.randint(0, 365 * 24 * 3600)
        return now - timedelta(seconds=delta)

    # TimeField
    if isinstance(field, models.TimeField):
        from datetime import time

        return time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))

    # DurationField
    if isinstance(field, models.DurationField):
        return timedelta(seconds=rng.randint(60, 86400))

    # JSONField
    if isinstance(field, models.JSONField):
        return {
            "key": _random_word(rng),
            "value": rng.randint(1, 100),
            "tags": [_random_word(rng) for _ in range(rng.randint(1, 3))],
        }

    # IPAddressField / GenericIPAddressField
    if isinstance(field, (models.IPAddressField, models.GenericIPAddressField)):
        return f"{rng.randint(1, 254)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"

    # FileField / ImageField - leave blank
    if isinstance(field, (models.FileField, models.ImageField)):
        return ""

    # ForeignKey
    if isinstance(field, models.ForeignKey):
        related_model = field.related_model
        existing = related_model.objects.order_by("?").first()
        if existing:
            return existing
        # create one if none exist
        return _create_minimal_instance(related_model, rng)

    # TextField
    if isinstance(field, models.TextField):
        sentences = rng.randint(2, 5)
        return ". ".join(_fake_sentence(rng) for _ in range(sentences)) + "."

    # CharField (fallback)
    if isinstance(field, models.CharField):
        max_len = getattr(field, "max_length", 100) or 100
        word = _fake_sentence(rng)
        return word[:max_len]

    # BinaryField
    if isinstance(field, models.BinaryField):
        return rng.randbytes(32)

    return None


def _generate_from_hint(hint: str, field: models.Field, rng: random.Random) -> Any:
    """Generate data based on a name heuristic hint."""
    max_len = getattr(field, "max_length", 255) or 255
    generators = {
        "email": lambda: _fake_email(rng),
        "first_name": lambda: rng.choice(_FIRST_NAMES),
        "last_name": lambda: rng.choice(_LAST_NAMES),
        "name": lambda: f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
        "username": lambda: f"{rng.choice(_FIRST_NAMES).lower()}{rng.randint(1, 9999)}",
        "phone": lambda: f"+1{rng.randint(2000000000, 9999999999)}",
        "sentence": lambda: _fake_sentence(rng),
        "paragraph": lambda: ". ".join(_fake_sentence(rng) for _ in range(3)) + ".",
        "address": lambda: f"{rng.randint(1, 9999)} {rng.choice(_LAST_NAMES)} St",
        "city": lambda: rng.choice(_CITIES),
        "state": lambda: rng.choice(_STATES),
        "country": lambda: rng.choice(["US", "UK", "CA", "AU", "DE", "FR", "JP"]),
        "zipcode": lambda: f"{rng.randint(10000, 99999)}",
        "company": lambda: f"{rng.choice(_LAST_NAMES)} {rng.choice(['Inc', 'LLC', 'Corp', 'Co'])}",
        "url": lambda: _fake_url(rng),
        "price": lambda: str(round(rng.uniform(1, 999), 2)),
    }
    gen = generators.get(hint)
    if gen:
        val = gen()
        return str(val)[:max_len] if isinstance(val, str) else val
    return _random_word(rng)[:max_len]


def _create_minimal_instance(model: type[models.Model], rng: random.Random) -> models.Model:
    """Create a minimal instance of a model for FK references."""
    kwargs: dict[str, Any] = {}
    for field in model._meta.fields:
        if field.primary_key and field.has_default():
            continue
        if field.has_default() or field.null or field.blank:
            continue
        if isinstance(field, models.ForeignKey):
            # avoid infinite recursion - try to find existing
            related = field.related_model.objects.first()
            if related:
                kwargs[field.name] = related
            else:
                # skip - will fail if required but prevents infinite loop
                continue
        else:
            kwargs[field.name] = _generate_for_field(field, model, rng)
    return model.objects.create(**kwargs)


# --- Simple data lists ---

_FIRST_NAMES = [
    "James",
    "John",
    "Robert",
    "Michael",
    "William",
    "David",
    "Richard",
    "Mary",
    "Patricia",
    "Jennifer",
    "Linda",
    "Elizabeth",
    "Susan",
    "Jessica",
    "Sarah",
    "Karen",
    "Emily",
    "Emma",
    "Ashley",
    "Amanda",
    "Andrew",
    "Daniel",
]

_LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
]

_CITIES = [
    "New York",
    "Los Angeles",
    "Chicago",
    "Houston",
    "Phoenix",
    "San Francisco",
    "Seattle",
    "Boston",
    "Denver",
    "Austin",
    "Portland",
    "Miami",
    "Dallas",
]

_STATES = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI", "WA", "CO"]

_LOREM_WORDS = [
    "lorem",
    "ipsum",
    "dolor",
    "sit",
    "amet",
    "consectetur",
    "adipiscing",
    "elit",
    "sed",
    "do",
    "eiusmod",
    "tempor",
    "incididunt",
    "ut",
    "labore",
    "et",
    "dolore",
    "magna",
    "aliqua",
    "veniam",
    "quis",
    "nostrud",
    "nisi",
]

_DOMAIN_WORDS = [
    "alpha",
    "beta",
    "tech",
    "data",
    "cloud",
    "quantum",
    "pixel",
    "code",
    "dev",
    "apex",
    "prime",
    "nova",
    "nexus",
    "core",
]


def _random_word(rng: random.Random) -> str:
    return rng.choice(_LOREM_WORDS)


def _fake_sentence(rng: random.Random) -> str:
    words = [rng.choice(_LOREM_WORDS) for _ in range(rng.randint(4, 10))]
    words[0] = words[0].capitalize()
    return " ".join(words)


def _fake_email(rng: random.Random) -> str:
    first = rng.choice(_FIRST_NAMES).lower()
    last = rng.choice(_LAST_NAMES).lower()
    num = rng.randint(1, 999)
    domain = rng.choice(_DOMAIN_WORDS)
    tld = rng.choice(["com", "org", "net", "io"])
    return f"{first}.{last}{num}@{domain}.{tld}"


def _fake_url(rng: random.Random) -> str:
    domain = rng.choice(_DOMAIN_WORDS)
    tld = rng.choice(["com", "org", "io", "dev"])
    path = rng.choice(_LOREM_WORDS)
    return f"https://{domain}.{tld}/{path}"


@dataclass
class SeedFixture:
    """Definition of seed data for a model."""

    model: str
    count: int = 10
    fields: dict[str, Any] = dataclass_field(default_factory=dict)
    unique_fields: list[str] = dataclass_field(default_factory=list)
    dependencies: list[str] = dataclass_field(default_factory=list)


def _parse_fixture_file(path: str) -> list[SeedFixture]:
    """Parse a YAML or TOML seed fixture file."""
    from pathlib import Path as P

    filepath = P(path)

    if not filepath.exists():
        raise CommandError(f"Fixture file not found: {path}")

    text = filepath.read_text()

    if filepath.suffix in (".yml", ".yaml"):
        try:
            import yaml

            data = yaml.safe_load(text)
        except ImportError:
            raise CommandError("PyYAML required for YAML fixtures. Install with: uv add pyyaml")
    elif filepath.suffix == ".toml":
        import tomllib

        data = tomllib.loads(text)
    else:
        raise CommandError(f"Unsupported fixture format: {filepath.suffix}. Use .yaml or .toml")

    fixtures: list[SeedFixture] = []
    for item in data.get("fixtures", []):
        fixtures.append(
            SeedFixture(
                model=item["model"],
                count=item.get("count", 10),
                fields=item.get("fields", {}),
                unique_fields=item.get("unique_fields", []),
                dependencies=item.get("dependencies", []),
            )
        )

    return fixtures


def _resolve_fixture_value(
    value: Any,
    field_obj: models.Field,
    index: int,
    rng: random.Random,
) -> Any:
    """Resolve a fixture field value to an actual value."""
    if isinstance(value, list):
        return rng.choice(value)

    if isinstance(value, dict):
        if "min" in value and "max" in value:
            min_val, max_val = value["min"], value["max"]
            if isinstance(min_val, float) or isinstance(max_val, float):
                result = rng.uniform(float(min_val), float(max_val))
                if isinstance(field_obj, models.DecimalField):
                    places = field_obj.decimal_places or 2
                    return Decimal(str(round(result, places)))
                return round(result, 2)
            return rng.randint(int(min_val), int(max_val))
        return value

    if isinstance(value, str) and "{n}" in value:
        return value.replace("{n}", str(index + 1))

    return value


class Command(MattCommand):
    """Seed the development database with realistic fake data generated from model introspection."""

    help = "Seed development database with realistic fake data"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "target",
            nargs="?",
            help="Model (myapp.Product) or app (myapp) to seed",
        )
        parser.add_argument("--all", action="store_true", help="Seed all models in all apps")
        parser.add_argument(
            "--count", "-n", type=int, default=10, help="Number of records (default: 10)"
        )
        parser.add_argument("--clear", action="store_true", help="Delete existing records first")
        parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
        parser.add_argument(
            "--fixtures",
            "-f",
            help="Path to YAML/TOML fixture definition file",
        )

    def handle(self, *args, **options):
        target = options.get("target")
        seed_all = options.get("all")
        count = options["count"]
        clear = options["clear"]
        seed_val = options.get("seed")

        rng = random.Random(seed_val)

        fixtures_path = options.get("fixtures")
        if fixtures_path:
            return self._handle_fixtures(fixtures_path, count, clear, rng)

        if not target and not seed_all:
            raise CommandError("Provide a model/app target or use --all")

        # resolve target models
        target_models = self._resolve_targets(target, seed_all)

        if not target_models:
            raise CommandError("No models found for the given target")

        self.console.header("Database Seeder", f"{len(target_models)} model(s)")

        if clear:
            self.console.warning("Clearing existing data...")
            for model in reversed(target_models):
                deleted, _ = model.objects.all().delete()
                if deleted:
                    self.console.info(f"  Deleted {deleted} {model.__name__} records")

        results: list[dict[str, str]] = []

        for model in target_models:
            model_name = f"{model._meta.app_label}.{model.__name__}"
            self.console.section(model_name)

            # skip models with no concrete fields (proxy, abstract)
            if model._meta.proxy or model._meta.abstract:
                self.console.warning(f"  Skipping {model_name} (proxy/abstract)")
                continue

            # identify which fields we can auto-populate
            auto_fields = []
            skip_fields = set()
            for field in model._meta.fields:
                if field.primary_key and (
                    field.has_default() or isinstance(field, models.AutoField)
                ):
                    skip_fields.add(field.name)
                    continue
                if isinstance(field, models.AutoField):
                    skip_fields.add(field.name)
                    continue
                auto_fields.append(field)

            created = 0
            error_count = 0

            with self.console.progress(f"Seeding {model.__name__}...", total=count) as progress:
                task = progress.add_task(f"Creating {model.__name__}", total=count)

                batch: list[models.Model] = []
                for _ in range(count):
                    progress.advance(task)
                    kwargs: dict[str, Any] = {}

                    for field in auto_fields:
                        if field.has_default() and not isinstance(field, models.ForeignKey):
                            # let default kick in sometimes
                            if rng.random() < 0.3:
                                continue
                        if field.null and rng.random() < 0.1:
                            kwargs[field.name] = None
                            continue

                        try:
                            val = _generate_for_field(field, model, rng)
                            if val is not None:
                                if isinstance(field, models.ForeignKey):
                                    kwargs[f"{field.name}_id"] = (
                                        val.pk if isinstance(val, models.Model) else val
                                    )
                                else:
                                    kwargs[field.name] = val
                        except Exception:
                            # skip fields we can't generate
                            pass

                    try:
                        instance = model(**kwargs)
                        # can't bulk_create with FK instances easily, so use individual create
                        # for models with unique constraints we save individually to handle errors
                        instance.full_clean()
                        batch.append(instance)
                    except Exception as e:
                        error_count += 1
                        if error_count <= 3:
                            self.console.error(f"  Row error: {e}")

                # bulk create
                try:
                    model.objects.bulk_create(batch, ignore_conflicts=True)
                    created = len(batch)
                except Exception:
                    # fallback to individual creates
                    for instance in batch:
                        try:
                            instance.save()
                            created += 1
                        except Exception:
                            error_count += 1

            results.append(
                {
                    "Model": model_name,
                    "Created": str(created),
                    "Errors": str(error_count),
                }
            )

        # summary
        self.console.newline()
        self.console.section("Seed Summary")
        self.console.table(results)
        self.console.newline()
        self.console.success("Seeding complete")

    def _handle_fixtures(
        self,
        fixture_path: str,
        default_count: int,
        clear: bool,
        rng: random.Random,
    ) -> None:
        """Handle seeding from a fixture definition file."""
        fixtures = _parse_fixture_file(fixture_path)
        fixtures = self._sort_fixtures(fixtures)

        self.console.header("Database Seeder (Fixture Mode)", f"{len(fixtures)} fixture(s)")

        if clear:
            self.console.warning("Clearing existing data...")
            for fixture in reversed(fixtures):
                try:
                    app_label, model_name = fixture.model.rsplit(".", 1)
                    model = apps.get_model(app_label, model_name)
                    deleted, _ = model.objects.all().delete()
                    if deleted:
                        self.console.info(f"  Deleted {deleted} {model.__name__} records")
                except Exception as e:
                    self.console.error(f"  Error clearing {fixture.model}: {e}")

        results: list[dict[str, str]] = []

        for fixture in fixtures:
            app_label, model_name = fixture.model.rsplit(".", 1)
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.console.error(f"Model not found: {fixture.model}")
                continue

            self.console.section(fixture.model)
            count_to_create = fixture.count or default_count

            auto_fields = []
            for f in model._meta.fields:
                if f.primary_key and (f.has_default() or isinstance(f, models.AutoField)):
                    continue
                if isinstance(f, models.AutoField):
                    continue
                auto_fields.append(f)

            created = 0
            error_count = 0

            with self.console.progress(
                f"Seeding {model.__name__}...", total=count_to_create
            ) as progress:
                task = progress.add_task(f"Creating {model.__name__}", total=count_to_create)
                batch: list[models.Model] = []

                for i in range(count_to_create):
                    progress.advance(task)
                    kwargs: dict[str, Any] = {}

                    for f in auto_fields:
                        if f.name in fixture.fields:
                            try:
                                val = _resolve_fixture_value(fixture.fields[f.name], f, i, rng)
                                if isinstance(f, models.ForeignKey):
                                    kwargs[f"{f.name}_id"] = (
                                        val.pk if isinstance(val, models.Model) else val
                                    )
                                else:
                                    kwargs[f.name] = val
                                continue
                            except Exception:
                                pass

                        if f.has_default() and not isinstance(f, models.ForeignKey):
                            if rng.random() < 0.3:
                                continue
                        if f.null and rng.random() < 0.1:
                            kwargs[f.name] = None
                            continue

                        try:
                            val = _generate_for_field(f, model, rng)
                            if val is not None:
                                if isinstance(f, models.ForeignKey):
                                    kwargs[f"{f.name}_id"] = (
                                        val.pk if isinstance(val, models.Model) else val
                                    )
                                else:
                                    kwargs[f.name] = val
                        except Exception:
                            pass

                    try:
                        instance = model(**kwargs)
                        instance.full_clean()
                        batch.append(instance)
                    except Exception as e:
                        error_count += 1
                        if error_count <= 3:
                            self.console.error(f"  Row error: {e}")

                try:
                    model.objects.bulk_create(batch, ignore_conflicts=True)
                    created = len(batch)
                except Exception:
                    for instance in batch:
                        try:
                            instance.save()
                            created += 1
                        except Exception:
                            error_count += 1

            results.append(
                {
                    "Model": fixture.model,
                    "Created": str(created),
                    "Errors": str(error_count),
                }
            )

        self.console.newline()
        self.console.section("Seed Summary")
        self.console.table(results)
        self.console.newline()
        self.console.success("Seeding complete")

    @staticmethod
    def _sort_fixtures(fixtures: list[SeedFixture]) -> list[SeedFixture]:
        """Topological sort of fixtures by dependencies."""
        by_model = {f.model: f for f in fixtures}
        visited: set[str] = set()
        result: list[SeedFixture] = []

        def visit(model_name: str) -> None:
            if model_name in visited:
                return
            visited.add(model_name)
            fixture = by_model.get(model_name)
            if fixture:
                for dep in fixture.dependencies:
                    visit(dep)
                result.append(fixture)

        for f in fixtures:
            visit(f.model)

        return result

    def _load_fixture_file(self, path) -> dict[str, Any]:
        """Load fixture definitions from YAML or TOML."""
        suffix = path.suffix.lower()
        content = path.read_text()

        if suffix in (".yaml", ".yml"):
            try:
                import yaml

                data = yaml.safe_load(content)
            except ImportError:
                raise CommandError("PyYAML required for YAML fixtures: uv add pyyaml")
        elif suffix == ".toml":
            import tomllib

            data = tomllib.loads(content)
        elif suffix == ".json":
            import orjson

            data = orjson.loads(content.encode())
        else:
            raise CommandError(f"Unsupported fixture format: {suffix}. Use .yaml, .toml, or .json")

        return data.get("models", {})

    def _get_model(self, model_path: str) -> type[models.Model] | None:
        """Resolve a model path like 'myapp.User' to a model class."""
        if "." not in model_path:
            return None
        app_label, model_name = model_path.rsplit(".", 1)
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    def _resolve_fixture_order(self, definitions: dict[str, Any]) -> list[str]:
        """Topological sort of models based on depends_on."""
        ordered = []
        visited: set[str] = set()

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            defn = definitions.get(name, {})
            for dep in defn.get("depends_on", []):
                if dep in definitions:
                    visit(dep)
            ordered.append(name)

        for name in definitions:
            visit(name)

        return ordered

    def _resolve_field_value(self, spec: Any, index: int, rng: random.Random) -> Any:
        """Resolve a fixture field spec to a concrete value."""
        if isinstance(spec, bool):
            return spec

        if isinstance(spec, (int, float)):
            return spec

        if isinstance(spec, str):
            # Template substitution
            if "{n}" in spec:
                return spec.replace("{n}", str(index + 1))
            if "{" in spec and "}" in spec:
                # Simple template: {first_name}, {last_name}, etc.
                import re

                def replacer(m):
                    key = m.group(1)
                    gen = _NAME_HEURISTICS.get(key)
                    if gen:
                        return str(
                            _generate_from_hint(
                                gen,
                                type("F", (), {"max_length": 255})(),
                                rng,
                            )
                        )
                    return m.group(0)

                return re.sub(r"\{(\w+)\}", replacer, spec)
            return spec

        if isinstance(spec, list):
            if len(spec) == 2 and all(isinstance(x, (int, float)) for x in spec):
                # Range: [min, max]
                return round(rng.uniform(spec[0], spec[1]), 2)
            # Choice list
            return rng.choice(spec)

        return spec

    def _resolve_targets(self, target: str | None, seed_all: bool) -> list[type[models.Model]]:
        """Resolve target string to a list of model classes."""
        skip_apps = {"contenttypes", "sessions", "admin", "auth", "migrations"}

        if seed_all:
            return [m for m in apps.get_models() if m._meta.app_label not in skip_apps]

        if not target:
            return []

        # try as model first (app_label.ModelName)
        if "." in target:
            parts = target.rsplit(".", 1)
            try:
                return [apps.get_model(parts[0], parts[1])]
            except LookupError:
                raise CommandError(f"Model '{target}' not found.")

        # try as app
        try:
            app_config = apps.get_app_config(target)
            return list(app_config.get_models())
        except LookupError:
            raise CommandError(
                f"'{target}' is not a valid app or model. "
                "Use 'app_label.ModelName' for a model or 'app_label' for an app."
            )
