# Organizations

Top-level tenant management for B2B applications.

## Model

```python
from django_matt.multitenancy import Organization

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    logo_url = models.URLField(blank=True, null=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Controller

```python
from django_matt.multitenancy import OrganizationController

api.register_controller(OrganizationController)

# Endpoints:
# GET /organizations/ - List user's organizations
# POST /organizations/ - Create organization
# GET /organizations/{id} - Get organization
# PUT /organizations/{id} - Update organization
# DELETE /organizations/{id} - Delete organization
# POST /organizations/switch - Switch to organization
```

## Usage

```python
from django_matt.multitenancy import Organization, Membership

# Create organization
org = await Organization.objects.acreate(
    name="Acme Inc",
    slug="acme",
)

# Add user as owner
await Membership.objects.acreate(
    user=user,
    organization=org,
    role="owner",
)
```

## Filtering by Organization

```python
@api.get("/projects")
async def list_projects(request):
    org = request.organization
    return await Project.objects.filter(organization=org)
```
