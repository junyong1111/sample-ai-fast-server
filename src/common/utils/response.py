from typing import Any, Generic, Optional, TypeVar

from pydantic.generics import GenericModel

T = TypeVar('T')


class JSendResponse(GenericModel, Generic[T]):
    status: str = 'success'
    data: Optional[T] = None
