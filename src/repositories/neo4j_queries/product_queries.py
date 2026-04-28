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