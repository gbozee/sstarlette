import asyncio
import datetime

import enum
import typing
import jwt
import asyncpg
from sstarlette.authentication import fields
from passlib.context import CryptContext
from pydantic import EmailStr, SecretStr, validator
from pydantic import BaseModel
from starlette.authentication import BaseUser
from .helpers import current_time, token_encoder_and_decoder

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "pbkdf2_sha1", "argon2", "bcrypt_sha256"],
    deprecated="auto",
)


def build_abstract_user(settings):
    class AbstractUser(BaseModel, BaseUser):
        full_name: str
        email: EmailStr
        password: SecretStr = ""
        is_active: bool = True
        created: datetime.datetime
        modified: datetime.datetime
        signup_info: typing.Optional[fields.JSON()] = {}
        roles: typing.Optional[fields.JSON()] = []
        additional_permissions: typing.Optional[fields.JSON()] = []

        @validator("signup_info", pre=True, always=True)
        def set_default_signup_info(cls, v):
            return v or {}

        def set_password(self, password: str):
            self.password = pwd_context.hash(password)

        def check_password(self, password: str):
            value = self.password
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            return pwd_context.verify(password, value)

        # auth properties

        @property
        def is_authenticated(self) -> bool:
            return True

        @property
        def display_name(self) -> str:
            return self.email

        @classmethod
        def decode_access_token(self, *args, **kwargs):
            _, decode_access_token = token_encoder_and_decoder(settings)
            return decode_access_token(*args, **kwargs)

        @classmethod
        def is_expired_token(cls, token, **kwargs):

            try:
                data = cls.decode_access_token(token, **kwargs)
            except jwt.exceptions.ExpiredSignatureError as e:
                return True
            else:
                return False

        async def validate_token(self, token):
            decoded_token = jwt.decode(token, verify=False)
            permissions = await self.permission_names()
            kwargs = {}
            if "aud" in decoded_token:
                kwargs["audience"] = permissions[0]
            if "exp" in decoded_token:
                kwargs["verify_exp"] = True
            try:
                decoded_token = self.decode_access_token(token, **kwargs)
            except (
                jwt.exceptions.InvalidAudienceError,
                jwt.exceptions.ExpiredSignatureError,
            ):
                return False
            else:
                return True

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

        @property
        def email_verified(self):
            return self.verified

        async def verify_user(self):
            self.signup_info["verified"] = True
            await self.save()

        async def get_permissions(self):
            raise NotImplementedError()  # pragma: no cover

        async def get_roles(self):
            raise NotImplementedError()  # pragma: no cover

        async def permission_names(self):
            permissions = await self.get_permissions()
            audience = list({x.name for x in permissions})
            return audience

        async def get_fields_to_generate_access_token(self):
            return {
                "email": self.email,
                "full_name": self.full_name,
                "signup_info": self.signup_info,
            }

        async def generate_access_token(
            self,
            expires=None,
            with_permissions: bool = True,
            additional_info: dict = None,
        ):

            info = await self.get_fields_to_generate_access_token()
            audience = None
            if with_permissions:
                audience = await self.permission_names()
            if additional_info:
                info.update(additional_info)
            create_access_token, _ = token_encoder_and_decoder(settings)
            return create_access_token(
                data=info, expires_delta=expires, audience=audience
            )

        async def create_user_token(self, **kwargs):
            return await self.generate_access_token(with_permissions=False, **kwargs)

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

        @staticmethod
        async def dalchemy_create_unverified_user(
            cls,
            email_verified=False,
            provider="",
            role_task: asyncio.Future = None,
            additional_info: dict = None,
            **kwargs,
        ):
            department = kwargs.pop("department", None)
            errors = cls.validate_model(**kwargs)
            instance = None
            token = None
            task = role_task
            if not errors:
                password = kwargs.pop("password", None)
                instance = cls(**cls.with_defaults(kwargs))
                if password:
                    instance.set_password(password)
                instance.signup_info = {"verified": email_verified}
                if provider:
                    instance.signup_info["provider"] = provider
                if provider.lower() in ["admin", "staff"]:
                    instance.roles = [provider]
                    if provider.lower() == "staff":
                        instance.signup_info["department"] = department
                try:
                    with_permissions = False
                    if task:
                        role_values = await task
                        instance.roles = [role_values.name]
                        with_permissions = True
                    await instance.save()
                    token = await instance.generate_access_token(
                        additional_info=additional_info,
                        with_permissions=with_permissions,
                    )
                except asyncpg.exceptions.UniqueViolationError as e:
                    errors = {"email": ["value_error.duplicate"]}
                    instance = None
            return (errors, instance, token)

    return AbstractUser

