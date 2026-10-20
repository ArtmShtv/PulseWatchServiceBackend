import asyncio

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UserAlreadyExistsError
from app.core.security import hash_password, verify_password
from app.db.models.user import User
from app.db.session import async_session_maker, get_session
from app.schemas.user_schemas import UserCreateSchema

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

_DUMMY_HASH = hash_password("dummy-password")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def _check_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == normalize_email(email))
    )
    return result.scalar_one_or_none()


async def register_user(session: AsyncSession, user_data: UserCreateSchema) -> User:
    email = normalize_email(user_data.email)

    result = await session.execute(
        select(User.id).where(
            (User.email == email) | (User.username == user_data.username)
        )
    )
    if result.first():
        raise UserAlreadyExistsError("Email or username already exists")

    user = User(
        email=email,
        username=user_data.username,
        password=await asyncio.to_thread(hash_password, user_data.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise UserAlreadyExistsError("Email or username already exists") from None

    await session.refresh(user)
    return user


async def get_user_from_token(
    session: AsyncSession,
    token: str,
    expected_type: str = "access",
) -> User | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None

    if payload.get("type") != expected_type:
        return None

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    return await get_user_by_id(session, user_id)


async def get_current_user_from_jwt(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await get_user_from_token(session, token)

    if user is None:
        raise _CREDENTIALS_EXCEPTION

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return user


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    user = await get_user_by_email(session, email)

    hashed = user.password if user else _DUMMY_HASH
    password_is_valid = await _check_password(password, hashed)

    if user is None or not password_is_valid or not user.is_active:
        return None
    return user


async def ws_authenticate_user(token: str) -> int | None:
    async with async_session_maker() as session:
        user = await get_user_from_token(session, token)
    if user is None or not user.is_active:
        return None
    return user.id