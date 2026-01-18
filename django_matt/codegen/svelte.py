"""
Svelte code generator.

Generates Svelte components and stores from Django models.
Supports both Svelte 4 (stores) and Svelte 5 (runes) patterns.

Usage:
    from django_matt.codegen.svelte import SvelteGenerator
    from myapp.models import User

    # Generate Svelte stores
    stores_code = generate_svelte_stores(User)

    # Generate Svelte components
    gen = SvelteGenerator([User, Post])
    gen.generate_all()
"""

from django.db import models

from django_matt.codegen.core import (
    CodeFile,
    CodeGenerator,
    Statement,
)
from django_matt.codegen.introspection import (
    FieldInfo,
    ModelIntrospector,
)
from django_matt.codegen.typescript import (
    generate_typescript_interface,
)


def _to_kebab_case(name: str) -> str:
    """Convert PascalCase to kebab-case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("-")
        result.append(char.lower())
    return "".join(result)


def _to_camel_case(name: str) -> str:
    """Convert PascalCase to camelCase."""
    if not name:
        return name
    return name[0].lower() + name[1:]


def _field_to_form_input(field: FieldInfo) -> str:
    """Generate Svelte form input for a field."""
    name = field.name
    label = field.verbose_name.title()

    # Handle choices with select
    if field.choices:
        options = "\n".join(
            f'        <option value="{c[0]}">{c[1]}</option>' for c in field.choices
        )
        return f'''    <div class="form-group">
      <label for="{name}">{label}</label>
      <select id="{name}" bind:value={{formData.{name}}} class="form-control">
        <option value="">Select {label}</option>
{options}
      </select>
    </div>'''

    # Map field types to input types
    input_type = "text"
    extra_attrs = ""

    if field.field_type in (
        "IntegerField",
        "SmallIntegerField",
        "BigIntegerField",
        "PositiveIntegerField",
        "PositiveSmallIntegerField",
        "PositiveBigIntegerField",
    ):
        input_type = "number"
        extra_attrs = ' step="1"'
    elif field.field_type in ("FloatField", "DecimalField"):
        input_type = "number"
        extra_attrs = ' step="any"'
    elif field.field_type == "EmailField":
        input_type = "email"
    elif field.field_type == "URLField":
        input_type = "url"
    elif field.field_type == "BooleanField":
        return f'''    <div class="form-group form-check">
      <input type="checkbox" id="{name}" bind:checked={{formData.{name}}} class="form-check-input" />
      <label for="{name}" class="form-check-label">{label}</label>
    </div>'''
    elif field.field_type == "DateField":
        input_type = "date"
    elif field.field_type == "DateTimeField":
        input_type = "datetime-local"
    elif field.field_type == "TimeField":
        input_type = "time"
    elif field.field_type == "TextField":
        return f'''    <div class="form-group">
      <label for="{name}">{label}</label>
      <textarea id="{name}" bind:value={{formData.{name}}} class="form-control" rows="4"></textarea>
    </div>'''
    elif field.field_type in ("FileField", "ImageField"):
        return f'''    <div class="form-group">
      <label for="{name}">{label}</label>
      <input type="file" id="{name}" on:change={{handleFileChange}} class="form-control" />
    </div>'''

    # Add max length
    if field.max_length:
        extra_attrs += f' maxlength="{field.max_length}"'

    # Add required
    if field.is_required:
        extra_attrs += " required"

    return f'''    <div class="form-group">
      <label for="{name}">{label}</label>
      <input type="{input_type}" id="{name}" bind:value={{formData.{name}}} class="form-control"{extra_attrs} />
    </div>'''


def generate_svelte_stores(
    model: type[models.Model],
    api_base: str = "/api",
) -> str:
    """
    Generate Svelte stores for a Django model.

    Creates readable/writable stores for CRUD operations.

    Args:
        model: Django model class
        api_base: Base URL for API endpoints

    Returns:
        Svelte store code (TypeScript)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)
    name_plural = f"{name_lower}s"
    endpoint = f"{api_base}/{name_plural}"

    return f"""/**
 * Svelte stores for {name} CRUD operations.
 * Auto-generated from Django model {info.full_name}.
 */

import {{ writable, derived, type Writable }} from 'svelte/store';
import type {{ {name}, {name}CreateInput, {name}UpdateInput }} from './types';

// State stores
export const {name_plural}: Writable<{name}[]> = writable([]);
export const current{name}: Writable<{name} | null> = writable(null);
export const isLoading: Writable<boolean> = writable(false);
export const error: Writable<string | null> = writable(null);

// Pagination
export const page: Writable<number> = writable(1);
export const pageSize: Writable<number> = writable(20);
export const totalCount: Writable<number> = writable(0);

// Derived stores
export const hasMore = derived(
  [page, pageSize, totalCount],
  ([$page, $pageSize, $totalCount]) => $page * $pageSize < $totalCount
);

export const isEmpty = derived({name_plural}, (${name_plural}) => ${name_plural}.length === 0);

// API functions
async function apiRequest<T>(
  url: string,
  options: RequestInit = {{}}
): Promise<T> {{
  const response = await fetch(url, {{
    headers: {{
      'Content-Type': 'application/json',
      ...options.headers,
    }},
    ...options,
  }});

  if (!response.ok) {{
    const errorData = await response.json().catch(() => ({{}}));
    throw new Error(errorData.detail || `Request failed: ${{response.status}}`);
  }}

  return response.json();
}}

// CRUD operations
export async function fetch{name}s(params?: {{
  page?: number;
  page_size?: number;
  search?: string;
}}): Promise<void> {{
  isLoading.set(true);
  error.set(null);

  try {{
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', String(params.page));
    if (params?.page_size) queryParams.set('page_size', String(params.page_size));
    if (params?.search) queryParams.set('search', params.search);

    const url = queryParams.toString()
      ? `{endpoint}?${{queryParams}}`
      : '{endpoint}';

    const data = await apiRequest<{{
      items: {name}[];
      count: number;
      page: number;
      page_size: number;
    }}>(url);

    {name_plural}.set(data.items);
    totalCount.set(data.count);
    if (params?.page) page.set(params.page);
  }} catch (e) {{
    error.set(e instanceof Error ? e.message : 'Failed to fetch {name_plural}');
    throw e;
  }} finally {{
    isLoading.set(false);
  }}
}}

export async function fetch{name}(id: number | string): Promise<{name}> {{
  isLoading.set(true);
  error.set(null);

  try {{
    const data = await apiRequest<{name}>(`{endpoint}/${{id}}`);
    current{name}.set(data);
    return data;
  }} catch (e) {{
    error.set(e instanceof Error ? e.message : 'Failed to fetch {name_lower}');
    throw e;
  }} finally {{
    isLoading.set(false);
  }}
}}

export async function create{name}(input: {name}CreateInput): Promise<{name}> {{
  isLoading.set(true);
  error.set(null);

  try {{
    const data = await apiRequest<{name}>('{endpoint}', {{
      method: 'POST',
      body: JSON.stringify(input),
    }});

    // Add to list
    {name_plural}.update((items) => [data, ...items]);
    totalCount.update((n) => n + 1);

    return data;
  }} catch (e) {{
    error.set(e instanceof Error ? e.message : 'Failed to create {name_lower}');
    throw e;
  }} finally {{
    isLoading.set(false);
  }}
}}

export async function update{name}(
  id: number | string,
  input: {name}UpdateInput
): Promise<{name}> {{
  isLoading.set(true);
  error.set(null);

  try {{
    const data = await apiRequest<{name}>(`{endpoint}/${{id}}`, {{
      method: 'PATCH',
      body: JSON.stringify(input),
    }});

    // Update in list
    {name_plural}.update((items) =>
      items.map((item) => (item.id === data.id ? data : item))
    );

    // Update current if viewing
    current{name}.update((current) =>
      current?.id === data.id ? data : current
    );

    return data;
  }} catch (e) {{
    error.set(e instanceof Error ? e.message : 'Failed to update {name_lower}');
    throw e;
  }} finally {{
    isLoading.set(false);
  }}
}}

export async function delete{name}(id: number | string): Promise<void> {{
  isLoading.set(true);
  error.set(null);

  try {{
    await apiRequest(`{endpoint}/${{id}}`, {{
      method: 'DELETE',
    }});

    // Remove from list
    {name_plural}.update((items) => items.filter((item) => item.id !== id));
    totalCount.update((n) => n - 1);

    // Clear current if deleted
    current{name}.update((current) =>
      current?.id === id ? null : current
    );
  }} catch (e) {{
    error.set(e instanceof Error ? e.message : 'Failed to delete {name_lower}');
    throw e;
  }} finally {{
    isLoading.set(false);
  }}
}}

// Reset state
export function reset{name}State(): void {{
  {name_plural}.set([]);
  current{name}.set(null);
  isLoading.set(false);
  error.set(null);
  page.set(1);
  totalCount.set(0);
}}
"""


