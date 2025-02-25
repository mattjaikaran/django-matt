from django.db import models
import pydantic

class {{ModelName}}(models.Model):
    """Auto-generated TypeScript interface: {{ModelName}}Interface"""
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        abstract = {% raw %}{{is_abstract}}{% endraw %}

class {{ModelName}}Schema(pydantic.BaseModel):
    id: int
    created_at: datetime
    
    @classmethod
    def from_orm(cls, instance: {{ModelName}}) -> "{{ModelName}}Schema":
        return cls(**model_dump(instance))
