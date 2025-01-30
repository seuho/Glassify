from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from api.items.model import Item
from api.database.connection import get_db
from api.core.security import get_current_user
from api.utils.common import encrypt_data, decrypt_data
import pandas as pd
from io import BytesIO
from bson import ObjectId

items_router = APIRouter()

@items_router.get("/", response_model=list)
async def get_items(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    items_cursor = db["Inventory"].find({"user_id": ObjectId(current_user["_id"])})
    items = await items_cursor.to_list(length=None)  # Fetch all documents
    item_list = []
    print(items)
    for item in items:
        item_data = {
            "id": str(item["id"]),  # Convert ObjectId to a string
            "name": decrypt_data(item["name"]),  # Decrypt sensitive data
            "description": decrypt_data(item["description"]),
            "quantity": decrypt_data(item["quantity"]),
            "cabinet": decrypt_data(item["cabinet"]),
            "room": decrypt_data(item["room"]),
            "location": decrypt_data(item["location"]),
        }
        item_list.append(item_data)  # Add to the result list

    return item_list

@items_router.post("/", response_model=dict)
async def add_item(item: Item, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    # Get the next item ID
    next_item_id_response = await get_next_item_id(current_user, db)  # Await the function
    next_item_id = next_item_id_response["next_id"]  # Extract the next_id from response

    # Prepare item data with encryption
    item_data = {
        "id": next_item_id,
        "name": encrypt_data(item.name),  # Encrypt the name
        "description": encrypt_data(item.description) if item.description else "",  # Encrypt the description if present
        "quantity": encrypt_data(str(item.quantity)),  # Encrypt the quantity
        "cabinet": encrypt_data(item.cabinet),  # Encrypt the cabinet
        "room": encrypt_data(item.room),  # Encrypt the room
        "location": encrypt_data(item.location),  # Encrypt the location
        "user_id": current_user["_id"],  # Associate with the current user
    }

    # Insert the encrypted item into the database
    await db["Inventory"].insert_one(item_data)

    return {"message": "Item added successfully", "id": next_item_id}

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
        last_item = await db["Inventory"].find_one(
            {"user_id": current_user["_id"]}, sort=[("id", -1)])
        next_id = last_item["id"] + 1 if last_item else 1 
        return {"next_id": next_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@items_router.put("/{item_id}", response_model=Item)
async def update_item(item_id: int, item: Item, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    try:
        # Prepare item data with encryption
        item_data = {
            "id": item_id,  # Use provided item ID
            "name": encrypt_data(item.name),  # Encrypt the name
            "description": encrypt_data(item.description) if item.description else "",  # Encrypt description if present
            "quantity": encrypt_data(str(item.quantity)),  # Encrypt the quantity
            "cabinet": encrypt_data(item.cabinet),  # Encrypt cabinet
            "room": encrypt_data(item.room),  # Encrypt room
            "location": encrypt_data(item.location),  # Encrypt location
            "user_id": current_user["_id"],  # Associate with current user
        }

        # Update or insert the item
        result = await db["Inventory"].replace_one(
            {"id": item_id, "user_id": current_user["_id"]}, item_data, upsert=True
        )

        if result.matched_count == 0 and not result.upserted_id:
            raise HTTPException(status_code=400, detail="Failed to update or insert item")
        
        # Decrypt the item data before returning to the user
        item_data["name"] = decrypt_data(item_data["name"])
        item_data["description"] = decrypt_data(item_data["description"]) if item_data["description"] else ""
        item_data["quantity"] = decrypt_data(item_data["quantity"])
        item_data["cabinet"] = decrypt_data(item_data["cabinet"])
        item_data["room"] = decrypt_data(item_data["room"])
        item_data["location"] = decrypt_data(item_data["location"])

        # Return the decrypted item data
        return Item(**item_data)

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
