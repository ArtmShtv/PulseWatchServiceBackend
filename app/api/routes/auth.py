from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExistsError
from app.core.rate_limit import limit_login_attempts
from app.core.security import create_access_token, create_refresh_token
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.token_schemas import RefreshTokenSchema, Token, TokenPair
from app.schemas.user_schemas import (
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
)
from app.services.auth_services import (
    authenticate_user,
    get_user_from_token,
    register_user,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

auth_routes = APIRouter(
    prefix="/users",
    tags=["User endpoints"],
)

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@auth_routes.post(
    "/register",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    responses={409: {"description": "Email or username already exists"}},
)
async def register(user_data: UserCreateSchema, session: SessionDep):
    try:
        return await register_user(session, user_data)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None


@auth_routes.post(
    "/login",
    response_model=TokenPair,
    summary="Log in with JSON",
    dependencies=[Depends(limit_login_attempts)],
    responses={429: {"description": "Too many login attempts"}},
)
async def login_json(data: UserLoginSchema, session: SessionDep):
    user = await authenticate_user(session, data.email, data.password)
    if not user:
        raise _INVALID_CREDENTIALS
    return _issue_tokens(user)


@auth_routes.post(
    "/token",
    response_model=TokenPair,
    summary="Log in with a form (used by the Swagger Authorize button)",
    description="Put your email in the username field",
    dependencies=[Depends(limit_login_attempts)],
    responses={429: {"description": "Too many login attempts"}},
)
async def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    user = await authenticate_user(session, form.username, form.password)
    if not user:
        raise _INVALID_CREDENTIALS
    return _issue_tokens(user)


@auth_routes.post("/refresh", response_model=Token)
async def refresh(data: RefreshTokenSchema, session: SessionDep):
    user = await get_user_from_token(session, data.refresh_token, expected_type="refresh")
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))