import typing

import pytest
from starlette.authentication import AuthCredentials
from starlette.exceptions import HTTPException

from sstarlette.authentication import AuthenticationStarlette, UserModel, types
import utils



class TestUserModel(UserModel):
    async def validate_provider(
        self, provider, bearer_token
    ) -> types.ValidateProviderType:
        if not bearer_token:
            return "Missing Auth header", False
        return None, True

    async def get_user(self, data: types.PostDataType) -> types.UserTokenType:
        password = data.post_data.get("password")
        if not data.provider:
            if not password:
                return {"password": "required"}, None, None
        return None, [utils.bg_task, data.post_data.get("email")], "Success Access Token"

    async def validate_provider_for_login(self, provider, bearer_token):
        if provider:
            if not bearer_token:
                return "Missing auth header"

    async def authenticate_user(
        self, data: types.PostDataType
    ) -> types.AuthenticateUserType:
        password = data.post_data.get("password")
        if not data.provider:
            if not password:
                return None, None
        return [utils.bg_task, data.post_data["email"]], "Access Token"

    async def approve_email_verification(
        self, email: str, token: str, callback_url: typing.Optional[str]
    ) -> types.EmailVerificationType:

        if "invalid" in token.lower():
            return {"msg": "Invalid token"}, None
        if not callback_url:
            callback_url = "http://google.com"
        return None, callback_url + "?access_token=user_token"

    async def send_email_to_reset_password(
        self, email: str, callback_url: str
    ) -> types.ErrorTaskType:
        return None, [utils.bg_task, email, dict(callback_url=callback_url)]

    async def verify_access_token(self, bearer_token: str) -> types.VerifiedUser:
        roles: typing.List[str] = []
        if "valid header" in bearer_token.lower():
            roles = ["authenticated"]
        if "staff header" in bearer_token.lower():
            roles = ["staff", "authenticated"]
        if not roles:
            raise ValueError
        return types.VerifiedUser(auth_roles=roles, user="james@example.com")

    async def reset_password(self, user, password: str):
        pass

    async def get_profile_info(self, user, roles: AuthCredentials, email=None):
        if email:
            if set(roles.scopes).intersection({"admin", "staff"}):
                return None, {"email": email}
            raise HTTPException(403, "Not Authorized")
        return None, {"email": user.username}

    async def delete_user(self, user, email=None, **kwargs) -> types.ErrorTaskType:
        if email == "shola@example.com":
            return None, [utils.bg_task, email]
        return {"msg": "Missing email"}, None

    async def hijack_user(self, email: str) -> typing.Optional[str]:
        if email != "shola@example.com":
            return None
        return "Hijacked token"


@pytest.fixture
def client(client_app):
    return client_app(TestUserModel())
