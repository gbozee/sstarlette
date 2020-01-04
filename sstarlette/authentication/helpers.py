from datetime import datetime, timedelta
import jwt


def current_time():
    return datetime.utcnow()


def create_app_access_token(
    *,
    data: dict,
    issuer: str,
    secret_key: str,
    timestamp: int,
    expire: datetime = None,
    algorithm="HS256",
    access_token_jwt_subject="access",
    audience=None,
):
    to_encode = data.copy()
    if expire:
        to_encode.update({"exp": expire})
    to_encode.update({"iss": issuer, "sub": access_token_jwt_subject, "iat": timestamp})
    if audience:
        to_encode.update(aud=audience)
    encoded_jwt = jwt.encode(to_encode, str(secret_key), algorithm=algorithm)
    return encoded_jwt.decode("utf-8")


def token_encoder_and_decoder(settings):
    access_token_jwt_subject = "access"
    ALGORITHM = "HS256"

    def create_access_token(*, data: dict, expires_delta: int = None, audience=None):
        # to_encode = data.copy()
        expire = None
        if expires_delta:
            expire = current_time() + timedelta(seconds=expires_delta)
        return create_app_access_token(
            data=data,
            issuer=settings.JWT_ISSUER,
            secret_key=settings.SECRET_KEY,
            timestamp=current_time().timestamp(),
            expire=expire,
            algorithm=ALGORITHM,
            access_token_jwt_subject=access_token_jwt_subject,
            audience=audience,
        )

    def decode_access_token(access_token, **kwargs):
        decoded_value = jwt.decode(
            access_token, str(settings.SECRET_KEY), algorithms=ALGORITHM, **kwargs
        )
        return decoded_value

    return create_access_token, decode_access_token

