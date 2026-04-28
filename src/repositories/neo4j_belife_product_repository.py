import logging

from src.repositories.product_repository import BaseProductRepository
from src.infrastructure.embedding_client import get_embeddings
from src.utils import clean_results, is_error
from src.infrastructure.neo4j_client import get_neo4j_client
from src.repositories.neo4j_queries import (
    PRODUCT_KEYWORD_SEARCH,
    PRODUCT_FULLTEXT_SEARCH,
    PRODUCT_VECTOR_SEARCH,
    PRODUCT_DETAILS
)

logger = logging.getLogger(__name__)

class Neo4jProductRepository(BaseProductRepository):
    def __init__(self):
        self.neo4j = get_neo4j_client()

    def search_products(self, query: str) -> list[dict] | None:

        #embeddings
        results = self._search_by_embedding(query)
        if results is None:
            return None
        if results:
            return results
        
        #fulltext
        results = self._search_by_keyword(query)
        if results is None:
            return None
        return results


    def get_product_details(self, product_name: str) -> list[dict] | None:

        results = self._get_details_by_exact_match(product_name)
        if results is None:
            return None
        if results:
            return results
        
        results = self._get_details_by_fulltext_match(product_name)
        if results is None:
            return None
        return results


    def _search_by_embedding(self, query: str) -> list[dict] | None:
        try:
            embeddings = get_embeddings(query)
            if not embeddings:
                return []   #skip to the next method(keyword matching)

            results = self.neo4j.run_safe_query(
                PRODUCT_VECTOR_SEARCH,
                {
                    "embedding_vector": embeddings,
                    "top_k": 5,
                    "similarity_threshold": 0.7
                }
            )
            if is_error(results):
                logger.error(f"Error searching products by embedding: {results}")
                return None
            return clean_results(results)
        except Exception as e:
            logger.error(f"Error searching products by embedding: {e}")
            return []

    def _search_by_keyword(self, query: list[str]) -> list[dict] | None:
        try:
            results = self.neo4j.run_safe_query(
                PRODUCT_KEYWORD_SEARCH,
                {
                    "keywords": query
                }
            )
            if is_error(results):
                logger.error(f"Error searching products by keyword: {results}")
                return None
            return clean_results(results)
        except Exception as e:
            logger.error(f"Error searching products by keyword: {e}")
            return None

        
    def _get_details_by_exact_match(self, product_name: str) -> list[dict] | None:
        results = self.neo4j.run_safe_query(
            PRODUCT_DETAILS,
            {"product_name": product_name}
        )
        if is_error(results):
            logger.error(f"DB error in exact product lookup: {results}")
            return None
        return clean_results(results)

    
    def _get_details_by_fulltext_match(self, product_name: str) -> list[dict] | None:
        try:
            results = self.neo4j.run_safe_query(
                PRODUCT_FULLTEXT_SEARCH,
                {
                    "query": product_name
                }
            )
            if is_error(results):
                logger.error(f"Error getting product details by fulltext match: {results}")
                return None
            return clean_results(results)
        except Exception as e:
            logger.error(f"Error getting product details by fulltext match: {e}")
            return None

                
_prod_repository_instance: Neo4jProductRepository | None = None

def get_neo4j_product_repository() -> Neo4jProductRepository:
    global _prod_repository_instance
    if _prod_repository_instance is None:
        _prod_repository_instance = Neo4jProductRepository()
    return _prod_repository_instance