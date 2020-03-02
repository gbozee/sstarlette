import asyncio

from sstarlette.notification.service_layer import NotificationLayer


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


# return await loop_helper(
#     lambda: getattr(client, function_name)(*args, **kwargs)
# )


class TwilioNotificationLayer(NotificationLayer):
    def __init__(
        self,
        sid=None,
        auth_token=None,
        sendgrid_api_key=None,
        verify_sid=None,
        sms_from=None,
    ):
        self.sid = sid
        self.auth_token = auth_token
        self.sendgrid_api_key = sendgrid_api_key
        self.verify_sid = verify_sid
        self.sms_from = sms_from

    @property
    def twilio(self):
        from twilio.rest import Client

        return Client(self.sid, self.auth_token)

    @property
    def sendgrid(self):
        from sendgrid import SendGridAPIClient

        return SendGridAPIClient(self.sendgrid_api_key)

    async def validate_and_send_sms(
        self, number, message, _from=None, whatsapp=False, **kwargs
    ):
        to = number
        if whatsapp:
            to = f"whatsapp:number"
        task = lambda: self.twilio.messages.create(
            from_=_from or self.sms_from, body=message, to=to
        )
        return None, task, {"msg": "message sent"}

    async def send_phone_verification_code(
        self, number, action="send_code", channel="sms", **kwargs
    ):
        if action == "verify":
            try:
                result = await loop_helper(
                    lambda: self.twilio.lookups.phone_numbers(number).fetch(
                        type=["carrier"]
                    )
                )
                return None, None, {"msg": "Valid phone number"}
            except Exception:
                return {"msg": "Invalid Phone number"}
        task = lambda: self.twilio.services(self.verify_sid).verifications.create(
            to=number, channel="sms"
        )
        return None, task, {"msg": "Sms verification sent"}

    async def confirm_phone_no(self, number, verification_code):
        result = await loop_helper(
            lambda: self.twilio.services(self.verify_id).verification_checks.create(
                to=number, code=verification_code
            )
        )
        if result.status == "approved":
            return None
        return {"msg": "Phone verification failed"}
