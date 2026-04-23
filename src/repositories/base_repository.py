from abc import ABC, abstractmethod
from typing import Optional

class BaseRepository(ABC):

    @abstractmethod
    def resolve(self, useer_input: str) -> Optional[str]:
        """
        Resolv a users's inout ti the canonical enitity name in the graph 
        """
        ...

    @staticmethod
    def extract_name(result) -> Optional[str]:
        """
        Extract the entity name from a raw neo4j result
        """
        
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("name")
        return None
