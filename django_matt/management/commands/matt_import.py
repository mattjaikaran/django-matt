"""
Import model data from CSV, JSON, or JSONL files.

Usage:
    python manage.py matt_import myapp.Product data.csv --dry-run
    python manage.py matt_import myapp.Product data.json --update-existing --match-field sku
    python manage.py matt_import myapp.Product data.csv --create-only
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db import models

import orjson

from django_matt.cli import MattCommand


def _resolve_model(model_path: str) -> type[models.Model]:
    """Resolve 'app_label.ModelName' to a Django model class."""
    parts = model_path.rsplit(".", 1)
    if len(parts) != 2:
        raise CommandError(f"Invalid model path '{model_path}'. Use 'app_label.ModelName' format.")
    app_label, model_name = parts
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        raise CommandError(f"Model '{model_path}' not found.")


def _detect_format(file_path: Path) -> str:
    """Detect file format from extension."""
    ext = file_path.suffix.lower()
    mapping = {".csv": "csv", ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl"}
    fmt = mapping.get(ext)
    if not fmt:
        raise CommandError(f"Unsupported file extension '{ext}'. Use .csv, .json, or .jsonl")
    return fmt


def _read_csv(file_path: Path) -> list[dict[str, Any]]:
    """Read rows from a CSV file."""
    with open(file_path, newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _read_json(file_path: Path) -> list[dict[str, Any]]:
    """Read rows from a JSON file (expects array of objects)."""
    data = orjson.loads(file_path.read_bytes())
    if not isinstance(data, list):
        raise CommandError("JSON file must contain a top-level array of objects.")
    return data


def _read_jsonl(file_path: Path) -> list[dict[str, Any]]:
    """Read rows from a JSONL file."""
    rows = []
    for line in file_path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(orjson.loads(line))
    return rows


def _coerce_value(field: models.Field, value: Any) -> Any:
    """Coerce a raw string/value to the appropriate Python type for a field."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if field.null:
            return None
        if field.has_default():
            return field.default
        return value

    if isinstance(field, models.BooleanField):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    if isinstance(field, (models.IntegerField, models.BigIntegerField, models.SmallIntegerField)):
        return int(value)

    if isinstance(field, (models.FloatField,)):
        return float(value)

    if isinstance(field, models.DecimalField):
        from decimal import Decimal

        return Decimal(str(value))

    if isinstance(field, models.ForeignKey):
        # accept raw PK value
        pk_field = field.related_model._meta.pk
        return _coerce_value(pk_field, value)

    return value


