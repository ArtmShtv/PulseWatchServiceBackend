from pydantic import BaseModel, EmailStr, Field


class UserResponseSchema(BaseModel):
    id: int
    email: EmailStr
    username: str

    model_config = {
        "from_attributes": True
    }


class UserCreateSchema(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)