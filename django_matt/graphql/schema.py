"""
GraphQL schema generation for Django Matt.

Provides automatic schema generation from Django models.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from django.db import models

try:
    import strawberry
    from strawberry import Schema
    from strawberry.types import Info
    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    Schema = object
    Info = Any


T = TypeVar("T")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL schema. "
            "Install it with: pip install strawberry-graphql[django]"
        )


class GraphQLSchema:
    """
    GraphQL schema builder for Django Matt.

    Usage:
        schema = GraphQLSchema()
        schema.add_model(User, UserType)
        schema.add_model(Post, PostType)

        strawberry_schema = schema.build()

        # Or use auto-generation
        schema = GraphQLSchema.from_models([User, Post, Comment])
    """

    def __init__(
        self,
        query_class: type | None = None,
        mutation_class: type | None = None,
        subscription_class: type | None = None,
        auto_generate_queries: bool = True,
        auto_generate_mutations: bool = True,
        auto_generate_subscriptions: bool = False,
    ):
        """
        Initialize the schema builder.

        Args:
            query_class: Custom Query class (will be merged with generated queries)
            mutation_class: Custom Mutation class
            subscription_class: Custom Subscription class
            auto_generate_queries: Auto-generate list/detail queries for models
            auto_generate_mutations: Auto-generate CRUD mutations for models
            auto_generate_subscriptions: Auto-generate subscriptions for models
        """
        _require_strawberry()

        self.query_class = query_class
        self.mutation_class = mutation_class
        self.subscription_class = subscription_class
        self.auto_generate_queries = auto_generate_queries
        self.auto_generate_mutations = auto_generate_mutations
        self.auto_generate_subscriptions = auto_generate_subscriptions

        # Registered models
        self._models: dict[type[models.Model], dict] = {}

        # Generated types
        self._types: dict[type[models.Model], type] = {}
        self._input_types: dict[str, type] = {}

        # Custom fields
        self._query_fields: dict[str, Any] = {}
        self._mutation_fields: dict[str, Any] = {}
        self._subscription_fields: dict[str, Any] = {}

    def add_model(
        self,
        model: type[models.Model],
        type_class: type | None = None,
        create_input_class: type | None = None,
        update_input_class: type | None = None,
        filter_class: type | None = None,
        permissions: list | None = None,
        include_queries: bool = True,
        include_mutations: bool = True,
        include_subscriptions: bool = False,
        soft_delete: bool = False,
    ) -> "GraphQLSchema":
        """
        Add a Django model to the schema.

        Args:
            model: Django model class
            type_class: Strawberry type class (auto-generated if None)
            create_input_class: Input type for create mutation
            update_input_class: Input type for update mutation
            filter_class: Filter input type
            permissions: Permission classes to apply
            include_queries: Generate queries for this model
            include_mutations: Generate mutations for this model
            include_subscriptions: Generate subscriptions for this model
            soft_delete: Use soft delete for delete mutations

        Returns:
            Self for chaining
        """
        _require_strawberry()

        # Generate type if not provided
        if type_class is None:
            from django_matt.graphql.types import create_type_from_model
            type_class = create_type_from_model(model)

        self._types[model] = type_class

        # Store model config
        self._models[model] = {
            "type_class": type_class,
            "create_input_class": create_input_class,
            "update_input_class": update_input_class,
            "filter_class": filter_class,
            "permissions": permissions or [],
            "include_queries": include_queries and self.auto_generate_queries,
            "include_mutations": include_mutations and self.auto_generate_mutations,
            "include_subscriptions": include_subscriptions or self.auto_generate_subscriptions,
            "soft_delete": soft_delete,
        }

        return self

    def add_query(self, name: str, resolver: Callable) -> "GraphQLSchema":
        """
        Add a custom query field.

        Args:
            name: Field name
            resolver: Resolver function (decorated with @strawberry.field)

        Returns:
            Self for chaining
        """
        self._query_fields[name] = resolver
        return self

    def add_mutation(self, name: str, resolver: Callable) -> "GraphQLSchema":
        """
        Add a custom mutation field.

        Args:
            name: Field name
            resolver: Resolver function (decorated with @strawberry.mutation)

        Returns:
            Self for chaining
        """
        self._mutation_fields[name] = resolver
        return self

    def add_subscription(self, name: str, resolver: Callable) -> "GraphQLSchema":
        """
        Add a custom subscription field.

        Args:
            name: Field name
            resolver: Resolver function (decorated with @strawberry.subscription)

        Returns:
            Self for chaining
        """
        self._subscription_fields[name] = resolver
        return self

    def build(self, extensions: list | None = None) -> Schema:
        """
        Build the Strawberry schema.

        Args:
            extensions: List of schema extensions

        Returns:
            Strawberry Schema instance
        """
        _require_strawberry()
        from django_matt.graphql.middleware import get_default_extensions

        # Generate query class
        query_class = self._build_query_class()

        # Generate mutation class
        mutation_class = self._build_mutation_class()

        # Generate subscription class
        subscription_class = self._build_subscription_class()

        # Get extensions
        if extensions is None:
            extensions = get_default_extensions()

        # Build schema
        schema_kwargs = {
            "query": query_class,
            "extensions": extensions,
        }

        if mutation_class is not None:
            schema_kwargs["mutation"] = mutation_class

        if subscription_class is not None:
            schema_kwargs["subscription"] = subscription_class

        return strawberry.Schema(**schema_kwargs)

    def _build_query_class(self) -> type:
        """Build the Query class."""
        from django_matt.graphql.queries import QueryGenerator

        # Start with base fields
        fields = dict(self._query_fields)

        # Generate model queries
        for model, config in self._models.items():
            if not config["include_queries"]:
                continue

            type_class = config["type_class"]
            permissions = config["permissions"]
            model_name = model.__name__

            generator = QueryGenerator(model, type_class)

            # List query
            list_name = f"{model_name.lower()}s"
            fields[list_name] = generator.list_query(
                permission_classes=permissions,
            )

            # Detail query
            detail_name = model_name.lower()
            fields[detail_name] = generator.detail_query(
                permission_classes=permissions,
            )

            # Connection query
            connection_name = f"{model_name.lower()}_connection"
            fields[connection_name] = generator.connection_query(
                permission_classes=permissions,
            )

        # Merge with custom query class if provided
        if self.query_class:
            for name, value in vars(self.query_class).items():
                if not name.startswith("_"):
                    fields[name] = value

        # Create the Query class dynamically
        Query = type("Query", (), {"__annotations__": {}, **fields})
        return strawberry.type(Query)

    def _build_mutation_class(self) -> type | None:
        """Build the Mutation class."""
        from django_matt.graphql.mutations import MutationGenerator

        # Start with base fields
        fields = dict(self._mutation_fields)

        # Generate model mutations
        for model, config in self._models.items():
            if not config["include_mutations"]:
                continue

            type_class = config["type_class"]
            permissions = config["permissions"]
            model_name = model.__name__

            generator = MutationGenerator(
                model,
                type_class,
                create_input_class=config["create_input_class"],
                update_input_class=config["update_input_class"],
            )

            # Create mutation
            create_name = f"create_{model_name.lower()}"
            fields[create_name] = generator.create_mutation(
                permission_classes=permissions,
            )

            # Update mutation
            update_name = f"update_{model_name.lower()}"
            fields[update_name] = generator.update_mutation(
                permission_classes=permissions,
            )

            # Delete mutation
            delete_name = f"delete_{model_name.lower()}"
            fields[delete_name] = generator.delete_mutation(
                permission_classes=permissions,
                soft_delete=config["soft_delete"],
            )

        # Merge with custom mutation class if provided
        if self.mutation_class:
            for name, value in vars(self.mutation_class).items():
                if not name.startswith("_"):
                    fields[name] = value

        if not fields:
            return None

        # Create the Mutation class dynamically
        Mutation = type("Mutation", (), {"__annotations__": {}, **fields})
        return strawberry.type(Mutation)

    def _build_subscription_class(self) -> type | None:
        """Build the Subscription class."""
        from django_matt.graphql.subscriptions import SubscriptionGenerator

        # Start with base fields
        fields = dict(self._subscription_fields)

        # Generate model subscriptions
        for model, config in self._models.items():
            if not config["include_subscriptions"]:
                continue

            type_class = config["type_class"]
            model_name = model.__name__

            generator = SubscriptionGenerator(model, type_class)

            # All events subscription
            events_name = f"{model_name.lower()}_events"
            fields[events_name] = generator.all_events_subscription()

        # Merge with custom subscription class if provided
        if self.subscription_class:
            for name, value in vars(self.subscription_class).items():
                if not name.startswith("_"):
                    fields[name] = value

        if not fields:
            return None

        # Create the Subscription class dynamically
        Subscription = type("Subscription", (), {"__annotations__": {}, **fields})
        return strawberry.type(Subscription)

    @classmethod
    def from_models(
        cls,
        models: list[type[models.Model]],
        **kwargs,
    ) -> Schema:
        """
        Create a schema from a list of Django models.

        Args:
            models: List of Django model classes
            **kwargs: Additional arguments for GraphQLSchema

        Returns:
            Strawberry Schema instance
        """
        _require_strawberry()
        schema_builder = cls(**kwargs)

        for model in models:
            schema_builder.add_model(model)

        return schema_builder.build()


def generate_schema(
    models: list[type[models.Model]],
    query: type | None = None,
    mutation: type | None = None,
    subscription: type | None = None,
    extensions: list | None = None,
    auto_mutations: bool = True,
    auto_subscriptions: bool = False,
) -> Schema:
    """
    Generate a GraphQL schema from Django models.

    This is a convenience function for quick schema generation.

    Args:
        models: List of Django model classes
        query: Optional custom Query class
        mutation: Optional custom Mutation class
        subscription: Optional custom Subscription class
        extensions: List of schema extensions
        auto_mutations: Auto-generate CRUD mutations
        auto_subscriptions: Auto-generate subscriptions

    Returns:
        Strawberry Schema instance

    Example:
        from django_matt.graphql import generate_schema

        schema = generate_schema(
            models=[User, Post, Comment],
            auto_mutations=True,
        )
    """
    _require_strawberry()

    builder = GraphQLSchema(
        query_class=query,
        mutation_class=mutation,
        subscription_class=subscription,
        auto_generate_mutations=auto_mutations,
        auto_generate_subscriptions=auto_subscriptions,
    )

    for model in models:
        builder.add_model(model)

    return builder.build(extensions=extensions)


def generate_queries(
    models: list[type[models.Model]],
) -> type:
    """
    Generate a Query class from Django models.

    Args:
        models: List of Django model classes

    Returns:
        Strawberry Query type class
    """
    _require_strawberry()
    builder = GraphQLSchema(auto_generate_mutations=False)

    for model in models:
        builder.add_model(model)

    return builder._build_query_class()


def generate_mutations(
    models: list[type[models.Model]],
) -> type:
    """
    Generate a Mutation class from Django models.

    Args:
        models: List of Django model classes

    Returns:
        Strawberry Mutation type class
    """
    _require_strawberry()
    builder = GraphQLSchema(auto_generate_queries=False)

    for model in models:
        builder.add_model(model)

    return builder._build_mutation_class()


__all__ = [
    "GraphQLSchema",
    "generate_schema",
    "generate_queries",
    "generate_mutations",
]
