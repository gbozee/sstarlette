from starlette.responses import JSONResponse

from sstarlette.base import SStarlette
from sstarlette.notification.service_layer import (NotificationLayer,
                                                   build_service_layer)


def on_auth_error(request, exc: Exception):
    return JSONResponse({"status": False, "msg": str(exc)}, status_code=403)


class NotificationStarlette:
    def __init__(
        self, kls: SStarlette, notification_layer: NotificationLayer, enforce_auth=False
    ):
        self.kls = kls
        self.notification_layer = notification_layer
        self.enforce_auth = enforce_auth

    def init_app(self, **kwargs) -> SStarlette:
        params = dict(service_layer=build_service_layer(self.notification_layer))
        if self.enforce_auth:
            # exception_handlers = kwargs.pop("exception_handlers", {})
            # if 403 not in exception_handlers.keys():
            #     exception_handlers[403] = not_authorized
            params.update(
                auth_token_verify_user_callback=self.notification_layer.verify_access_token,
                auth_result_callback=self.notification_layer.auth_result_callback,
                enforce_auth=self.enforce_auth,
                # exception_handlers=exception_handlers,
                on_auth_error=on_auth_error
            )
        return self.kls(**params, **kwargs) # type: none
