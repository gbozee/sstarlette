import typing

from sstarlette import SResult as ServiceResult
from starlette import datastructures
from starlette.datastructures import QueryParams
from starlette.requests import Request

from . import types


def build_service_layer(
    _util_klass: types.UserModel,
    social_headers="g_authorization",
    invalid_token_msg="Token is invalid or expired",
):
    async def on_signup(post_data, headers=None, **kwargs) -> ServiceResult:
        signup_info = post_data.pop("signup_info", None)
        email_verified = False
        bearer_token = None
        if not signup_info:
            return ServiceResult(errors={"msg": "Not Authorized"})
        auth_headers = headers.get(social_headers) or ""
        bearer_token = auth_headers.replace("Bearer", "").strip()
        provider = signup_info.get("provider") or ""
        if provider:
            validation_msg, email_verified = await _util_klass.validate_provider(
                provider, bearer_token
            )
            if validation_msg:
                return ServiceResult(errors={"msg": validation_msg})
        tasks = []
        params = dict(
            signup_info=signup_info, provider=provider, email_verified=email_verified
        )
        errors, task, access_token = await _util_klass.get_user(
            types.PostDataType(post_data, **params)
        )
        if errors:
            return ServiceResult(errors={"errors": errors})
        if task:
            tasks.append(task)
        return ServiceResult(data={"access_token": access_token}, task=tasks)

    async def reset_user_password(
        post_data: typing.Dict[str, typing.Any],
        query_params,
        headers: datastructures.Headers,
        path_params,
        user=None,
        **kwargs,
    ) -> ServiceResult:
        if not post_data.get("password"):
            return ServiceResult(errors={"msg": "Missing password"})
        return ServiceResult(
            task=[[_util_klass.reset_password, user, post_data["password"]]]
        )

    async def on_login(
        post_data: typing.Dict[str, typing.Any], headers=None, **kwargs
    ) -> ServiceResult:
        login_info = post_data.pop("login_info", {}) or {}
        email = post_data.get("email")
        number = post_data.get("number")
        endpoint = login_info.get("phone_verification_endpoint")
        provider = login_info.get("provider")
        bearer_token = None
        auth_headers = headers.get(social_headers) or ""
        bearer_token = auth_headers.replace("Bearer", "").strip()
        if not email and not number:
            return ServiceResult(errors={"msg": "Missing email or phone number"})
        # phone number authentication
        if number and not endpoint:
            return ServiceResult(
                errors={"msg": "Missing verification endpoint for number"}
            )
        if provider:
            validation_msg = await _util_klass.validate_provider_for_login(
                provider, bearer_token
            )
            if validation_msg:
                return ServiceResult(errors={"msg": validation_msg})
        task, access_token = await _util_klass.authenticate_user(
            types.PostDataType(post_data, bearer_token=bearer_token, provider=provider)
        )
        if not access_token:
            return ServiceResult(errors={"msg": "Invalid credentials"})
        tasks = []
        if task:
            tasks.append(task)
        return ServiceResult(data={"access_token": access_token}, task=tasks)

    async def on_email_confirmation(
        query_params: typing.Dict[str, str] = {}, **kwargs
    ) -> ServiceResult:
        callback_url = query_params.get("callback_url")
        if not all([query_params.get("email"), query_params.get("token")]):
            return ServiceResult(errors={"msg": "Missing query parameters"})
        email = query_params["email"]
        token = query_params["token"]
        errors, redirect_url = await _util_klass.approve_email_verification(
            email, token, callback_url
        )
        if errors:
            return ServiceResult(errors=errors)
        return ServiceResult(data={"redirect_url": redirect_url})

    async def get_hijacked_user_token(query_params={}, **kwargs) -> ServiceResult:
        if not query_params.get("email"):
            return ServiceResult(errors={"msg": "Missing email"})
        email = query_params["email"]
        access_token = await _util_klass.hijack_user(email)
        if not access_token:
            return ServiceResult(errors={"msg": f"No user with email <{email}>"})
        return ServiceResult(data={"access_token": access_token})

    async def forgot_password_action(query_params={}, **kwargs) -> ServiceResult:
        if not query_params.get("email") or not query_params.get("callback_url"):
            return ServiceResult(
                errors={"msg": "Both email and callback_url is expected"}
            )
        email = query_params["email"]
        callback_url = query_params["callback_url"]
        errors, tasks = await _util_klass.send_email_to_reset_password(
            email, callback_url
        )
        if errors:
            return ServiceResult(errors=errors)
        return ServiceResult(task=[tasks])

    async def get_user_profile(query_params={}, user=None, **kwargs) -> ServiceResult:
        request: Request = kwargs["request"]
        errors, profile_data = await _util_klass.get_profile_info(
            user, request.auth, email=query_params.get("email")
        )
        if errors:
            return ServiceResult(errors={"msg": errors})
        return ServiceResult(data=profile_data)

    async def delete_user(query_params={}, user=None, **kwargs) -> ServiceResult:
        errors, task = await _util_klass.delete_user(user, **query_params)
        if errors:
            return ServiceResult(errors=errors)
        tasks = []
        if task:
            tasks.append(task)
        return ServiceResult(data={"msg": "Done"}, task=tasks)

    return {
        "/delete-user": {"func": delete_user, "methods": ["DELETE"], "auth": ["staff"]},
        "/hijack-user": {
            "func": get_hijacked_user_token,
            "methods": ["GET"],
            "auth": ["staff"],
        },
        "/signup": {"func": on_signup, "methods": ["POST"]},
        "/login": {"func": on_login, "methods": ["POST"]},
        "/verify-email": {
            "func": on_email_confirmation,
            "methods": ["GET"],
            "redirect": True,
            "redirect_key": "redirect_url",
        },
        "/forgot-password": {"func": forgot_password_action, "methods": ["GET"]},
        "/reset-password": {
            "func": reset_user_password,
            "methods": ["POST"],
            "auth": ["authenticated"],
        },
        "/get-profile": {
            "func": get_user_profile,
            "methods": ["GET"],
            "auth": ["authenticated"],
        },
    }
