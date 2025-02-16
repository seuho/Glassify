from pydantic import BaseModel
from typing import Optional, Union
import uuid  # For generating unique barcodes

class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    quantity: Union[str, int, float]
    cabinet: str
    room: str
    location: str
    barcode: Optional[str] = None  # New barcode field