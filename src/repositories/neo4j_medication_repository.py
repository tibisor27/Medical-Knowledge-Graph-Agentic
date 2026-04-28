import logging
 
from src.repositories.entity_repository import BaseRepository
from src.repositories.neo4j_entity_mixin import Neo4jEntityMixin
from src.infrastructure.neo4j_client import get_neo4j_client
from src.repositories.neo4j_queries import (
    MEDICATION_DIRECT_QUERY,
    MEDICATION_FULLTEXT_QUERY,
    MEDICATION_EMBEDDINGS_QUERY,
    MEDICATION_LOOKUP
)
from src.infrastructure.embedding_client import get_embeddings
from src.utils import clean_results, is_error
 
logger = logging.getLogger(__name__)
 
 
class Neo4jMedicationRepository(BaseRepository, Neo4jEntityMixin):
 
    def __init__(self):
        self._neo4j = get_neo4j_client()
 
    def resolve(self, user_input: str) -> str | None:
        return (
            self.find_by_direct_match(user_input) or
            self.find_by_fulltext_match(user_input) or
            self.find_by_embeddings_match(user_input)
        )


    def find_by_direct_match(self, name: str) -> str | None:
        result = self._neo4j.run_safe_query(
            MEDICATION_DIRECT_QUERY,
            {"search_term": name},
        )

        return self.extract_name(result)
   
 
    def find_by_fulltext_match(self, name: str) -> str | None:
        result = self._neo4j.run_safe_query(
            MEDICATION_FULLTEXT_QUERY,
            {"search_term": name},
        )

        return self.extract_name(result)
 
    def find_by_embeddings_match(self, name: str) -> str | None:
        try:
            embedding_vector = get_embeddings(name)
            if embedding_vector:
                result = self._neo4j.run_safe_query(
                    MEDICATION_EMBEDDINGS_QUERY,
                    {
                        "embedding_vector": embedding_vector, 
                        "top_k": 3, 
                        "similarity_threshold": 0.95
                    }
                )
                return self.extract_name(result)
        except Exception as e:
            logger.warning(f"Embeddings search failed for medication '{name}': {e}")
        return None
 
 
    def fetch_entity_data(self, canonical_name: str) -> list[dict]:
 
        results = self._neo4j.run_safe_query(
            MEDICATION_LOOKUP,
            {"medications": [canonical_name]},
        )
 
        if is_error(results):
            logger.error(f"Database error during medication depletion lookup: {results}")
            return None
 
        return clean_results(results)
 
 
_med_repo_instance: Neo4jMedicationRepository | None = None
 
 
def get_neo4j_medication_repository() -> Neo4jMedicationRepository:
    global _med_repo_instance
    if _med_repo_instance is None:
        _med_repo_instance = Neo4jMedicationRepository()
    return _med_repo_instance