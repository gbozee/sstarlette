import typing

from sstarlette.base import ServiceResult
from sstarlette.types import BaseModelType

ErrorTaskDataType = typing.Tuple[
    typing.Optional[typing.Dict[str, typing.Any]],
    typing.Optional[typing.Any],
    typing.Optional[typing.Dict[str, typing.Any]],
]
ErrorType = typing.Optional[typing.Dict]


class NotificationLayer(BaseModelType):
    async def validate_and_send_email(
        self, to: str, _from=None, context: typing.Dict[str, typing.Any] = None
    ) -> ErrorTaskDataType:
        raise NotImplementedError

    async def validate_and_send_sms(
        self, to: str, message: str, _from=None
    ) -> ErrorTaskDataType:
        raise NotImplementedError

    async def send_phone_verification_code(
        self, number: str, email: typing.Optional[str] = None
    ) -> ErrorTaskDataType:
        raise NotImplementedError

    async def confirm_phone_no(self, number: str, code: str) -> ErrorType:
        raise NotImplementedError


def build_service_layer(_util_klass: NotificationLayer):
    async def send_email(post_data, **kwargs):
        to = post_data.get("to")
        _from = post_data.get("from")
        context = post_data.get("context")
        if not to:
            return ServiceResult(errors={"msg": "Missing recipient"})
        errors, task, data = await _util_klass.validate_and_send_email(
            to, _from=_from, context=context
        )
        if error:
            return ServiceResult(errors=errors)
        return ServiceResult(data=data, task=[task])

    async def send_sms(post_data, **kwargs):
        to = post_data.get("to")
        message = post_data.get("msg")
        _from = post_data.get("from")
        if not to or not message:
            return ServiceResult(
                errors={"msg": "Missing recipient `to` or message `msg`"}
            )
        errors, task, data = await _util_klass.validate_and_send_sms(
            to, message, _from=_from
        )
        if errors:
            return ServiceResult(errors=errors)
        return ServiceResult(data=data, task=[task])

    async def send_phone_verification(post_data, **kwargs):
        phone_no = post_data.get("number")
        email = post_data.get("email")
        if not phone_no:
            return ServiceResult({"msg": "Missing phone number"})
        error, task, data = await _util_klass.send_phone_verification_code(
            phone_no, email=email
        )
        if error:
            return ServiceResult(errors=error)
        tasks = []
        if task:
            tasks.append(task)
        return ServiceResult(data=data, task=tasks)

    async def confirm_phone_verification(post_data, **kwargs):
        phone_no = post_data.get("number")
        verification_code = post_data.get("code")
        if not phone_no or not verification_code:
            return ServiceResult(
                errors={"msg": "Missing phone number or verification code"}
            )
        error = await _util_klass.confirm_phone_no(phone_no, validation_code)
        if error:
            return ServiceResult(errors=error)
        return ServiceResult(data={"msg": "Phone number verified"})

    return {
        "/send-email": {"func": send_email, "methods": ["POST"]},
        "/send-sms": {"func": send_sms, "methods": ["POST"]},
        "/phone/send-verification": {
            "func": send_phone_verification,
            "methods": ["POST"],
        },
        "/phone/confirm": {"func": confirm_phone_verification, "methods": ["POST"]},
    }
