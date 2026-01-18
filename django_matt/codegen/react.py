"""
React code generator.

Generates React components and TanStack Query hooks from Django models.

Usage:
    from django_matt.codegen.react import ReactGenerator
    from myapp.models import User

    # Generate hooks
    hooks_code = generate_react_hooks(User, api_base="/api")

    # Full generation
    gen = ReactGenerator([User, Post])
    gen.generate_all("./frontend/src/generated")
"""

from typing import Dict, List, Optional, Type

from django.db import models

from django_matt.codegen.core import (
    CodeFile,
    CodeGenerator,
    Comment,
    Import,
    ImportFrom,
    Function,
    Parameter,
    Statement,
    Return,
    Variable,
    ObjectLiteral,
)
from django_matt.codegen.introspection import (
    ModelIntrospector,
    ModelInfo,
    FieldInfo,
)


def _to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(x.title() for x in name.split("_"))


def _pluralize(name: str) -> str:
    """Simple pluralization."""
    if name.endswith("y"):
        return name[:-1] + "ies"
    elif name.endswith("s"):
        return name + "es"
    else:
        return name + "s"


def generate_react_hooks(
    model: Type[models.Model],
    api_base: str = "/api",
    include_mutations: bool = True,
) -> str:
    """
    Generate TanStack Query hooks for a Django model.

    Args:
        model: Django model class
        api_base: Base API URL
        include_mutations: Include create/update/delete mutations

    Returns:
        React hooks code
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = name.lower()
    name_plural = _pluralize(name_lower)

    lines = [
        f'// TanStack Query hooks for {name}',
        f'import {{ useQuery, useMutation, useQueryClient, UseQueryOptions }} from "@tanstack/react-query"',
        f'import type {{ {name}, {name}CreateInput, {name}UpdateInput }} from "./types"',
        '',
        f'const API_BASE = "{api_base}"',
        '',
        f'// Query keys',
        f'export const {name_lower}Keys = {{',
        f'  all: ["{name_plural}"] as const,',
        f'  lists: () => [...{name_lower}Keys.all, "list"] as const,',
        f'  list: (params: Record<string, unknown>) => [...{name_lower}Keys.lists(), params] as const,',
        f'  details: () => [...{name_lower}Keys.all, "detail"] as const,',
        f'  detail: (id: number | string) => [...{name_lower}Keys.details(), id] as const,',
        f'}}',
        '',
        f'// Fetch functions',
        f'async function fetch{name}s(params?: Record<string, unknown>): Promise<{name}[]> {{',
        f'  const url = new URL(`${{API_BASE}}/{name_plural}/`, window.location.origin)',
        f'  if (params) {{',
        f'    Object.entries(params).forEach(([key, value]) => {{',
        f'      if (value !== undefined) url.searchParams.set(key, String(value))',
        f'    }})',
        f'  }}',
        f'  const res = await fetch(url)',
        f'  if (!res.ok) throw new Error(`Failed to fetch {name_plural}`)',
        f'  return res.json()',
        f'}}',
        '',
        f'async function fetch{name}(id: number | string): Promise<{name}> {{',
        f'  const res = await fetch(`${{API_BASE}}/{name_plural}/${{id}}/`)',
        f'  if (!res.ok) throw new Error(`{name} not found`)',
        f'  return res.json()',
        f'}}',
        '',
        f'// List hook',
        f'export function use{name}s(',
        f'  params?: Record<string, unknown>,',
        f'  options?: Omit<UseQueryOptions<{name}[]>, "queryKey" | "queryFn">',
        f') {{',
        f'  return useQuery({{',
        f'    queryKey: {name_lower}Keys.list(params ?? {{}}),',
        f'    queryFn: () => fetch{name}s(params),',
        f'    ...options,',
        f'  }})',
        f'}}',
        '',
        f'// Detail hook',
        f'export function use{name}(',
        f'  id: number | string,',
        f'  options?: Omit<UseQueryOptions<{name}>, "queryKey" | "queryFn">',
        f') {{',
        f'  return useQuery({{',
        f'    queryKey: {name_lower}Keys.detail(id),',
        f'    queryFn: () => fetch{name}(id),',
        f'    enabled: !!id,',
        f'    ...options,',
        f'  }})',
        f'}}',
    ]

    if include_mutations:
        lines.extend([
            '',
            f'// Create mutation',
            f'export function useCreate{name}() {{',
            f'  const queryClient = useQueryClient()',
            f'  return useMutation({{',
            f'    mutationFn: async (data: {name}CreateInput) => {{',
            f'      const res = await fetch(`${{API_BASE}}/{name_plural}/`, {{',
            f'        method: "POST",',
            f'        headers: {{ "Content-Type": "application/json" }},',
            f'        body: JSON.stringify(data),',
            f'      }})',
            f'      if (!res.ok) throw new Error("Failed to create {name_lower}")',
            f'      return res.json() as Promise<{name}>',
            f'    }},',
            f'    onSuccess: () => {{',
            f'      queryClient.invalidateQueries({{ queryKey: {name_lower}Keys.lists() }})',
            f'    }},',
            f'  }})',
            f'}}',
            '',
            f'// Update mutation',
            f'export function useUpdate{name}() {{',
            f'  const queryClient = useQueryClient()',
            f'  return useMutation({{',
            f'    mutationFn: async ({{ id, data }}: {{ id: number | string; data: {name}UpdateInput }}) => {{',
            f'      const res = await fetch(`${{API_BASE}}/{name_plural}/${{id}}/`, {{',
            f'        method: "PATCH",',
            f'        headers: {{ "Content-Type": "application/json" }},',
            f'        body: JSON.stringify(data),',
            f'      }})',
            f'      if (!res.ok) throw new Error("Failed to update {name_lower}")',
            f'      return res.json() as Promise<{name}>',
            f'    }},',
            f'    onSuccess: (data, variables) => {{',
            f'      queryClient.invalidateQueries({{ queryKey: {name_lower}Keys.detail(variables.id) }})',
            f'      queryClient.invalidateQueries({{ queryKey: {name_lower}Keys.lists() }})',
            f'    }},',
            f'  }})',
            f'}}',
            '',
            f'// Delete mutation',
            f'export function useDelete{name}() {{',
            f'  const queryClient = useQueryClient()',
            f'  return useMutation({{',
            f'    mutationFn: async (id: number | string) => {{',
            f'      const res = await fetch(`${{API_BASE}}/{name_plural}/${{id}}/`, {{',
            f'        method: "DELETE",',
            f'      }})',
            f'      if (!res.ok) throw new Error("Failed to delete {name_lower}")',
            f'    }},',
            f'    onSuccess: (_, id) => {{',
            f'      queryClient.removeQueries({{ queryKey: {name_lower}Keys.detail(id) }})',
            f'      queryClient.invalidateQueries({{ queryKey: {name_lower}Keys.lists() }})',
            f'    }},',
            f'  }})',
            f'}}',
        ])

    return "\n".join(lines)


def generate_react_form(
    model: Type[models.Model],
    ui_library: str = "shadcn",
) -> str:
    """
    Generate a React form component for a Django model.

    Args:
        model: Django model class
        ui_library: UI library to use ("shadcn", "tailwind", "none")

    Returns:
        React form component code
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = name.lower()

    # Get editable fields
    editable_fields = [f for f in info.fields if f.is_editable and not f.is_auto and not f.is_primary_key]

    lines = [
        f'"use client"',
        '',
        f'import {{ useForm }} from "react-hook-form"',
        f'import {{ zodResolver }} from "@hookform/resolvers/zod"',
        f'import {{ {name}CreateSchema, type {name}CreateInput }} from "./schemas"',
        f'import {{ useCreate{name} }} from "./hooks"',
        '',
    ]

    if ui_library == "shadcn":
        lines.extend([
            'import { Button } from "@/components/ui/button"',
            'import { Input } from "@/components/ui/input"',
            'import { Textarea } from "@/components/ui/textarea"',
            'import { Checkbox } from "@/components/ui/checkbox"',
            'import {',
            '  Form,',
            '  FormControl,',
            '  FormDescription,',
            '  FormField,',
            '  FormItem,',
            '  FormLabel,',
            '  FormMessage,',
            '} from "@/components/ui/form"',
            '',
        ])

    lines.extend([
        f'interface {name}FormProps {{',
        f'  onSuccess?: (data: {name}CreateInput) => void',
        f'  defaultValues?: Partial<{name}CreateInput>',
        f'}}',
        '',
        f'export function {name}Form({{ onSuccess, defaultValues }}: {name}FormProps) {{',
        f'  const create{name} = useCreate{name}()',
        '',
        f'  const form = useForm<{name}CreateInput>({{',
        f'    resolver: zodResolver({name}CreateSchema),',
        f'    defaultValues: defaultValues ?? {{}},',
        f'  }})',
        '',
        f'  async function onSubmit(data: {name}CreateInput) {{',
        f'    try {{',
        f'      await create{name}.mutateAsync(data)',
        f'      onSuccess?.(data)',
        f'      form.reset()',
        f'    }} catch (error) {{',
        f'      console.error("Failed to create {name_lower}:", error)',
        f'    }}',
        f'  }}',
        '',
        f'  return (',
        f'    <Form {{...form}}>',
        f'      <form onSubmit={{form.handleSubmit(onSubmit)}} className="space-y-4">',
    ])

    # Generate form fields
    for field in editable_fields:
        field_name = field.name
        label = field.verbose_name.title()

        if field.field_type == "BooleanField":
            lines.extend([
                f'        <FormField',
                f'          control={{form.control}}',
                f'          name="{field_name}"',
                f'          render={{({{ field }}) => (',
                f'            <FormItem className="flex flex-row items-start space-x-3 space-y-0">',
                f'              <FormControl>',
                f'                <Checkbox checked={{field.value}} onCheckedChange={{field.onChange}} />',
                f'              </FormControl>',
                f'              <div className="space-y-1 leading-none">',
                f'                <FormLabel>{label}</FormLabel>',
                f'                {f"<FormDescription>{field.help_text}</FormDescription>" if field.help_text else ""}',
                f'              </div>',
                f'            </FormItem>',
                f'          )}}',
                f'        />',
            ])
        elif field.field_type == "TextField":
            lines.extend([
                f'        <FormField',
                f'          control={{form.control}}',
                f'          name="{field_name}"',
                f'          render={{({{ field }}) => (',
                f'            <FormItem>',
                f'              <FormLabel>{label}</FormLabel>',
                f'              <FormControl>',
                f'                <Textarea {{...field}} />',
                f'              </FormControl>',
                f'              {f"<FormDescription>{field.help_text}</FormDescription>" if field.help_text else ""}',
                f'              <FormMessage />',
                f'            </FormItem>',
                f'          )}}',
                f'        />',
            ])
        else:
            input_type = "email" if field.field_type == "EmailField" else "text"
            if field.field_type in ("IntegerField", "FloatField", "DecimalField"):
                input_type = "number"
            lines.extend([
                f'        <FormField',
                f'          control={{form.control}}',
                f'          name="{field_name}"',
                f'          render={{({{ field }}) => (',
                f'            <FormItem>',
                f'              <FormLabel>{label}</FormLabel>',
                f'              <FormControl>',
                f'                <Input type="{input_type}" {{...field}} />',
                f'              </FormControl>',
                f'              {f"<FormDescription>{field.help_text}</FormDescription>" if field.help_text else ""}',
                f'              <FormMessage />',
                f'            </FormItem>',
                f'          )}}',
                f'        />',
            ])

    lines.extend([
        '',
        f'        <Button type="submit" disabled={{create{name}.isPending}}>',
        f'          {{create{name}.isPending ? "Creating..." : "Create {name}"}}',
        f'        </Button>',
        f'      </form>',
        f'    </Form>',
        f'  )',
        f'}}',
    ])

    return "\n".join(lines)


