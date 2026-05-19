# Zod Schema Generation

Generate Zod validation schemas from Django models for client-side validation.

## Overview

Zod schemas provide:
- **Type inference** - TypeScript types from schemas
- **Runtime validation** - Validate data at runtime
- **Form integration** - Works with react-hook-form, Formik, etc.
- **Error messages** - Detailed validation errors

## Quick Start

### CLI Usage

```bash
# Generate Zod schemas only
python manage.py sync_types --target zod --output frontend/src/schemas/api.ts --apps myapp

# Generate Zod schemas as part of a full React output
python manage.py sync_types --target react --output frontend/src/generated
```

### Programmatic Usage

```python
from django_matt.codegen import generate_zod_schema
from myapp.models import User

# Generate Zod schema
zod_code = generate_zod_schema(User, "UserSchema")
print(zod_code)
```

## Generated Schemas

For a Django model:

```python
# models.py
class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ("electronics", "Electronics"),
            ("clothing", "Clothing"),
            ("books", "Books"),
        ]
    )
    sku = models.CharField(max_length=50, unique=True)
```

The generator produces:

```typescript
import { z } from "zod"

export const ProductSchema = z.object({
  id: z.number().int(),
  name: z.string().max(200),
  description: z.string().optional(),
  price: z.string(),  // Decimal as string for precision
  stock: z.number().int(),
  is_available: z.boolean(),
  category: z.enum(["electronics", "clothing", "books"]),
  sku: z.string().max(50),
})

export const ProductCreateSchema = z.object({
  name: z.string().max(200),
  description: z.string().optional(),
  price: z.string(),
  stock: z.number().int().optional(),
  is_available: z.boolean().optional(),
  category: z.enum(["electronics", "clothing", "books"]),
  sku: z.string().max(50),
})

export const ProductUpdateSchema = z.object({
  name: z.string().max(200).optional(),
  description: z.string().optional(),
  price: z.string().optional(),
  stock: z.number().int().optional(),
  is_available: z.boolean().optional(),
  category: z.enum(["electronics", "clothing", "books"]).optional(),
  sku: z.string().max(50).optional(),
})

// Inferred types
export type Product = z.infer<typeof ProductSchema>
export type ProductCreate = z.infer<typeof ProductCreateSchema>
export type ProductUpdate = z.infer<typeof ProductUpdateSchema>
```

## Django Field to Zod Mapping

| Django Field | Zod Schema | Notes |
|--------------|------------|-------|
| `AutoField` | `z.number().int()` | Auto-generated IDs |
| `IntegerField` | `z.number().int()` | Integer validation |
| `PositiveIntegerField` | `z.number().int().positive()` | Must be positive |
| `FloatField` | `z.number()` | Float/decimal |
| `DecimalField` | `z.string()` | String for precision |
| `CharField` | `z.string().max(N)` | With max length |
| `TextField` | `z.string()` | Unlimited text |
| `EmailField` | `z.string().email()` | Email validation |
| `URLField` | `z.string().url()` | URL validation |
| `UUIDField` | `z.string().uuid()` | UUID validation |
| `SlugField` | `z.string()` | Slug format |
| `BooleanField` | `z.boolean()` | Boolean |
| `DateField` | `z.string()` | ISO date string |
| `DateTimeField` | `z.string()` | ISO datetime string |
| `TimeField` | `z.string()` | Time string |
| `JSONField` | `z.record(z.unknown())` | JSON object |
| `IPAddressField` | `z.string().ip()` | IP validation |
| Choices field | `z.enum([...])` | Enum from choices |

## Using with react-hook-form

```tsx
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { ProductCreateSchema, ProductCreate } from "@/generated/schemas"
import { useCreateProduct } from "@/generated/hooks"

export function ProductForm() {
  const createProduct = useCreateProduct()

  const form = useForm<ProductCreate>({
    resolver: zodResolver(ProductCreateSchema),
    defaultValues: {
      name: "",
      description: "",
      price: "0.00",
      category: "electronics",
      is_available: true,
    },
  })

  const onSubmit = async (data: ProductCreate) => {
    try {
      await createProduct.mutateAsync(data)
      form.reset()
    } catch (error) {
      console.error(error)
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <input {...form.register("name")} />
      {form.formState.errors.name && (
        <span>{form.formState.errors.name.message}</span>
      )}

      <input {...form.register("price")} />
      {form.formState.errors.price && (
        <span>{form.formState.errors.price.message}</span>
      )}

      <select {...form.register("category")}>
        <option value="electronics">Electronics</option>
        <option value="clothing">Clothing</option>
        <option value="books">Books</option>
      </select>

      <button type="submit" disabled={createProduct.isPending}>
        Create Product
      </button>
    </form>
  )
}
```

## Nullable vs Optional

The generator handles nullable and optional fields differently:

```typescript
// Nullable field (null=True in Django)
bio: z.string().nullable()  // Can be null

// Optional field (blank=True or has default)
status: z.string().optional()  // Can be undefined

// Both nullable and optional
notes: z.string().nullable().optional()  // Can be null or undefined
```

## Custom Refinements

For complex validation, you can extend generated schemas:

```typescript
import { ProductCreateSchema } from "@/generated/schemas"

// Add custom validation
const ProductFormSchema = ProductCreateSchema.extend({
  price: z.string()
    .refine((val) => parseFloat(val) > 0, {
      message: "Price must be greater than 0",
    }),
  sku: z.string()
    .regex(/^[A-Z]{2}-\d{4}$/, {
      message: "SKU must be in format XX-0000",
    }),
})
```

## Pydantic to Zod

For Pydantic schemas (not Django models):

```python
from django_matt.typegen import generate_zod_schema
from myapp.schemas import UserSchema, PostSchema

# Generate from Pydantic schemas
zod_code = generate_zod_schema(
    schemas=[UserSchema, PostSchema],
    output_path="frontend/src/schemas.ts",
)
```

## Full Example

### Django Model

```python
# models.py
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
    ]

    customer_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Generated Zod Schema

```typescript
// schemas.ts
import { z } from "zod"

export const OrderSchema = z.object({
  id: z.number().int(),
  customer_email: z.string().email(),
  status: z.enum(["pending", "processing", "shipped", "delivered"]),
  total: z.string(),
  notes: z.string().nullable().optional(),
  created_at: z.string(),
})

export const OrderCreateSchema = z.object({
  customer_email: z.string().email(),
  status: z.enum(["pending", "processing", "shipped", "delivered"]).optional(),
  total: z.string(),
  notes: z.string().nullable().optional(),
})

export type Order = z.infer<typeof OrderSchema>
export type OrderCreate = z.infer<typeof OrderCreateSchema>
```

### Usage

```typescript
import { OrderCreateSchema, OrderCreate } from "@/generated/schemas"

// Validate data
function validateOrder(data: unknown): OrderCreate {
  return OrderCreateSchema.parse(data)
}

// Safe parse (doesn't throw)
function safeValidateOrder(data: unknown) {
  const result = OrderCreateSchema.safeParse(data)
  if (result.success) {
    return { data: result.data, errors: null }
  }
  return { data: null, errors: result.error.format() }
}
```

## Next Steps

- [React Hooks](./react-hooks.md) - TanStack Query hooks
- [React Components](./overview.md#react-generator) - Form and list components
- [Configuration](./overview.md#configuration) - Customizing generation
