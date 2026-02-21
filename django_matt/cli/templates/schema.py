"""
Schema template generation.
"""


def generate_schema_template(name: str) -> str:
    """
    Generate a Pydantic schema template.

    Args:
        name: The model/resource name (e.g., "Product", "User")

    Returns:
        Python code for the schemas
    """
    lines = [
        '"""',
        f"{name} Pydantic Schemas.",
        '"""',
        "",
        "from pydantic import BaseModel, Field",
        "",
        "",
        f"class {name}Schema(BaseModel):",
        f'    """Response schema for {name}."""',
        "",
        "    id: int",
        "    name: str",
        "",
        "    class Config:",
        "        from_attributes = True",
        "",
        "",
        f"class {name}CreateSchema(BaseModel):",
        f'    """Schema for creating a {name}."""',
        "",
        "    name: str = Field(max_length=255)",
        "",
        "",
        f"class {name}UpdateSchema(BaseModel):",
        f'    """Schema for updating a {name} (all fields optional)."""',
        "",
        "    name: str | None = None",
        "",
        "",
        f"class {name}ListSchema(BaseModel):",
        f'    """Schema for list of {name} objects."""',
        "",
        f"    items: list[{name}Schema]",
        "    total: int",
        "    page: int = 1",
        "    page_size: int = 20",
    ]

    return "\n".join(lines)
