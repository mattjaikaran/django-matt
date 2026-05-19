from django.contrib.auth.hashers import check_password, make_password
from django_matt.auth import jwt_required
from django_matt.auth.jwt import acreate_token_pair
from django_matt.core import APIController
from django_matt.core.errors import APIError, ValidationAPIError

from apps.users.models import User
from apps.users.schemas import (
    LoginSchema,
    ProfileUpdateSchema,
    RegisterSchema,
    TokenSchema,
    UserSchema,
)


class AuthController(APIController):
    tags = ["Auth"]

    @staticmethod
    async def register(request, body: RegisterSchema) -> dict:
        if await User.objects.filter(email=body.email).aexists():
            raise ValidationAPIError("Email already registered")

        user = await User.objects.acreate(
            email=body.email,
            password=make_password(body.password),
            name=body.name,
        )
        tokens = await acreate_token_pair(user)
        return {
            "user": UserSchema(
                id=str(user.id),
                email=user.email,
                name=user.name,
                bio=user.bio,
                avatar_url=user.avatar_url,
                github_url=user.github_url,
                linkedin_url=user.linkedin_url,
                website_url=user.website_url,
                date_joined=user.date_joined,
            ).model_dump(mode="json"),
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
        }

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
    @jwt_required
    async def me(request) -> dict:
        user = request.user
        return UserSchema(
            id=str(user.id),
            email=user.email,
            name=user.name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            github_url=user.github_url,
            linkedin_url=user.linkedin_url,
            website_url=user.website_url,
            date_joined=user.date_joined,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_profile(request, body: ProfileUpdateSchema) -> dict:
        user = request.user
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()
        return UserSchema(
            id=str(user.id),
            email=user.email,
            name=user.name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            github_url=user.github_url,
            linkedin_url=user.linkedin_url,
            website_url=user.website_url,
            date_joined=user.date_joined,
        ).model_dump(mode="json")
