from pydantic import BaseModel


class SearchResultSchema(BaseModel):
    id: str
    name: str
    type: str
    description: str = ""
    price: float | None = None
    image_url: str | None = None
    url: str


class SearchResponseSchema(BaseModel):
    results: list[SearchResultSchema]
    total: int
    query: str


class FacetValueSchema(BaseModel):
    value: str
    count: int


class FacetSchema(BaseModel):
    name: str
    values: list[FacetValueSchema]
