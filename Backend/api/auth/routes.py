from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from api.database.connection import get_db
from api.core.security import create_access_token, get_password_hash, verify_password
from api.auth.model import User, Token

auth_router = APIRouter()

@auth_router.post("/register", response_model=dict)
async def register(user: User, db=Depends(get_db)):
    existing_user = await db["Users"].find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_password = get_password_hash(user.password)
    await db["Users"].insert_one({"username": user.username, "hashed_password": hashed_password})
    return {"message": "User registered successfully"}

@auth_router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    # Check if the user exists
    user = await db["Users"].find_one({"username": form_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    # Verify the password
    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )

    # Generate and return the access token
    access_token = create_access_token({"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}