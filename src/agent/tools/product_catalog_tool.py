from langchain_core.tools import tool
import json
import logging
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.results_formatter import clean_results

logger = logging.getLogger(__name__)


@tool
def product_catalog(category: str = "") -> str:
    """Browse the BeLife product catalog, optionally filtered by category.
    Use when user wants to see what products are available or browse by category.
    If no category is specified, returns all categories with product counts.
    
    Args:
        category: Optional category filter (e.g., 'vitamin', 'mineral', 'energy', 'immunity').
                  Leave empty to list all categories.
    """
    neo4j = get_neo4j_client()
    
    logger.info(f"Product catalog browse, category='{category}'")
    
    results = neo4j.run_safe_query(
        CypherQueries.PRODUCT_CATALOG,
        {"category": category}
    )
    
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during product catalog browse: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue browsing products. Please try again."
        }, ensure_ascii=False)
    
    cleaned = clean_results(results)
    if not cleaned:
        if category:
            return json.dumps({
                "error": False,
                "message": f"No BeLife products found in category '{category}'. Try browsing all categories by leaving the category empty.",
                "category_searched": category
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "error": False,
                "message": "No products found in the catalog."
            }, ensure_ascii=False)
    
    logger.info(f"Found {len(cleaned)} catalog entries")
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
