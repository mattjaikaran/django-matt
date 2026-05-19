from django_matt import MattAPI

from apps.users.schemas import RegisterResponseSchema, TokenSchema, UserSchema

from .auth_controller import AuthController


def register_auth_routes(api: MattAPI) -> None:
    api.post("auth/register", response_model=RegisterResponseSchema, tags=["Auth"])(
        AuthController.register
    )
    api.post("auth/login", response_model=TokenSchema, status_code=200, tags=["Auth"])(
        AuthController.login
    )
    api.post("auth/refresh", response_model=TokenSchema, status_code=200, tags=["Auth"])(
        AuthController.refresh
    )
    api.get("auth/me", response_model=UserSchema, tags=["Auth"])(AuthController.me)
    api.patch("auth/me", response_model=UserSchema, tags=["Auth"])(
        AuthController.update_me
    )
    api.post("auth/change-password", status_code=200, tags=["Auth"])(
        AuthController.change_password
    )
