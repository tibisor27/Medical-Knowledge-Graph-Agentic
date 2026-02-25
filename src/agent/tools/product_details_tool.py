from langchain_core.tools import tool
import json
import logging
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.results_formatter import clean_results

logger = logging.getLogger(__name__)


PRODUCT_DETAILS_FULLTEXT = """
CALL db.index.fulltext.queryNodes("product_name_search", $product_name)
YIELD node AS product, score
WHERE score > 0.5

RETURN {
    name: product.name,
    primary_category: product.primary_category,
    target_benefit: product.target_benefit,
    scientific_description: product.scientific_description,
    dosage_per_day: product.dosage_per_day,
    dosage_timing: product.dosage_timing,
    precautions: product.precautions,
    marketing_claims: product.marketing_claims,
    ingredients_summary: product.ingredients_text,
    ingredient_names: product.ingredient_names,
    interactions: product.interactions_text
} AS product_details

ORDER BY score DESC
LIMIT 1
"""


@tool
def product_details(product_name: str) -> str:
    """Get the full details (prospect) of a specific BeLife product.
    Use when the user asks about a product's dosage, ingredients, precautions, or how to take it.
    Use this AFTER find_belife_products has shown results and user wants more info.
    
    Args:
        product_name: The name of the BeLife product (e.g., 'Be-Energy', 'Magnesium Quatro 900', 'Anti-Stress 600').
    """
    neo4j = get_neo4j_client()
    
    logger.info(f"Product details lookup for: '{product_name}'")
    
    # Strategy 1: Exact match + CONTAINS (fast, precise)
    results = neo4j.run_safe_query(
        CypherQueries.PRODUCT_DETAILS,
        {"product_name": product_name}
    )
    
    if not _is_error(results):
        cleaned = clean_results(results)
        if cleaned:
            found_name = _extract_name(cleaned)
            logger.info(f"Product details found (exact/contains): '{found_name}'")
            return json.dumps(cleaned, indent=2, ensure_ascii=False)
    
    # Strategy 2: Fulltext fuzzy match (handles typos, spacing)
    logger.info(f"Exact/CONTAINS miss for '{product_name}', trying fulltext")
    try:
        results = neo4j.run_safe_query(
            PRODUCT_DETAILS_FULLTEXT,
            {"product_name": product_name}
        )
        if not _is_error(results):
            cleaned = clean_results(results)
            if cleaned:
                found_name = _extract_name(cleaned)
                logger.info(f"Product details found (fulltext): '{found_name}'")
                return json.dumps(cleaned, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Fulltext search failed: {e}")
    
    # Nothing found
    return json.dumps({
        "error": False,
        "message": f"I couldn't find a BeLife product named '{product_name}'. Check the exact name or use find_belife_products to search.",
        "product_searched": product_name
    }, ensure_ascii=False)


def _is_error(results) -> bool:
    return isinstance(results, str) and "ERROR" in results


def _extract_name(cleaned) -> str:
    """Extract product name from cleaned results for logging."""
    if isinstance(cleaned, list) and cleaned:
        item = cleaned[0]
        if isinstance(item, dict):
            pd = item.get("product_details", item)
            return pd.get("name", "unknown")
    return "unknown"
