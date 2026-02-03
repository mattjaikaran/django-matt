# GraphQL Quickstart

Get a fully functional GraphQL API running in 5 minutes.

## Prerequisites

Install strawberry-graphql:

```bash
pip install strawberry-graphql[django]
```

## Step 1: Define Your Models

```python
# myapp/models.py
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Book(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    published_at = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_published = models.BooleanField(default=False)
```

## Step 2: Auto-Generate Schema

The simplest approach - let Django Matt generate everything:

```python
# myapp/graphql.py
from django_matt.graphql import generate_schema
from .models import Author, Book

schema = generate_schema(
    models=[Author, Book],
    auto_mutations=True,
)
```

## Step 3: Add URL Route

```python
# myapp/urls.py
from django.urls import path
from django_matt.graphql import GraphQLView
from .graphql import schema

urlpatterns = [
    path("graphql/", GraphQLView.as_view(schema=schema)),
]
```

## Step 4: Test Your API

Start your Django server:

```bash
python manage.py runserver
```

Open `http://localhost:8000/graphql/` to access GraphiQL.

### Query Examples

**List all authors:**

```graphql
query {
  authors {
    id
    name
    email
  }
}
```

**Get a single book:**

```graphql
query {
  book(id: "1") {
    id
    title
    description
    author {
      name
    }
  }
}
```

**Filter and paginate:**

```graphql
query {
  books(
    filter: { is_published: true }
    orderBy: ["-published_at"]
    limit: 10
    offset: 0
  ) {
    id
    title
    publishedAt
  }
}
```

**Relay-style connection:**

```graphql
query {
  bookConnection(first: 10, after: "cursor123") {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      cursor
      node {
        id
        title
      }
    }
    totalCount
  }
}
```

### Mutation Examples

**Create an author:**

```graphql
mutation {
  createAuthor(input: {
    name: "Jane Doe"
    email: "jane@example.com"
  }) {
    id
    name
    email
  }
}
```

**Update a book:**

```graphql
mutation {
  updateBook(
    id: "1"
    input: {
      title: "Updated Title"
      isPublished: true
    }
  ) {
    id
    title
    isPublished
  }
}
```

**Delete a book:**

```graphql
mutation {
  deleteBook(id: "1") {
    success
    deletedId
    message
  }
}
```

## Complete Example

Here's a complete example with custom types:

=== "Basic (Auto-generated)"

    ```python
    # myapp/graphql.py
    from django_matt.graphql import generate_schema, GraphQLAPI
    from .models import Author, Book

    # Everything auto-generated
    schema = generate_schema(
        models=[Author, Book],
        auto_mutations=True,
    )

    graphql_api = GraphQLAPI(schema=schema)
    ```

=== "Custom Types"

    ```python
    # myapp/graphql.py
    from django_matt.graphql import (
        GraphQLSchema,
        create_type_from_model,
        create_input_from_model,
        graphql_type,
    )
    from .models import Author, Book

    # Create types with custom fields
    @graphql_type
    class AuthorType:
        id: int
        name: str
        email: str
        book_count: int

        @staticmethod
        def resolve_book_count(root, info) -> int:
            return root.books.count()

    BookType = create_type_from_model(
        Book,
        fields=["id", "title", "description", "price", "is_published"],
    )

    # Build schema
    schema_builder = GraphQLSchema()
    schema_builder.add_model(Author, type_class=AuthorType)
    schema_builder.add_model(Book, type_class=BookType)
    schema = schema_builder.build()
    ```

=== "Full Control"

    ```python
    # myapp/graphql.py
    import strawberry
    from django_matt.graphql import (
        create_type_from_model,
        QueryGenerator,
        MutationGenerator,
    )
    from .models import Author, Book

    AuthorType = create_type_from_model(Author)
    BookType = create_type_from_model(Book)

    author_queries = QueryGenerator(Author, AuthorType)
    book_queries = QueryGenerator(Book, BookType)
    book_mutations = MutationGenerator(Book, BookType)

    @strawberry.type
    class Query:
        # Generated queries
        authors = author_queries.list_query()
        author = author_queries.detail_query()
        books = book_queries.list_query()
        book = book_queries.detail_query()

        # Custom query
        @strawberry.field
        def featured_books(self) -> list[BookType]:
            return Book.objects.filter(
                is_published=True
            ).order_by("-published_at")[:5]

    @strawberry.type
    class Mutation:
        # Generated mutations
        create_book = book_mutations.create_mutation()
        update_book = book_mutations.update_mutation()
        delete_book = book_mutations.delete_mutation()

        # Custom mutation
        @strawberry.mutation
        def publish_book(self, id: strawberry.ID) -> BookType:
            book = Book.objects.get(id=id)
            book.is_published = True
            book.save()
            return BookType.from_orm(book)

    schema = strawberry.Schema(query=Query, mutation=Mutation)
    ```

## Adding to Existing MattAPI

If you already have a REST API with MattAPI:

```python
# myapp/api.py
from django_matt import MattAPI
from django_matt.graphql import GraphQLAPI, generate_schema
from .models import Author, Book

# Your existing REST API
api = MattAPI()

@api.get("/health")
def health(request):
    return {"status": "ok"}

# Add GraphQL
schema = generate_schema(models=[Author, Book])
api.add_graphql("/graphql", schema=schema)

# Or create separate GraphQL API
graphql = GraphQLAPI(schema=schema)
```

```python
# urls.py
from django.urls import path, include
from myapp.api import api, graphql

urlpatterns = [
    path("api/", api.urls),
    path("graphql/", include(graphql.urls)),
]
```

## Async Support

For better performance with async views:

```python
from django_matt.graphql import AsyncGraphQLView

urlpatterns = [
    path("graphql/", AsyncGraphQLView.as_view(schema=schema)),
]
```

Or with GraphQLAPI:

```python
graphql = GraphQLAPI(
    schema=schema,
    async_mode=True,
)
```

## Next Steps

Now that you have a working GraphQL API:

1. **Add Authentication** - [Authentication Guide](authentication.md)
2. **Optimize Queries** - [DataLoaders](dataloaders.md)
3. **Add Real-time** - [Subscriptions](subscriptions.md)
4. **Generate Clients** - [Code Generation](codegen.md)
5. **Secure Your API** - [Middleware](middleware.md)
