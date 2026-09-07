from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    status
)
from fastapi.security import (
    OAuth2PasswordRequestForm
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.schemas.user_schemas import (
    UserResponseSchema,
    UserCreateSchema, 
)
from app.db.session import get_session
from app.services.user_services import (
    register_user,
    get_current_user_from_jwt,
    authenticate_user
)


auth_routes = APIRouter(
    prefix = "/users",
    tags = ["User endpoints"]
)


@auth_routes.post("/register", response_model=UserResponseSchema)
async def register(
    user_data: UserCreateSchema,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await register_user(session, user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        )

    return user


@auth_routes.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_user(
        session,
        form_data.username,
        form_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@auth_routes.get("/me")
async def get_me(
    current_user=Depends(get_current_user_from_jwt),
):
    return {
        "username": current_user.username,
    }


@auth_routes.get("/protected")
async def protected_route(current_user=Depends(get_current_user_from_jwt)):
    return {
        "message": "You are authenticated",
        "username": current_user.username,
    }