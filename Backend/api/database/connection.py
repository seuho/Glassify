from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from dotenv import load_dotenv
import os

load_dotenv()

client = None

# Connect to MongoDB
async def connect_to_mongo():
    global client
    mongo_url = os.getenv("Mongo_url")
    
    if not mongo_url:
        raise HTTPException(status_code=500, detail="MongoDB connection string not found")
    
    client = AsyncIOMotorClient(mongo_url)
    # Check if the connection is successful by pinging the database
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to MongoDB: {str(e)}")

# Get database reference
def get_db():
    if not client:
        raise HTTPException(status_code=500, detail="Database connection not established")
    return client["Glassify"]  # Replace "Glassify" with the actual database name

# Close the MongoDB connection gracefully during app shutdown
async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")

# Get user by ID
async def get_user_by_id(user_id: str):
    db = get_db()
    user = await db["Users"].find_one({"username": user_id})  # Assuming the collection name is "Users"
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found.")
    return user
