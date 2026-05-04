from __future__ import annotations
 
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
 
 
class ResultStatus(Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    EMPTY_DATA = "empty_data"
    DB_ERROR = "db_error"
 
 
@dataclass(frozen=True)     #immutable object(frozen)- once instantiated with its fields, its fields cannot be modified
class ServiceResult:
    """Uniform result from any service method.
 
    Attributes:
        status:          What happened (success / not_found / empty_data / db_error)
        data:            The cleaned result list on success, else empty list
        entity_searched: The raw input from the user (e.g., "metformin")
        entity_found:    The resolved canonical name (e.g., "Metformin HCl"), or None
    """
    status: ResultStatus
    data: list[Any] = field(default_factory=list)   #because list is mutable(same position in memory), we use default_factory to ensure each instance gets its own list
    entity_searched: str = ""
    entity_found: str | None = None
 
    @property
    def is_success(self) -> bool:
        return self.status == ResultStatus.SUCCESS
 
    @property
    def is_not_found(self) -> bool:
        return self.status == ResultStatus.NOT_FOUND
 
    @property
    def is_empty(self) -> bool:
        return self.status == ResultStatus.EMPTY_DATA
 
    @property
    def is_error(self) -> bool:
        return self.status == ResultStatus.DB_ERROR