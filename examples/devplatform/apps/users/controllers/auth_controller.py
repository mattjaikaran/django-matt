import orjson
from django.contrib.auth.hashers import check_password, make_password
from django_matt.auth import create_token_pair, jwt_required, refresh_tokens
from django_matt.core import APIController
from django_matt.core.errors import APIError, ValidationAPIError

from apps.users.models import User
from apps.users.schemas import (
    ChangePasswordSchema,
    LoginSchema,
    TokenSchema,
    UserCreateSchema,
    UserSchema,
    UserUpdateSchema,
)


class AuthController(APIController):
    tags = ["Auth"]

    @staticmethod
    async def register(request) -> dict:
        body = orjson.loads(request.body)
        data = UserCreateSchema(**body)

        if await User.objects.filter(email=data.email).aexists():
            raise ValidationAPIError("Email already registered")
        if await User.objects.filter(username=data.username).aexists():
            raise ValidationAPIError("Username already taken")

        user = await User.objects.acreate(
            email=data.email,
            username=data.username,
            password=make_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
        )
        return UserSchema.model_validate(user).model_dump(mode="json")

    @staticmethod
    async def login(request) -> dict:
        body = orjson.loads(request.body)
        data = LoginSchema(**body)

        try:
            user = await User.objects.aget(email=data.email)
        except User.DoesNotExist:
            raise APIError(status_code=401, message="Invalid credentials")

        if not check_password(data.password, user.password):
            raise APIError(status_code=401, message="Invalid credentials")

        if not user.is_active:
            raise APIError(status_code=401, message="Account is disabled")

        tokens = create_token_pair(user)
        return TokenSchema(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        ).model_dump()

    @staticmethod
    async def refresh(request) -> dict:
        body = orjson.loads(request.body)
        data = {"refresh_token": body.get("refresh_token", "")}
        tokens = refresh_tokens(data["refresh_token"])
        return TokenSchema(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        ).model_dump()

    @staticmethod
    @jwt_required
    async def me(request) -> dict:
        return UserSchema.model_validate(request.user).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_me(request) -> dict:
        body = orjson.loads(request.body)
        data = UserUpdateSchema(**body)
        user = request.user
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()
        return UserSchema.model_validate(user).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def change_password(request) -> dict:
        body = orjson.loads(request.body)
        data = ChangePasswordSchema(**body)
        user = request.user

        if not check_password(data.current_password, user.password):
            raise ValidationAPIError("Current password is incorrect")

        user.password = make_password(data.new_password)
        await user.asave(update_fields=["password"])
        return {"message": "Password changed successfully"}
