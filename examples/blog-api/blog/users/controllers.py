"""Auth and user controllers."""

from django.contrib.auth import authenticate
from django_matt.auth import create_access_token, create_refresh_token, jwt_required
from django_matt.core import APIController
from django_matt.core.errors import AuthenticationAPIError, NotFoundAPIError, ValidationAPIError

from blog.users.models import AuthorProfile, User
from blog.users.schemas import (
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserPublicResponse,
    UserResponse,
)


class AuthController(APIController):
    prefix = "/auth"
    tags = ["Auth"]

    @staticmethod
    async def register(data: RegisterRequest) -> TokenResponse:
        """Register a new user."""
        if await User.objects.filter(email=data.email).aexists():
            raise ValidationAPIError("A user with this email already exists.")
        if await User.objects.filter(username=data.username).aexists():
            raise ValidationAPIError("A user with this username already exists.")

        user = await User.objects.acreate_user(
            email=data.email,
            username=data.username,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        await AuthorProfile.objects.acreate(user=user)

        access = create_access_token({"sub": str(user.id), "email": user.email})
        refresh = create_refresh_token({"sub": str(user.id)})
        return TokenResponse(access=access, refresh=refresh, user=UserResponse.model_validate(user))

    @staticmethod
    async def login(data: LoginRequest) -> TokenResponse:
        """Authenticate and return tokens."""
        user = await User.objects.filter(email=data.email).select_related("author_profile").afirst()
        if user is None:
            raise AuthenticationAPIError("Invalid credentials.")

        from django.contrib.auth.hashers import check_password

        if not check_password(data.password, user.password):
            raise AuthenticationAPIError("Invalid credentials.")

        if not user.is_active:
            raise AuthenticationAPIError("This account is inactive.")

        access = create_access_token({"sub": str(user.id), "email": user.email})
        refresh = create_refresh_token({"sub": str(user.id)})
        return TokenResponse(access=access, refresh=refresh, user=UserResponse.model_validate(user))

    @staticmethod
    async def refresh_token(data: RefreshRequest) -> RefreshResponse:
        """Issue a new access token from a refresh token."""
        from django_matt.auth import decode_token, create_access_token as _create

        try:
            payload = decode_token(data.refresh)
        except Exception:
            raise AuthenticationAPIError("Invalid or expired refresh token.")

        user = await User.objects.filter(id=payload.get("sub")).afirst()
        if user is None or not user.is_active:
            raise AuthenticationAPIError("User not found or inactive.")

        access = _create({"sub": str(user.id), "email": user.email})
        return RefreshResponse(access=access)

    @jwt_required
    async def me(self, request) -> UserResponse:
        """Return current authenticated user."""
        user = await User.objects.select_related("author_profile").aget(id=request.user.id)
        return UserResponse.model_validate(user)

    @jwt_required
    async def update_profile(self, request, data: ProfileUpdateRequest) -> UserResponse:
        """Update the current user's profile."""
        user = await User.objects.select_related("author_profile").aget(id=request.user.id)

        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        await user.asave(update_fields=["first_name", "last_name"])

        profile, _ = await AuthorProfile.objects.aget_or_create(user=user)
        profile_fields = ["bio", "website", "twitter", "github", "linkedin", "location"]
        updated = []
        for field in profile_fields:
            val = getattr(data, field, None)
            if val is not None:
                setattr(profile, field, val)
                updated.append(field)
        if updated:
            await profile.asave(update_fields=updated + ["updated_at"])

        await user.arefresh_from_db()
        return UserResponse.model_validate(user)


class AuthorController(APIController):
    prefix = "/authors"
    tags = ["Authors"]

    @staticmethod
    async def list_authors() -> list[UserPublicResponse]:
        """List all authors (users who have published at least one post)."""
        users = (
            User.objects.filter(posts__status="published")
            .select_related("author_profile")
            .distinct()
        )
        return [UserPublicResponse.model_validate(u) async for u in users]

    @staticmethod
    async def get_author(username: str) -> UserPublicResponse:
        """Get a single author by username."""
        user = (
            await User.objects.select_related("author_profile")
            .filter(username=username)
            .afirst()
        )
        if user is None:
            raise NotFoundAPIError(f"Author '{username}' not found.")
        return UserPublicResponse.model_validate(user)
