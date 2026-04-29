import logging

from src.repositories.entity_repository import BaseRepository
from src.repositories.neo4j_entity_mixin import Neo4jEntityMixin
from src.infrastructure.neo4j_client import get_neo4j_client
from src.repositories.neo4j_queries import (
    SYMPTOM_INVESTIGATION,
    SYMPTOM_DIRECT_QUERY,
    SYMPTOM_FULLTEXT_QUERY,
    SYMPTOM_EMBEDDINGS_QUERY
)
from src.infrastructure.embedding_client import get_embeddings
from src.utils import clean_results, is_error
 
logger = logging.getLogger(__name__)

class Neo4jSymptomRepository(BaseRepository, Neo4jEntityMixin):

    def __init__(self):
        self._neo4j = get_neo4j_client()
        
    def resolve(self, user_input: str) -> str | None:
        return (
            self.find_by_direct_match(user_input) or
            self.find_by_fulltext_match(user_input) or
            self.find_by_embeddings_match(user_input)
        )

    
    def find_by_direct_match(self, name: str) -> str | None:
        results = self._neo4j.run_safe_query(
            SYMPTOM_DIRECT_QUERY,
            {"search_term": name}
        )

        return self.extract_name(results)
    

    def find_by_fulltext_match(self, name: str) -> str | None:
        results = self._neo4j.run_safe_query(
            SYMPTOM_FULLTEXT_QUERY,
            {"search_term": name}
        )

        return self.extract_name(results)
    

    def find_by_embeddings_match(self, name: str) -> str | None:
        try:
            embedding = get_embeddings(name)
            if not embedding:
                return None
            
            results = self._neo4j.run_safe_query(
                SYMPTOM_EMBEDDINGS_QUERY,
                {
                    "embedding_vector": embedding,
                    "top_k": 1,
                    "similarity_threshold": 0.7
                }
            )
            return self.extract_name(results)
        except Exception as e:
            logger.error(f"Embeddings search failed for symptom '{name}': {e}")
            return None
    

    def fetch_entity_data(self, symptom_name: str) -> list[dict]:
        results = self._neo4j.run_safe_query(
            SYMPTOM_INVESTIGATION,
            {"symptom": symptom_name}
        )
        if is_error(results):
            logger.error(f"Error finding causes for symptom '{symptom_name}': {results}")
            return None
        return clean_results(results)


_symptom_repo_instance: Neo4jSymptomRepository | None = None    

def get_neo4j_symptom_repository() -> Neo4jSymptomRepository:
    global _symptom_repo_instance
    if _symptom_repo_instance is None:
        _symptom_repo_instance = Neo4jSymptomRepository()
    return _symptom_repo_instance