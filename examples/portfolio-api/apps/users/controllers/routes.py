from django_matt import DjangoMattAPI

from apps.users.schemas import RegisterResponseSchema, TokenSchema, UserSchema

from .auth_controller import AuthController


def register_auth_routes(api: DjangoMattAPI) -> None:
    api.post(
        "auth/register", response_model=RegisterResponseSchema, status_code=201, tags=["Auth"]
    )(AuthController.register)
    api.post("auth/login", response_model=TokenSchema, status_code=200, tags=["Auth"])(
        AuthController.login
    )
    api.get("auth/me", response_model=UserSchema, tags=["Auth"])(AuthController.me)
    api.patch("auth/me", response_model=UserSchema, tags=["Auth"])(AuthController.update_profile)
