from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import Optional, Union, List
import nest_asyncio
from uvicorn import Config, Server
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
from pyngrok import ngrok
from motor.motor_asyncio import AsyncIOMotorClient
import re

# Load environment variables
load_dotenv(dotenv_path="/Users/yashasvipamu/Documents/Web Applications/Glassify/Backend/config.env")

# Mongo connection function (Async version)
async def mongo_connection():
    mongo_url = os.getenv("Mongo_url")
    if not mongo_url:
        raise ValueError("Mongo_url environment variable not set correctly.")
    
    print(f"Connecting to MongoDB with URL: {mongo_url}")

    try:
        print(f"Sanitized MongoDB URL: {mongo_url.split('@')[0]}@<redacted>")
        if not re.match(r"^mongodb(\+srv)?:\/\/", mongo_url):
            raise ValueError("line -28 Invalid MongoDB URI: URI must begin with 'mongodb://' or 'mongodb+srv://'")

        client = AsyncIOMotorClient(mongo_url)
        db = client["Glassify"]
        collection = db["Inventory"]
        return collection, client  # Return both collection and client
    except Exception as e:
        print(f"Error during MongoDB connection: {e}")
        raise HTTPException(status_code=500, detail=f"MongoDB connection failed: {str(e)}")

# Enable nested asyncio loops for compatibility
nest_asyncio.apply()
app = FastAPI()

# Pydantic model
class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    quantity: Union[str, int, float]
    cabinet: str
    room: str
    location: str

@app.get("/")
async def get_health_check():
    return "The health check was successful"

@app.get("/items", response_model=List[Item])
async def get_items():
    client = None  # Initialize client variable
    try:
        collection, client = await mongo_connection()
        items_cursor = collection.find()  # This is an AsyncIOMotorCursor
        items = await items_cursor.to_list(length=None)  # Convert cursor to list asynchronously
        # Convert ObjectId to string for JSON serialization
        for item in items:
            item["_id"] = str(item["_id"])
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.get("/items/name/{item_name}", response_model=List[Item])
async def get_items_by_name(item_name: str):
    client = None  # Initialize client variable
    try:
        collection, client = await mongo_connection()
        pattern = re.compile(f".*{re.escape(item_name)}.*", re.IGNORECASE)
        items_cursor = collection.find({"name": pattern})
        items = await items_cursor.to_list(length=None)  # Convert cursor to list asynchronously
        # Convert ObjectId to string for JSON serialization
        for item in items:
            item["_id"] = str(item["_id"])
        if not items:
            raise HTTPException(status_code=404, detail="No items found with that name")
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.delete("/items/{item_id}", response_model=dict)
async def delete_item(item_id: int):
    client = None  # Initialize client variable
    try:
        collection, client = await mongo_connection()
        result = await collection.delete_one({"id": item_id})  # Asynchronous delete operation
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Item with ID {item_id} not found.")
        return {"message": f"Item with ID {item_id} successfully deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.get("/next-item-id")
async def get_next_item_id():
    try:
        collection, client = await mongo_connection()
        max_id = await collection.find_one(sort=[("id", -1)], projection={"id": 1})  # Asynchronous find
        next_id = (max_id["id"] if max_id else 0) + 1
        return {"next_id": next_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.put("/items/{item_id}", response_model=Item)
async def add_or_update_item(item_id: int, item: Item):
    try:
        collection, client = await mongo_connection()
        result = await collection.replace_one({"id": item_id}, item.dict(), upsert=True)  # Asynchronous replace operation
        if result.matched_count == 0 and not result.upserted_id:
            raise HTTPException(status_code=400, detail="Failed to update or insert item")
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.post("/upload/")
async def upload_excel(file: UploadFile = File(...)):
    collection, client = await mongo_connection()  # Use async connection
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid file format. Only .xlsx files are supported.")
    try:
        df = pd.read_excel(BytesIO(await file.read()))
        required_columns = {"Name", "Quantity", "Cabinet", "Room", "Location"}
        if not required_columns.issubset(df.columns):
            raise HTTPException(status_code=400, detail="Excel file is missing required columns")
        items = []
        for i, row in df.iterrows():
            quantity = row["Quantity"] if pd.notna(row["Quantity"]) and row["Quantity"] != "" else "too many"
            item_data = {
                "id": await collection.estimated_document_count() + i + 1,  # Async operation to get count
                "name": row["Name"],
                "description": row.get("Description", ""),
                "quantity": quantity,
                "cabinet": row["Cabinet"],
                "room": row["Room"],
                "location": row["Location"]
            }
            items.append(item_data)
        if items:
            await collection.insert_many(items)  # Async insert operation
        return {"message": f"Successfully uploaded and inserted {len(items)} items into the database."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

# Main server entry
if __name__ == "__main__":
    port = 8000
    config = Config(app=app, host="127.0.0.1", port=port)
    server = Server(config=config)
    server.run()
