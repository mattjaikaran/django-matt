"""
SolidJS code generator.

Generates SolidJS components and signals from Django models.
Uses SolidJS primitives like createSignal, createResource, and createStore.

Usage:
    from django_matt.codegen.solid import SolidGenerator
    from myapp.models import User

    # Generate SolidJS hooks
    hooks_code = generate_solid_resource(User)

    # Generate SolidJS components
    gen = SolidGenerator([User, Post])
    gen.generate_all()
"""

from typing import Dict, List, Optional, Type

from django.db import models

from django_matt.codegen.core import (
    CodeFile,
    CodeGenerator,
    Statement,
)
from django_matt.codegen.introspection import (
    ModelIntrospector,
    ModelInfo,
    FieldInfo,
)
from django_matt.codegen.typescript import (
    generate_typescript_interface,
    django_field_to_typescript,
)


def _to_camel_case(name: str) -> str:
    """Convert PascalCase to camelCase."""
    if not name:
        return name
    return name[0].lower() + name[1:]


def _field_to_form_input(field: FieldInfo, form_data_accessor: str = "formData") -> str:
    """Generate SolidJS form input for a field."""
    name = field.name
    label = field.verbose_name.title()

    # Handle choices with select
    if field.choices:
        options = "\n".join(
            f'          <option value="{c[0]}">{c[1]}</option>'
            for c in field.choices
        )
        return f'''      <div class="form-group">
        <label for="{name}">{label}</label>
        <select
          id="{name}"
          value={{{form_data_accessor}().{name}}}
          onChange={{(e) => setFormData('{name}', e.currentTarget.value)}}
          class="form-control"
        >
          <option value="">Select {label}</option>
{options}
        </select>
      </div>'''

    # Map field types to input types
    input_type = "text"
    extra_attrs = ""
    value_handler = f'{form_data_accessor}().{name}'
    change_handler = f"setFormData('{name}', e.currentTarget.value)"

    if field.field_type in ("IntegerField", "SmallIntegerField", "BigIntegerField",
                            "PositiveIntegerField", "PositiveSmallIntegerField",
                            "PositiveBigIntegerField"):
        input_type = "number"
        extra_attrs = ' step="1"'
        change_handler = f"setFormData('{name}', parseInt(e.currentTarget.value) || 0)"
    elif field.field_type in ("FloatField", "DecimalField"):
        input_type = "number"
        extra_attrs = ' step="any"'
        change_handler = f"setFormData('{name}', parseFloat(e.currentTarget.value) || 0)"
    elif field.field_type == "EmailField":
        input_type = "email"
    elif field.field_type == "URLField":
        input_type = "url"
    elif field.field_type == "BooleanField":
        return f'''      <div class="form-group form-check">
        <input
          type="checkbox"
          id="{name}"
          checked={{{form_data_accessor}().{name}}}
          onChange={{(e) => setFormData('{name}', e.currentTarget.checked)}}
          class="form-check-input"
        />
        <label for="{name}" class="form-check-label">{label}</label>
      </div>'''
    elif field.field_type == "DateField":
        input_type = "date"
    elif field.field_type == "DateTimeField":
        input_type = "datetime-local"
    elif field.field_type == "TimeField":
        input_type = "time"
    elif field.field_type == "TextField":
        return f'''      <div class="form-group">
        <label for="{name}">{label}</label>
        <textarea
          id="{name}"
          value={{{form_data_accessor}().{name}}}
          onInput={{(e) => setFormData('{name}', e.currentTarget.value)}}
          class="form-control"
          rows="4"
        />
      </div>'''
    elif field.field_type in ("FileField", "ImageField"):
        return f'''      <div class="form-group">
        <label for="{name}">{label}</label>
        <input
          type="file"
          id="{name}"
          onChange={{handleFileChange}}
          class="form-control"
        />
      </div>'''

    # Add max length
    if field.max_length:
        extra_attrs += f' maxLength={{{field.max_length}}}'

    # Add required
    if field.is_required:
        extra_attrs += ' required'

    return f'''      <div class="form-group">
        <label for="{name}">{label}</label>
        <input
          type="{input_type}"
          id="{name}"
          value={{{value_handler}}}
          onInput={{(e) => {change_handler}}}
          class="form-control"{extra_attrs}
        />
      </div>'''


