# Teams

Sub-groups within organizations for finer-grained access control.

## Model

```python
from django_matt.multitenancy import Team

class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)  # unique within org
    description = models.TextField(blank=True, null=True)
    settings = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Controller

```python
from django_matt.multitenancy import TeamController

api.register_controller(TeamController)

# Endpoints:
# GET /teams/ - List teams in organization
# POST /teams/ - Create team
# GET /teams/{id} - Get team
# PUT /teams/{id} - Update team
# DELETE /teams/{id} - Delete team
# GET /teams/{id}/members - List team members
# POST /teams/{id}/members - Add member
# DELETE /teams/{id}/members/{user_id} - Remove member
```

## Usage

```python
from django_matt.multitenancy import Membership, Team, TeamMembership

# Create team
team = await Team.objects.acreate(
    organization=org,
    name="Engineering",
)

# Add user to team
org_membership = await Membership.objects.aget(organization=org, user=user)
await TeamMembership.objects.acreate(
    team=team,
    user=user,
    organization_membership=org_membership,
)
```
