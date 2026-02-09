import json
import logging
from typing import List
from langchain_core.tools import tool

from src.database.neo4j_client import get_neo4j_client

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════s════════════
# KNOWLEDGE GRAPH TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def medication_lookup(medication: str) -> str:
    """Look up what nutrients a medication depletes and what symptoms might occur.
    Use when user mentions a medication they take.
    
    Args:
        medication: The medication name (e.g., 'Metformin', 'Omeprazole', 'Aspirin')
    """
    neo4j = get_neo4j_client()
    
    query = """
    MATCH (med:Medicament)
    WHERE toLower(med.name) CONTAINS toLower($medication)
       OR ANY(syn IN med.synonyms WHERE toLower(syn) CONTAINS toLower($medication))
       OR ANY(brand IN med.brand_names WHERE toLower(brand) CONTAINS toLower($medication))
    WITH med
    ORDER BY
        CASE WHEN toLower(med.name) = toLower($medication) THEN 0
             WHEN toLower(med.name) STARTS WITH toLower($medication) THEN 1
             ELSE 2 END ASC,
        size(med.name) ASC
    LIMIT 1
    
    OPTIONAL MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
    OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
    
    WITH med, nut, collect(DISTINCT sym.name) AS symptoms
    WHERE nut IS NOT NULL
    
    WITH med, collect({nutrient: nut.name, symptoms: symptoms}) AS depleted_nutrients
    
    RETURN {
        medication: med.name,
        synonyms: med.synonyms,
        depleted_nutrients: depleted_nutrients
    } AS result
    """
    
    results = neo4j.run_safe_query(query, {"medication": medication})
    
    if isinstance(results, str) and "ERROR" in results:
        return f"Error looking up medication: {results}"
    
    if not results:
        return f"No information found for medication: {medication}"
    
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def symptom_investigation(symptom: str) -> str:
    """Investigate what could cause a symptom - which nutrient deficiencies or medications might be responsible.
    Use when user reports a symptom like fatigue, numbness, headache, etc.
    
    Args:
        symptom: The symptom to investigate (e.g., 'fatigue', 'numbness', 'headache')
    """
    neo4j = get_neo4j_client()
    
    query = """
    MATCH (sym:Symptom)
    WHERE toLower(sym.name) CONTAINS toLower($symptom)
       OR ANY(variant IN sym.layman_variants WHERE toLower(variant) CONTAINS toLower($symptom))
    WITH sym LIMIT 1
    
    MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
    MATCH (de)-[:DEPLETES]->(nut:Nutrient)
    OPTIONAL MATCH (med:Medicament)-[:CAUSES]->(de)
    
    WITH sym, collect(DISTINCT {
        medication: med.name,
        nutrient_depleted: nut.name
    }) AS possible_causes
    
    RETURN {
        symptom: sym.name,
        possible_causes: possible_causes
    } AS result
    """
    
    results = neo4j.run_safe_query(query, {"symptom": symptom})
    
    if isinstance(results, str) and "ERROR" in results:
        return f"Error investigating symptom: {results}"
    
    if not results:
        return f"No information found for symptom: {symptom}"
    
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def connection_validation(medication: str, symptom: str) -> str:
    """Check if there's a connection between a medication and symptom through nutrient depletion.
    Use when user asks if their medication could be causing their symptom.
    
    Args:
        medication: The medication to check
        symptom: The symptom to validate connection for
    """
    neo4j = get_neo4j_client()
    
    query = """
    MATCH (med:Medicament)
    WHERE toLower(med.name) CONTAINS toLower($medication)
    WITH med LIMIT 1
    
    MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
    MATCH (de)-[:Has_Symptom]->(sym:Symptom)
    WHERE toLower(sym.name) CONTAINS toLower($symptom)
    
    WITH med, sym, collect(DISTINCT nut.name) as connecting_nutrients
    
    RETURN {
        connection_found: true,
        medication: med.name,
        symptom: sym.name,
        connecting_nutrients: connecting_nutrients
    } AS result
    """
    
    results = neo4j.run_safe_query(query, {
        "medication": medication,
        "symptom": symptom
    })
    
    if isinstance(results, str) and "ERROR" in results:
        return f"Error validating connection: {results}"
    
    if not results or len(results) == 0:
        return json.dumps({
            "connection_found": False,
            "medication": medication,
            "symptom": symptom,
            "message": "No direct connection found in knowledge graph"
        }, ensure_ascii=False)
    
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def nutrient_education(nutrient: str) -> str:
    """Get detailed information about a nutrient - what it does, RDA, food sources, deficiency symptoms.
    Use when user wants to learn about a specific vitamin or mineral.
    
    Args:
        nutrient: The nutrient to learn about (e.g., 'Vitamin B12', 'Magnesium', 'Iron')
    """
    neo4j = get_neo4j_client()
    
    query = """
    MATCH (nut:Nutrient)
    WHERE toLower(nut.name) CONTAINS toLower($nutrient)
    WITH nut LIMIT 1
    
    OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
    OPTIONAL MATCH (nut)-[:Has_Side_Effect]->(se:SideEffect)
    OPTIONAL MATCH (nut)<-[:DEPLETES]-(de:DepletionEvent)-[:Has_Symptom]->(sym:Symptom)
    
    WITH nut, 
         collect(DISTINCT food.dietary_source)[0..5] as food_sources,
         collect(DISTINCT se.side_effect)[0..5] as side_effects,
         collect(DISTINCT sym.name)[0..5] as deficiency_symptoms
    
    RETURN {
        nutrient: nut.name,
        overview: nut.overview,
        biological_function: nut.biological_function_effect,
        rda: nut.rda,
        forms: nut.forms,
        food_sources: food_sources,
        side_effects: side_effects,
        deficiency_symptoms: deficiency_symptoms
    } AS result
    """
    
    results = neo4j.run_safe_query(query, {"nutrient": nutrient})
    
    if isinstance(results, str) and "ERROR" in results:
        return f"Error getting nutrient info: {results}"
    
    if not results:
        return f"No information found for nutrient: {nutrient}"
    
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def product_recommendation(nutrients: List[str]) -> str:
    """Find BeLife products that contain specific nutrients.
    Use ONLY after nutrients have been identified through previous lookups, 
    and user explicitly asks for a recommendation.
    
    Args:
        nutrients: List of nutrients to find products for (e.g., ['Vitamin B12', 'Folic Acid'])
    """
    neo4j = get_neo4j_client()
    
    # Handle single nutrient passed as string
    if isinstance(nutrients, str):
        nutrients = [nutrients]
    
    query = """
    WITH $nutrients AS needed_nutrients
    
    MATCH (product:BeLifeProduct)-[r:CONTAINS]->(nut:Nutrient)
    WHERE nut.name IN needed_nutrients
    
    WITH product, needed_nutrients,
         collect(DISTINCT {name: nut.name, amount: r.amount, unit: r.unit}) AS matched_nutrients,
         size(collect(DISTINCT nut.name)) AS coverage
    
    ORDER BY coverage DESC
    LIMIT 3
    
    RETURN {
        product_name: product.name,
        category: product.primary_category,
        target_benefit: product.target_benefit,
        dosage: product.dosage_per_day,
        timing: product.dosage_timing,
        matched_nutrients: matched_nutrients,
        coverage: coverage,
        total_needed: size(needed_nutrients)
    } AS result
    """
    
    results = neo4j.run_safe_query(query, {"nutrients": nutrients})
    
    if isinstance(results, str) and "ERROR" in results:
        return f"Error finding products: {results}"
    
    if not results:
        return f"No BeLife products found for nutrients: {nutrients}"
    
    return json.dumps(results, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def custom_graph_query(question: str) -> str:
    """Generate and execute a custom Cypher query for complex questions not covered by other tools.
    Use this ONLY when medication_lookup, symptom_investigation, connection_validation, 
    nutrient_education, and product_recommendation cannot answer the user's question.
    
    Examples of when to use:
    - "What medications deplete both B12 AND Magnesium?"
    - "Show me all nutrients with more than 5 food sources"
    - "Which symptoms are shared by multiple nutrient deficiencies?"
    
    Args:
        question: Natural language description of what information to find in the knowledge graph
    """
    from src.utils.get_llm import get_llm_4_1_mini
    
    neo4j = get_neo4j_client()
    llm = get_llm_4_1_mini()
    
    # Get schema for context
    schema_query = """
    CALL db.schema.visualization() YIELD nodes, relationships
    RETURN nodes, relationships
    """
    
    # Simplified schema description
    schema_description = """
    Knowledge Graph Schema:
    
    Nodes:
    - Medicament (name, synonyms, brand_names)
    - Nutrient (name, overview, biological_function_effect, rda, forms)
    - Symptom (name, layman_variants)
    - DepletionEvent (mechanism)
    - FoodSource (dietary_source)
    - SideEffect (side_effect)
    - BeLifeProduct (name, primary_category, target_benefit, dosage_per_day)
    
    Relationships:
    - (Medicament)-[:CAUSES]->(DepletionEvent)
    - (DepletionEvent)-[:DEPLETES]->(Nutrient)
    - (DepletionEvent)-[:Has_Symptom]->(Symptom)
    - (Nutrient)-[:Found_In]->(FoodSource)
    - (Nutrient)-[:Has_Side_Effect]->(SideEffect)
    - (BeLifeProduct)-[:CONTAINS]->(Nutrient)
    """
    
    # Generate Cypher query
    generation_prompt = f"""You are a Neo4j Cypher expert. Generate a Cypher query to answer this question:

Question: {question}

{schema_description}

Rules:
1. Return results as a list of objects with meaningful property names
2. Use LIMIT 10 to avoid large result sets
3. Use toLower() for string matching
4. Only query existing node labels and relationships
5. Return ONLY the Cypher query, no explanations

Cypher query:"""

    try:
        response = llm.invoke(generation_prompt)
        cypher_query = response.content.strip()
        
        # Clean up the query (remove markdown code blocks if present)
        if "```" in cypher_query:
            cypher_query = cypher_query.split("```")[1]
            if cypher_query.startswith("cypher"):
                cypher_query = cypher_query[6:]
            cypher_query = cypher_query.strip()
        
        logger.info(f"Generated Cypher: {cypher_query}")
        
        # Execute the query
        results = neo4j.run_safe_query(cypher_query, {})
        
        if isinstance(results, str) and "ERROR" in results:
            return f"Query execution error: {results}. The generated query was: {cypher_query}"
        
        if not results:
            return f"No results found for: {question}"
        
        return json.dumps({
            "question": question,
            "generated_query": cypher_query,
            "results": results
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"Error in custom_graph_query: {e}")
        return f"Error generating or executing query: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

ALL_TOOLS = [
    medication_lookup,
    symptom_investigation,
    connection_validation,
    nutrient_education,
    product_recommendation,
    custom_graph_query,  
]


def get_all_tools():
    """Get all available tools for the agent."""
    return ALL_TOOLS