def generate_svelte5_stores(
    model: type[models.Model],
    api_base: str = "/api",
) -> str:
    """
    Generate Svelte 5 runes-based state for a Django model.

    Uses $state, $derived, and $effect for reactivity.

    Args:
        model: Django model class
        api_base: Base URL for API endpoints

    Returns:
        Svelte 5 runes code (TypeScript)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)
    name_plural = f"{name_lower}s"
    endpoint = f"{api_base}/{name_plural}"

    return f"""/**
 * Svelte 5 runes-based state for {name} CRUD operations.
 * Auto-generated from Django model {info.full_name}.
 */

import type {{ {name}, {name}CreateInput, {name}UpdateInput }} from './types';

// Create reactive state using Svelte 5 runes
export function create{name}State() {{
  // State
  let {name_plural} = $state<{name}[]>([]);
  let current{name} = $state<{name} | null>(null);
  let isLoading = $state(false);
  let error = $state<string | null>(null);
  let page = $state(1);
  let pageSize = $state(20);
  let totalCount = $state(0);

  // Derived values
  const hasMore = $derived(page * pageSize < totalCount);
  const isEmpty = $derived({name_plural}.length === 0);

  // API helper
  async function apiRequest<T>(url: string, options: RequestInit = {{}}): Promise<T> {{
    const response = await fetch(url, {{
      headers: {{
        'Content-Type': 'application/json',
        ...options.headers,
      }},
      ...options,
    }});

    if (!response.ok) {{
      const errorData = await response.json().catch(() => ({{}}));
      throw new Error(errorData.detail || `Request failed: ${{response.status}}`);
    }}

    return response.json();
  }}

  // CRUD operations
  async function fetchAll(params?: {{
    page?: number;
    page_size?: number;
    search?: string;
  }}) {{
    isLoading = true;
    error = null;

    try {{
      const queryParams = new URLSearchParams();
      if (params?.page) queryParams.set('page', String(params.page));
      if (params?.page_size) queryParams.set('page_size', String(params.page_size));
      if (params?.search) queryParams.set('search', params.search);

      const url = queryParams.toString()
        ? `{endpoint}?${{queryParams}}`
        : '{endpoint}';

      const data = await apiRequest<{{
        items: {name}[];
        count: number;
      }}>(url);

      {name_plural} = data.items;
      totalCount = data.count;
      if (params?.page) page = params.page;
    }} catch (e) {{
      error = e instanceof Error ? e.message : 'Failed to fetch';
      throw e;
    }} finally {{
      isLoading = false;
    }}
  }}

  async function fetchOne(id: number | string): Promise<{name}> {{
    isLoading = true;
    error = null;

    try {{
      const data = await apiRequest<{name}>(`{endpoint}/${{id}}`);
      current{name} = data;
      return data;
    }} catch (e) {{
      error = e instanceof Error ? e.message : 'Failed to fetch';
      throw e;
    }} finally {{
      isLoading = false;
    }}
  }}

  async function create(input: {name}CreateInput): Promise<{name}> {{
    isLoading = true;
    error = null;

    try {{
      const data = await apiRequest<{name}>('{endpoint}', {{
        method: 'POST',
        body: JSON.stringify(input),
      }});

      {name_plural} = [data, ...{name_plural}];
      totalCount += 1;
      return data;
    }} catch (e) {{
      error = e instanceof Error ? e.message : 'Failed to create';
      throw e;
    }} finally {{
      isLoading = false;
    }}
  }}

  async function update(id: number | string, input: {name}UpdateInput): Promise<{name}> {{
    isLoading = true;
    error = null;

    try {{
      const data = await apiRequest<{name}>(`{endpoint}/${{id}}`, {{
        method: 'PATCH',
        body: JSON.stringify(input),
      }});

      {name_plural} = {name_plural}.map((item) => (item.id === data.id ? data : item));
      if (current{name}?.id === data.id) current{name} = data;
      return data;
    }} catch (e) {{
      error = e instanceof Error ? e.message : 'Failed to update';
      throw e;
    }} finally {{
      isLoading = false;
    }}
  }}

  async function remove(id: number | string): Promise<void> {{
    isLoading = true;
    error = null;

    try {{
      await apiRequest(`{endpoint}/${{id}}`, {{ method: 'DELETE' }});
      {name_plural} = {name_plural}.filter((item) => item.id !== id);
      totalCount -= 1;
      if (current{name}?.id === id) current{name} = null;
    }} catch (e) {{
      error = e instanceof Error ? e.message : 'Failed to delete';
      throw e;
    }} finally {{
      isLoading = false;
    }}
  }}

  function reset() {{
    {name_plural} = [];
    current{name} = null;
    isLoading = false;
    error = null;
    page = 1;
    totalCount = 0;
  }}

  return {{
    // State (getters for reactivity)
    get {name_plural}() {{ return {name_plural}; }},
    get current{name}() {{ return current{name}; }},
    get isLoading() {{ return isLoading; }},
    get error() {{ return error; }},
    get page() {{ return page; }},
    get pageSize() {{ return pageSize; }},
    get totalCount() {{ return totalCount; }},
    get hasMore() {{ return hasMore; }},
    get isEmpty() {{ return isEmpty; }},
    // Actions
    fetchAll,
    fetchOne,
    create,
    update,
    remove,
    reset,
  }};
}}
"""


def generate_svelte_form(
    model: type[models.Model],
    mode: str = "create",
) -> str:
    """
    Generate a Svelte form component for a Django model.

    Args:
        model: Django model class
        mode: "create" or "edit"

    Returns:
        Svelte component code
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)

    # Get editable fields
    fields = [f for f in info.fields if f.is_editable and not f.is_auto and not f.is_primary_key]

    # Generate form fields
    form_fields = "\n\n".join(_field_to_form_input(f) for f in fields)

    # Generate initial values
    initial_values = ",\n    ".join(f"{f.name}: {_get_field_default(f)}" for f in fields)

    is_edit = mode == "edit"
    title = f"Edit {name}" if is_edit else f"Create {name}"
    submit_text = "Save Changes" if is_edit else f"Create {name}"

    return f'''<script lang="ts">
  import {{ createEventDispatcher }} from 'svelte';
  import type {{ {name}CreateInput }} from './types';
  {"import { create" + name + ", update" + name + ' } from "./' + name_lower + '-stores";' if not is_edit else "import { update" + name + ' } from "./' + name_lower + '-stores";'}

  export let initial: Partial<{name}CreateInput> = {{}};
  {"export let id: number | string;" if is_edit else ""}

  const dispatch = createEventDispatcher<{{
    success: {name}CreateInput;
    cancel: void;
  }}>();

  let formData: {name}CreateInput = {{
    {initial_values},
    ...initial,
  }};

  let isSubmitting = false;
  let errorMessage: string | null = null;

  async function handleSubmit() {{
    isSubmitting = true;
    errorMessage = null;

    try {{
      {"await update" + name + "(id, formData);" if is_edit else "await create" + name + "(formData);"}
      dispatch('success', formData);
    }} catch (e) {{
      errorMessage = e instanceof Error ? e.message : 'An error occurred';
    }} finally {{
      isSubmitting = false;
    }}
  }}

  function handleCancel() {{
    dispatch('cancel');
  }}
</script>

<form on:submit|preventDefault={{handleSubmit}} class="{name_lower}-form">
  <h2>{title}</h2>

  {{#if errorMessage}}
    <div class="alert alert-error" role="alert">
      {{errorMessage}}
    </div>
  {{/if}}

{form_fields}

  <div class="form-actions">
    <button type="button" on:click={{handleCancel}} class="btn btn-secondary" disabled={{isSubmitting}}>
      Cancel
    </button>
    <button type="submit" class="btn btn-primary" disabled={{isSubmitting}}>
      {{#if isSubmitting}}
        Saving...
      {{:else}}
        {submit_text}
      {{/if}}
    </button>
  </div>
</form>

<style>
  .{name_lower}-form {{
    max-width: 600px;
    margin: 0 auto;
  }}

  .form-group {{
    margin-bottom: 1rem;
  }}

  .form-group label {{
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
  }}

  .form-control {{
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 1rem;
  }}

  .form-control:focus {{
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }}

  .form-check {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}

  .form-check-input {{
    width: auto;
  }}

  .form-actions {{
    display: flex;
    gap: 1rem;
    justify-content: flex-end;
    margin-top: 1.5rem;
  }}

  .btn {{
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }}

  .btn:disabled {{
    opacity: 0.6;
    cursor: not-allowed;
  }}

  .btn-primary {{
    background: #007bff;
    color: white;
  }}

  .btn-primary:hover:not(:disabled) {{
    background: #0056b3;
  }}

  .btn-secondary {{
    background: #6c757d;
    color: white;
  }}

  .btn-secondary:hover:not(:disabled) {{
    background: #545b62;
  }}

  .alert {{
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }}

  .alert-error {{
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }}
</style>
'''


