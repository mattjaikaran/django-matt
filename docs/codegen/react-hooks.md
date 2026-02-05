# React Query Hooks Generation

Generate type-safe TanStack Query (React Query) hooks from Django models.

## Overview

The React hooks generator creates fully typed hooks for:
- **List queries** - `useUsers()`, `useProducts()`, etc.
- **Detail queries** - `useUser(id)`, `useProduct(id)`, etc.
- **Create mutations** - `useCreateUser()`, etc.
- **Update mutations** - `useUpdateUser()`, etc.
- **Delete mutations** - `useDeleteUser()`, etc.

All hooks include:
- Proper query key management for cache invalidation
- TypeScript generics for type safety
- Error handling
- Loading states

## Quick Start

### CLI Usage

```bash
# Generate hooks for all models
python manage.py sync_types --target react --output frontend/src/generated

# Watch mode for development
python manage.py sync_types --target react --output frontend/src/generated --watch
```

### Programmatic Usage

```python
from django_matt.codegen import generate_react_hooks
from myapp.models import User

# Generate hooks for a single model
hooks_code = generate_react_hooks(User, api_base="/api/v1")

# Write to file
with open("frontend/src/hooks/useUsers.ts", "w") as f:
    f.write(hooks_code)
```

## Generated Code Example

For a `User` model, the generator produces:

```typescript
// Auto-generated from Django models
import { useQuery, useMutation, useQueryClient, UseQueryOptions } from "@tanstack/react-query"
import type { User, UserCreateInput, UserUpdateInput } from "./types"

const API_BASE = "/api"

// Query keys - for cache management
export const userKeys = {
  all: ["users"] as const,
  lists: () => [...userKeys.all, "list"] as const,
  list: (params: Record<string, unknown>) => [...userKeys.lists(), params] as const,
  details: () => [...userKeys.all, "detail"] as const,
  detail: (id: number | string) => [...userKeys.details(), id] as const,
}

// Fetch functions
async function fetchUsers(params?: Record<string, unknown>): Promise<User[]> {
  const url = new URL(`${API_BASE}/users/`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) url.searchParams.set(key, String(value))
    })
  }
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch users`)
  return res.json()
}

async function fetchUser(id: number | string): Promise<User> {
  const res = await fetch(`${API_BASE}/users/${id}/`)
  if (!res.ok) throw new Error(`User not found`)
  return res.json()
}

// List hook with optional filtering
export function useUsers(
  params?: Record<string, unknown>,
  options?: Omit<UseQueryOptions<User[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: userKeys.list(params ?? {}),
    queryFn: () => fetchUsers(params),
    ...options,
  })
}

// Detail hook
export function useUser(
  id: number | string,
  options?: Omit<UseQueryOptions<User>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
    enabled: !!id,
    ...options,
  })
}

// Create mutation with automatic cache invalidation
export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: UserCreateInput) => {
      const res = await fetch(`${API_BASE}/users/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!res.ok) throw new Error("Failed to create user")
      return res.json() as Promise<User>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
    },
  })
}

// Update mutation
export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: number | string; data: UserUpdateInput }) => {
      const res = await fetch(`${API_BASE}/users/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!res.ok) throw new Error("Failed to update user")
      return res.json() as Promise<User>
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: userKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
    },
  })
}

// Delete mutation
export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number | string) => {
      const res = await fetch(`${API_BASE}/users/${id}/`, {
        method: "DELETE",
      })
      if (!res.ok) throw new Error("Failed to delete user")
    },
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: userKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
    },
  })
}
```

## Usage in React Components

### List Component

```tsx
import { useUsers, useDeleteUser } from "@/generated/hooks"

export function UserList() {
  const { data: users, isLoading, error } = useUsers()
  const deleteUser = useDeleteUser()

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  return (
    <ul>
      {users?.map((user) => (
        <li key={user.id}>
          {user.email}
          <button onClick={() => deleteUser.mutate(user.id)}>
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
```

### Detail Component

```tsx
import { useUser } from "@/generated/hooks"

export function UserDetail({ id }: { id: number }) {
  const { data: user, isLoading, error } = useUser(id)

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  if (!user) return <div>User not found</div>

  return (
    <div>
      <h1>{user.name}</h1>
      <p>Email: {user.email}</p>
    </div>
  )
}
```

### Create Form

```tsx
import { useCreateUser } from "@/generated/hooks"
import { UserCreateInput } from "@/generated/types"

export function CreateUserForm() {
  const createUser = useCreateUser()

  const handleSubmit = async (data: UserCreateInput) => {
    try {
      const user = await createUser.mutateAsync(data)
      console.log("Created user:", user)
    } catch (error) {
      console.error("Failed to create user:", error)
    }
  }

  return (
    <form onSubmit={(e) => {
      e.preventDefault()
      const formData = new FormData(e.target as HTMLFormElement)
      handleSubmit({
        email: formData.get("email") as string,
        name: formData.get("name") as string,
      })
    }}>
      <input name="email" type="email" required />
      <input name="name" required />
      <button type="submit" disabled={createUser.isPending}>
        {createUser.isPending ? "Creating..." : "Create User"}
      </button>
    </form>
  )
}
```

## Configuration Options

### generate_react_hooks()

```python
from django_matt.codegen import generate_react_hooks

hooks_code = generate_react_hooks(
    model=User,                    # Django model class
    api_base="/api/v1",           # Base URL for API calls
    include_mutations=True,        # Include create/update/delete
)
```

### ReactGenerator

```python
from django_matt.codegen import ReactGenerator

generator = ReactGenerator(
    models=[User, Post, Comment],   # List of Django models
    output_dir="./frontend/src/generated",
    api_base="/api",
    ui_library="shadcn",            # UI library for components
)

files = generator.generate_all()
```

## Read-Only Hooks

For models that should only be read (not created/updated/deleted):

```python
hooks_code = generate_react_hooks(
    model=AuditLog,
    api_base="/api",
    include_mutations=False,  # No create/update/delete
)
```

## Query Key Patterns

The generated query keys follow a consistent pattern for cache management:

```typescript
// All users data
userKeys.all  // ["users"]

// All list queries
userKeys.lists()  // ["users", "list"]

// Specific list with params
userKeys.list({ active: true })  // ["users", "list", { active: true }]

// All detail queries
userKeys.details()  // ["users", "detail"]

// Specific detail
userKeys.detail(123)  // ["users", "detail", 123]
```

## Integrating with QueryClient

The hooks automatically invalidate related queries on mutations:

- **Create**: Invalidates all list queries
- **Update**: Invalidates the specific detail and all lists
- **Delete**: Removes the specific detail and invalidates all lists

## Next Steps

- [TypeScript Types](./overview.md#typescript-types) - Understanding generated types
- [Zod Schemas](./overview.md#zod-schemas) - Validation with Zod
- [React Components](./overview.md#react-generator) - Form and list components
