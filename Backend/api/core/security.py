from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from api.core.config import config
from fastapi import HTTPException
from typing import Dict
from api.database.connection import get_user_by_id

SECRET_KEY = config.SECRET_KEY  # Use a strong key from environment variables
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to hash passwords
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Function to verify password hashes
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Function to create an access token (JWT) for user authentication
def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=30)) -> str:
    """
    Generates a JWT token for user authentication with an expiration time.
    """
    to_encode = data.copy()  # Copy user data into the token
    expire = datetime.utcnow() + expires_delta  # Set the token expiration
    to_encode.update({"exp": expire})  # Add expiration to token data
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # Encode and return the token

# Function to verify the JWT token and extract the payload (user information)
def verify_token(token: str) -> Dict:
    """
    Verifies and decodes a JWT token to extract the payload (user information).
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # Decode the token
        return payload  # Return the decoded payload (usually contains user ID or username)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")  # Token is expired
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token is invalid")  # Invalid token

# Function to get the current user from the token (used for authentication)
async def get_current_user(token: str) -> Dict:
    """
    Retrieves the current user from the JWT token.
    """
    payload = verify_token(token)  # Verify and decode the token to get user data
    user_id = payload.get("sub")  # Extract the user ID from the token (sub claim)
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")  # Raise error if user ID is not found

    # Assuming you have a database method to fetch user by user ID (replace this with your DB call)
    user = await get_user_by_id(user_id)  # Replace this with actual DB query function
    print("User", user)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")  # User not found in DB
    
    return user  # Return the user object (could be a dictionary with user details)
