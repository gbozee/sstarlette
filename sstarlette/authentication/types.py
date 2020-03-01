import typing

from starlette.authentication import AuthCredentials, SimpleUser

from sstarlette.types import BaseModelType


class VerifiedUser(typing.NamedTuple):
    user: typing.Any
    auth_roles: typing.List[str]

    @property
    def email(self) -> str:
        return self.user.email


class PostDataType:
    def __init__(
        self,
        data: typing.Dict[str, typing.Any],
        signup_info=None,
        provider=None,
        bearer_token=None,
        email_verified: bool = False,
    ):
        self.post_data = data
        self.signup_info = signup_info
        self.provider = provider
        self.bearer_token = bearer_token
        self.email_verified = email_verified


BackgroundTaskType = typing.Optional[
    typing.Union[typing.Callable, typing.List[typing.Any]]
]
UserTokenType = typing.Tuple[
    typing.Optional[typing.Dict[str, typing.Any]],
    BackgroundTaskType,
    typing.Optional[str],
]
ValidateProviderType = typing.Tuple[typing.Optional[str], bool]
AuthenticateUserType = typing.Tuple[BackgroundTaskType, typing.Optional[str]]
EmailVerificationType = typing.Tuple[
    typing.Optional[typing.Dict[str, typing.Any]], typing.Optional[str]
]
ErrorTaskType = typing.Tuple[
    typing.Optional[typing.Dict[str, typing.Any]], BackgroundTaskType
]
ProfileType = typing.Tuple[
    typing.Optional[str], typing.Optional[typing.Dict[str, typing.Any]]
]


class UserModel(BaseModelType):
    async def get_user(self, post_data: PostDataType) -> UserTokenType:
        raise NotImplementedError

    async def validate_provider(
        self, provider: typing.Optional[str], bearer_token: str
    ) -> ValidateProviderType:
        """If supporting authentication scheme aside from password,
        
        Arguments:
            provider {str} -- The authentication scheme supported
            bearer_token {str} -- The header token or identifier to be verified
        
        Returns:
            types.ValidateProviderType -- An Error string and  a boolean indicating if the email is verified
        """
        raise NotImplementedError

    async def reset_password(self, user, password: str) -> None:
        raise NotImplementedError

    async def validate_provider_for_login(
        self, provider: typing.Optional[str], bearer_token: str
    ) -> typing.Optional[str]:
        raise NotImplementedError

    async def authenticate_user(self, data: PostDataType) -> AuthenticateUserType:
        raise NotImplementedError

    async def approve_email_verification(
        self, email: str, token: str, callback_url: typing.Optional[str]
    ) -> EmailVerificationType:
        raise NotImplementedError

    async def delete_user(self, user, **kwargs) -> ErrorTaskType:
        raise NotImplemented

    async def send_email_to_reset_password(
        self, email: str, callback_url: str
    ) -> ErrorTaskType:
        raise NotImplementedError

    async def get_profile_info(
        self, user, roles: AuthCredentials, email: typing.Optional[str] = None
    ) -> ProfileType:
        ...

    async def hijack_user(self, email: str) -> typing.Optional[str]:
        ...

    def auth_result_callback(self, kls, verified_user: VerifiedUser):
        return kls(verified_user.auth_roles), SimpleUser(verified_user.user)
