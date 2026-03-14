import orjson
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.keys.models import APIKey
from apps.keys.schemas import (
    APIKeyCreatedSchema,
    APIKeyCreateSchema,
    APIKeySchema,
)
from apps.organizations.controllers.utils import get_membership, require_admin
from apps.projects.models import Project


async def _get_project_or_404(org_id: str, project_id: str) -> Project:
    """Fetch a project scoped to the organization or raise 404."""
    project = await Project.objects.filter(
        id=project_id,
        organization_id=org_id,
    ).afirst()
    if not project:
        raise NotFoundAPIError("Project not found")
    return project


class APIKeyController(APIController):
    prefix = "/organizations/{org_id}/projects/{project_id}/keys"
    tags = ["API Keys"]

    @staticmethod
    @jwt_required
    async def list_keys(request, org_id: str, project_id: str) -> dict:
        """List active API keys for a project."""
        await get_membership(request.user, org_id)
        await _get_project_or_404(org_id, project_id)

        keys = APIKey.objects.filter(
            project_id=project_id,
            is_active=True,
        ).order_by("-created_at")

        items = []
        async for key in keys:
            items.append(
                APIKeySchema(
                    id=str(key.id),
                    project_id=str(key.project_id),
                    name=key.name,
                    key_prefix=key.key_prefix,
                    scopes=key.scopes,
                    is_active=key.is_active,
                    last_used_at=key.last_used_at,
                    expires_at=key.expires_at,
                    created_by_id=key.created_by_id,
                    created_at=key.created_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_key(request, org_id: str, project_id: str) -> dict:
        """Create a new API key. Returns the full key only once."""
        await require_admin(request.user, org_id)
        await _get_project_or_404(org_id, project_id)

        body = orjson.loads(request.body)
        data = APIKeyCreateSchema(**body)

        full_key, prefix, key_hash = APIKey.generate_key()

        key = await APIKey.objects.acreate(
            project_id=project_id,
            name=data.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=data.scopes,
            expires_at=data.expires_at,
            created_by=request.user,
        )

        return APIKeyCreatedSchema(
            id=str(key.id),
            project_id=str(key.project_id),
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            is_active=key.is_active,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            created_by_id=key.created_by_id,
            created_at=key.created_at,
            full_key=full_key,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def rotate_key(request, org_id: str, project_id: str, key_id: str) -> dict:
        """Rotate an API key: deactivate old, create new with same config."""
        await require_admin(request.user, org_id)
        await _get_project_or_404(org_id, project_id)

        old_key = await APIKey.objects.filter(
            id=key_id,
            project_id=project_id,
            is_active=True,
        ).afirst()

        if not old_key:
            raise NotFoundAPIError("API key not found")

        # Deactivate old key
        old_key.is_active = False
        await old_key.asave(update_fields=["is_active", "updated_at"])

        # Create new key with same config
        full_key, prefix, key_hash = APIKey.generate_key()

        new_key = await APIKey.objects.acreate(
            project_id=project_id,
            name=old_key.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=old_key.scopes,
            expires_at=old_key.expires_at,
            created_by=request.user,
        )

        return APIKeyCreatedSchema(
            id=str(new_key.id),
            project_id=str(new_key.project_id),
            name=new_key.name,
            key_prefix=new_key.key_prefix,
            scopes=new_key.scopes,
            is_active=new_key.is_active,
            last_used_at=new_key.last_used_at,
            expires_at=new_key.expires_at,
            created_by_id=new_key.created_by_id,
            created_at=new_key.created_at,
            full_key=full_key,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def revoke_key(request, org_id: str, project_id: str, key_id: str) -> dict:
        """Revoke an API key (soft delete by setting is_active=False)."""
        await require_admin(request.user, org_id)
        await _get_project_or_404(org_id, project_id)

        key = await APIKey.objects.filter(
            id=key_id,
            project_id=project_id,
            is_active=True,
        ).afirst()

        if not key:
            raise NotFoundAPIError("API key not found")

        key.is_active = False
        await key.asave(update_fields=["is_active", "updated_at"])

        return {"message": "API key revoked"}
