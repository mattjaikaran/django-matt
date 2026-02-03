# TypeScript Code Generation

Django Matt can generate TypeScript types, interfaces, and API clients from your GraphQL schema, ensuring type safety across your full stack.

## Overview

The code generation system produces:

- **TypeScript interfaces** for all GraphQL types
- **Input types** for mutations
- **Enum definitions** (as TS enums or union types)
- **Operation types** for queries and mutations
- **A typed GraphQL client** for making requests

## TypeScriptGenerator

The `TypeScriptGenerator` class converts your GraphQL schema to TypeScript:

```python
from django_matt.graphql import TypeScriptGenerator, generate_schema

# Generate schema from models
schema = generate_schema(models=[User, Post, Comment])

# Create generator
generator = TypeScriptGenerator(schema)

# Generate all TypeScript code
ts_code = generator.generate()
print(ts_code)
```

## Generating Types

### All Types

```python
from django_matt.graphql import generate_typescript_types

# Generate and save to file
generate_typescript_types(
    schema,
    output_path="frontend/src/types/graphql.ts",
)

# Or get as string
ts_code = generate_typescript_types(schema)
```

### Output Example

```typescript
// Auto-generated TypeScript types from GraphQL schema
// Do not edit manually

// Scalar types
export type Scalars = {
  ID: string;
  String: string;
  Boolean: boolean;
  Int: number;
  Float: number;
  DateTime: string;
  Date: string;
  JSON: Record<string, any>;
};

// Object Types
export interface UserType {
  __typename?: "UserType";
  id: number;
  email: string;
  username: string;
  firstName: string | null;
  lastName: string | null;
  createdAt: string;
}

export interface PostType {
  __typename?: "PostType";
  id: number;
  title: string;
  content: string;
  isPublished: boolean;
  publishedAt: string | null;
  author: UserType;
}

// Input Types
export interface CreatePostInput {
  title: string;
  content: string;
  isPublished?: boolean;
}

export interface UpdatePostInput {
  title?: string;
  content?: string;
  isPublished?: boolean;
}

// Enums
export enum PostStatus {
  DRAFT = "DRAFT",
  PUBLISHED = "PUBLISHED",
  ARCHIVED = "ARCHIVED",
}

// Operations
export interface QueryOperations {
  users: UserType[];
  user: UserType | null;
  posts: PostType[];
  post: PostType | null;
}

export interface MutationOperations {
  createPost: PostType;
  updatePost: PostType | null;
  deletePost: DeleteResult;
}
```

## Generator Options

```python
generator = TypeScriptGenerator(
    schema,
    export_style="named",      # "named" or "default"
    use_enums=True,            # True for enums, False for union types
    add_typename=True,         # Add __typename field
    nullable_style="union",    # "union" (T | null) or "optional" (T?)
)
```

### Export Styles

=== "Named Exports"

    ```typescript
    // export_style="named"
    export interface UserType {
      id: number;
      email: string;
    }

    export interface PostType {
      id: number;
      title: string;
    }
    ```

=== "No Exports"

    ```typescript
    // export_style="default"
    interface UserType {
      id: number;
      email: string;
    }

    interface PostType {
      id: number;
      title: string;
    }
    ```

### Enum Styles

=== "TypeScript Enums"

    ```typescript
    // use_enums=True
    export enum PostStatus {
      DRAFT = "DRAFT",
      PUBLISHED = "PUBLISHED",
      ARCHIVED = "ARCHIVED",
    }
    ```

=== "Union Types"

    ```typescript
    // use_enums=False
    export type PostStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
    ```

### Nullable Styles

=== "Union (Recommended)"

    ```typescript
    // nullable_style="union"
    export interface UserType {
      id: number;
      email: string;
      phone: string | null;  // Explicitly nullable
    }
    ```

=== "Optional"

    ```typescript
    // nullable_style="optional"
    export interface UserType {
      id: number;
      email: string;
      phone?: string;  // Optional field
    }
    ```

## Generating a Client

Generate a complete TypeScript GraphQL client:

```python
from django_matt.graphql import generate_typescript_client

generate_typescript_client(
    schema,
    output_path="frontend/src/api/client.ts",
    client_name="ApiClient",
    base_url="/graphql",
)
```

### Generated Client

