# Organizations

Top-level tenant management for B2B applications.

## Model

```python
from django_matt.multitenancy import Organization

class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Billing
    plan = models.CharField(max_length=50, default="free")
    stripe_customer_id = models.CharField(max_length=255, blank=True)
```

## Controller

```python
from django_matt.multitenancy import OrganizationController

api.register_controller(OrganizationController, prefix="/organizations")

# Endpoints:
# GET /organizations/ - List user's organizations
# POST /organizations/ - Create organization
# GET /organizations/{id} - Get organization
# PUT /organizations/{id} - Update organization
# DELETE /organizations/{id} - Delete organization
# GET /organizations/{id}/members - List members
# POST /organizations/{id}/invite - Invite user
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
    org = request.org
    return await Project.objects.filter(organization=org)
```
