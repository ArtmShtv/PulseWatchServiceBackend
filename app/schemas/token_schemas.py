from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPair(Token):
    refresh_token: str


class TokenData(BaseModel):
    username: str | None = None


class RefreshTokenSchema(BaseModel):
    refresh_token: str