def generate_react_list(
    model: Type[models.Model],
    ui_library: str = "shadcn",
) -> str:
    """Generate a React list component for a Django model."""
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = name.lower()
    name_plural = _pluralize(name)

    # Get display fields (first few non-auto fields)
    display_fields = [f for f in info.fields if not f.is_auto][:5]

    lines = [
        f'"use client"',
        '',
        f'import {{ use{name}s }} from "./hooks"',
        f'import type {{ {name} }} from "./types"',
        '',
    ]

    if ui_library == "shadcn":
        lines.extend([
            'import {',
            '  Table,',
            '  TableBody,',
            '  TableCell,',
            '  TableHead,',
            '  TableHeader,',
            '  TableRow,',
            '} from "@/components/ui/table"',
            'import { Skeleton } from "@/components/ui/skeleton"',
            '',
        ])

    lines.extend([
        f'interface {name}ListProps {{',
        f'  onSelect?: (item: {name}) => void',
        f'}}',
        '',
        f'export function {name}List({{ onSelect }}: {name}ListProps) {{',
        f'  const {{ data: {name_lower}s, isLoading, error }} = use{name}s()',
        '',
        f'  if (isLoading) {{',
        f'    return (',
        f'      <div className="space-y-2">',
        f'        <Skeleton className="h-10 w-full" />',
        f'        <Skeleton className="h-10 w-full" />',
        f'        <Skeleton className="h-10 w-full" />',
        f'      </div>',
        f'    )',
        f'  }}',
        '',
        f'  if (error) {{',
        f'    return <div className="text-red-500">Error: {{error.message}}</div>',
        f'  }}',
        '',
        f'  if (!{name_lower}s?.length) {{',
        f'    return <div className="text-muted-foreground">No {name_plural.lower()} found</div>',
        f'  }}',
        '',
        f'  return (',
        f'    <Table>',
        f'      <TableHeader>',
        f'        <TableRow>',
    ])

    for field in display_fields:
        lines.append(f'          <TableHead>{field.verbose_name.title()}</TableHead>')

    lines.extend([
        f'        </TableRow>',
        f'      </TableHeader>',
        f'      <TableBody>',
        f'        {{{name_lower}s.map((item) => (',
        f'          <TableRow',
        f'            key={{item.id}}',
        f'            onClick={{() => onSelect?.(item)}}',
        f'            className={{onSelect ? "cursor-pointer hover:bg-muted" : ""}}',
        f'          >',
    ])

    for field in display_fields:
        lines.append(f'            <TableCell>{{String(item.{field.name})}}</TableCell>')

    lines.extend([
        f'          </TableRow>',
        f'        ))}}',
        f'      </TableBody>',
        f'    </Table>',
        f'  )',
        f'}}',
    ])

    return "\n".join(lines)


