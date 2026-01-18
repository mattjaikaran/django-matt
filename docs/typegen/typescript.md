# TypeScript Generation

Generate TypeScript types from Django models and Pydantic schemas.

## Quick Start

```bash
python manage.py sync_types --target typescript --output frontend/types
```

## Generated Output

```typescript
// types.ts
export interface User {
  id: number
  email: string
  firstName: string
  lastName: string
  createdAt: string
}

// schemas.ts
export const userSchema = z.object({
  email: z.string().email(),
  firstName: z.string().min(1),
  lastName: z.string().min(1),
})

// api.ts
export const api = {
  users: {
    list: () => client.get<User[]>('/users/'),
    get: (id: number) => client.get<User>(`/users/${id}`),
    create: (data: UserCreate) => client.post<User>('/users/', data),
  },
}
```

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "TYPEGEN": {
        "OUTPUT_DIR": "frontend/src/generated",
        "INCLUDE_ZOD": True,
        "INCLUDE_API_CLIENT": True,
    },
}
```
