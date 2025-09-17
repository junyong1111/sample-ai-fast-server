from typing import List, Union
from pydantic import BaseModel


class StateInput(BaseModel):
    user_id: str

