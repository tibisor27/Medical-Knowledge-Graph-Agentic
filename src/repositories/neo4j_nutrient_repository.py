import logging
from typing import Optional
 
from src.repositories.entity_repository import BaseRepository
from src.database.neo4j_client import get_neo4j_client
from .neo4j_queries import (
    NUTRIENT_DIRECT_QUERY,
    NUTRIENT_FULLTEXT_QUERY,
    NUTRIENT_LOOKUP
)
from src.services.embeddings_service import get_embeddings
from src.services.results_formatter import clean_results, is_error
 
logger = logging.getLogger(__name__)
 
class Neo4jNutrientRepository(BaseRepository):
    
    def __init__(self):
        self._neo4j = get_neo4j_client()

    def resolve(self, user_input: str) -> Optional[str]:
        return (
            self.find_by_direct_match(user_input) or
            self.find_by_fulltext_match(user_input)
        )

    def find_by_direct_match(self, name: str) -> Optional[str]:
        result = self._neo4j.run_safe_query(
            NUTRIENT_DIRECT_QUERY,
            {"search_term": name}
        )
        return self.extract_name(result)
    
    def find_by_fulltext_match(self, name: str) -> Optional[str]:
        result = self._neo4j.run_safe_query(
            NUTRIENT_FULLTEXT_QUERY,
            {"search_term": name}
        )
        return self.extract_name(result)

    
    def find_nutrient_metadata(self, canonical_name: str) -> list[dict]:

        results = self._neo4j.run_safe_query(
            NUTRIENT_LOOKUP,
            {"nutrients": [canonical_name]}
        )

        if is_error(results):
            logger.error(f"Database error during nutrient lookup: {results}")
            return None

        return clean_results(results)
            
            
_nutrient_repo_instance: Neo4jNutrientRepository | None = None

def get_neo4j_nutrient_repository() -> Neo4jNutrientRepository:
    global _nutrient_repo_instance
    if _nutrient_repo_instance is None:
        _nutrient_repo_instance = Neo4jNutrientRepository()
    return _nutrient_repo_instance   
    