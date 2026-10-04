from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from app.auth.models import Token
from app.auth.security import create_access_token, verify_password, USERS
from app.auth.database import get_user
from app.core.config import settings
from app.core.errors import CopilotError
from pydantic import BaseModel

router = APIRouter()

@router.post("/auth/login", response_model=Token)
async def login_endpoint(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise CopilotError("Incorrect username or password", status_code=401)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username, "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}

class RegisterRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/register")
async def register_endpoint(request: RegisterRequest):
    from app.auth.database import create_user
    success = create_user(request.username, request.password, role="user")
    if not success:
        raise CopilotError("Username already exists.", status_code=409)
    return {"status": "ok", "message": f"User '{request.username}' created successfully."}
