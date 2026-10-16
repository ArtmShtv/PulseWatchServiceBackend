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

from app.core.security import (
    create_access_token,
    create_refresh_token
)
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
from app.services.token_services import decode_token
from app.core.exceptions import UserAlreadyExistsError


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
    refresh_token = create_refresh_token(user.username)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@auth_routes.post("/refresh")
def refresh(
    refresh_token: str
):
    payload = decode_token(refresh_token, expected_type="refresh")
    username = payload["sub"]

    new_access_token = create_access_token(username)
    return {"access_token": new_access_token, "token_type": "bearer"}