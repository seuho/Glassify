from pydantic import BaseModel
from typing import Optional, Union

class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    quantity: Union[str, int, float]
    cabinet: str
    room: str
    location: str