```typescript
// GraphQL Client
// Auto-generated - do not edit manually

// ... types ...

export interface GraphQLError {
  message: string;
  locations?: { line: number; column: number }[];
  path?: (string | number)[];
  extensions?: Record<string, any>;
}

export interface GraphQLResponse<T> {
  data?: T;
  errors?: GraphQLError[];
}

export interface ApiClientOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
  credentials?: RequestCredentials;
}

export class ApiClient {
  private baseUrl: string;
  private headers: Record<string, string>;
  private credentials: RequestCredentials;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl || "/graphql";
    this.headers = {
      "Content-Type": "application/json",
      ...options.headers,
    };
    this.credentials = options.credentials || "same-origin";
  }

  setHeader(key: string, value: string): void {
    this.headers[key] = value;
  }

  setAuthToken(token: string): void {
    this.headers["Authorization"] = `Bearer ${token}`;
  }

  async query<T>(
    query: string,
    variables?: Record<string, any>,
    operationName?: string,
  ): Promise<GraphQLResponse<T>> {
    const response = await fetch(this.baseUrl, {
      method: "POST",
      headers: this.headers,
      credentials: this.credentials,
      body: JSON.stringify({
        query,
        variables,
        operationName,
      }),
    });

    return response.json();
  }

  async mutate<T>(
    mutation: string,
    variables?: Record<string, any>,
    operationName?: string,
  ): Promise<GraphQLResponse<T>> {
    return this.query<T>(mutation, variables, operationName);
  }
}

// Default client instance
export const graphqlClient = new ApiClient();
```

### Client Usage

```typescript
import { graphqlClient, UserType, PostType } from "./api/client";

// Set auth token after login
graphqlClient.setAuthToken(token);

// Query example
const { data, errors } = await graphqlClient.query<{ users: UserType[] }>(`
  query GetUsers {
    users {
      id
      email
      username
    }
  }
`);

if (data) {
  console.log(data.users);
}

// Mutation example
const { data: createData } = await graphqlClient.mutate<{ createPost: PostType }>(
  `
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        id
        title
        content
      }
    }
  `,
  {
    input: {
      title: "My New Post",
      content: "Hello, World!",
    },
  },
);
```

## Generating Operations

Generate typed GraphQL operation strings:

```python
from django_matt.graphql import generate_graphql_operations

generate_graphql_operations(
    schema,
    output_path="frontend/src/api/operations.ts",
)
```

### Generated Operations

```typescript
// GraphQL Operations
// Auto-generated - do not edit manually

// Queries
export const GetUsersQuery = `
  query GetUsers {
    users {
      ...UserTypeFields
    }
  }
`;

export const GetUserQuery = `
  query GetUser($id: ID!) {
    user(id: $id) {
      ...UserTypeFields
    }
  }
`;

export const GetPostsQuery = `
  query GetPosts {
    posts {
      ...PostTypeFields
    }
  }
`;

// Mutations
export const CreatePostMutation = `
  mutation CreatePost($input: CreatePostInput!) {
    createPost(input: $input) {
      ...PostTypeFields
    }
  }
`;

export const UpdatePostMutation = `
  mutation UpdatePost($id: ID!, $input: UpdatePostInput!) {
    updatePost(id: $id, input: $input) {
      ...PostTypeFields
    }
  }
`;

export const DeletePostMutation = `
  mutation DeletePost($id: ID!) {
    deletePost(id: $id) {
      ...DeleteResultFields
    }
  }
`;
```

## Integration with Build Tools

### Watch Mode with Django

Add a management command to regenerate types on model changes:

```python
# management/commands/generate_types.py
from django.core.management.base import BaseCommand
from django_matt.graphql import generate_typescript_client
from myapp.graphql import schema

class Command(BaseCommand):
    help = "Generate TypeScript types from GraphQL schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="frontend/src/types/graphql.ts",
            help="Output file path",
        )

    def handle(self, *args, **options):
        output = options["output"]
        generate_typescript_client(schema, output_path=output)
        self.stdout.write(
            self.style.SUCCESS(f"Generated TypeScript types at {output}")
        )
```

```bash
python manage.py generate_types
```

### With npm Scripts

```json
// package.json
{
  "scripts": {
    "codegen": "python ../manage.py generate_types --output src/types/graphql.ts",
    "codegen:watch": "nodemon --watch ../myapp/models.py --exec 'npm run codegen'"
  }
}
```

### With Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: graphql-codegen
        name: Generate GraphQL Types
        entry: python manage.py generate_types
        language: system
        pass_filenames: false
        files: ^myapp/models\.py$
