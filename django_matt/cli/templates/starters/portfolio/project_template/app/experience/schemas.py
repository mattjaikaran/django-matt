from ninja import Schema


class ExperienceSchema(Schema):
    id: str
    company: str
    role: str
    company_url: str | None = None
    location: str | None = None
    start_date: str
    end_date: str | None = None
    is_current: bool
    description: str
    tech_used: list[str] = []

    class Config:
        from_attributes = True


class ExperienceCreateSchema(Schema):
    company: str
    role: str
    company_url: str | None = None
    location: str | None = None
    start_date: str
    end_date: str | None = None
    is_current: bool = False
    description: str
    tech_used: list[str] = []
    order: int = 0


class ExperienceUpdateSchema(Schema):
    company: str | None = None
    role: str | None = None
    company_url: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    description: str | None = None
    tech_used: list[str] | None = None
    order: int | None = None
