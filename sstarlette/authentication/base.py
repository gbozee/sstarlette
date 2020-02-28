import importlib
import typing

from sstarlette import SStarlette
from starlette.responses import JSONResponse

from .service_layer import build_service_layer
from .types import UserModel


async def not_authorized(request, exc):
    return JSONResponse(
        {"status": False, "msg": "Not Authorized"}, status_code=exc.status_code
    )


class AuthenticationStarlette:
    def __init__(self, kls: SStarlette, user_model: UserModel):
        self.kls = kls
        self.user_model = user_model

    def init_app(self, **kwargs) -> SStarlette:
        exception_handlers = kwargs.pop("exception_handlers", {})
        if 403 not in exception_handlers.keys():
            exception_handlers[403] = not_authorized
        return self.kls(
            service_layer=build_service_layer(self.user_model),
            auth_token_verify_user_callback=self.user_model.verify_access_token,
            auth_result_callback=self.user_model.auth_result_callback,
            exception_handlers=exception_handlers,
            **kwargs,
        )
