from ninja import Schema


class ProjectSchema(Schema):
    id: str
    title: str
    slug: str
    description: str
    tech_stack: list[str] = []
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool
    created_at: str

    class Config:
        from_attributes = True


class ProjectDetailSchema(ProjectSchema):
    long_description: str | None = None
    updated_at: str


class ProjectCreateSchema(Schema):
    title: str
    slug: str
    description: str
    long_description: str | None = None
    tech_stack: list[str] = []
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool = False
    order: int = 0


class ProjectUpdateSchema(Schema):
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    long_description: str | None = None
    tech_stack: list[str] | None = None
    image_url: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    featured: bool | None = None
    order: int | None = None
    is_published: bool | None = None
