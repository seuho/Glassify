from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import Optional, Union
import nest_asyncio
from uvicorn import Config, Server
from pymongo import MongoClient
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
from pyngrok import ngrok
import re

# Load environment variables
load_dotenv(dotenv_path="/Users/yashasvipamu/Documents/Web Applications/Glassify/Backend/config.env")

def mongo_connection():
    client = MongoClient(os.getenv("Mongo-url"))
    db = client["Glassify"]
    return db["Inventory"], client  # Return both collection and client

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

@app.get("/items", response_model=list[Item])
async def get_items():
    try:
        collection, client = mongo_connection()
        items = collection.find()
        results = []
        for item in items:
            item["_id"] = str(item["_id"])  # Convert ObjectId to string for JSON serialization
            results.append(item)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.get("/items/name/{item_name}", response_model=list[Item])
async def get_items_by_name(item_name: str):
    try:
        collection, client = mongo_connection()
        pattern = re.compile(f".*{re.escape(item_name)}.*", re.IGNORECASE)
        items = collection.find({"name": pattern})
        result = [
            {**item, "_id": str(item["_id"])} for item in items
        ]
        if not result:
            raise HTTPException(status_code=404, detail="No items found with that name") 
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

@app.delete("/items/{item_id}", response_model=dict)
async def delete_item(item_id: int):
    try:
        collection, client = mongo_connection()
        result = collection.delete_one({"id": item_id})
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
        collection, client = mongo_connection()
        max_id = collection.find_one(sort=[("id", -1)], projection={"id": 1})
        next_id = (max_id["id"] if max_id else 0) + 1
        return {"next_id": next_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.put("/items/{item_id}", response_model=Item)
async def add_or_update_item(item_id: int, item: Item):
    try:
        collection, client = mongo_connection()
        result = collection.replace_one({"id": item_id}, item.dict(), upsert=True)
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
    collection, client = mongo_connection()
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
                "id": collection.estimated_document_count() + i + 1,
                "name": row["Name"],
                "description": row.get("Description", ""),
                "quantity": quantity,
                "cabinet": row["Cabinet"],
                "room": row["Room"],
                "location": row["Location"]
            }
            items.append(item_data)
        if items:
            collection.insert_many(items)
        return {"message": f"Successfully uploaded and inserted {len(items)} items into the database."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if client:
            client.close()

def start_ngrok(port):
    ngrok.set_auth_token(os.getenv("NGROK_AUTHTOKEN"))  # Set your ngrok auth token
    tunnel = ngrok.connect(port, bind_tls=True, hostname="barnacle-vocal-jointly.ngrok-free.app")
    print(f"ngrok tunnel created: {tunnel.public_url}")
    return tunnel

# Main server entry
if __name__ == "__main__":
    port = 8000
    start_ngrok(port)  # Start ngrok tunnel
    config = Config(app=app, host="127.0.0.1", port=port)
    server = Server(config=config)
    server.run()
