from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(validation_alias=AliasChoices("email", "username"))
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
