from abc import ABC, abstractmethod

class BaseProductRepository(ABC):
    @abstractmethod
    def search_products(self, query: str) -> list[dict] | None:
        """
        semantic + keyword product discovery
        """
        ...

    @abstractmethod
    def get_product_details(self, product_name: str) -> list[dict] | None:
        """
        full product prospect discovery
        """
        ...