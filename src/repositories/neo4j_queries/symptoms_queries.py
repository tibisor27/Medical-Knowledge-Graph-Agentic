SYMPTOM_INVESTIGATION = """
    // INPUT: $symptom (A symptom)
    // OUTPUT: ALL possible causes - filtered by the agent
   
    // 1. Find the symptom
    CALL db.index.fulltext.queryNodes('symptom_full_search', $symptom)
    YIELD node AS sym, score
    WHERE score > 0.3
    WITH sym ORDER BY score DESC LIMIT 1
   
    // 2. Find ALL connections
    MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
    MATCH (de)-[:DEPLETES]->(nut:Nutrient)
    OPTIONAL MATCH (med:Medicament)-[:CAUSES]->(de)
   
    // 3. Group by medication
    WITH sym, med, collect(DISTINCT nut.name) AS nutrients_depleted
   
    // 4. Collect all medication-cause pairs
    WITH sym, collect({
        medication: COALESCE(med.name, "General Deficiency (no specific drug)"),
        depleted_nutrients: nutrients_depleted
    }) AS all_causes
   
    // 5. Return results
    RETURN {
        symptom: sym.name,
        possible_causes: all_causes,
        total_causes_found: size(all_causes)
    } AS context
    """

SYMPTOM_DIRECT_QUERY = """
    MATCH (s:Symptom)
    WHERE toLower(s.name) CONTAINS toLower($search_term)
    RETURN s.name AS name, 1.0 AS score, "Symptom" AS node_type
    LIMIT 3
    """

SYMPTOM_FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes("symptom_full_search", $search_term)
    YIELD node, score
    WHERE score > 0.90
    RETURN node.name AS name, score, "Symptom" AS node_type
    ORDER BY score DESC
    LIMIT 3
    """


SYMPTOM_EMBEDDINGS_QUERY = """
    CALL db.index.vector.queryNodes(
        'symptom_embeddings',
        $top_k,
        $embedding_vector
    )
    YIELD node, score
    WHERE score > $similarity_threshold
    RETURN node.name AS name,
           score AS similarity,
           "Symptom" AS node_type
    ORDER BY score DESC
    LIMIT 1
    """