```

## Using with Apollo Client

```typescript
import { ApolloClient, InMemoryCache, createHttpLink } from "@apollo/client";
import { setContext } from "@apollo/client/link/context";

// Import generated types
import { UserType, PostType, CreatePostInput } from "./types/graphql";

const httpLink = createHttpLink({
  uri: "/graphql",
});

const authLink = setContext((_, { headers }) => ({
  headers: {
    ...headers,
    authorization: localStorage.getItem("token")
      ? `Bearer ${localStorage.getItem("token")}`
      : "",
  },
}));

const client = new ApolloClient({
  link: authLink.concat(httpLink),
  cache: new InMemoryCache(),
});

// Typed query
const { data } = await client.query<{ users: UserType[] }>({
  query: gql`
    query GetUsers {
      users {
        id
        email
        username
      }
    }
  `,
});

// Typed mutation
const { data: mutationData } = await client.mutate<
  { createPost: PostType },
  { input: CreatePostInput }
>({
  mutation: gql`
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        id
        title
      }
    }
  `,
  variables: {
    input: {
      title: "New Post",
      content: "Content here",
    },
  },
});
```

## Using with React Query

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { graphqlClient, UserType, PostType, CreatePostInput } from "./api/client";

// Typed query hook
function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data, errors } = await graphqlClient.query<{ users: UserType[] }>(`
        query GetUsers {
          users {
            id
            email
            username
          }
        }
      `);

      if (errors) throw new Error(errors[0].message);
      return data!.users;
    },
  });
}

// Typed mutation hook
function useCreatePost() {
  return useMutation({
    mutationFn: async (input: CreatePostInput) => {
      const { data, errors } = await graphqlClient.mutate<{ createPost: PostType }>(
        `
          mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
              id
              title
              content
            }
          }
        `,
        { input },
      );

      if (errors) throw new Error(errors[0].message);
      return data!.createPost;
    },
  });
}

// Usage in component
function PostForm() {
  const createPost = useCreatePost();

  const handleSubmit = async (data: CreatePostInput) => {
    const newPost = await createPost.mutateAsync(data);
    console.log("Created:", newPost);
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

## Complete Example

```python
# scripts/generate_frontend_types.py
from django_matt.graphql import (
    generate_typescript_types,
    generate_typescript_client,
    generate_graphql_operations,
)
from myapp.graphql import schema

OUTPUT_DIR = "frontend/src/generated"

def main():
    # Generate types only
    generate_typescript_types(
        schema,
        output_path=f"{OUTPUT_DIR}/types.ts",
        use_enums=True,
        add_typename=True,
    )

    # Generate full client with types
    generate_typescript_client(
        schema,
        output_path=f"{OUTPUT_DIR}/client.ts",
        client_name="GraphQLClient",
        base_url="/api/graphql",
    )

    # Generate operation strings
    generate_graphql_operations(
        schema,
        output_path=f"{OUTPUT_DIR}/operations.ts",
    )

    print(f"Generated TypeScript files in {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
```

## Reference

### TypeScriptGenerator

```python
class TypeScriptGenerator:
    def __init__(
        self,
        schema: Schema,
        export_style: str = "named",    # "named" or "default"
        use_enums: bool = True,          # TS enums vs union types
        add_typename: bool = True,       # Include __typename
        nullable_style: str = "union",   # "union" or "optional"
    ):
        ...

    def generate(self) -> str:
        """Generate complete TypeScript code."""

    def generate_types(self) -> str:
        """Generate TypeScript interfaces for GraphQL types."""

    def generate_input_types(self) -> str:
        """Generate TypeScript interfaces for input types."""

    def generate_enums(self) -> str:
        """Generate TypeScript enums/unions."""

    def generate_operations(self) -> str:
        """Generate types for queries/mutations."""
```

### Helper Functions

```python
def generate_typescript_types(
    schema: Schema,
    output_path: str | None = None,
    **kwargs,  # TypeScriptGenerator options
) -> str:
    """Generate and optionally save TypeScript types."""

def generate_typescript_client(
    schema: Schema,
    output_path: str | None = None,
    client_name: str = "GraphQLClient",
    base_url: str = "/graphql",
) -> str:
    """Generate a complete TypeScript GraphQL client."""

def generate_graphql_operations(
    schema: Schema,
    output_path: str | None = None,
) -> str:
    """Generate GraphQL operation strings."""
```
