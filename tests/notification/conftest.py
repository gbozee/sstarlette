import os
import typing

import httpx
import pytest
from starlette.authentication import SimpleUser
from starlette.templating import Jinja2Templates

import utils
from sstarlette.base import ServiceResult
from sstarlette.notification.base import NotificationStarlette
from sstarlette.notification.service_layer import NotificationLayer
from sstarlette.with_middleware import SStarlette

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class TestNotificationLayer(NotificationLayer):
    async def validate_and_send_email(self, to, _from=None, context=None):
        template_name = context.pop("template_name", None)
        if not template_name:
            return {"msg": "Missing template name in context"}, None, None
        html = templates.get_template(template_name).render(context)
        return None, [utils.bg_task, to, html], None

    async def validate_and_send_sms(self, to, message, _from=None):
        return None, [utils.bg_task, to, message, "Main App"], None

    async def send_phone_verification_code(self, number, **kwargs):
        return None, [utils.bg_task, number], None

    async def confirm_phone_no(self, number, code):
        return None

    async def verify_access_token(self, bearer_token: str):
        roles: typing.List[str] = []
        if "authorized" in bearer_token.lower():
            roles = ["authenticated"]
        if "staff header" in bearer_token.lower():
            roles = ["staff", "authenticated"]
        if not roles:
            raise ValueError
        return {"auth_roles": roles, "user": "james@example.com"}

    def auth_result_callback(self, kls, verified_user):
        return kls(verified_user["auth_roles"]), SimpleUser(verified_user["user"])


@pytest.fixture
def client_app():
    def _app(
        user_model,
        kls=NotificationStarlette,
        cls=SStarlette,
        as_app=False,
        enforce_auth=False,
        **kwargs
    ) -> typing.Callable:
        app = kls(cls, user_model, enforce_auth=enforce_auth).init_app(
            auth_error_msg="Not Authorized", **kwargs
        )
        if as_app:
            return app
        return httpx.AsyncClient(app=app, base_url="http://test_server")

    return _app


@pytest.fixture
def auth_client(client_app):
    return client_app(TestNotificationLayer(), enforce_auth=True)


@pytest.fixture
def client(client_app):
    return client_app(TestNotificationLayer())
