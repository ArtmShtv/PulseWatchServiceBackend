from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from pwdlib import PasswordHash

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.db.models.user import User
from app.schemas.user_schemas import (
    UserCreateSchema,
)
from app.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def register_user(
    session: AsyncSession,
    user_data: UserCreateSchema
) -> User:
    result = await session.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )

    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise ValueError("Email or username already exists")

    user = User(
        email = user_data.email,
        username = user_data.username,
        password = hash_password(user_data.password)
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def authenticate_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username)
    )

    user = result.scalar_one_or_none()

    if not user:
        return None

    if not verify_password(password, user.password):
        return None

    return user


async def get_user_by_username(
    session: AsyncSession,
    username: str,
) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username)
    )

    return result.scalar_one_or_none()


async def get_current_user_from_jwt(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    user = await get_user_by_username(session, username)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return user