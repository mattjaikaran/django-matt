# Data Components

Backend-served data display components for tables, lists, detail views, pagination, search, and stats dashboards. Define your UI in Python, render with any frontend framework.

## Quick Start

```python
from django_matt.components.data import DataTable, TableColumn, TableAction

users_table = DataTable(
    columns=[
        TableColumn(key="id", label="ID", sortable=True),
        TableColumn(key="name", label="Name", sortable=True, filterable=True),
        TableColumn(key="email", label="Email"),
        TableColumn(key="created_at", label="Created", format="date"),
    ],
    data=[
        {"id": 1, "name": "Alice", "email": "alice@example.com", "created_at": "2024-01-15"},
        {"id": 2, "name": "Bob", "email": "bob@example.com", "created_at": "2024-02-20"},
    ],
    actions=[
        TableAction(label="Edit", action="/users/{id}/edit"),
        TableAction(label="Delete", action="/users/{id}", method="DELETE", variant="destructive"),
    ],
    pagination=True,
    page_size=10,
)
```

## Components

### DataTable

Full-featured data table with sorting, filtering, pagination, row selection, and server-side processing.

```python
from django_matt.components.data import DataTable, TableColumn, TableAction

table = DataTable(
    columns=[...],
    data=[...],
    row_key="id",

    # Sorting
    sortable=True,
    default_sort="name",
    default_sort_direction="asc",  # "asc" | "desc"

    # Filtering
    filterable=True,
    search_placeholder="Search...",

    # Row selection
    selectable=True,
    select_mode="multiple",  # "single" | "multiple"
    on_selection_change="/api/selection",

    # Pagination
    pagination=True,
    page_size=10,
    page_size_options=[10, 25, 50, 100],
    total_count=500,
    current_page=1,

    # Appearance
    striped=False,
    bordered=False,
    compact=False,
    hover=True,
    sticky_header=False,
    empty_message="No data available",

    # Server-side data fetching
    data_url="/api/users",
    server_side=True,
)

# Fluent API
table.add_column("status", "Status", sortable=True, format="badge")
table.add_action("View", "/users/{id}", method="GET")
```

**TableColumn** fields: `key`, `label`, `sortable`, `filterable`, `width`, `align` (left/center/right), `hidden`, `format` (currency/date/number), `render`, `cell_class`, `header_class`.

**TableAction** fields: `label`, `icon`, `action` (URL with `{id}` placeholder), `method`, `variant` (default/destructive/outline), `confirm`.

### List

Flexible list display with grid/masonry layouts, infinite scroll, and item templates.

```python
from django_matt.components.data import List

users_list = List(
    items=[{"id": 1, "name": "Alice", "avatar": "/img/alice.jpg"}],
    item_key="id",
    item_template="user_card",
    layout="grid",       # "list" | "grid" | "masonry"
    columns=3,
    gap="1rem",
    empty_message="No items",

    # Infinite scroll
    infinite_scroll=True,
    load_more_url="/api/users?page=2",
    has_more=True,

    # Selection
    selectable=True,
    select_mode="single",
)
```

### DetailView

Display a single record with labeled fields and formatting.

```python
from django_matt.components.data import DetailView, DetailField

user_detail = DetailView(
    fields=[
        DetailField(key="name", label="Name"),
        DetailField(key="email", label="Email", copy_button=True),
        DetailField(key="created_at", label="Created", format="date"),
        DetailField(key="website", label="Website", link="https://{value}"),
    ],
    data={"name": "Alice", "email": "alice@example.com", "created_at": "2024-01-15"},
    layout="vertical",   # "vertical" | "horizontal" | "grid"
    columns=2,
    show_empty=True,
    empty_value="-",
    title="User Profile",
)

# Fluent API
user_detail.add_field("phone", "Phone Number", format="phone")
```

### Pagination

Standalone pagination component.

```python
from django_matt.components.data import Pagination

pager = Pagination(
    current_page=3,
    total_pages=10,
    total_items=100,
    page_size=10,
    page_size_options=[10, 25, 50, 100],
    show_page_size=True,
    show_total=True,
    show_quick_jump=False,
    on_change="/users?page={page}",
    max_visible_pages=5,
    variant="default",  # "default" | "simple" | "minimal"
)
```

### SearchInput

Search field with debounce and autocomplete suggestions.

```python
from django_matt.components.data import SearchInput

search = SearchInput(
    placeholder="Search users...",
    search_url="/api/users/search",
    param_name="q",
    debounce_ms=300,
    min_length=2,
    show_suggestions=True,
    suggestions_url="/api/users/suggest",
    show_clear=True,
    on_search="/users?q={value}",
)
```

### Stats

Dashboard stats/metrics display.

```python
from django_matt.components.data import Stats, StatItem

dashboard_stats = Stats(
    items=[
        StatItem(label="Users", value=1234, change=12.5, trend="up"),
        StatItem(label="Revenue", value="$12,345", change=-5.2, trend="down"),
        StatItem(label="Orders", value=89, trend="neutral"),
        StatItem(label="Conversion", value="3.2%", icon="chart"),
    ],
    columns=4,
    variant="card",  # "default" | "card" | "minimal"
)

# Fluent API
dashboard_stats.add_stat("Active", 42, change=8.0, trend="up")
```

### EmptyState and Skeleton

```python
from django_matt.components.data import EmptyState, Skeleton
from django_matt.components.layout import Button

empty = EmptyState(
    icon="inbox",
    title="No messages",
    description="You don't have any messages yet.",
    action=Button(label="Send a message"),
)

loading = Skeleton(variant="table-row", count=5, animate=True)
# variant: "text" | "circle" | "rect" | "card" | "table-row"
```

## Practical Example

A complete admin page with search, table, and pagination:

```python
from django_matt.components.data import DataTable, TableColumn, TableAction, SearchInput, Pagination
from django_matt.components.layout import Container, Card, Heading

admin_page = Card(
    title="Users",
    children=[
        SearchInput(placeholder="Search users...", search_url="/api/users/search"),
        DataTable(
            columns=[
                TableColumn(key="id", label="ID", sortable=True, width="60px"),
                TableColumn(key="name", label="Name", sortable=True, filterable=True),
                TableColumn(key="email", label="Email", sortable=True),
                TableColumn(key="role", label="Role", format="badge"),
                TableColumn(key="created_at", label="Joined", format="date", sortable=True),
            ],
            data=[...],
            actions=[
                TableAction(label="Edit", action="/admin/users/{id}/edit"),
                TableAction(label="Delete", action="/admin/users/{id}", method="DELETE",
                           variant="destructive", confirm="Delete this user?"),
            ],
            selectable=True,
            hover=True,
            server_side=True,
            data_url="/api/admin/users",
        ),
        Pagination(current_page=1, total_pages=10, total_items=97),
    ],
)

# Serialize to JSON for any frontend
json_data = admin_page.to_json()
```