def generate_react_detail(
    model: Type[models.Model],
    ui_library: str = "shadcn",
) -> str:
    """Generate a React detail component for a Django model."""
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = name.lower()

    lines = [
        f'"use client"',
        '',
        f'import {{ use{name} }} from "./hooks"',
        '',
    ]

    if ui_library == "shadcn":
        lines.extend([
            'import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"',
            'import { Skeleton } from "@/components/ui/skeleton"',
            '',
        ])

    lines.extend([
        f'interface {name}DetailProps {{',
        f'  id: number | string',
        f'}}',
        '',
        f'export function {name}Detail({{ id }}: {name}DetailProps) {{',
        f'  const {{ data: {name_lower}, isLoading, error }} = use{name}(id)',
        '',
        f'  if (isLoading) {{',
        f'    return (',
        f'      <Card>',
        f'        <CardHeader>',
        f'          <Skeleton className="h-6 w-32" />',
        f'        </CardHeader>',
        f'        <CardContent className="space-y-2">',
        f'          <Skeleton className="h-4 w-full" />',
        f'          <Skeleton className="h-4 w-3/4" />',
        f'        </CardContent>',
        f'      </Card>',
        f'    )',
        f'  }}',
        '',
        f'  if (error) {{',
        f'    return <div className="text-red-500">Error: {{error.message}}</div>',
        f'  }}',
        '',
        f'  if (!{name_lower}) {{',
        f'    return <div className="text-muted-foreground">{name} not found</div>',
        f'  }}',
        '',
        f'  return (',
        f'    <Card>',
        f'      <CardHeader>',
        f'        <CardTitle>{name} #{{{name_lower}.id}}</CardTitle>',
        f'      </CardHeader>',
        f'      <CardContent>',
        f'        <dl className="space-y-2">',
    ])

    for field in info.fields:
        if not field.is_auto:
            lines.extend([
                f'          <div>',
                f'            <dt className="text-sm font-medium text-muted-foreground">{field.verbose_name.title()}</dt>',
                f'            <dd>{{{name_lower}.{field.name} != null ? String({name_lower}.{field.name}) : "-"}}</dd>',
                f'          </div>',
            ])

    lines.extend([
        f'        </dl>',
        f'      </CardContent>',
        f'    </Card>',
        f'  )',
        f'}}',
    ])

    return "\n".join(lines)


