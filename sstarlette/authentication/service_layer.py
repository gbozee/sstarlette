import datetime
import typing

from pydantic import BaseModel
from starlette import background, datastructures, requests
from starlette.background import BackgroundTasks
from .helpers import token_encoder_and_decoder


class CreateUserResult:
    def __init__(
        self,
        errors: dict = None,
        task: typing.List[typing.Any] = None,
        data: dict = None,
    ):
        self.errors = errors
        self.task = task
        self.data = data


class SettingsType:
    REDIRECT_URL_ON_EMAIL_VERIFICATION: str
    REDIRECT_ERROR_AS_JSON: bool
    STAFF_ACCESS_CODE: str


class BaseModelUtil:
    klass = typing.Any
    get_user: typing.Callable[..., typing.Coroutine]
    create_user: typing.Callable[..., typing.Coroutine]


BM = typing.TypeVar("BM", bound=BaseModelUtil)


def build_service_layer(
    settings: SettingsType,
    _util_klass: typing.Type[BM],
    build_utils: typing.Callable[
        ..., typing.Dict[str, typing.Callable[..., typing.Coroutine]]
    ],
) -> typing.Dict[str, typing.Callable[..., typing.Coroutine]]:
    class VerifiedUser(typing.NamedTuple):
        user: typing.Any
        auth_roles: typing.List[str]

        @property
        def email(self) -> str:
            return self.user.email

    def get_func_from_utils(
        func_name: str
    ) -> typing.Optional[typing.Callable[..., typing.Coroutine]]:
        utils = build_utils()
        return utils.get(func_name)

    async def delete_user(token_user) -> CreateUserResult:
        record = await _util_klass.get_user(email=token_user["email"])
        if not record:
            return CreateUserResult(
                errors={"msg": "Missing user record"}
            )  # type: ignore
        await record.delete()
        return CreateUserResult(data={"msg": "Done"})  # type: ignore

    async def on_signup(
        data: dict, headers: typing.Union[dict, datastructures.Headers]
    ) -> CreateUserResult:
        signup_info = data.pop("signup_info", None)
        email_verified = False
        provider = ""
        bearer_token = None
        if not signup_info:
            return CreateUserResult(errors={"msg": "Not Authorized"})  # type: ignore
        if "provider" in signup_info:
            provider = signup_info["provider"]
            auth_header = headers.get("g_authorization") or ""
            bearer_token = auth_header.replace("Bearer", "").strip()
        provider = signup_info.get("provider") or ""
        email_verified = False
        if provider:
            if (
                provider.lower() in ["google", "facebook", "admin"] and not bearer_token
            ):  # no bearer token for google and admin
                auth_errors = {
                    "google": "Missing Authorization header",
                    "admin": "Not Authorized",
                    "staff": "Not Authorized",
                    "facebook": "Missing Authorization header",
                }
                return CreateUserResult(
                    errors={"msg": auth_errors[provider]}
                )  # type: ignore
            if provider.lower() == "staff" and not data.get(
                "department"
            ):  # no department staff
                return CreateUserResult(
                    errors={"msg": "Department for staff missing"}
                )  # type: ignore
            provider_verification = get_func_from_utils("provider_verification")
            if provider_verification:
                error_by_provider = await provider_verification(
                    signup_info, bearer_token, data
                )
                if error_by_provider:
                    return CreateUserResult(
                        errors={"msg": error_by_provider[provider]}
                    )  # type: ignore

            if provider != "facebook":
                email_verified = True
        tasks = []
        errors, instance, access_token = await _util_klass.create_user(
            email_verified=email_verified,
            provider=provider,
            role=signup_info.get("role"),
            **data,
        )
        if not errors:
            # email or identity verification.
            if "email" in (signup_info.get("verification") or ""):
                temp_token = await instance.create_user_token()
                # wrapped in a lambda for easy passage as a background function
                email_verification = get_func_from_utils("email_verification")
                if email_verification:
                    task = lambda: email_verification(instance.email, temp_token)
                    tasks.append(task)

        if errors:
            return CreateUserResult(errors={"errors": errors})  # type: ignore
        return CreateUserResult(
            data={"access_token": access_token}, task=tasks
        )  # type: ignore

    async def reset_user_password(
        user: VerifiedUser, bearer_token: str, password=None, **kwargs
    ) -> CreateUserResult:
        validated_token = await user.user.validate_token(bearer_token)
        if not validated_token:
            return CreateUserResult(
                errors={"msg": "Token is invalid or expired"}
            )  # type: ignore
        if not password:
            return CreateUserResult(errors={"msg": "Missing password"})  # type: ignore
        tasks = []

        async def callback():
            _user = user.user
            _user.set_password(password)
            await _user.save()

        tasks.append(callback)
        return CreateUserResult(task=tasks)  # type: ignore

    async def on_login(params: dict, bearer_token) -> CreateUserResult:
        login_info = params.pop("login_info", {}) or {}

        result = await authenticate_user(
            login_info=login_info, bearer_token=bearer_token, **params
        )
        if result.errors:
            return CreateUserResult(errors=result.errors)
        if result.task:
            tasks = []
            tasks.append(result.task)
            return CreateUserResult(data={"msg": "Email verification sent"}, task=tasks)
        return CreateUserResult(data=result.data)

    async def authenticate_user(login_info: dict, bearer_token=None, **data):
        email = data.get("email") or ""
        number = data.get("number")
        password = data.get("password")
        callback_url = data.get("callback_url")
        provider = login_info.get("provider")
        endpoint = login_info.get("endpoint")
        # email or number not provided
        if not email and not number:
            return CreateUserResult(errors={"msg": "Missing email or phone number"})
        if provider:
            # authentication attempt through google
            if provider.lower() in ["google", "facebook"] and not bearer_token:
                auth_errors = {"google": "Missing Authorization header"}
                return CreateUserResult(errors={"msg": auth_errors[provider]})
            provider_verification = get_func_from_utils("provider_verification")
            if provider_verification:
                error_by_provider = await provider_verification(
                    {
                        "provider": provider,
                        "client_id": login_info.get("client_id"),
                        "verify": login_info.get("verify"),
                    },
                    bearer_token,
                    {"email": email.strip()},
                )
                if not error_by_provider:
                    return CreateUserResult(errors={"msg": "Verification failed"})

        # phone number authentication
        if number and not endpoint:
            return CreateUserResult(
                errors={"msg": "Missing verification endpoint for number"}
            )
        # not requiring a password to login
        if callback_url:
            provider = "token"  # force generation of access token
        access_token = await _authenticate_user(
            email=email.strip(),
            number=number,
            password=password,
            role=bearer_token,
            provider=provider,
            endpoint=endpoint,
        )
        if not access_token:
            return CreateUserResult(errors={"msg": "Invalid credentials"})
        email_verification = get_func_from_utils("email_verification")
        if email_verification:
            tasks = []
            if callback_url:
                task = lambda: email_verification(
                    email, token=access_token, callback_url=callback_url
                )
                tasks.append(task)
                return CreateUserResult(task=tasks)
        return CreateUserResult(data={"access_token": access_token})

    async def on_email_confirmation(
        email: str, token: str, callback_url: str = None
    ) -> CreateUserResult:
        if not all([email, token]):
            return CreateUserResult(errors={"msg": "Missing query parameters"})

        user = await _util_klass.get_user(email=email.strip())
        redirect_url = None
        if user:
            is_valid = await user.validate_token(token)
            if is_valid:
                if callback_url:
                    access_token = await user.generate_access_token()
                    redirect_url = f"{callback_url}?access_token={access_token}"
                else:
                    await user.verify_user()
                    redirect_url = settings.REDIRECT_URL_ON_EMAIL_VERIFICATION
        if not redirect_url:
            if not settings.REDIRECT_ERROR_AS_JSON:
                redirect_url = f"{settings.REDIRECT_URL_ON_EMAIL_VERIFICATION}?error_msg=Invalid user or token"
            else:
                return CreateUserResult(errors={"msg": "Invalid user or token"})
        return CreateUserResult(data=dict(redirect_url=redirect_url))

    async def _authenticate_user(
        email: str = None,
        number: str = None,
        endpoint: str = None,
        password: typing.Optional[str] = "",
        role: str = None,
        provider: str = None,
    ):
        _email = email
        get_email_from_number = get_func_from_utils("get_email_from_number")
        if get_email_from_number:
            if not _email:
                _email = await get_email_from_number(number, endpoint)
        access_token = None
        if _email:
            user = await _util_klass.get_user(email=_email)
            if user:
                if password:
                    if user.check_password(password):
                        access_token = await user.create_user_token()
                        if role:
                            if role == settings.STAFF_ACCESS_CODE:
                                access_token = await user.generate_access_token()
                if provider:
                    access_token = await user.create_user_token()
                    if provider != "token":
                        access_token = await user.generate_access_token()
        return access_token

    async def get_hijacked_user_token(
        staff, bearer_token: str, email: str = None
    ) -> CreateUserResult:
        validated_token = await staff.user.validate_token(bearer_token)
        if not validated_token:
            return CreateUserResult(errors={"msg": "Token is invalid or expired"})
        if not email:
            return CreateUserResult(errors={"msg": "Missing email"})
        user_to_hijack = await _util_klass.get_user(email=email)
        access_token = None
        if user_to_hijack:
            access_token = await user_to_hijack.generate_access_token(
                additional_info={"hijacker": staff.email}
            )
        if not access_token:
            return CreateUserResult(errors={"msg": "No user with email"})
        return CreateUserResult(data=dict(access_token=access_token))

    async def verify_access_token(bearer_token: str) -> VerifiedUser:
        _, decode_access_token = token_encoder_and_decoder(settings)
        user_data = decode_access_token(bearer_token, verify=False)
        email = user_data["email"]
        user = await _util_klass.get_user(email=email)
        auth_roles = ["authenticated"]
        if user.is_staff and "aud" in user_data:
            auth_roles.append("staff")
        if user.is_superuser and "aud" in user_data:
            auth_roles.append("admin")
        return VerifiedUser(user=user, auth_roles=auth_roles)

    async def forgot_password_action(email: str, callback_url) -> CreateUserResult:
        if not email or not callback_url:
            return CreateUserResult(
                errors={"msg": "Both email and callback url is expected"}
            )
        email_verification = get_func_from_utils("email_verification")
        tasks = []
        if email_verification:
            tasks.append([email_verification, email, dict(callback_url=callback_url)])
        return CreateUserResult(task=tasks)

    return {
        "reset-password": reset_user_password,
        "forgot-password": forgot_password_action,
        "verify-email": on_email_confirmation,
        "login": on_login,
        "signup": on_signup,
        "hijack-user": get_hijacked_user_token,
        "delete-user": delete_user,
        "verify-access-token": verify_access_token,
    }


