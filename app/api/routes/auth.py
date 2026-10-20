from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExistsError
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_session
from app.schemas.token_schemas import RefreshTokenSchema
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

auth_routes = APIRouter(
    prefix = "/users",
    tags = ["User endpoints"]
)


@auth_routes.post(
    "/register",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    responses={409: {"description": "Email or username already exists"}},
)
async def register(
    user_data: UserCreateSchema,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await register_user(session, user_data)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@auth_routes.post("/login")
async def login_json(
    data: UserLoginSchema,
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_user(session, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }


@auth_routes.post("/refresh")
async def refresh(
    data: RefreshTokenSchema,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_from_token(
        session, data.refresh_token, expected_type="refresh"
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
    }