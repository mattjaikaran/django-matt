"""
GraphQL mutation generators for Django Matt.

Provides utilities for generating CRUD mutations from Django models.
"""

from __future__ import annotations

from typing import Any, TypeVar

from django.db import models, transaction

try:
    import strawberry
    from strawberry import UNSET
    from strawberry.types import Info
    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    UNSET = None
    Info = Any


T = TypeVar("T")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL mutations. "
            "Install it with: pip install strawberry-graphql[django]"
        )


if STRAWBERRY_AVAILABLE:
    @strawberry.type
    class MutationResult:
        """Generic mutation result type."""
        success: bool
        message: str | None = None
        errors: list[str] | None = None


    @strawberry.type
    class DeleteResult:
        """Result of a delete mutation."""
        success: bool
        deleted_id: strawberry.ID | None = None
        message: str | None = None


    @strawberry.type
    class BulkDeleteResult:
        """Result of a bulk delete mutation."""
        success: bool
        deleted_count: int = 0
        deleted_ids: list[strawberry.ID] | None = None
        message: str | None = None


class MutationGenerator:
    """
    Generate GraphQL mutations for a Django model.

    Usage:
        generator = MutationGenerator(User, UserType, CreateUserInput, UpdateUserInput)

        @strawberry.type
        class Mutation:
            create_user = generator.create_mutation()
            update_user = generator.update_mutation()
            delete_user = generator.delete_mutation()
    """

    def __init__(
        self,
        model: type[models.Model],
        type_class: type,
        create_input_class: type | None = None,
        update_input_class: type | None = None,
    ):
        """
        Initialize the mutation generator.

        Args:
            model: Django model class
            type_class: Strawberry type class for the model
            create_input_class: Input type for create mutations
            update_input_class: Input type for update mutations
        """
        _require_strawberry()
        self.model = model
        self.type_class = type_class
        self.create_input_class = create_input_class
        self.update_input_class = update_input_class

    def create_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        pre_save_hook: callable | None = None,
        post_save_hook: callable | None = None,
    ) -> strawberry.mutation:
        """
        Generate a create mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            pre_save_hook: Function called before saving (receives data dict)
            post_save_hook: Function called after saving (receives instance)

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        input_class = self.create_input_class

        if input_class is None:
            from django_matt.graphql.types import create_input_from_model
            input_class = create_input_from_model(model, name=f"Create{model.__name__}Input")

        def resolver(
            info: Info,
            input: input_class,
        ):
            # Convert input to dict
            data = {}
            for field_name, value in vars(input).items():
                if value is not UNSET and value is not None:
                    data[field_name] = value

            # Pre-save hook
            if pre_save_hook:
                data = pre_save_hook(info, data)

            # Create instance
            with transaction.atomic():
                instance = model.objects.create(**data)

            # Post-save hook
            if post_save_hook:
                post_save_hook(info, instance)

            # Convert to type
            if hasattr(type_class, "from_orm"):
                return type_class.from_orm(instance)
            return instance

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Create a new {model.__name__}",
            permission_classes=permission_classes or [],
        )

    def update_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
        pre_save_hook: callable | None = None,
        post_save_hook: callable | None = None,
    ) -> strawberry.mutation:
        """
        Generate an update mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            lookup_field: Field to look up by
            pre_save_hook: Function called before saving
            post_save_hook: Function called after saving

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        input_class = self.update_input_class

        if input_class is None:
            from django_matt.graphql.types import create_input_from_model
            input_class = create_input_from_model(
                model,
                name=f"Update{model.__name__}Input",
                optional_fields=[f.name for f in model._meta.fields],
            )

        def resolver(
            info: Info,
            id: strawberry.ID,
            input: input_class,
        ):
            try:
                instance = model.objects.get(**{lookup_field: id})
            except model.DoesNotExist:
                return None

            # Convert input to dict, only non-UNSET values
            data = {}
            for field_name, value in vars(input).items():
                if value is not UNSET:
                    data[field_name] = value

            # Pre-save hook
            if pre_save_hook:
                data = pre_save_hook(info, instance, data)

            # Update instance
            with transaction.atomic():
                for field_name, value in data.items():
                    setattr(instance, field_name, value)
                instance.save()

            # Post-save hook
            if post_save_hook:
                post_save_hook(info, instance)

            # Convert to type
            if hasattr(type_class, "from_orm"):
                return type_class.from_orm(instance)
            return instance

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Update an existing {model.__name__}",
            permission_classes=permission_classes or [],
        )

    def delete_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
        soft_delete: bool = False,
        soft_delete_field: str = "is_deleted",
        pre_delete_hook: callable | None = None,
        post_delete_hook: callable | None = None,
    ) -> strawberry.mutation:
        """
        Generate a delete mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            lookup_field: Field to look up by
            soft_delete: Use soft delete instead of hard delete
            soft_delete_field: Field to set for soft delete
            pre_delete_hook: Function called before deleting
            post_delete_hook: Function called after deleting

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model

        def resolver(
            info: Info,
            id: strawberry.ID,
        ) -> DeleteResult:
            try:
                instance = model.objects.get(**{lookup_field: id})
            except model.DoesNotExist:
                return DeleteResult(
                    success=False,
                    message=f"{model.__name__} not found",
                )

            # Pre-delete hook
            if pre_delete_hook:
                pre_delete_hook(info, instance)

            with transaction.atomic():
                if soft_delete:
                    setattr(instance, soft_delete_field, True)
                    instance.save()
                else:
                    instance.delete()

            # Post-delete hook
            if post_delete_hook:
                post_delete_hook(info, id)

            return DeleteResult(
                success=True,
                deleted_id=id,
                message=f"{model.__name__} deleted successfully",
            )

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Delete a {model.__name__}",
            permission_classes=permission_classes or [],
        )

    def bulk_create_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
    ) -> strawberry.mutation:
        """
        Generate a bulk create mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            max_items: Maximum number of items to create at once

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class
        input_class = self.create_input_class

        if input_class is None:
            from django_matt.graphql.types import create_input_from_model
            input_class = create_input_from_model(model, name=f"Create{model.__name__}Input")

        def resolver(
            info: Info,
            inputs: list[input_class],
        ) -> list:
            if len(inputs) > max_items:
                raise ValueError(f"Cannot create more than {max_items} items at once")

            instances = []
            with transaction.atomic():
                for input_data in inputs:
                    data = {}
                    for field_name, value in vars(input_data).items():
                        if value is not UNSET and value is not None:
                            data[field_name] = value
                    instances.append(model(**data))

                created = model.objects.bulk_create(instances)

            # Convert to types
            results = []
            for instance in created:
                if hasattr(type_class, "from_orm"):
                    results.append(type_class.from_orm(instance))
                else:
                    results.append(instance)
            return results

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Create multiple {model.__name__} objects",
            permission_classes=permission_classes or [],
        )

    def bulk_update_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
    ) -> strawberry.mutation:
        """
        Generate a bulk update mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            max_items: Maximum number of items to update at once

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class

        @strawberry.input
        class BulkUpdateInput:
            id: strawberry.ID
            data: dict[str, Any]

        def resolver(
            info: Info,
            inputs: list[BulkUpdateInput],
        ) -> list:
            if len(inputs) > max_items:
                raise ValueError(f"Cannot update more than {max_items} items at once")

            ids = [inp.id for inp in inputs]
            data_map = {inp.id: inp.data for inp in inputs}

            with transaction.atomic():
                instances = list(model.objects.filter(id__in=ids))
                for instance in instances:
                    data = data_map.get(str(instance.id), {})
                    for field_name, value in data.items():
                        setattr(instance, field_name, value)

                model.objects.bulk_update(
                    instances,
                    fields=list(set().union(*[d.keys() for d in data_map.values()])),
                )

            # Convert to types
            results = []
            for instance in instances:
                if hasattr(type_class, "from_orm"):
                    results.append(type_class.from_orm(instance))
                else:
                    results.append(instance)
            return results

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Update multiple {model.__name__} objects",
            permission_classes=permission_classes or [],
        )

    def bulk_delete_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
        soft_delete: bool = False,
        soft_delete_field: str = "is_deleted",
    ) -> strawberry.mutation:
        """
        Generate a bulk delete mutation.

        Args:
            name: Mutation field name
            description: Mutation description
            permission_classes: Permission classes to apply
            max_items: Maximum number of items to delete at once
            soft_delete: Use soft delete
            soft_delete_field: Field for soft delete

        Returns:
            Strawberry mutation descriptor
        """
        _require_strawberry()
        model = self.model

        def resolver(
            info: Info,
            ids: list[strawberry.ID],
        ) -> BulkDeleteResult:
            if len(ids) > max_items:
                raise ValueError(f"Cannot delete more than {max_items} items at once")

            with transaction.atomic():
                queryset = model.objects.filter(id__in=ids)
                count = queryset.count()

                if soft_delete:
                    queryset.update(**{soft_delete_field: True})
                else:
                    queryset.delete()

            return BulkDeleteResult(
                success=True,
                deleted_count=count,
                deleted_ids=ids,
                message=f"Deleted {count} {model.__name__} objects",
            )

        return strawberry.mutation(
            resolver,
            name=name,
            description=description or f"Delete multiple {model.__name__} objects",
            permission_classes=permission_classes or [],
        )


# Convenience functions
def generate_create_mutation(
    model: type[models.Model],
    type_class: type,
    input_class: type | None = None,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate a create mutation.
    """
    generator = MutationGenerator(model, type_class, create_input_class=input_class)
    return generator.create_mutation(**kwargs)


