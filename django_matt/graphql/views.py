"""
GraphQL views for Django Matt.

Provides Django views for serving GraphQL endpoints.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.views import View
from django.views.decorators.csrf import csrf_exempt

try:
    import strawberry
    from strawberry.django.views import AsyncGraphQLView as StrawberryAsyncGraphQLView
    from strawberry.django.views import GraphQLView as StrawberryGraphQLView
    from strawberry.http import GraphQLHTTPResponse
    from strawberry.types import ExecutionResult

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    StrawberryGraphQLView = View
    StrawberryAsyncGraphQLView = View


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL views. "
            'Install it with: uv add "strawberry-graphql[django]"'
        )


class GraphQLView(StrawberryGraphQLView if STRAWBERRY_AVAILABLE else View):
    """
    Synchronous GraphQL view for Django.

    Usage:
        from django_matt.graphql import GraphQLView
        from django_matt.graphql.schema import generate_schema

        schema = generate_schema(models=[User, Post])

        urlpatterns = [
            path("graphql/", GraphQLView.as_view(schema=schema)),
        ]
    """

    def __init__(self, schema=None, graphiql: bool = True, **kwargs):
        _require_strawberry()

        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()

        if graphiql is None:
            graphiql = config.graphiql_enabled

        super().__init__(schema=schema, graphiql=graphiql, **kwargs)

    def get_context(self, request: HttpRequest, response: HttpResponse) -> dict:
        """
        Get the context for GraphQL execution.

        Override this to add custom context.
        """
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        context = {
            "request": request,
            "response": response,
        }

        # Add user if authenticated
        if hasattr(request, "user"):
            context["user"] = request.user

        # Add DataLoader registry
        context["dataloaders"] = DataLoaderRegistry()

        return context


class AsyncGraphQLView(StrawberryAsyncGraphQLView if STRAWBERRY_AVAILABLE else View):
    """
    Asynchronous GraphQL view for Django.

    Usage:
        from django_matt.graphql import AsyncGraphQLView
        from django_matt.graphql.schema import generate_schema

        schema = generate_schema(models=[User, Post])

        urlpatterns = [
            path("graphql/", AsyncGraphQLView.as_view(schema=schema)),
        ]
    """

    def __init__(self, schema=None, graphiql: bool = True, **kwargs):
        _require_strawberry()

        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()

        if graphiql is None:
            graphiql = config.graphiql_enabled

        super().__init__(schema=schema, graphiql=graphiql, **kwargs)

    async def get_context(self, request: HttpRequest, response: HttpResponse) -> dict:
        """
        Get the context for GraphQL execution.

        Override this to add custom context.
        """
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        context = {
            "request": request,
            "response": response,
        }

        # Add user if authenticated
        if hasattr(request, "user"):
            context["user"] = request.user

        # Add DataLoader registry
        context["dataloaders"] = DataLoaderRegistry()

        return context


class GraphQLAPI:
    """
    GraphQL API class for integration with MattAPI.

    Provides a high-level interface for adding GraphQL to your API.

    Usage:
        from django_matt import MattAPI
        from django_matt.graphql import GraphQLAPI, generate_schema

        api = MattAPI()
        schema = generate_schema(models=[User, Post])

        graphql = GraphQLAPI(schema=schema)
        api.add_graphql("/graphql", graphql)

        # Or create schema from models
        graphql = GraphQLAPI.from_models([User, Post])
        api.add_graphql("/graphql", graphql)
    """

    def __init__(
        self,
        schema=None,
        models: list | None = None,
        graphiql: bool = True,
        async_mode: bool = False,
        prefix: str = "/graphql",
        subscription_prefix: str = "/graphql/ws",
        csrf_exempt: bool = True,
    ):
        """
        Initialize the GraphQL API.

        Args:
            schema: Strawberry schema (optional if models provided)
            models: List of Django models (will auto-generate schema)
            graphiql: Enable GraphiQL interface
            async_mode: Use async views
            prefix: URL prefix for GraphQL endpoint
            subscription_prefix: URL prefix for WebSocket subscriptions
            csrf_exempt: Exempt from CSRF protection
        """
        _require_strawberry()

        self.graphiql = graphiql
        self.async_mode = async_mode
        self.prefix = prefix
        self.subscription_prefix = subscription_prefix
        self.csrf_exempt_enabled = csrf_exempt

        # Build schema if models provided
        if schema is None and models is not None:
            from django_matt.graphql.schema import generate_schema

            schema = generate_schema(models=models)

        self.schema = schema

    @classmethod
    def from_models(
        cls,
        models: list,
        auto_mutations: bool = True,
        auto_subscriptions: bool = False,
        **kwargs,
    ) -> GraphQLAPI:
        """
        Create a GraphQL API from Django models.

        Args:
            models: List of Django model classes
            auto_mutations: Generate CRUD mutations
            auto_subscriptions: Generate subscriptions
            **kwargs: Additional arguments for GraphQLAPI

        Returns:
            GraphQLAPI instance
        """
        _require_strawberry()
        from django_matt.graphql.schema import generate_schema

        schema = generate_schema(
            models=models,
            auto_mutations=auto_mutations,
            auto_subscriptions=auto_subscriptions,
        )

        return cls(schema=schema, **kwargs)

    def get_view(self) -> View:
        """
        Get the Django view for this GraphQL API.

        Returns:
            GraphQL view class
        """
        if self.async_mode:
            view_class = AsyncGraphQLView
        else:
            view_class = GraphQLView

        view = view_class.as_view(
            schema=self.schema,
            graphiql=self.graphiql,
        )

        if self.csrf_exempt_enabled:
            view = csrf_exempt(view)

        return view

    def get_urls(self) -> list:
        """
        Get URL patterns for the GraphQL API.

        Returns:
            List of URL patterns
        """
        patterns = []

        # Main GraphQL endpoint
        endpoint_path = self.prefix.lstrip("/")
        patterns.append(path(endpoint_path, self.get_view(), name="graphql"))

        # GraphQL endpoint with trailing slash
        if not endpoint_path.endswith("/"):
            patterns.append(path(f"{endpoint_path}/", self.get_view(), name="graphql-slash"))

        return patterns

    @property
    def urls(self) -> list:
        """URL patterns property for easy inclusion."""
        return self.get_urls()


def add_graphql_to_api(api, path: str = "/graphql", **kwargs) -> GraphQLAPI:
    """
    Add GraphQL to a MattAPI instance.

    This function patches the MattAPI class to support GraphQL.

    Usage:
        from django_matt import MattAPI
        from django_matt.graphql import add_graphql_to_api

        api = MattAPI()
        graphql = add_graphql_to_api(api, models=[User, Post])
    """
    _require_strawberry()

    graphql = GraphQLAPI(prefix=path, **kwargs)

    # Add the GraphQL URLs to the API
    original_get_urls = api.get_urls

    def patched_get_urls():
        urls = original_get_urls()
        urls.extend(graphql.get_urls())
        return urls

    api.get_urls = patched_get_urls

    # Store reference
    api._graphql = graphql

    return graphql


# Monkey-patch MattAPI to add add_graphql method
def _patch_matt_api():
    """Patch MattAPI to support GraphQL."""
    try:
        from django_matt.api import MattAPI

        def add_graphql(self, path: str = "/graphql", **kwargs) -> GraphQLAPI:
            """Add GraphQL endpoint to this API."""
            return add_graphql_to_api(self, path=path, **kwargs)

        if not hasattr(MattAPI, "add_graphql"):
            MattAPI.add_graphql = add_graphql
    except ImportError:
        pass


# Apply patch when module is imported
if STRAWBERRY_AVAILABLE:
    _patch_matt_api()


__all__ = [
    "GraphQLView",
    "AsyncGraphQLView",
    "GraphQLAPI",
    "add_graphql_to_api",
]
