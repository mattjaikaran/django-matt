from django.contrib.auth.hashers import check_password, make_password
from django_matt.auth import jwt_required
from django_matt.auth.jwt import acreate_token_pair, async_refresh_tokens
from django_matt.core import APIController
from django_matt.core.errors import APIError, ValidationAPIError

from apps.users.models import User
from apps.users.schemas import (
    ChangePasswordSchema,
    LoginSchema,
    RefreshTokenSchema,
    TokenSchema,
    UserCreateSchema,
    UserSchema,
    UserUpdateSchema,
)


class AuthController(APIController):
    tags = ["Auth"]

    @staticmethod
    async def register(request, body: UserCreateSchema) -> dict:
        if await User.objects.filter(email=body.email).aexists():
            raise ValidationAPIError("Email already registered")
        if await User.objects.filter(username=body.username).aexists():
            raise ValidationAPIError("Username already taken")

        user = await User.objects.acreate(
            email=body.email,
            username=body.username,
            password=make_password(body.password),
            first_name=body.first_name,
            last_name=body.last_name,
        )
        return UserSchema.model_validate(user).model_dump(mode="json")

    @staticmethod
    async def login(request, body: LoginSchema) -> dict:
        try:
            user = await User.objects.aget(email=body.email)
        except User.DoesNotExist:
            raise APIError(status_code=401, message="Invalid credentials")

        if not check_password(body.password, user.password):
            raise APIError(status_code=401, message="Invalid credentials")

        if not user.is_active:
            raise APIError(status_code=401, message="Account is disabled")

        tokens = await acreate_token_pair(user)
        return TokenSchema(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        ).model_dump()

    @staticmethod
    async def refresh(request, body: RefreshTokenSchema) -> dict:
        tokens = await async_refresh_tokens(body.refresh_token)
        return TokenSchema(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        ).model_dump()

    @staticmethod
    @jwt_required
    async def me(request) -> dict:
        return UserSchema.model_validate(request.user).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_me(request, body: UserUpdateSchema) -> dict:
        user = request.user
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()
        return UserSchema.model_validate(user).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def change_password(request, body: ChangePasswordSchema) -> dict:
        user = request.user

        if not check_password(body.current_password, user.password):
            raise ValidationAPIError("Current password is incorrect")

        user.password = make_password(body.new_password)
        await user.asave(update_fields=["password"])
        return {"message": "Password changed successfully"}