def _get_field_default(field: FieldInfo) -> str:
    """Get the default value for a field in JavaScript."""
    if field.field_type == "BooleanField":
        return "false"
    if field.field_type in ("IntegerField", "SmallIntegerField", "BigIntegerField",
                            "PositiveIntegerField", "PositiveSmallIntegerField",
                            "PositiveBigIntegerField", "FloatField", "DecimalField"):
        return "0"
    return "''"


def generate_solid_resource(
    model: Type[models.Model],
    api_base: str = "/api",
) -> str:
    """
    Generate SolidJS resource and store for a Django model.

    Uses createResource for data fetching and createStore for state.

    Args:
        model: Django model class
        api_base: Base URL for API endpoints

    Returns:
        SolidJS resource/store code (TypeScript)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)
    name_plural = f"{name_lower}s"
    endpoint = f"{api_base}/{name_plural}"

    return f'''/**
 * SolidJS resources and stores for {name} CRUD operations.
 * Auto-generated from Django model {info.full_name}.
 */

import {{ createSignal, createResource, createEffect }} from 'solid-js';
import {{ createStore, produce }} from 'solid-js/store';
import type {{ {name}, {name}CreateInput, {name}UpdateInput }} from './types';

// Types
interface {name}ListResponse {{
  items: {name}[];
  count: number;
  page: number;
  page_size: number;
}}

interface FetchParams {{
  page?: number;
  page_size?: number;
  search?: string;
}}

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

// Fetchers
async function fetch{name}List(params: FetchParams): Promise<{name}ListResponse> {{
  const queryParams = new URLSearchParams();
  if (params.page) queryParams.set('page', String(params.page));
  if (params.page_size) queryParams.set('page_size', String(params.page_size));
  if (params.search) queryParams.set('search', params.search);

  const url = queryParams.toString()
    ? `{endpoint}?${{queryParams}}`
    : '{endpoint}';

  return apiRequest<{name}ListResponse>(url);
}}

async function fetch{name}Detail(id: number | string): Promise<{name}> {{
  return apiRequest<{name}>(`{endpoint}/${{id}}`);
}}

/**
 * Create a {name} list resource with pagination.
 */
export function create{name}ListResource(initialParams: FetchParams = {{}}) {{
  const [params, setParams] = createSignal<FetchParams>(initialParams);
  const [data, {{ mutate, refetch }}] = createResource(params, fetch{name}List);

  return {{
    // Data
    get items() {{ return data()?.items ?? []; }},
    get count() {{ return data()?.count ?? 0; }},
    get page() {{ return data()?.page ?? 1; }},
    get pageSize() {{ return data()?.page_size ?? 20; }},
    get loading() {{ return data.loading; }},
    get error() {{ return data.error; }},

    // Derived
    get hasMore() {{
      const d = data();
      return d ? d.page * d.page_size < d.count : false;
    }},
    get isEmpty() {{ return !data.loading && (data()?.items.length ?? 0) === 0; }},

    // Actions
    setPage(page: number) {{
      setParams((p) => ({{ ...p, page }}));
    }},
    setSearch(search: string) {{
      setParams((p) => ({{ ...p, search, page: 1 }}));
    }},
    refetch,
    mutate,
  }};
}}

/**
 * Create a {name} detail resource.
 */
export function create{name}DetailResource(id: () => number | string | undefined) {{
  const [data, {{ mutate, refetch }}] = createResource(id, (id) =>
    id !== undefined ? fetch{name}Detail(id) : Promise.resolve(undefined)
  );

  return {{
    get data() {{ return data(); }},
    get loading() {{ return data.loading; }},
    get error() {{ return data.error; }},
    refetch,
    mutate,
  }};
}}

/**
 * Create a {name} store with CRUD operations.
 */
export function create{name}Store() {{
  const [state, setState] = createStore<{{
    items: {name}[];
    current: {name} | null;
    loading: boolean;
    error: string | null;
    page: number;
    totalCount: number;
  }}>(({{
    items: [],
    current: null,
    loading: false,
    error: null,
    page: 1,
    totalCount: 0,
  }}));

  async function fetchAll(params?: FetchParams) {{
    setState('loading', true);
    setState('error', null);

    try {{
      const data = await fetch{name}List(params ?? {{}});
      setState('items', data.items);
      setState('totalCount', data.count);
      if (params?.page) setState('page', params.page);
    }} catch (e) {{
      setState('error', e instanceof Error ? e.message : 'Failed to fetch');
      throw e;
    }} finally {{
      setState('loading', false);
    }}
  }}

  async function fetchOne(id: number | string) {{
    setState('loading', true);
    setState('error', null);

    try {{
      const data = await fetch{name}Detail(id);
      setState('current', data);
      return data;
    }} catch (e) {{
      setState('error', e instanceof Error ? e.message : 'Failed to fetch');
      throw e;
    }} finally {{
      setState('loading', false);
    }}
  }}

  async function create(input: {name}CreateInput): Promise<{name}> {{
    setState('loading', true);
    setState('error', null);

    try {{
      const data = await apiRequest<{name}>('{endpoint}', {{
        method: 'POST',
        body: JSON.stringify(input),
      }});

      setState(
        produce((s) => {{
          s.items.unshift(data);
          s.totalCount += 1;
        }})
      );

      return data;
    }} catch (e) {{
      setState('error', e instanceof Error ? e.message : 'Failed to create');
      throw e;
    }} finally {{
      setState('loading', false);
    }}
  }}

  async function update(id: number | string, input: {name}UpdateInput): Promise<{name}> {{
    setState('loading', true);
    setState('error', null);

    try {{
      const data = await apiRequest<{name}>(`{endpoint}/${{id}}`, {{
        method: 'PATCH',
        body: JSON.stringify(input),
      }});

      setState(
        produce((s) => {{
          const idx = s.items.findIndex((item) => item.id === data.id);
          if (idx !== -1) s.items[idx] = data;
          if (s.current?.id === data.id) s.current = data;
        }})
      );

      return data;
    }} catch (e) {{
      setState('error', e instanceof Error ? e.message : 'Failed to update');
      throw e;
    }} finally {{
      setState('loading', false);
    }}
  }}

  async function remove(id: number | string): Promise<void> {{
    setState('loading', true);
    setState('error', null);

    try {{
      await apiRequest(`{endpoint}/${{id}}`, {{ method: 'DELETE' }});

      setState(
        produce((s) => {{
          s.items = s.items.filter((item) => item.id !== id);
          s.totalCount -= 1;
          if (s.current?.id === id) s.current = null;
        }})
      );
    }} catch (e) {{
      setState('error', e instanceof Error ? e.message : 'Failed to delete');
      throw e;
    }} finally {{
      setState('loading', false);
    }}
  }}

  function reset() {{
    setState({{
      items: [],
      current: null,
      loading: false,
      error: null,
      page: 1,
      totalCount: 0,
    }});
  }}

  return {{
    state,
    fetchAll,
    fetchOne,
    create,
    update,
    remove,
    reset,
  }};
}}
'''


def generate_solid_form(
    model: Type[models.Model],
    mode: str = "create",
) -> str:
    """
    Generate a SolidJS form component for a Django model.

    Args:
        model: Django model class
        mode: "create" or "edit"

    Returns:
        SolidJS component code (TSX)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)

    # Get editable fields
    fields = [f for f in info.fields if f.is_editable and not f.is_auto and not f.is_primary_key]

    # Generate form fields
    form_fields = "\n\n".join(_field_to_form_input(f) for f in fields)

    # Generate initial values
    initial_values = ",\n      ".join(
        f"{f.name}: {_get_field_default(f)}" for f in fields
    )

    is_edit = mode == "edit"
    title = f"Edit {name}" if is_edit else f"Create {name}"
    submit_text = "Save Changes" if is_edit else f"Create {name}"

    return f'''/**
 * SolidJS form component for {name}.
 * Auto-generated from Django model {info.full_name}.
 */

import {{ createSignal }} from 'solid-js';
import {{ createStore }} from 'solid-js/store';
import type {{ {name}CreateInput }} from './types';

interface {name}FormProps {{
  initial?: Partial<{name}CreateInput>;
  {'id: number | string;' if is_edit else ''}
  onSuccess?: (data: {name}CreateInput) => void;
  onCancel?: () => void;
  onSubmit: (data: {name}CreateInput) => Promise<void>;
}}

export function {name}{'Edit' if is_edit else ''}Form(props: {name}FormProps) {{
  const [formData, setFormData] = createStore<{name}CreateInput>({{
    {initial_values},
    ...props.initial,
  }});

  const [isSubmitting, setIsSubmitting] = createSignal(false);
  const [errorMessage, setErrorMessage] = createSignal<string | null>(null);

  async function handleSubmit(e: Event) {{
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {{
      await props.onSubmit(formData);
      props.onSuccess?.(formData);
    }} catch (err) {{
      setErrorMessage(err instanceof Error ? err.message : 'An error occurred');
    }} finally {{
      setIsSubmitting(false);
    }}
  }}

  return (
    <form onSubmit={{handleSubmit}} class="{name_lower}-form">
      <h2>{title}</h2>

      {{errorMessage() && (
        <div class="alert alert-error" role="alert">
          {{errorMessage()}}
        </div>
      )}}

{form_fields}

      <div class="form-actions">
        <button
          type="button"
          onClick={{() => props.onCancel?.()}}
          class="btn btn-secondary"
          disabled={{isSubmitting()}}
        >
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" disabled={{isSubmitting()}}>
          {{isSubmitting() ? 'Saving...' : '{submit_text}'}}
        </button>
      </div>
    </form>
  );
}}

export default {name}{'Edit' if is_edit else ''}Form;
'''