class ReactGenerator(CodeGenerator):
    """
    Generate React components and hooks from Django models.

    Usage:
        gen = ReactGenerator([User, Post, Comment])
        gen.generate_all("./frontend/src/generated")
    """

    def __init__(
        self,
        models: List[Type[models.Model]],
        output_dir: str = "./generated",
        api_base: str = "/api",
        ui_library: str = "shadcn",
    ):
        super().__init__(output_dir)
        self.models = models
        self.api_base = api_base
        self.ui_library = ui_library
        self.model_infos = {m._meta.object_name: ModelIntrospector(m).introspect() for m in models}

    def generate_hooks_file(self) -> str:
        """Generate hooks.ts file with all TanStack Query hooks."""
        parts = [
            '// Auto-generated TanStack Query hooks from Django models.',
            '// Do not edit manually.',
            '',
        ]

        for model in self.models:
            parts.append(generate_react_hooks(model, self.api_base))
            parts.append('')

        return "\n".join(parts)

    def generate_components_file(self, model: Type[models.Model]) -> str:
        """Generate components file for a model."""
        info = self.model_infos[model._meta.object_name]

        parts = [
            f'// Auto-generated React components for {info.name}',
            '// Do not edit manually.',
            '',
            generate_react_form(model, self.ui_library),
            '',
            generate_react_list(model, self.ui_library),
            '',
            generate_react_detail(model, self.ui_library),
        ]

        return "\n".join(parts)

    def generate_all(self) -> Dict[str, str]:
        """Generate all React files."""
        from django_matt.codegen.typescript import TypeScriptGenerator

        # Generate TypeScript types and schemas
        ts_gen = TypeScriptGenerator(self.models, self.output_dir)
        ts_files = ts_gen.generate_all()

        # Generate hooks
        files = dict(ts_files)
        files["hooks.ts"] = self.generate_hooks_file()

        # Generate component files per model
        for model in self.models:
            info = self.model_infos[model._meta.object_name]
            files[f"components/{info.name}.tsx"] = self.generate_components_file(model)

        # Generate index file
        index_lines = [
            '// Auto-generated index - re-exports all generated code',
            '',
            'export * from "./types"',
            'export * from "./schemas"',
            'export * from "./hooks"',
            '',
        ]
        for model in self.models:
            info = self.model_infos[model._meta.object_name]
            index_lines.append(f'export * from "./components/{info.name}"')

        files["index.ts"] = "\n".join(index_lines)

        return files


__all__ = [
    "ReactGenerator",
    "generate_react_hooks",
    "generate_react_form",
    "generate_react_list",
    "generate_react_detail",
]
