import logging
from typing import Optional
 
from src.repositories.base_repository import BaseRepository
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries, CypherEntityValidationQueries
from src.services.embeddings_service import get_embeddings
from src.services.results_formatter import clean_results, is_error
 
logger = logging.getLogger(__name__)
 
 
class MedicationRepository(BaseRepository):
 
    def __init__(self):
        self._neo4j = get_neo4j_client()
 
    def find_by_direct_match(self, name: str) -> Optional[str]:
        result = self._neo4j.run_safe_query(
            CypherEntityValidationQueries.MEDICATION_DIRECT_QUERY,
            {"search_term": name},
        )
        return self.extract_name(result)
   
 
    def find_by_fulltext_match(self, name: str) -> Optional[str]:
        result = self._neo4j.run_safe_query(
            CypherEntityValidationQueries.MEDICATION_FULLTEXT_QUERY,
            {"search_term": name},
        )
        return self.extract_name(result)
 
    def find_by_embeddings_match(self, name: str) -> Optional[str]:
        try:
            embedding_vector = get_embeddings(name)
            if embedding_vector:
                result = self._neo4j.run_safe_query(
                    CypherEntityValidationQueries.MEDICATION_EMBEDDINGS_QUERY,
                    {"embedding_vector": embedding_vector, "top_k": 3, "similarity_threshold": 0.95},
                )
                return self.extract_name(result)
        except Exception as e:
            logger.warning(f"Embeddings search failed for medication '{name}': {e}")
        return None
 
    def resolve(self, user_input: str) -> Optional[str]:
        return (
            self.find_by_direct_match(user_input) or
            self.find_by_fulltext_match(user_input) or
            self.find_by_embeddings_match(user_input)
        )
 
    def find_depletions(self, canonical_name: str) -> list[dict]:
 
        results = self._neo4j.run_safe_query(
            CypherQueries.MEDICATION_LOOKUP,
            {"medications": [canonical_name]},
        )
 
        if is_error(results):
            logger.error(f"Database error during medication depletion lookup: {results}")
            return None
 
        return clean_results(results)
 
 
_med_repo_instance: MedicationRepository | None = None
 
 
def get_medication_repository() -> MedicationRepository:
    global _med_repo_instance
    if _med_repo_instance is None:
        _med_repo_instance = MedicationRepository()
    return _med_repo_instance