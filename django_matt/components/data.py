"""
Data display components.

Provides tables, lists, detail views, and pagination
for displaying structured data.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from django_matt.components.base import (
    Component,
    ComponentTree,
    ComponentType,
    registry,
)

# =============================================================================
# Table Components
# =============================================================================


class TableColumn(BaseModel):
    """Definition for a table column."""

    key: str  # Data key
    label: str  # Header label
    sortable: bool = False
    filterable: bool = False
    width: str | None = None  # CSS width
    align: Literal["left", "center", "right"] = "left"
    hidden: bool = False
    format: str | None = None  # Format string (e.g., "currency", "date", "number")
    render: str | None = None  # Custom render component type
    cell_class: str | None = None
    header_class: str | None = None


class TableAction(BaseModel):
    """Row action for tables."""

    label: str
    icon: str | None = None
    action: str  # URL pattern with {id} placeholder
    method: str = "GET"
    variant: Literal["default", "destructive", "outline"] = "default"
    confirm: str | None = None  # Confirmation message


@registry.register("data_table", aliases=["table"])
class DataTable(Component):
    """
    Data table component with sorting, filtering, and pagination.

    Usage:
        users_table = DataTable(
            columns=[
                TableColumn(key="id", label="ID", sortable=True),
                TableColumn(key="name", label="Name", sortable=True, filterable=True),
                TableColumn(key="email", label="Email", sortable=True),
                TableColumn(key="created_at", label="Created", format="date"),
            ],
            data=[...],  # List of dicts
            actions=[
                TableAction(label="Edit", action="/users/{id}/edit"),
                TableAction(label="Delete", action="/users/{id}", method="DELETE", variant="destructive"),
            ],
            selectable=True,
            pagination=True,
        )
    """

    type: ComponentType = ComponentType.DATA_TABLE
    columns: list[TableColumn] = Field(default_factory=list)
    data: list[dict[str, Any]] = Field(default_factory=list)
    row_key: str = "id"  # Key for unique row identification
    actions: list[TableAction] = Field(default_factory=list)

    # Features
    sortable: bool = True
    default_sort: str | None = None
    default_sort_direction: Literal["asc", "desc"] = "asc"

    filterable: bool = True
    search_placeholder: str = "Search..."

    selectable: bool = False
    select_mode: Literal["single", "multiple"] = "multiple"
    on_selection_change: str | None = None  # Callback URL

    # Pagination
    pagination: bool = True
    page_size: int = 10
    page_size_options: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])
    total_count: int | None = None
    current_page: int = 1

    # Appearance
    striped: bool = False
    bordered: bool = False
    compact: bool = False
    hover: bool = True
    sticky_header: bool = False
    empty_message: str = "No data available"
    loading_message: str = "Loading..."

    # Data source (for server-side)
    data_url: str | None = None  # URL for fetching data
    server_side: bool = False  # Enable server-side processing

    def add_column(
        self,
        key: str,
        label: str,
        **kwargs,
    ) -> "DataTable":
        """Add a column to the table."""
        self.columns.append(TableColumn(key=key, label=label, **kwargs))
        return self

    def add_action(
        self,
        label: str,
        action: str,
        **kwargs,
    ) -> "DataTable":
        """Add a row action."""
        self.actions.append(TableAction(label=label, action=action, **kwargs))
        return self


# =============================================================================
# List Components
# =============================================================================


@registry.register("list", aliases=["list_view"])
class List(Component):
    """
    List display component.

    Usage:
        users_list = List(
            items=[...],
            item_template="user_card",
            layout="grid",
            columns=3,
        )
    """

    type: ComponentType = ComponentType.LIST
    items: list[dict[str, Any]] = Field(default_factory=list)
    item_key: str = "id"
    item_template: str | None = None  # Component type for each item
    layout: Literal["list", "grid", "masonry"] = "list"
    columns: int = 1  # Grid columns
    gap: str = "1rem"
    empty_message: str = "No items"
    loading_message: str = "Loading..."

    # Infinite scroll
    infinite_scroll: bool = False
    load_more_url: str | None = None
    has_more: bool = False

    # Selection
    selectable: bool = False
    select_mode: Literal["single", "multiple"] = "single"


# =============================================================================
# Detail View
# =============================================================================


class DetailField(BaseModel):
    """Field definition for detail view."""

    key: str
    label: str
    format: str | None = None  # date, currency, boolean, etc.
    hidden: bool = False
    copy_button: bool = False  # Show copy to clipboard
    link: str | None = None  # Make value a link


@registry.register("detail_view", aliases=["detail"])
class DetailView(Component):
    """
    Detail view component for displaying a single record.

    Usage:
        user_detail = DetailView(
            fields=[
                DetailField(key="name", label="Name"),
                DetailField(key="email", label="Email", copy_button=True),
                DetailField(key="created_at", label="Created", format="date"),
            ],
            data={"name": "John", "email": "john@example.com", ...},
            layout="vertical",
        )
    """

    type: ComponentType = ComponentType.DETAIL_VIEW
    fields: list[DetailField] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    layout: Literal["vertical", "horizontal", "grid"] = "vertical"
    columns: int = 2  # For grid layout
    show_empty: bool = True  # Show fields with empty values
    empty_value: str = "-"
    title: str | None = None
    actions: ComponentTree | None = None  # Action buttons

    def add_field(self, key: str, label: str, **kwargs) -> "DetailView":
        """Add a field."""
        self.fields.append(DetailField(key=key, label=label, **kwargs))
        return self


# =============================================================================
# Pagination
# =============================================================================


@registry.register("pagination")
class Pagination(Component):
    """
    Pagination component.

    Usage:
        pager = Pagination(
            current_page=1,
            total_pages=10,
            total_items=100,
            page_size=10,
            on_change="/users?page={page}",
        )
    """

    type: ComponentType = ComponentType.PAGINATION
    current_page: int = 1
    total_pages: int = 1
    total_items: int | None = None
    page_size: int = 10
    page_size_options: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])
    show_page_size: bool = True
    show_total: bool = True
    show_quick_jump: bool = False  # Jump to page input
    on_change: str | None = None  # URL pattern with {page} placeholder
    max_visible_pages: int = 5  # Max page buttons to show
    variant: Literal["default", "simple", "minimal"] = "default"


# =============================================================================
# Search
# =============================================================================


@registry.register("search_input", aliases=["search"])
class SearchInput(Component):
    """
    Search input with debounce and suggestions.

    Usage:
        search = SearchInput(
            placeholder="Search users...",
            search_url="/api/users/search",
            debounce_ms=300,
            show_suggestions=True,
        )
    """

    type: ComponentType = ComponentType.TEXT_FIELD
    placeholder: str = "Search..."
    search_url: str | None = None  # URL for search requests
    param_name: str = "q"  # Query parameter name
    debounce_ms: int = 300
    min_length: int = 2  # Min chars before searching
    show_suggestions: bool = False
    suggestions_url: str | None = None
    show_clear: bool = True
    show_icon: bool = True
    full_width: bool = False
    on_search: str | None = None  # Callback URL


# =============================================================================
# Stats & Metrics
# =============================================================================


class StatItem(BaseModel):
    """Individual stat item."""

    label: str
    value: str | int | float
    change: float | None = None  # Percentage change
    change_label: str | None = None
    icon: str | None = None
    trend: Literal["up", "down", "neutral"] | None = None
    format: str | None = None


@registry.register("stats", aliases=["metrics"])
class Stats(Component):
    """
    Stats/metrics display component.

    Usage:
        dashboard_stats = Stats(
            items=[
                StatItem(label="Users", value=1234, change=12.5, trend="up"),
                StatItem(label="Revenue", value="$12,345", change=-5.2, trend="down"),
                StatItem(label="Orders", value=89, trend="neutral"),
            ],
            columns=4,
        )
    """

    type: ComponentType = ComponentType.CONTAINER
    items: list[StatItem] = Field(default_factory=list)
    columns: int = 4
    variant: Literal["default", "card", "minimal"] = "default"

    def add_stat(self, label: str, value: Any, **kwargs) -> "Stats":
        """Add a stat item."""
        self.items.append(StatItem(label=label, value=value, **kwargs))
        return self


# =============================================================================
# Empty State
# =============================================================================


@registry.register("empty_state", aliases=["empty"])
class EmptyState(Component):
    """
    Empty state component for when there's no data.

    Usage:
        empty = EmptyState(
            icon="inbox",
            title="No messages",
            description="You don't have any messages yet.",
            action=Button(label="Send a message"),
        )
    """

    type: ComponentType = ComponentType.CONTAINER
    icon: str | None = None
    title: str = "No data"
    description: str | None = None
    action: Component | None = None


# =============================================================================
# Skeleton
# =============================================================================


@registry.register("skeleton")
class Skeleton(Component):
    """
    Skeleton loading placeholder.

    Usage:
        loading = Skeleton(variant="card", count=3)
    """

    type: ComponentType = ComponentType.CONTAINER
    variant: Literal["text", "circle", "rect", "card", "table-row"] = "text"
    width: str | None = None
    height: str | None = None
    count: int = 1  # Number of skeleton items
    animate: bool = True


__all__ = [
    # Table
    "TableColumn",
    "TableAction",
    "DataTable",
    # List
    "List",
    # Detail
    "DetailField",
    "DetailView",
    # Pagination
    "Pagination",
    # Search
    "SearchInput",
    # Stats
    "StatItem",
    "Stats",
    # Empty/Loading
    "EmptyState",
    "Skeleton",
]