def generate_update_mutation(
    model: type[models.Model],
    type_class: type,
    input_class: type | None = None,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate an update mutation.
    """
    generator = MutationGenerator(model, type_class, update_input_class=input_class)
    return generator.update_mutation(**kwargs)


def generate_delete_mutation(
    model: type[models.Model],
    type_class: type,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate a delete mutation.
    """
    generator = MutationGenerator(model, type_class)
    return generator.delete_mutation(**kwargs)


def generate_bulk_create_mutation(
    model: type[models.Model],
    type_class: type,
    input_class: type | None = None,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate a bulk create mutation.
    """
    generator = MutationGenerator(model, type_class, create_input_class=input_class)
    return generator.bulk_create_mutation(**kwargs)


def generate_bulk_update_mutation(
    model: type[models.Model],
    type_class: type,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate a bulk update mutation.
    """
    generator = MutationGenerator(model, type_class)
    return generator.bulk_update_mutation(**kwargs)


def generate_bulk_delete_mutation(
    model: type[models.Model],
    type_class: type,
    **kwargs,
) -> strawberry.mutation:
    """
    Convenience function to generate a bulk delete mutation.
    """
    generator = MutationGenerator(model, type_class)
    return generator.bulk_delete_mutation(**kwargs)


__all__ = [
    "MutationGenerator",
    "MutationResult",
    "DeleteResult",
    "BulkDeleteResult",
    "generate_create_mutation",
    "generate_update_mutation",
    "generate_delete_mutation",
    "generate_bulk_create_mutation",
    "generate_bulk_update_mutation",
    "generate_bulk_delete_mutation",
]
