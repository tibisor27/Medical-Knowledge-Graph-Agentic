import logging 
from src.infrastructure.neo4j_client import get_neo4j_client
from src.repositories.neo4j_queries import (
    MEDICATION_SYMPTOM_CONNECTION
)
from src.utils import clean_results, is_error
 
logger = logging.getLogger(__name__)
 
 
class Neo4jQueryRepository:
 
    def __init__(self):
        self._neo4j = get_neo4j_client()
 

    def find_med_symptom_connection(self, med_canonical_name: str, sym_canonical_name: str) -> list[dict]:
 
        results = self._neo4j.run_safe_query(
            MEDICATION_SYMPTOM_CONNECTION,
            {"medications": [med_canonical_name], "symptoms": [sym_canonical_name]},
        )
 
        if is_error(results):
            logger.error(f"Database error during medication symptom connection lookup: {results}")
            return None
 
        return clean_results(results)
 
 
_med_sym_repo_instance: Neo4jQueryRepository | None = None
 
 
def get_neo4j_query_repository() -> Neo4jQueryRepository:
    global _med_sym_repo_instance
    if _med_sym_repo_instance is None:
        _med_sym_repo_instance = Neo4jQueryRepository()
    return _med_sym_repo_instance