def generate_svelte_list(
    model: type[models.Model],
) -> str:
    """
    Generate a Svelte list component for a Django model.

    Args:
        model: Django model class

    Returns:
        Svelte component code
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)
    name_plural = f"{name_lower}s"

    # Get display fields (first 5 non-auto fields)
    display_fields = [f for f in info.fields if not f.is_auto][:5]

    # Generate table headers
    headers = "\n      ".join(f"<th>{f.verbose_name.title()}</th>" for f in display_fields)

    # Generate table cells
    cells = "\n        ".join(f"<td>{{item.{f.name}}}</td>" for f in display_fields)

    return f'''<script lang="ts">
  import {{ onMount }} from 'svelte';
  import {{
    {name_plural},
    isLoading,
    error,
    page,
    totalCount,
    hasMore,
    fetch{name}s,
    delete{name},
  }} from './{name_lower}-stores';

  export let onSelect: ((id: number | string) => void) | undefined = undefined;
  export let onCreate: (() => void) | undefined = undefined;

  let searchQuery = '';
  let deleteConfirmId: number | string | null = null;

  onMount(() => {{
    fetch{name}s();
  }});

  function handleSearch() {{
    fetch{name}s({{ search: searchQuery, page: 1 }});
  }}

  function handlePageChange(newPage: number) {{
    fetch{name}s({{ page: newPage, search: searchQuery }});
  }}

  async function handleDelete(id: number | string) {{
    if (deleteConfirmId === id) {{
      await delete{name}(id);
      deleteConfirmId = null;
    }} else {{
      deleteConfirmId = id;
    }}
  }}

  function cancelDelete() {{
    deleteConfirmId = null;
  }}
</script>

<div class="{name_lower}-list">
  <div class="list-header">
    <h2>{name}s</h2>
    {{#if onCreate}}
      <button class="btn btn-primary" on:click={{onCreate}}>
        Add {name}
      </button>
    {{/if}}
  </div>

  <div class="search-bar">
    <input
      type="search"
      placeholder="Search {name_plural}..."
      bind:value={{searchQuery}}
      on:input={{handleSearch}}
      class="search-input"
    />
  </div>

  {{#if $error}}
    <div class="alert alert-error" role="alert">
      {{$error}}
    </div>
  {{/if}}

  {{#if $isLoading}}
    <div class="loading">Loading...</div>
  {{:else if ${name_plural}.length === 0}}
    <div class="empty-state">
      <p>No {name_plural} found.</p>
    </div>
  {{:else}}
    <table class="data-table">
      <thead>
        <tr>
          {headers}
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {{#each ${name_plural} as item (item.id)}}
          <tr>
            {cells}
            <td class="actions">
              {{#if onSelect}}
                <button class="btn btn-sm" on:click={{() => onSelect(item.id)}}>
                  View
                </button>
              {{/if}}
              {{#if deleteConfirmId === item.id}}
                <button class="btn btn-sm btn-danger" on:click={{() => handleDelete(item.id)}}>
                  Confirm
                </button>
                <button class="btn btn-sm" on:click={{cancelDelete}}>
                  Cancel
                </button>
              {{:else}}
                <button class="btn btn-sm btn-danger" on:click={{() => handleDelete(item.id)}}>
                  Delete
                </button>
              {{/if}}
            </td>
          </tr>
        {{/each}}
      </tbody>
    </table>

    <div class="pagination">
      <button
        class="btn btn-sm"
        disabled={{$page <= 1}}
        on:click={{() => handlePageChange($page - 1)}}
      >
        Previous
      </button>
      <span class="page-info">
        Page {{$page}} ({{$totalCount}} total)
      </span>
      <button
        class="btn btn-sm"
        disabled={{!$hasMore}}
        on:click={{() => handlePageChange($page + 1)}}
      >
        Next
      </button>
    </div>
  {{/if}}
</div>

<style>
  .{name_lower}-list {{
    max-width: 1200px;
    margin: 0 auto;
  }}

  .list-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }}

  .search-bar {{
    margin-bottom: 1rem;
  }}

  .search-input {{
    width: 100%;
    max-width: 400px;
    padding: 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 1rem;
  }}

  .data-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
  }}

  .data-table th,
  .data-table td {{
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid #ddd;
  }}

  .data-table th {{
    background: #f5f5f5;
    font-weight: 600;
  }}

  .data-table tbody tr:hover {{
    background: #f9f9f9;
  }}

  .actions {{
    display: flex;
    gap: 0.5rem;
  }}

  .pagination {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    margin-top: 1rem;
  }}

  .page-info {{
    color: #666;
  }}

  .loading,
  .empty-state {{
    text-align: center;
    padding: 2rem;
    color: #666;
  }}

  .btn {{
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }}

  .btn:disabled {{
    opacity: 0.6;
    cursor: not-allowed;
  }}

  .btn-sm {{
    padding: 0.25rem 0.5rem;
    font-size: 0.875rem;
  }}

  .btn-primary {{
    background: #007bff;
    color: white;
  }}

  .btn-danger {{
    background: #dc3545;
    color: white;
  }}

  .alert {{
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }}

  .alert-error {{
    background: #f8d7da;
    color: #721c24;
  }}
</style>
'''


def generate_svelte_detail(
    model: type[models.Model],
) -> str:
    """
    Generate a Svelte detail component for a Django model.

    Args:
        model: Django model class

    Returns:
        Svelte component code
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)

    # Generate field displays
    field_displays = "\n    ".join(
        f"""<div class="field">
      <dt>{f.verbose_name.title()}</dt>
      <dd>{{${name_lower}?.{f.name} ?? '-'}}</dd>
    </div>"""
        for f in info.fields
    )

    return f'''<script lang="ts">
  import {{ onMount }} from 'svelte';
  import {{ current{name} as {name_lower}, isLoading, error, fetch{name} }} from './{name_lower}-stores';

  export let id: number | string;
  export let onEdit: ((id: number | string) => void) | undefined = undefined;
  export let onBack: (() => void) | undefined = undefined;

  onMount(() => {{
    fetch{name}(id);
  }});
</script>

<div class="{name_lower}-detail">
  {{#if $isLoading}}
    <div class="loading">Loading...</div>
  {{:else if $error}}
    <div class="alert alert-error" role="alert">
      {{$error}}
    </div>
  {{:else if ${name_lower}}}
    <div class="detail-header">
      <h2>{name} Details</h2>
      <div class="actions">
        {{#if onBack}}
          <button class="btn btn-secondary" on:click={{onBack}}>
            Back
          </button>
        {{/if}}
        {{#if onEdit}}
          <button class="btn btn-primary" on:click={{() => onEdit(id)}}>
            Edit
          </button>
        {{/if}}
      </div>
    </div>

    <dl class="detail-fields">
      {field_displays}
    </dl>
  {{:else}}
    <div class="not-found">
      <p>{name} not found.</p>
      {{#if onBack}}
        <button class="btn btn-secondary" on:click={{onBack}}>
          Go Back
        </button>
      {{/if}}
    </div>
  {{/if}}
</div>

<style>
  .{name_lower}-detail {{
    max-width: 800px;
    margin: 0 auto;
  }}

  .detail-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }}

  .actions {{
    display: flex;
    gap: 0.5rem;
  }}

  .detail-fields {{
    display: grid;
    gap: 1rem;
  }}

  .field {{
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid #eee;
  }}

  .field dt {{
    font-weight: 600;
    color: #666;
  }}

  .field dd {{
    margin: 0;
  }}

  .loading,
  .not-found {{
    text-align: center;
    padding: 2rem;
    color: #666;
  }}

  .btn {{
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }}

  .btn-primary {{
    background: #007bff;
    color: white;
  }}

  .btn-secondary {{
    background: #6c757d;
    color: white;
  }}

  .alert {{
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }}

  .alert-error {{
    background: #f8d7da;
    color: #721c24;
  }}
</style>
'''


