from typing import List, Union
from pydantic import BaseModel


class RenderIn(BaseModel):
    html: Union[str, List[str]]
