"""
Graph Executor Node.

This node executes the generated Cypher query against the Neo4j database
and handles the results.
"""

from typing import Dict, Any, List
from src.agent.state import MedicalAgentState, add_to_execution_path, format_conversation_history_for_analysis
from src.database.neo4j_client import get_neo4j_client


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def graph_executor_node(state: MedicalAgentState) -> Dict[str, Any]:

    print(f"\n********* NODE 5: GRAPH EXECUTOR *********\n")
    conv_history = format_conversation_history_for_analysis(state.get("conversation_history"))
    print(f"----> CONVERSATION HISTORY:\n{conv_history}")

    cypher = state.get("generated_cypher", "")
    is_valid = state.get("cypher_is_valid", False)
    params = state.get("cypher_params", {})
    
    # Don't execute if Cypher is invalid or empty
    if not cypher or not is_valid:
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": "No valid Cypher query to execute",
            "execution_path": add_to_execution_path(state, "graph_executor")
        }
    
    try:
        # Get Neo4j client and execute query
        neo4j_client = get_neo4j_client()
        results = neo4j_client.run_safe_query(cypher, params)
        
        # Handle different result types
        if isinstance(results, str):
            # Error message returned as string
            if "ERROR" in results or "SECURITY_BLOCK" in results:
                return {
                    **state,
                    "graph_results": [],
                    "has_results": False,
                    "execution_error": results,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
            else:
                # Some other string result
                return {
                    **state,
                    "graph_results": [{"result": results}],
                    "has_results": True,
                    "execution_error": None,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
        
        elif isinstance(results, list):
            # Normal list of results
            has_results = len(results) > 0
            
            # Clean up results (remove None values, empty strings)
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
            
            return {
                **state,
                "graph_results": cleaned_results,
                "has_results": len(cleaned_results) > 0,
                "execution_error": None,
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
        
        else:
            # Unexpected result type
            return {
                **state,
                "graph_results": [],
                "has_results": False,
                "execution_error": f"Unexpected result type: {type(results)}",
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
            
    except Exception as e:
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": f"Query execution failed: {str(e)}",
            "execution_path": add_to_execution_path(state, "graph_executor"),
            "errors": state.get("errors", []) + [f"Error in graph_executor: {str(e)}"]
        }

