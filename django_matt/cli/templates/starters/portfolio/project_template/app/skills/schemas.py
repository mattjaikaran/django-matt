from ninja import Schema


class SkillSchema(Schema):
    id: str
    name: str
    category: str
    level: int
    icon: str | None = None
    order: int

    class Config:
        from_attributes = True


class SkillCreateSchema(Schema):
    name: str
    category: str
    level: int = 3
    icon: str | None = None
    order: int = 0


class SkillUpdateSchema(Schema):
    name: str | None = None
    category: str | None = None
    level: int | None = None
    icon: str | None = None
    order: int | None = None
