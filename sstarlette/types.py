import typing


class BaseModelType:
    async def verify_access_token(self, bearer_token: str):
        raise NotImplementedError

    def auth_result_callback(self, kls, verified_user):
        raise NotImplementedError
