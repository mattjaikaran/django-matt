"""Auth and user controllers."""

from django_matt.auth import create_access_token, create_refresh_token, jwt_required
from django_matt.core import APIController
from django_matt.core.errors import AuthenticationAPIError, NotFoundAPIError, ValidationAPIError
from django_matt.core.router import get, patch, post

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

    @post("/signup")
    async def register(self, request, body: RegisterRequest) -> TokenResponse:
        if await User.objects.filter(email=body.email).aexists():
            raise ValidationAPIError("A user with this email already exists.")
        if await User.objects.filter(username=body.username).aexists():
            raise ValidationAPIError("A user with this username already exists.")

        from asgiref.sync import sync_to_async

        @sync_to_async
        def _create_user():
            return User.objects.create_user(
                email=body.email,
                username=body.username,
                password=body.password,
                first_name=body.first_name,
                last_name=body.last_name,
            )

        @sync_to_async
        def _create_profile(user):
            return AuthorProfile.objects.create(user=user)

        user = await _create_user()
        await _create_profile(user)

        access = create_access_token(user)
        refresh = create_refresh_token(user)
        return TokenResponse(access=access, refresh=refresh, user=UserResponse.model_validate(user))

    @post("/login")
    async def login(self, request, body: LoginRequest) -> TokenResponse:
        user = await User.objects.filter(email=body.email).select_related("author_profile").afirst()
        if user is None:
            raise AuthenticationAPIError("Invalid credentials.")

        from asgiref.sync import sync_to_async
        from django.contrib.auth.hashers import check_password

        if not await sync_to_async(check_password)(body.password, user.password):
            raise AuthenticationAPIError("Invalid credentials.")
        if not user.is_active:
            raise AuthenticationAPIError("This account is inactive.")
        access = create_access_token(user)
        refresh = create_refresh_token(user)
        return TokenResponse(access=access, refresh=refresh, user=UserResponse.model_validate(user))

    @post("/token/refresh")
    async def refresh_token(self, request, body: RefreshRequest) -> RefreshResponse:
        from django_matt.auth import decode_token

        try:
            payload = decode_token(body.refresh)
        except Exception:
            raise AuthenticationAPIError("Invalid or expired refresh token.")

        user = await User.objects.filter(id=payload.get("sub")).afirst()
        if user is None or not user.is_active:
            raise AuthenticationAPIError("User not found or inactive.")

        access = create_access_token({"sub": str(user.id), "email": user.email})
        return RefreshResponse(access=access)

    @get("/me")
    @jwt_required
    async def me(self, request) -> UserResponse:
        user = await User.objects.select_related("author_profile").aget(id=request.user.id)
        return UserResponse.model_validate(user)

    @patch("/me")
    @jwt_required
    async def update_profile(self, request, body: ProfileUpdateRequest) -> UserResponse:
        user = await User.objects.select_related("author_profile").aget(id=request.user.id)

        if body.first_name is not None:
            user.first_name = body.first_name
        if body.last_name is not None:
            user.last_name = body.last_name
        await user.asave(update_fields=["first_name", "last_name"])

        profile, _ = await AuthorProfile.objects.aget_or_create(user=user)
        profile_fields = ["bio", "website", "twitter", "github", "linkedin", "location"]
        updated = []
        for field in profile_fields:
            val = getattr(body, field, None)
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

    @get("/")
    async def list_authors(self) -> list[UserPublicResponse]:
        users = (
            User.objects.filter(posts__status="published")
            .select_related("author_profile")
            .distinct()
        )
        return [UserPublicResponse.model_validate(u) async for u in users]

    @get("/<str:username>")
    async def get_author(self, username: str) -> UserPublicResponse:
        user = (
            await User.objects.select_related("author_profile").filter(username=username).afirst()
        )
        if user is None:
            raise NotFoundAPIError(f"Author '{username}' not found.")
        return UserPublicResponse.model_validate(user)
