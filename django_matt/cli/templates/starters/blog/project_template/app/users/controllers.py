"""Auth controller."""

from django_matt.auth import create_access_token, create_refresh_token, jwt_required
from django_matt.auth.jwt_builtin import decode_jwt
from django_matt.core import APIController
from django_matt.core.errors import AuthenticationAPIError, ValidationAPIError
from django_matt.core.router import get, post

from {{ project_name }}_app.users.models import User
from {{ project_name }}_app.users.schemas import (
    LoginSchema,
    RefreshResponse,
    RefreshSchema,
    RegisterSchema,
    TokenResponse,
    UserSchema,
)


class AuthController(APIController):
    prefix = "/auth"
    tags = ["Auth"]

    @post("/register")
    async def register(self, request, body: RegisterSchema) -> TokenResponse:
        if await User.objects.filter(email=body.email).aexists():
            raise ValidationAPIError("Email already registered.")
        if await User.objects.filter(username=body.username).aexists():
            raise ValidationAPIError("Username already taken.")

        user = await User.objects.acreate_user(
            username=body.username,
            email=body.email,
            password=body.password,
        )
        access = create_access_token(user)
        refresh = create_refresh_token(user)
        return TokenResponse(
            access=access,
            refresh=refresh,
            user=UserSchema.model_validate(user),
        )

    @post("/login")
    async def login(self, request, body: LoginSchema) -> TokenResponse:
        user = await User.objects.filter(email=body.email).afirst()
        if user is None or not await user.acheck_password(body.password):
            raise AuthenticationAPIError("Invalid email or password.")

        access = create_access_token(user)
        refresh = create_refresh_token(user)
        return TokenResponse(
            access=access,
            refresh=refresh,
            user=UserSchema.model_validate(user),
        )

    @post("/refresh")
    async def refresh_token(self, request, body: RefreshSchema) -> RefreshResponse:
        try:
            payload = decode_jwt(body.refresh)
        except Exception:
            raise AuthenticationAPIError("Invalid refresh token.")
        return RefreshResponse(access=create_access_token(payload))

    @get("/me")
    @jwt_required
    async def me(self, request) -> UserSchema:
        user = await User.objects.aget(id=request.user.id)
        return UserSchema.model_validate(user)
