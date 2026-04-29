from abc import ABC, abstractmethod

class BaseRepository(ABC):

    @abstractmethod
    def resolve(self, user_input: str) -> str | None:
        """
        Resolve a user's input to the canonical entity name in the graph.
        """
        ...


    @abstractmethod
    def fetch_entity_data(self, canonical_name: str) -> list[dict] | None:
        """
        Retrieve domain data for a resolved entity.
        Returns None on DB error, empty list if no data found.
        """
        ...

