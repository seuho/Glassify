from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from items.model import Item
from database.connection import get_db
from core.security import get_current_user
from utils.common import encrypt_data
import pandas as pd
from io import BytesIO
from bson import ObjectId

items_router = APIRouter()

@items_router.get("/", response_model=list)
async def get_items(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    print("current user _id", current_user["_id"])
    items = await db["Inventory"].find_one({"user_id": ObjectId('67818a4db5589edb3863313f')})
    print(items)
    return items

@items_router.post("/", response_model=dict)
async def add_item(item: Item, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    item_data = item.dict()
    item_data["user_id"] = current_user["_id"]
    await db["Inventory"].insert_one(item_data)
    return {"message": "Item added successfully"}

# Delete an item by ID for the logged-in user
@items_router.delete("/{item_id}", response_model=dict)
async def delete_item(item_id: int, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    try:
        result = await db["Inventory"].delete_one({"id": item_id, "user_id": current_user["_id"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Item with ID {item_id} not found or not owned by the current user.")
        return {"message": f"Item with ID {item_id} successfully deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Get the next available item ID for the logged-in user
@items_router.get("/next-item-id", response_model=dict)
async def get_next_item_id(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    try:
        max_id = await db["Inventory"].find_one(
            {"user_id": current_user["_id"]}, sort=[("id", -1)], projection={"id": 1}
        )
        next_id = (max_id["id"] if max_id else 0) + 1
        return {"next_id": next_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Update or add an item for the logged-in user
@items_router.put("/{item_id}", response_model=Item)
async def update_item(item_id: int, item: Item, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    try:
        item_data = item.dict()
        item_data["user_id"] = current_user["_id"]
        
        result = await db["Inventory"].replace_one({"id": item_id, "user_id": current_user["_id"]}, item_data, upsert=True)
        if result.matched_count == 0 and not result.upserted_id:
            raise HTTPException(status_code=400, detail="Failed to update or insert item")
        
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@items_router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)):
    """
    Upload an Excel file and insert its contents into the inventory.
    """
    if not current_user or "_id" not in current_user:
        raise HTTPException(status_code=401, detail="Invalid user credentials")

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
                "id": await db["Inventory"].estimated_document_count() + i + 1,  # Async operation to get count
                "name": encrypt_data(row["Name"]),  # Encrypt sensitive data
                "description": encrypt_data(row.get("Description", "")),
                "quantity": encrypt_data(str(quantity)),
                "cabinet": encrypt_data(row["Cabinet"]),
                "room": encrypt_data(row["Room"]),
                "location": encrypt_data(row["Location"]),
                "user_id": current_user["_id"],
            }
            items.append(item_data)

        if items:
            await db["Inventory"].insert_many(items)  # Async insert operation
        return {"message": f"Successfully uploaded and inserted {len(items)} items into the database."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
