# Teams

Sub-groups within organizations for finer-grained access control.

## Model

```python
from django_matt.multitenancy import Team

class Team(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Controller

```python
from django_matt.multitenancy import TeamController

api.register_controller(TeamController, prefix="/teams")

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
from django_matt.multitenancy import Team, TeamMembership

# Create team
team = await Team.objects.acreate(
    organization=org,
    name="Engineering",
)

# Add user to team
await TeamMembership.objects.acreate(
    team=team,
    user=user,
)
```
