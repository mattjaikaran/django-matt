# Basic CRUD API

## Simple Blog API

```python
# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

```python
# schemas.py
from django_matt.core import ModelSchema
from .models import Post

class PostSchema(ModelSchema):
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "content", "author_id", "published", "created_at"]

class PostCreate(ModelSchema):
    class Meta:
        model = Post
        fields = ["title", "content"]

class PostUpdate(ModelSchema):
    class Meta:
        model = Post
        fields = ["title", "content", "published"]
        fields_optional = "__all__"
```

```python
# api.py
from django_matt import MattAPI
from django_matt.core import CRUDController
from django_matt.permissions import IsAuthenticated, IsOwner
from django_matt.auth import jwt_required

from .models import Post
from .schemas import PostSchema, PostCreate, PostUpdate

api = MattAPI(title="Blog API", version="1.0.0")

@api.controller("/posts", tags=["Posts"])
class PostController(CRUDController):
    model = Post
    schema = PostSchema
    create_schema = PostCreate
    update_schema = PostUpdate

    # Public list, authenticated create
    permission_classes = []

    def get_queryset(self, request):
        qs = Post.objects.select_related("author")
        if not request.user.is_authenticated:
            qs = qs.filter(published=True)
        return qs

    @api.post("/")
    @jwt_required
    async def create(self, request, data: PostCreate):
        from django.utils.text import slugify
        post = await Post.objects.acreate(
            author=request.user,
            slug=slugify(data.title),
            **data.dict()
        )
        return PostSchema.from_orm(post)

    @api.put("/{id}")
    @jwt_required
    @IsOwner(owner_field="author_id")
    async def update(self, request, id: int, data: PostUpdate):
        post = await self.get_object(id)
        for key, value in data.dict(exclude_unset=True).items():
            setattr(post, key, value)
        await post.asave()
        return PostSchema.from_orm(post)

    @api.delete("/{id}")
    @jwt_required
    @IsOwner(owner_field="author_id")
    async def delete(self, request, id: int):
        post = await self.get_object(id)
        await post.adelete()
        return {"success": True}
```