def generate_solid_list(
    model: Type[models.Model],
) -> str:
    """
    Generate a SolidJS list component for a Django model.

    Args:
        model: Django model class

    Returns:
        SolidJS component code (TSX)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)
    name_plural = f"{name_lower}s"

    # Get display fields (first 5 non-auto fields)
    display_fields = [f for f in info.fields if not f.is_auto][:5]

    # Generate table headers
    headers = "\n            ".join(
        f"<th>{f.verbose_name.title()}</th>" for f in display_fields
    )

    # Generate table cells
    cells = "\n              ".join(
        f"<td>{{item.{f.name}}}</td>" for f in display_fields
    )

    return f'''/**
 * SolidJS list component for {name}.
 * Auto-generated from Django model {info.full_name}.
 */

import {{ createSignal, createEffect, For, Show }} from 'solid-js';
import {{ create{name}Store }} from './{name_lower}-resource';

interface {name}ListProps {{
  onSelect?: (id: number | string) => void;
  onCreate?: () => void;
}}

export function {name}List(props: {name}ListProps) {{
  const store = create{name}Store();
  const [searchQuery, setSearchQuery] = createSignal('');
  const [deleteConfirmId, setDeleteConfirmId] = createSignal<number | string | null>(null);

  // Load initial data
  createEffect(() => {{
    store.fetchAll();
  }});

  function handleSearch(e: Event) {{
    const value = (e.target as HTMLInputElement).value;
    setSearchQuery(value);
    store.fetchAll({{ search: value, page: 1 }});
  }}

  function handlePageChange(newPage: number) {{
    store.fetchAll({{ page: newPage, search: searchQuery() }});
  }}

  async function handleDelete(id: number | string) {{
    if (deleteConfirmId() === id) {{
      await store.remove(id);
      setDeleteConfirmId(null);
    }} else {{
      setDeleteConfirmId(id);
    }}
  }}

  const hasMore = () => {{
    const s = store.state;
    return s.page * 20 < s.totalCount;
  }};

  return (
    <div class="{name_lower}-list">
      <div class="list-header">
        <h2>{name}s</h2>
        <Show when={{props.onCreate}}>
          <button class="btn btn-primary" onClick={{props.onCreate}}>
            Add {name}
          </button>
        </Show>
      </div>

      <div class="search-bar">
        <input
          type="search"
          placeholder="Search {name_plural}..."
          value={{searchQuery()}}
          onInput={{handleSearch}}
          class="search-input"
        />
      </div>

      <Show when={{store.state.error}}>
        <div class="alert alert-error" role="alert">
          {{store.state.error}}
        </div>
      </Show>

      <Show when={{store.state.loading}}>
        <div class="loading">Loading...</div>
      </Show>

      <Show when={{!store.state.loading && store.state.items.length === 0}}>
        <div class="empty-state">
          <p>No {name_plural} found.</p>
        </div>
      </Show>

      <Show when={{!store.state.loading && store.state.items.length > 0}}>
        <table class="data-table">
          <thead>
            <tr>
              {headers}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <For each={{store.state.items}}>
              {{(item) => (
                <tr>
                  {cells}
                  <td class="actions">
                    <Show when={{props.onSelect}}>
                      <button
                        class="btn btn-sm"
                        onClick={{() => props.onSelect?.(item.id)}}
                      >
                        View
                      </button>
                    </Show>
                    <Show
                      when={{deleteConfirmId() === item.id}}
                      fallback={{
                        <button
                          class="btn btn-sm btn-danger"
                          onClick={{() => handleDelete(item.id)}}
                        >
                          Delete
                        </button>
                      }}
                    >
                      <button
                        class="btn btn-sm btn-danger"
                        onClick={{() => handleDelete(item.id)}}
                      >
                        Confirm
                      </button>
                      <button
                        class="btn btn-sm"
                        onClick={{() => setDeleteConfirmId(null)}}
                      >
                        Cancel
                      </button>
                    </Show>
                  </td>
                </tr>
              )}}
            </For>
          </tbody>
        </table>

        <div class="pagination">
          <button
            class="btn btn-sm"
            disabled={{store.state.page <= 1}}
            onClick={{() => handlePageChange(store.state.page - 1)}}
          >
            Previous
          </button>
          <span class="page-info">
            Page {{store.state.page}} ({{store.state.totalCount}} total)
          </span>
          <button
            class="btn btn-sm"
            disabled={{!hasMore()}}
            onClick={{() => handlePageChange(store.state.page + 1)}}
          >
            Next
          </button>
        </div>
      </Show>
    </div>
  );
}}

export default {name}List;
'''


def generate_solid_detail(
    model: Type[models.Model],
) -> str:
    """
    Generate a SolidJS detail component for a Django model.

    Args:
        model: Django model class

    Returns:
        SolidJS component code (TSX)
    """
    info = ModelIntrospector(model).introspect()
    name = info.name
    name_lower = _to_camel_case(name)

    # Generate field displays
    field_displays = "\n          ".join(
        f'''<div class="field">
            <dt>{f.verbose_name.title()}</dt>
            <dd>{{resource.data?.{f.name} ?? '-'}}</dd>
          </div>'''
        for f in info.fields
    )

    return f'''/**
 * SolidJS detail component for {name}.
 * Auto-generated from Django model {info.full_name}.
 */

import {{ createEffect, Show }} from 'solid-js';
import {{ create{name}DetailResource }} from './{name_lower}-resource';

interface {name}DetailProps {{
  id: number | string;
  onEdit?: (id: number | string) => void;
  onBack?: () => void;
}}

export function {name}Detail(props: {name}DetailProps) {{
  const resource = create{name}DetailResource(() => props.id);

  return (
    <div class="{name_lower}-detail">
      <Show when={{resource.loading}}>
        <div class="loading">Loading...</div>
      </Show>

      <Show when={{resource.error}}>
        <div class="alert alert-error" role="alert">
          {{resource.error?.message || 'An error occurred'}}
        </div>
      </Show>

      <Show when={{resource.data}}>
        <div class="detail-header">
          <h2>{name} Details</h2>
          <div class="actions">
            <Show when={{props.onBack}}>
              <button class="btn btn-secondary" onClick={{props.onBack}}>
                Back
              </button>
            </Show>
            <Show when={{props.onEdit}}>
              <button
                class="btn btn-primary"
                onClick={{() => props.onEdit?.(props.id)}}
              >
                Edit
              </button>
            </Show>
          </div>
        </div>

        <dl class="detail-fields">
          {field_displays}
        </dl>
      </Show>

      <Show when={{!resource.loading && !resource.data && !resource.error}}>
        <div class="not-found">
          <p>{name} not found.</p>
          <Show when={{props.onBack}}>
            <button class="btn btn-secondary" onClick={{props.onBack}}>
              Go Back
            </button>
          </Show>
        </div>
      </Show>
    </div>
  );
}}

export default {name}Detail;
'''


class SolidGenerator(CodeGenerator):
    """
    Generate SolidJS components and resources from Django models.

    Usage:
        gen = SolidGenerator([User, Post, Comment])
        gen.generate_all()
    """

    def __init__(
        self,
        models: List[Type[models.Model]],
        output_dir: str = "./generated",
        api_base: str = "/api",
    ):
        super().__init__(output_dir)
        self.models = models
        self.api_base = api_base
        self.model_infos = {
            m._meta.object_name: ModelIntrospector(m).introspect()
            for m in models
        }

    def generate_types_file(self) -> CodeFile:
        """Generate a types.ts file with all interfaces."""
        file = CodeFile()
        file.header_comment = "Auto-generated TypeScript types from Django models.\nDo not edit manually."

        for model in self.models:
            ts_code = generate_typescript_interface(model)
            file.add_node(Statement(ts_code))

        return file

    def generate_resource_file(self, model: Type[models.Model]) -> str:
        """Generate resource file for a model."""
        return generate_solid_resource(model, self.api_base)

    def generate_form_component(self, model: Type[models.Model], mode: str = "create") -> str:
        """Generate form component for a model."""
        return generate_solid_form(model, mode)

    def generate_list_component(self, model: Type[models.Model]) -> str:
        """Generate list component for a model."""
        return generate_solid_list(model)

    def generate_detail_component(self, model: Type[models.Model]) -> str:
        """Generate detail component for a model."""
        return generate_solid_detail(model)

    def generate_all(self) -> Dict[str, str]:
        """Generate all SolidJS files."""
        files = {}

        # Types file
        types_file = self.generate_types_file()
        files["types.ts"] = types_file.to_typescript()

        # Per-model files
        for model in self.models:
            info = self.model_infos[model._meta.object_name]
            name_lower = _to_camel_case(info.name)

            # Resources
            files[f"{name_lower}-resource.ts"] = self.generate_resource_file(model)

            # Components
            files[f"{info.name}Form.tsx"] = self.generate_form_component(model, "create")
            files[f"{info.name}EditForm.tsx"] = self.generate_form_component(model, "edit")
            files[f"{info.name}List.tsx"] = self.generate_list_component(model)
            files[f"{info.name}Detail.tsx"] = self.generate_detail_component(model)

        return files


__all__ = [
    "SolidGenerator",
    "generate_solid_resource",
    "generate_solid_form",
    "generate_solid_list",
    "generate_solid_detail",
]
