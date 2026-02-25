"""
Consolidated product discovery tool — replaces product_recommendation,
product_recommendation_flexible, and product_search.

Uses vector embeddings for cross-language semantic search,
with keyword fallback for exact ingredient matches.
"""
from langchain_core.tools import tool
import json
import logging
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.embeddings_service import get_embeddings
from src.services.results_formatter import clean_results

logger = logging.getLogger(__name__)


@tool
def find_belife_products(query: str) -> str:
    """Find BeLife supplement products matching a user need.
    Works with ANY input in ANY language: symptoms, nutrients, benefits,
    ingredients, product names, or health goals.
    
    This is the PRIMARY tool for all product discovery questions.
    
    Examples:
      - "fatigue" / "oboseală" / "vermoeidheid" → finds energy products
      - "Omega-3" → finds Omega products  
      - "probiotics" → finds Bifibiol, Imubiol
      - "stress" / "stres" → finds Anti-Stress 600
      - "B12" → finds products with B12
      - "muscle relaxation" → finds Magnesium products
      - "immunity" / "immuniteit" → finds immune products
      - "joint health" → finds Glucosamine, Tricartil
    
    Args:
        query: Natural language description of what the user needs — 
               product name, ingredient, symptom, benefit, or health goal.
    """
    neo4j = get_neo4j_client()
    
    logger.info(f"find_belife_products: '{query}'")
    
    # Strategy 1: Vector search (cross-language, semantic)
    embedding = get_embeddings(query)
    if embedding:
        try:
            results = neo4j.run_safe_query(
                CypherQueries.PRODUCT_VECTOR_SEARCH,
                {"embedding_vector": embedding, "top_k": 5}
            )
            if not _is_error(results):
                cleaned = clean_results(results)
                if cleaned:
                    logger.info(f"Vector search found {len(cleaned)} products for '{query}'")
                    return json.dumps(cleaned, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Vector search failed for '{query}': {e}")
    
    # Strategy 2: Keyword fallback (exact ingredient/name match)
    logger.info(f"Vector miss, trying keyword for '{query}'")
    try:
        results = neo4j.run_safe_query(
            CypherQueries.PRODUCT_KEYWORD_SEARCH,
            {"keywords": [query]}
        )
        if not _is_error(results):
            cleaned = clean_results(results)
            if cleaned:
                logger.info(f"Keyword search found {len(cleaned)} products for '{query}'")
                return json.dumps(cleaned, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Keyword search failed for '{query}': {e}")
    
    return json.dumps({
        "error": False,
        "message": f"I couldn't find BeLife products matching '{query}' in my database. Try different keywords or ask to browse the catalog.",
        "query": query,
        "tip": "You can also call product_catalog() to see all available categories."
    }, ensure_ascii=False)


def _is_error(results) -> bool:
    return isinstance(results, str) and "ERROR" in results