def _get_field_default(field: FieldInfo) -> str:
    """Get the default value for a field in JavaScript."""
    if field.field_type == "BooleanField":
        return "false"
    if field.field_type in (
        "IntegerField",
        "SmallIntegerField",
        "BigIntegerField",
        "PositiveIntegerField",
        "PositiveSmallIntegerField",
        "PositiveBigIntegerField",
        "FloatField",
        "DecimalField",
    ):
        return "0"
    if field.choices:
        return "''"
    return "''"


class SvelteGenerator(CodeGenerator):
    """
    Generate Svelte components and stores from Django models.

    Usage:
        gen = SvelteGenerator([User, Post, Comment])
        gen.generate_all()
    """

    def __init__(
        self,
        models: list[type[models.Model]],
        output_dir: str = "./generated",
        api_base: str = "/api",
        svelte_version: int = 4,  # 4 or 5
    ):
        super().__init__(output_dir)
        self.models = models
        self.api_base = api_base
        self.svelte_version = svelte_version
        self.model_infos = {m._meta.object_name: ModelIntrospector(m).introspect() for m in models}

    def generate_types_file(self) -> CodeFile:
        """Generate a types.ts file with all interfaces."""
        file = CodeFile()
        file.header_comment = (
            "Auto-generated TypeScript types from Django models.\nDo not edit manually."
        )

        for model in self.models:
            ts_code = generate_typescript_interface(model)
            file.add_node(Statement(ts_code))

        return file

    def generate_stores_file(self, model: type[models.Model]) -> str:
        """Generate stores file for a model."""
        if self.svelte_version >= 5:
            return generate_svelte5_stores(model, self.api_base)
        return generate_svelte_stores(model, self.api_base)

    def generate_form_component(self, model: type[models.Model], mode: str = "create") -> str:
        """Generate form component for a model."""
        return generate_svelte_form(model, mode)

    def generate_list_component(self, model: type[models.Model]) -> str:
        """Generate list component for a model."""
        return generate_svelte_list(model)

    def generate_detail_component(self, model: type[models.Model]) -> str:
        """Generate detail component for a model."""
        return generate_svelte_detail(model)

    def generate_all(self) -> dict[str, str]:
        """Generate all Svelte files."""
        files = {}

        # Types file
        types_file = self.generate_types_file()
        files["types.ts"] = types_file.to_typescript()

        # Per-model files
        for model in self.models:
            info = self.model_infos[model._meta.object_name]
            name_lower = _to_camel_case(info.name)

            # Stores
            files[f"{name_lower}-stores.ts"] = self.generate_stores_file(model)

            # Components
            files[f"{info.name}Form.svelte"] = self.generate_form_component(model, "create")
            files[f"{info.name}EditForm.svelte"] = self.generate_form_component(model, "edit")
            files[f"{info.name}List.svelte"] = self.generate_list_component(model)
            files[f"{info.name}Detail.svelte"] = self.generate_detail_component(model)

        return files


__all__ = [
    "SvelteGenerator",
    "generate_svelte5_stores",
    "generate_svelte_detail",
    "generate_svelte_form",
    "generate_svelte_list",
    "generate_svelte_stores",
]
