class CypherQueries:
    """Predefined Cypher queries for different retrieval types."""

    PRODUCT_KEYWORD_SEARCH = """
    // Search for products by keyword in name, description, ingredients, or benefit
    // Searches enriched properties: ingredients_text, ingredient_names, marketing_text
    
    UNWIND $keywords AS keyword
    
    MATCH (product:BeLifeProduct)
    WHERE toLower(product.name) CONTAINS toLower(keyword)
       OR toLower(product.scientific_description) CONTAINS toLower(keyword)
       OR toLower(product.target_benefit) CONTAINS toLower(keyword)
       OR toLower(COALESCE(product.ingredients_text, "")) CONTAINS toLower(keyword)
       OR ANY(ing IN COALESCE(product.ingredient_names, []) WHERE toLower(ing) CONTAINS toLower(keyword))
       OR toLower(COALESCE(product.marketing_text, "")) CONTAINS toLower(keyword)
    
    // Collect all nutrients in the product for context
    OPTIONAL MATCH (product)-[r:CONTAINS]->(nut:Nutrient)
    WITH product, keyword,
         collect(DISTINCT {
             name: nut.name,
             amount: r.amount,
             unit: r.unit
         }) AS all_product_nutrients
    
    RETURN {
        recommended_product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            dosage_timing: product.dosage_timing,
            precautions: product.precautions,
            ingredients_summary: product.ingredients_text
        },
        search_method: "keyword_match",
        matched_keyword: keyword,
        all_nutrients_in_product: all_product_nutrients[0..10]
    } AS recommendation
    
    LIMIT 5
"""

    PRODUCT_FULLTEXT_SEARCH = """
    // Fulltext search on BeLifeProduct nodes (requires product_full_search index)
    // Uses scoring for better relevance ranking
    
    CALL db.index.fulltext.queryNodes("product_full_search", $search_term)
    YIELD node AS product, score
    WHERE score > 0.3
    
    // Collect linked nutrients for context
    OPTIONAL MATCH (product)-[r:CONTAINS]->(nut:Nutrient)
    WITH product, score,
         collect(DISTINCT {
             name: nut.name,
             amount: r.amount,
             unit: r.unit
         }) AS all_product_nutrients
    
    ORDER BY score DESC
    
    RETURN {
        recommended_product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            dosage_timing: product.dosage_timing,
            precautions: product.precautions,
            ingredients_summary: product.ingredients_text
        },
        search_method: "fulltext",
        relevance_score: score,
        all_nutrients_in_product: all_product_nutrients[0..10]
    } AS recommendation
    
    LIMIT 5
"""

    PRODUCT_VECTOR_SEARCH = """
    // Semantic product search using embeddings (cross-language)
    // Returns top-k products by cosine similarity to the query embedding
    
    CALL db.index.vector.queryNodes(
        'product_embeddings', $top_k, $embedding_vector
    )
    YIELD node AS product, score
    
    RETURN {
        product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            dosage_timing: product.dosage_timing,
            precautions: product.precautions,
            ingredients_summary: product.ingredients_text,
            ingredient_names: product.ingredient_names
        },
        search_method: "vector_semantic",
        similarity_score: score
    } AS recommendation
    
    ORDER BY score DESC
    LIMIT $top_k
"""



    PRODUCT_CATALOG = """
    // Browse products - optionally filtered by category
    WITH $category AS cat_filter
    
    MATCH (product:BeLifeProduct)
    WHERE cat_filter = "" OR toLower(product.primary_category) CONTAINS toLower(cat_filter)
       OR toLower(product.target_benefit) CONTAINS toLower(cat_filter)
    
    RETURN {
        product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            ingredients_summary: product.ingredients_text
        }
    } AS catalog_entry
    
    ORDER BY product.primary_category, product.name
    LIMIT 20
"""
   
    PRODUCT_DETAILS = """
    MATCH (product:BeLifeProduct)
    WHERE toLower(product.name) = toLower($product_name)
       OR toLower(product.name) CONTAINS toLower($product_name)
    
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
    ORDER BY CASE WHEN toLower(product.name) = toLower($product_name) THEN 0 ELSE 1 END
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
 
   
    NUTRIENT_LOOKUP = """
    UNWIND $nutrients AS nut_name
    CALL db.index.fulltext.queryNodes("nutrient_full_search", nut_name)
    YIELD node AS nut, score
    WHERE score > 0.5
    WITH nut ORDER BY score DESC LIMIT 1
           
    // 2. Collect food sources
    OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
    WITH nut, collect(DISTINCT food.dietary_source) AS food_sources
 
    // 3. Collect side effects of supplementation (not deficiency!)
    OPTIONAL MATCH (nut)-[:Has_Side_Effect]->(se:SideEffect)
    WITH nut, food_sources, collect(DISTINCT se.side_effect) AS side_effects_list
           
    // 4. Final Aggregation - EDUCATIONAL INFORMATION ONLY
    RETURN {
        nutrient_info: {
            name: nut.name,
            overview: nut.overview,
            biological_function: nut.biological_function_effect
        },
       
        supplementation: {
            recommended_forms: nut.forms,
            daily_allowance: nut.rda,
            // Side effects if you take TOO MUCH supplement
            side_effects_if_overdosed: side_effects_list[0..5]
        },
       
        dietary_sources: food_sources[0..10]          
    } AS context
    """
   
    CONNECTION_VALIDATION = """
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
 
class CypherEntityValidationQueries:
    """Predefined Cypher queries for entity validation."""
   
    MEDICATION_FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes("medicament_full_search", $search_term)
    YIELD node, score
    WHERE score > 0.8
    RETURN node.name AS name, score, "Medicament" AS node_type
    ORDER BY score DESC
    LIMIT 3
    """
 
    NUTRIENT_FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes("nutrient_full_search", $search_term)
    YIELD node, score
    WHERE score > 0.9
    RETURN node.name AS name, score, "Nutrient" AS node_type
    ORDER BY score DESC
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
 
    SYMPTOM_DIRECT_QUERY = """
    MATCH (s:Symptom)
    WHERE toLower(s.name) CONTAINS toLower($search_term)
    RETURN s.name AS name, 1.0 AS score, "Symptom" AS node_type
    LIMIT 3
    """
 
    MEDICATION_DIRECT_QUERY = """
    MATCH (m:Medicament)
    WHERE toLower(m.name) CONTAINS toLower($search_term)
    OR ANY(brand IN m.brand_names WHERE toLower(brand) CONTAINS toLower($search_term))
    OR ANY(syn IN m.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
    RETURN m.name AS name, 1.0 AS score, "Medicament" AS node_type
    LIMIT 3
    """
 
    NUTRIENT_DIRECT_QUERY = """
    MATCH (n:Nutrient)
    WHERE toLower(n.name) CONTAINS toLower($search_term)
    OR ANY(syn IN n.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
    RETURN n.name AS name, 1.0 AS score, "Nutrient" AS node_type
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