class Command(MattCommand):
    """Import model data from CSV, JSON, or JSONL files with type coercion and validation."""

    help = "Import model data from CSV, JSON, or JSONL files"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("model", help="Model path (e.g. myapp.Product)")
        parser.add_argument("file", help="Input file path (.csv, .json, .jsonl)")
        parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing records instead of skipping",
        )
        parser.add_argument(
            "--match-field",
            default="pk",
            help="Field to match existing records (default: pk)",
        )
        parser.add_argument(
            "--create-only",
            action="store_true",
            help="Only create new records, skip existing",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Batch size for bulk operations (default: 500)",
        )

    def handle(self, *args, **options):
        """Import records from file into the specified model."""
        model = _resolve_model(options["model"])
        file_path = Path(options["file"])

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        fmt = _detect_format(file_path)
        dry_run = options["dry_run"]
        update_existing = options["update_existing"]
        create_only = options["create_only"]
        match_field = options["match_field"]
        batch_size = options["batch_size"]

        self.console.header(
            "Data Import",
            f"{file_path.name} -> {options['model']}" + (" [DRY RUN]" if dry_run else ""),
        )

        # read data
        readers = {"csv": _read_csv, "json": _read_json, "jsonl": _read_jsonl}
        rows = readers[fmt](file_path)
        self.console.info(f"Read {len(rows)} rows from {file_path.name}")

        if not rows:
            self.console.warning("No data to import")
            return

        # get valid field names from model
        valid_fields = {f.name for f in model._meta.fields}
        fk_fields = {f.name: f for f in model._meta.fields if isinstance(f, models.ForeignKey)}
        # also accept field_id for FK fields
        fk_id_map = {f"{name}_id": name for name in fk_fields}

        # process rows
        created = 0
        updated = 0
        skipped = 0
        errors: list[dict[str, Any]] = []
        to_create: list[models.Model] = []
        to_update: list[models.Model] = []
        update_fields: set[str] = set()

        with self.console.progress("Importing...", total=len(rows)) as progress:
            task = progress.add_task("Processing", total=len(rows))

            for row_num, raw_row in enumerate(rows, 1):
                progress.advance(task)

                # normalize field names (strip whitespace, handle _id suffix)
                row: dict[str, Any] = {}
                for key, val in raw_row.items():
                    key = key.strip()
                    if key in fk_id_map:
                        key = fk_id_map[key]
                    if key in valid_fields or key == "pk":
                        row[key] = val

                # coerce values
                try:
                    coerced: dict[str, Any] = {}
                    for key, val in row.items():
                        if key == "pk":
                            coerced["pk"] = val
                            continue
                        field = model._meta.get_field(key)
                        coerced[key] = _coerce_value(field, val)
                        # for FK, assign to field_id
                        if isinstance(field, models.ForeignKey):
                            coerced[f"{key}_id"] = coerced.pop(key)
                except (ValueError, TypeError) as e:
                    errors.append({"row": row_num, "error": str(e), "data": raw_row})
                    continue

                # check for existing record
                existing = None
                match_val = coerced.get(match_field, coerced.get(f"{match_field}_id"))
                if match_val is not None:
                    try:
                        lookup = {match_field: match_val}
                        existing = model.objects.filter(**lookup).first()
                    except Exception:
                        pass

                if existing:
                    if create_only:
                        skipped += 1
                        continue
                    if update_existing:
                        # update fields on existing instance
                        for key, val in coerced.items():
                            if key not in ("pk", match_field, f"{match_field}_id"):
                                setattr(existing, key, val)
                                update_fields.add(key)
                        # validate
                        try:
                            existing.full_clean()
                        except ValidationError as e:
                            errors.append({"row": row_num, "error": str(e), "data": raw_row})
                            continue
                        to_update.append(existing)
                        updated += 1
                    else:
                        skipped += 1
                else:
                    # build new instance
                    # strip pk if it's empty
                    create_kwargs = {k: v for k, v in coerced.items() if k != "pk" or v}
                    try:
                        instance = model(**create_kwargs)
                        instance.full_clean()
                    except (ValidationError, ValueError, TypeError) as e:
                        errors.append({"row": row_num, "error": str(e), "data": raw_row})
                        continue
                    to_create.append(instance)
                    created += 1

        # persist
        if not dry_run:
            if to_create:
                model.objects.bulk_create(to_create, batch_size=batch_size)
            if to_update and update_fields:
                model.objects.bulk_update(
                    to_update, fields=list(update_fields), batch_size=batch_size
                )

        # summary
        self.console.newline()
        self.console.section("Import Summary")
        summary = [
            {"Metric": "Created", "Count": str(created)},
            {"Metric": "Updated", "Count": str(updated)},
            {"Metric": "Skipped", "Count": str(skipped)},
            {"Metric": "Errors", "Count": str(len(errors))},
        ]
        self.console.table(summary)

        if errors:
            self.console.newline()
            self.console.section("Errors")
            for err in errors[:20]:
                self.console.error(f"Row {err['row']}: {err['error']}")
            if len(errors) > 20:
                self.console.warning(f"... and {len(errors) - 20} more errors")

        if dry_run:
            self.console.newline()
            self.console.warning("DRY RUN - no changes were saved")
        else:
            self.console.newline()
            self.console.success(f"Import complete: {created} created, {updated} updated")
