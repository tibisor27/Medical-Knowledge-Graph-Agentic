import json
import logging
from typing import Dict, Any, Tuple

from src.agent.state import MedicalAgentState, RetrievalType, add_to_execution_path
from src.agent.utils import extract_nutrients_from_results
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries

logger = logging.getLogger(__name__)


def graph_executor_node(state: MedicalAgentState) -> Dict[str, Any]:
    
    analysis = state.get("conversation_analysis")
    if not analysis:
        logger.warning("No conversation analysis found")
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": "No conversation analysis available",
            "execution_path": add_to_execution_path(state, "graph_executor")
        }
    
    r_type = analysis.retrieval_type
    
    query_medications = analysis.query_medications
    query_symptoms = analysis.query_symptoms
    query_nutrients = analysis.query_nutrients
    
    # Log what we're using for the query
    logger.info(f"Graph Executor using query entities:")
    logger.info(f"  Medications: {query_medications}")
    logger.info(f"  Symptoms: {query_symptoms}")
    logger.info(f"  Nutrients: {query_nutrients}")

    # Select query and params based on retrieval type
    query, params = _get_query_and_params(
        r_type,
        query_medications,
        query_symptoms,
        query_nutrients,
        analysis.accumulated_nutrients
    )
    
    # If no query (e.g., NO_RETRIEVAL), return empty results
    if not query:
        logger.info(f"No query needed for retrieval type: {r_type}")
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": None,
            "execution_path": add_to_execution_path(state, "graph_executor")
        }
    
    # Execute query
    return _execute_query(state, query, params)


def _get_query_and_params(
    r_type: RetrievalType,
    query_medications: list,
    query_symptoms: list,
    query_nutrients: list,
    accumulated_nutrients: list
) -> Tuple[str, Dict[str, Any]]:

    if r_type == RetrievalType.MEDICATION_LOOKUP:
        return CypherQueries.MEDICATION_LOOKUP, {"medications": query_medications}
    
    elif r_type == RetrievalType.SYMPTOM_INVESTIGATION:
        return CypherQueries.SYMPTOM_INVESTIGATION, {"symptoms": query_symptoms}
    
    elif r_type == RetrievalType.NUTRIENT_EDUCATION:
        return CypherQueries.NUTRIENT_EDUCATION, {"nutrients": query_nutrients}
    
    elif r_type == RetrievalType.CONNECTION_VALIDATION:
        return CypherQueries.CONNECTION_VALIDATION, {
            "medications": query_medications,
            "symptoms": query_symptoms
        }
    
    elif r_type == RetrievalType.PRODUCT_RECOMMENDATION:

        nutrients_to_use = accumulated_nutrients if accumulated_nutrients else query_nutrients
        logger.info(f"PRODUCT_RECOMMENDATION using nutrients: {nutrients_to_use}")
        return CypherQueries.PRODUCT_RECOMMENDATION, {"nutrients": nutrients_to_use}
    
    elif r_type == RetrievalType.NO_RETRIEVAL:
        return "", {}
    
    else:
        logger.warning(f"Unknown retrieval type: {r_type}")
        return "", {}


def _execute_query(state: MedicalAgentState, query: str, params: dict) -> Dict[str, Any]:

    try:
        neo4j_client = get_neo4j_client()
        results = neo4j_client.run_safe_query(query, params)
        
        # Handle error string response
        if isinstance(results, str):
            if "ERROR" in results or "SECURITY_BLOCK" in results:
                logger.error(f"Query error: {results}")
                return {
                    **state,
                    "graph_results": [],
                    "has_results": False,
                    "execution_error": results,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
            else:
                logger.info(f"Query returned string result")
                return {
                    **state,
                    "graph_results": [{"result": results}],
                    "has_results": True,
                    "execution_error": None,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
        
        # Handle list response (normal case)
        elif isinstance(results, list):
            cleaned_results = _clean_results(results)
            logger.info(f"Query returned {len(cleaned_results)} results")
            
            # Extract nutrients directly from DB results and merge into analysis
            discovered_nutrients = extract_nutrients_from_results(cleaned_results)
            if discovered_nutrients:
                logger.info(f"Discovered nutrients from DB: {discovered_nutrients}")
                analysis = state.get("conversation_analysis")
                if analysis:
                    existing = set(getattr(analysis, "accumulated_nutrients", []) or [])
                    merged = list(existing.union(discovered_nutrients))
                    analysis.accumulated_nutrients = merged
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Graph Results: {json.dumps(cleaned_results, indent=2)}")
            
            return {
                **state,
                "graph_results": cleaned_results,
                "has_results": len(cleaned_results) > 0,
                "execution_error": None,
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
        
        else:
            logger.error(f"Unexpected result type: {type(results)}")
            return {
                **state,
                "graph_results": [],
                "has_results": False,
                "execution_error": f"Unexpected result type: {type(results)}",
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
            
    except Exception as e:
        logger.exception(f"Query execution failed: {e}")
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": f"Query execution failed: {str(e)}",
            "execution_path": add_to_execution_path(state, "graph_executor"),
            "errors": state.get("errors", []) + [f"Error in graph_executor: {str(e)}"]
        }


def _clean_results(results: list) -> list:
    """
    Clean query results by removing None values and empty strings/lists.
    
    Args:
        results: Raw query results
        
    Returns:
        Cleaned results list
    """
    cleaned_results = []
    for record in results:
        if isinstance(record, dict):
            cleaned_record = {
                k: v for k, v in record.items() 
                if v is not None and v != "" and v != []
            }
            if cleaned_record:
                cleaned_results.append(cleaned_record)
        else:
            cleaned_results.append(record)
    return cleaned_results

