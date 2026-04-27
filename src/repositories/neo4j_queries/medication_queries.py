MEDICATION_DIRECT_QUERY = """
    MATCH (m:Medicament)
    WHERE toLower(m.name) CONTAINS toLower($search_term)
    OR ANY(brand IN m.brand_names WHERE toLower(brand) CONTAINS toLower($search_term))
    OR ANY(syn IN m.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
    RETURN m.name AS name, 1.0 AS score, "Medicament" AS node_type
    LIMIT 3
    """

MEDICATION_FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes("medicament_full_search", $search_term)
    YIELD node, score
    WHERE score > 0.8
    RETURN node.name AS name, score, "Medicament" AS node_type
    ORDER BY score DESC
    LIMIT 3
    """

MEDICATION_EMBEDDINGS_QUERY = """
    CALL db.index.vector.queryNodes(
        'medication_embeddings',
        $top_k,
        $embedding_vector
    )
    YIELD node, score
    WHERE score > $similarity_threshold
    RETURN node.name AS name,
           score AS similarity,
           "Medicament" AS node_type
    ORDER BY score DESC
    LIMIT 1
    """

MEDICATION_LOOKUP = """
    UNWIND $medications AS med_name
   
    // 1. Find the medication
    CALL db.index.fulltext.queryNodes("medicament_full_search", med_name)
    YIELD node AS med, score
    WHERE score > 0.5
    WITH med, score ORDER BY score DESC LIMIT 1
 
    // 2. Find the relationships: Medication → DepletionEvent → Nutrient
    OPTIONAL MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
   
    // 3. For each nutrient, collect the associated symptoms
    OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
   
    // 4. Group symptoms by nutrient (KEY AGGREGATION!)
    WITH med, nut, de, collect(DISTINCT sym.name) AS symptoms_for_nutrient
   
    // 5. Build the object per nutrient with its symptoms
    WITH med,
        CASE WHEN nut IS NOT NULL THEN {
            nutrient: nut.name,
            symptoms: symptoms_for_nutrient
        } ELSE null END AS nutrient_data
   
    // 6. Collect all nutrients into a list
    WITH med, collect(nutrient_data) AS all_nutrients
   
    // 7. Filter out nulls and extract the list of symptoms for quick questions
    WITH med,
        [n IN all_nutrients WHERE n IS NOT NULL] AS depletions,
        reduce(acc = [], n IN all_nutrients |
            CASE WHEN n IS NOT NULL THEN acc + n.symptoms ELSE acc END
        ) AS all_symptoms_flat
   
    // 8. Return the final structure
    RETURN {
        medication: {
            name: med.name,
            synonyms: med.synonyms
        },
        // List of nutrients with their associated symptoms (structured)
        depletions: depletions[0..10]
    } AS context
    """

MEDICATION_SYMPTOM_CONNECTION = """
// 1. FIRST, find the medication (only one)
        UNWIND $medications AS med_input
        CALL db.index.fulltext.queryNodes('medicament_full_search', med_input)
        YIELD node AS med, score AS med_score
        WHERE med_score > 0.2
        WITH med ORDER BY med_score DESC LIMIT 1
       
        // 2. THEN, check EACH symptom from the input
        UNWIND $symptoms AS sym_input
       
        // 3. Find the connection for this symptom
        MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
        MATCH (de)-[:Has_Symptom]->(real_symptom:Symptom)
        WHERE toLower(real_symptom.name) CONTAINS toLower(sym_input)
        OR toLower(sym_input) CONTAINS toLower(real_symptom.name)
       
        // 4. Collect all matches for this symptom
        WITH med, sym_input,
            collect(DISTINCT {
                nutrient: nut.name,
                graph_symptom: real_symptom.name
            }) AS matches_for_symptom
        WHERE size(matches_for_symptom) > 0
       
        // 5. Aggregate results for ALL symptoms
        WITH med, collect({
            user_symptom: sym_input,
            matched_nutrients: [m IN matches_for_symptom | m.nutrient],
            matched_graph_symptoms: [m IN matches_for_symptom | m.graph_symptom]
        }) AS all_symptom_matches
       
        // 6. Extract unique list of nutrients
        WITH med, all_symptom_matches,
            reduce(acc = [], sm IN all_symptom_matches |
                acc + [n IN sm.matched_nutrients WHERE NOT n IN acc]
            ) AS unique_nutrients
       
        RETURN {
            connection_found: true,
            medication: med.name,
            validated_symptoms: all_symptom_matches,
            nutrients_to_recommend: unique_nutrients
        } AS validation
        """