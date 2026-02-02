from pydantic import BaseModel


class Login(BaseModel):
    identity: str
    password: str