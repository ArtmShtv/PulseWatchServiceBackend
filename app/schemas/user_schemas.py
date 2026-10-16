from pydantic import BaseModel, EmailStr, Field, field_validator, StringConstraints
from typing import Annotated


class UserResponseSchema(BaseModel):
    id: int
    email: EmailStr
    username: str

    model_config = {
        "from_attributes": True
    }


class UserCreateSchema(BaseModel):
    email: EmailStr
    username: Annotated[str, StringConstraints(
        strip_whitespace=True, to_lower=True, min_length=3, max_length=50
    )]
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)