def build_view(service_layer, staff_key="StaffAuth"):
    def get_token(headers: requests.Headers) -> str:
        auth = headers["Authorization"]
        bearer_token = auth.replace("Bearer", "").strip()
        return bearer_token

        # validate the token to see if it is expired

    def get_bearer_token(params: dict, headers: requests.Headers):
        login_info = params.get("login_info", {}) or {}
        auth_key = staff_key
        if "provider" in login_info:
            auth_key = "g_authorization"
        authorization = headers.get(auth_key) or ""
        bearer_token = authorization.replace("Bearer", "").strip()
        return bearer_token

    async def delete_user(post_data, **kwargs) -> CreateUserResult:
        return await service_layer["delete-user"](post_data)

    async def forgot_password(**kwargs):
        params = kwargs["query_params"]
        email = params.get("email")
        callback_url = params.get("callback_url")
        return await service_layer["forgot-password"](email, callback_url)

    async def signup(post_data, **kwargs):
        return await service_layer["signup"](post_data, kwargs["headers"])

    async def reset_password(post_data, **kwargs) -> CreateUserResult:
        return await service_layer["reset-password"](
            kwargs["user"], get_token(kwargs["headers"]), **post_data
        )

    async def login(post_data, **kwargs):
        bearer_token = get_bearer_token(post_data, kwargs["headers"])
        return await service_layer["login"](post_data, bearer_token)

    async def on_email_confirmation(**kwargs) -> CreateUserResult:
        params = kwargs["query_params"]
        email = params.get("email") or ""
        token = params.get("token")
        callback_url = params.get("callback_url")
        return await service_layer["verify-email"](
            email=email, token=token, callback_url=callback_url
        )

    async def hijack_user(**kwargs) -> CreateUserResult:
        # validate the token to see if it is expired
        return await service_layer["hijack-user"](
            kwargs["user"],
            get_token(kwargs["headers"]),
            email=kwargs["query_params"].get("email"),
        )

    return {
        "/delete-user": {"func": delete_user, "methods": ["POST"]},
        "/hijack-user": {"func": hijack_user, "methods": ["GET"], "auth": "staff"},
        "/signup": {"func": signup, "methods": ["POST"]},
        "/login": {"func": login, "methods": ["POST"]},
        "/verify-email": {
            "func": on_email_confirmation,
            "methods": ["GET"],
            "redirect": True,
            "redirect_key": "redirect_url",
        },
        "/forgot-password": {"func": forgot_password, "methods": ["GET"]},
        "/reset-password": {
            "func": reset_password,
            "methods": ["POST"],
            "auth": "authenticated",
        },
    }


def build_app(
    settings, _util_klass, build_utils, routes=None, staff_key="StaffAuth", **kwargs
):
    from sstarlette.base import SStarlette

    service_layer = build_service_layer(settings, _util_klass, build_utils)
    return SStarlette(
        str(settings.DATABASE_URL),
        auth_token_verify_user_callback=service_layer["verify-access-token"],
        serverless=settings.ENVIRONMENT == "serverless",
        model_initializer=_util_klass.model_initializer,
        service_layer=build_view(service_layer, staff_key=staff_key),
        routes=routes,
        **kwargs,
    )

