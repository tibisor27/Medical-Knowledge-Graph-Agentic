from src.database.neo4j_client import neo4j_client
from src.database.cypher_queries import CypherEntityValidationQueries
from src.agent.state import ResolvedEntity
import logging
from typing import Optional
from src.services.embeddings_service import get_embeddings
 
logger = logging.getLogger(__name__)
 
class EntityResolver:
    def __init__(self):
        self.neo4j_client = neo4j_client
 
    def resolve_nutrient(self, name) -> Optional[ResolvedEntity]:
 
        # First strategy: direct match (case-insensitive)
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.NUTRIENT_DIRECT_QUERY,
            {"search_term":name}
        )
 
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Nutrient"),
                match_method="direct_match",
                match_score=result[0].get("score", 1.0)
            )
            return resolved
       
        # Second strategy: full-text search
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.NUTRIENT_FULLTEXT_QUERY,
            {"search_term": name}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Nutrient"),
                match_method="fulltext_search",
                match_score=result[0].get("score", 1.0)
            )
            return resolved
       
        logger.warning(f"Could not resolve nutrient: '{name}'")
        return None
 
 
    def resolve_medication(self, name) -> Optional[ResolvedEntity]:
 
        # Strategy 1: Direct match
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.MEDICATION_DIRECT_QUERY,
            {"search_term": name}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Medication"),
                match_method="direct_match",
                match_score=result[0].get("score", 1.0)
            )
            logger.info(f"Medication resolved: {resolved}")
            return resolved
       
        # Strategy 2: Fulltext
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.MEDICATION_FULLTEXT_QUERY,
            {"search_term": name}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Medication"),
                match_method="fulltext_search",
                match_score=result[0].get("score", 1.0)
            )
            logger.info(f"Medication resolved: {resolved}")
            return resolved
       
        # Strategy 3: Embeddings
        try:
            embedding_vector = get_embeddings(name)
            if embedding_vector:
                query = CypherEntityValidationQueries.MEDICATION_EMBEDDINGS_QUERY
                params = {"embedding_vector": embedding_vector, "top_k": 3, "similarity_threshold": 0.95}
                result = self.neo4j_client.run_safe_query(query, params)
                if result and isinstance(result, list) and len(result) > 0:
                    resolved = ResolvedEntity(
                        original_text = name,
                        resolved_name=result[0].get("name", name),
                        node_type=result[0].get("node_type", "Medication"),
                        match_method="embeddings_search",
                        match_score=float(result[0].get("similarity", 0.0))
                    )
                    logger.info(f"Medication resolved via embeddings: {resolved}")
                    return resolved
        except Exception as e:
            logger.warning(f"Embeddings search failed for medication '{name}': {e}")
       
        logger.warning(f"Could not resolve medication: '{name}'")
        return None
 
    def resolve_symptom(self, name) -> Optional[ResolvedEntity]:
 
        # Strategy 1: Direct match
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.SYMPTOM_DIRECT_QUERY,
            {"search_term": name}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Symptom"),
                match_method="direct_match",
                match_score=result[0].get("score", 1.0)
            )
            return resolved
       
        # Strategy 2: Fulltext
        result = self.neo4j_client.run_safe_query(
            CypherEntityValidationQueries.SYMPTOM_FULLTEXT_QUERY,
            {"search_term": name}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = ResolvedEntity(
                original_text = name,
                resolved_name=result[0].get("name", name),
                node_type=result[0].get("node_type", "Symptom"),
                match_method="fulltext_search",
                match_score=result[0].get("score", 1.0)
            )
            return resolved
       
        #Strategy 3: Embeddings
        try:
            embedding_vector = get_embeddings(name)
            if embedding_vector:
                query = CypherEntityValidationQueries.SYMPTOM_EMBEDDINGS_QUERY
                params = {"embedding_vector": embedding_vector, "top_k": 3, "similarity_threshold": 0.65}
                result = self.neo4j_client.run_safe_query(query, params)
                if result and isinstance(result, list) and len(result) > 0:
                    resolved = ResolvedEntity(
                        original_text = name,
                        resolved_name=result[0].get("name", name),
                        node_type=result[0].get("node_type", "Symptom"),
                        match_method="embeddings_search",
                        match_score=float(result[0].get("similarity", 0.0))
                    )
                    logger.info(f"Symptom resolved via embeddings: {resolved}")
                    return resolved
        except Exception as e:
            logger.warning(f"Embeddings search failed for symptom '{name}': {e}")
       
        logger.warning(f"Could not resolve symptom: '{name}'")
        return None
   
 
 
_resolver = None
 
def get_entity_resolver() -> EntityResolver:
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver