import datetime
import typing

from orm import Base, fields
from pydantic import BaseModel, EmailStr, SecretStr, validator
from sstarlette.sql import SStarlette
from starlette.authentication import BaseUser

from . import types
from .base import AuthenticationStarlette as BaseStarlette
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "pbkdf2_sha1", "argon2", "bcrypt_sha256"],
    deprecated="auto",
)


class Role(Base):
    name: str

    class Config:
        table_name = "roles"
        table_config = {
            "id": {"primary_key": True, "index": True, "unique": True},
            "name": {"index": True, "index": True, "unique": True},
        }

    @classmethod
    async def get_role(cls, name):
        role = await cls.objects.get(name=name)
        if not role:
            role = await cls.objects.create(name=name)
        return role


class Permission(Base):
    name: str
    active: bool = True
    role: fields.Foreign(Role) = None  # type: ignore

    class Config:
        table_name = "permissions"
        table_config = {
            "id": {"primary_key": True, "index": True},
            "name": {"index": True},
            "role": {"name": "role_id", "type": int},
            "active": {"default": True},
        }

    @validator("active", pre=True, always=True)
    def set_active(cls, v):
        if v is None:
            return True
        return v


class AbstractBaseUser(BaseModel, BaseUser):
    full_name: str
    email: EmailStr
    password: SecretStr = ""  # type: ignore
    is_active: bool = True
    created: datetime.datetime
    modified: datetime.datetime
    signup_info: typing.Optional[fields.JSON()] = {}  # type: ignore
    roles: typing.Optional[fields.JSON()] = []  # type: ignore
    additional_permissions: typing.Optional[fields.JSON()] = []  # type: ignore

    @validator("signup_info", pre=True, always=True)
    def set_default_signup_info(cls, v):
        return v or {}

    def set_password(self, password: str):
        self.password = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        value = self.password
        if isinstance(value, SecretStr):
            value = value.get_secret_value()  # type: ignore
        return pwd_context.verify(password, value)

    # auth properties
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.email

    @property
    def is_staff(self):
        if self.is_superuser:
            return True
        return "staff" in [x.lower() for x in self.roles]

    @property
    def is_superuser(self):
        return "admin" in [x.lower() for x in self.roles]

    @property
    def verified(self):
        return bool(self.signup_info.get("verified"))

    async def verify_user(self):
        self.signup_info["verified"] = True
        await self.save()

    async def permission_names(self):
        permissions = await self.get_permissions()
        audience = list({x.name for x in permissions})
        return audience

    @classmethod
    def dalchemy_table_config(self, additional_fields: dict = None) -> dict:
        obj = {
            "id": {"primary_key": True, "index": True},
            "full_name": {"index": True},
            "email": {"index": True, "unique": True},
            "is_active": {"default": True},
            "roles": {"default": []},
            "signup_info": {"default": {}},
            "additional_permissions": {"default": []},
            "created": {"default": datetime.datetime.now, "timestamp": True},
            "modified": {"onupdate": datetime.datetime.now, "timestamp": True},
        }
        if additional_fields:
            obj.update(additional_fields)
        return obj


class ServiceModel(types.UserModel):
    async def get_user(
        self, data, signup_info, provider=None, email_verified=False
    ) -> types.UserTokenType:
        pass

    async def validate_provider(
        self, provider, bearer_token: str
    ) -> types.ValidateProviderType:
        pass

    async def reset_password(self, user: AbstractBaseUser, password: str):
        pass

    async def validate_provider_for_login(self, provider, bearer_token: str):
        pass

    async def authenticate_user(
        self, data, bearer_token: str, provider
    ) -> types.AuthenticateUserType:
        pass

    async def approve_email_verification(
        self, email: str, token: str, callback_url: typing.Optional[str]
    ) -> types.EmailVerificationType:
        return "Invalid user or token", None

    async def delete_user(
        self, user: AbstractBaseUser, **kwargs
    ) -> types.ErrorTaskType:
        pass

    async def send_email_to_reset_password(
        self, email: str, callback_url: typing.Optional[str]
    ) -> types.ErrorTaskType:
        pass

    async def get_profile_info(
        self, user, email: typing.Optional[str]
    ) -> types.ProfileType:
        pass

    async def hijack_user(self, email: str):
        pass

    async def verify_access_token(self, bearer_token: str) -> types.VerifiedUser:
        pass


class AuthenticationStarlette(BaseStarlette):
    def __init__(self, user_mixin_class, user_model=ServiceModel()):
        self.user_mixin = user_mixin_class
        super().__init__(SStarlette, user_model)
