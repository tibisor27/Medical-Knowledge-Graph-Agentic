from abc import ABC, abstractmethod

class BaseRepository(ABC):

    @abstractmethod
    def resolve(self, user_input: str) -> str | None:
        """
        Resolv a users's inout ti the canonical enitity name in the graph 
        """
        ...

    @staticmethod
    def extract_name(result: list) -> str | None:
        """
        Extract the entity name from a raw neo4j result
        """
        
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("name")
        return None
