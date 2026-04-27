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
   
   
NUTRIENT_FULLTEXT_QUERY = """
    CALL db.index.fulltext.queryNodes("nutrient_full_search", $search_term)
    YIELD node, score
    WHERE score > 0.9
    RETURN node.name AS name, score, "Nutrient" AS node_type
    ORDER BY score DESC
    LIMIT 3
    """


NUTRIENT_DIRECT_QUERY = """
    MATCH (n:Nutrient)
    WHERE toLower(n.name) CONTAINS toLower($search_term)
    OR ANY(syn IN n.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
    RETURN n.name AS name, 1.0 AS score, "Nutrient" AS node_type
    LIMIT 3
    """