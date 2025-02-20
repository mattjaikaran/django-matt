# CRUD Generator

## Overview
- Generate back end code for CRUD operations
- Generate Django models from Pydantic models, Pydantic models from Django models, and plain text documentation for the models
- When there are changes to the models/schemas, 
    - Automatically create migrations for the models/schemas upon save.
    - Automatically or manually apply new migrations to the database
    - Update the script
    - Update the seed data

- If fullstack/has a front end connected
    - Generate TypeScript interfaces from Django models (if applicable)
    - Generate React components from Django models (if applicable)



#### I want a way for a dev to do any of the following:
- create models in a models.py file and have the CRUD operations generated for them
```python
class User(AbstractUser):
    id: models.UUIDField(default=models.UUIDField.uuid4, editable=False, unique=True)
    first_name: models.CharField(max_length=255)
    last_name: models.CharField(max_length=255)
    email: models.EmailField(unique=True)

class AbstractModel(models.Model):
    id: models.UUIDField(default=models.UUIDField.uuid4, editable=False, unique=True)
    datetime_created: models.DateTimeField(auto_now_add=True)
    datetime_updated: models.DateTimeField(auto_now=True)

class Todo(AbstractModel):
    name: models.CharField(max_length=255)
    description: models.TextField()
    completed: models.BooleanField(default=False)
    user: models.ForeignKey(User, on_delete=models.CASCADE)
```



- create a Pydantic model and have the Django model generated for it, then generate the CRUD operations for it
```python
from pydantic import BaseModel, EmailStr
from uuid import UUID

class User(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr

class TodoCreate(BaseModel):
    name: str
    description: str
    completed: bool
    user: User

class TodoUpdate(BaseModel):
    name: str
    description: str
    completed: bool
    user: User

class Todo(BaseModel):
    id: UUID
    name: str
    description: str
    completed: bool
    user: User
```
- create a list of models and fields in a text file or Markdown file. and include permissions and permissions groups.
```
- User
    - id: UUID
    - first_name: str
    - last_name: str
    - email: EmailStr
    - permissions: list[Permission]
    - permissions_groups: list[PermissionGroup]
- Permission
    - id: UUID
    - name: str
    - description: str
- PermissionGroup
    - id: UUID  
    - name: str
    - permissions: list[Permission]

- Todo
    - id: UUID
    - name: str
    - description: str
    - completed: bool
    - user: User
    - permissions: list[Permission]
    - permissions_groups: list[PermissionGroup]
```