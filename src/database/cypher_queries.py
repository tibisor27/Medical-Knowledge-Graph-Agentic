class CypherQueries:
    """Predefined Cypher queries for different retrieval types."""

    PRODUCT_RECOMMENDATION = """
    // 1. Primim lista de nutrienți necesari
    WITH $nutrients AS needed_nutrients
    
    // 2. Găsim produsele care conțin CEL PUȚIN UN nutrient din listă
    MATCH (product:BeLifeProduct)-[r:CONTAINS]->(nut:Nutrient)
    WHERE nut.name IN needed_nutrients
    
    // 3. Grupăm per produs - colectăm nutrienții matched cu toate detaliile
    WITH product, needed_nutrients,
         collect(DISTINCT {
             name: nut.name,
             amount: r.amount,
             unit: r.unit
         }) AS matched_nutrients
    
    // 4. Calculăm scorul de coverage
    WITH product, needed_nutrients, matched_nutrients,
         size(matched_nutrients) AS nutrients_covered,
         size(needed_nutrients) AS nutrients_needed
    
    // 5. Colectăm TOȚI nutrienții din produs (pentru context complet)
    OPTIONAL MATCH (product)-[all_r:CONTAINS]->(all_nut:Nutrient)
    WITH product, needed_nutrients, matched_nutrients, nutrients_covered, nutrients_needed,
         collect(DISTINCT {
             name: all_nut.name,
             amount: all_r.amount,
             unit: all_r.unit
         }) AS all_product_nutrients
    
    // 6. Ordonăm după câți nutrienți acoperă (cel mai bun primul)
    ORDER BY nutrients_covered DESC
    
    // 7. Returnăm rezultatul cu TOATE informațiile
    RETURN {
        recommended_product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            dosage_timing: product.dosage_timing,
            precautions: product.precautions
        },
        coverage: {
            nutrients_covered: nutrients_covered,
            nutrients_needed: nutrients_needed,
            coverage_percent: toInteger(toFloat(nutrients_covered) / nutrients_needed * 100)
        },
        matched_nutrients: matched_nutrients,
        other_nutrients_in_product: [n IN all_product_nutrients WHERE NOT n.name IN needed_nutrients][0..5]
    } AS recommendation
    
    LIMIT 1
"""
    
    MEDICATION_LOOKUP = """
    UNWIND $medications AS med_name
    
    // 1. Găsim medicamentul
    CALL db.index.fulltext.queryNodes("medicament_full_search", med_name)
    YIELD node AS med, score
    WHERE score > 0.5
    WITH med, score ORDER BY score DESC LIMIT 1
 
    // 2. Găsim relațiile: Medicament → DepletionEvent → Nutrient
    OPTIONAL MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
    
    // 3. Pentru fiecare nutrient, colectăm simptomele asociate
    OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
    
    // 4. Grupăm simptomele per nutrient (AGREGARE CHEIE!)
    WITH med, nut, de, collect(DISTINCT sym.name) AS symptoms_for_nutrient
    
    // 5. Construim obiectul per nutrient cu simptomele sale
    WITH med,
        CASE WHEN nut IS NOT NULL THEN {
            nutrient: nut.name,
            symptoms: symptoms_for_nutrient
        } ELSE null END AS nutrient_data
    
    // 6. Agregăm toți nutrienții într-o listă
    WITH med, collect(nutrient_data) AS all_nutrients
    
    // 7. Filtrăm null-urile și extragem lista de simptome pentru întrebări rapide
    WITH med,
        [n IN all_nutrients WHERE n IS NOT NULL] AS depletions,
        reduce(acc = [], n IN all_nutrients |
            CASE WHEN n IS NOT NULL THEN acc + n.symptoms ELSE acc END
        ) AS all_symptoms_flat
    
    // 8. Returnăm structura finală
    RETURN {
        medication: {
            name: med.name,
            synonyms: med.synonyms
        },
        // Lista de nutrienți cu simptomele lor (structurată)
        depletions: depletions[0..10]
    } AS context
    """
 
    
    SYMPTOM_INVESTIGATION = """
    // ═══════════════════════════════════════════════════════════════════════════════
    // SYMPTOM_INVESTIGATION - Caută simptome DOAR în medicamentele userului
    // ═══════════════════════════════════════════════════════════════════════════════
    // INPUT: $symptoms (lista de simptome), $medications (lista de medicamente user)
    // OUTPUT: Pentru fiecare simptom, care din medicamentele userului îl pot cauza
    // ═══════════════════════════════════════════════════════════════════════════════
    
    // Parametrii de input
    WITH $symptoms AS input_symptoms, $medications AS user_medications
    
    UNWIND input_symptoms AS symptom_name
    
    // 1. Căutare Simptom în index fulltext
    CALL {
        WITH symptom_name
        CALL db.index.fulltext.queryNodes('symptom_full_search', symptom_name) 
        YIELD node AS sym, score
        WHERE score > 0.3
        RETURN sym
        ORDER BY score DESC
        LIMIT 1
    }
    
    // 2. Găsim relațiile - FILTRATE pe medicamentele userului
    WITH sym, user_medications
    MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
    MATCH (de)-[:DEPLETES]->(nut:Nutrient)
    OPTIONAL MATCH (med:Medicament)-[:CAUSES]->(de)
    
    // 3. FILTRUL CHEIE: Doar medicamentele userului SAU deficiențe orfane
    WHERE med IS NULL 
       OR ANY(user_med IN user_medications WHERE 
              toLower(med.name) CONTAINS toLower(user_med) OR 
              toLower(user_med) CONTAINS toLower(med.name))

    // 4. Grupăm după simptom și medicament
    WITH sym, med, collect(DISTINCT nut.name) AS nutrients_depleted

    // 5. Separăm: Medicamente user vs. Deficiențe generale (fără medicament cunoscut)
    WITH sym,
        CASE WHEN med IS NOT NULL THEN {
            drug_name: med.name,
            depletes_nutrients: nutrients_depleted 
        } ELSE null END AS drug_match,
        
        CASE WHEN med IS NULL THEN nutrients_depleted ELSE null END AS orphan_nutrients

    // 6. Agregare finală per simptom
    WITH sym, 
        collect(drug_match) AS all_drug_matches,
        collect(orphan_nutrients) AS all_orphan_lists

    WITH sym, 
        [x IN all_drug_matches WHERE x IS NOT NULL] AS user_drug_causes,
        reduce(acc=[], list IN [y IN all_orphan_lists WHERE y IS NOT NULL] | acc + list) AS general_deficiencies

    // 7. Return structurat per simptom
    // IMPORTANT: possible_deficiencies DOAR când NU avem conexiune cu medicamentele userului
    // Previne halucinații: LLM nu va confunda deficiențele orfane cu cele din medicament
    RETURN {
        symptom: sym.name,
        // Medicamentele USERULUI care cauzează acest simptom
        your_medications_causing_this: user_drug_causes,
        // Deficiențe generale - DOAR dacă nu am găsit conexiune cu medicamentele userului
        possible_deficiencies: CASE 
            WHEN size(user_drug_causes) > 0 THEN []  // Am conexiune → nu mai dăm alternative
            ELSE general_deficiencies[0..5]          // Nu am conexiune → dăm sugestii
        END,
        // Flag: Am găsit legătură cu medicamentele userului?
        found_connection: size(user_drug_causes) > 0
    } AS context
    """
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # NUTRIENT EDUCATION - STRICT INFORMATIONAL (NO MEDICATIONS/SYMPTOMS)
    # ═══════════════════════════════════════════════════════════════════════════════
    # Returnează DOAR informații educaționale despre nutrient:
    # - Ce este, cum funcționează în corp
    # - Forme recomandate, doză zilnică
    # - Surse alimentare
    # - Efecte adverse ale suplimentării
    # NU include: simptome, medicamente, conexiuni
    # ═══════════════════════════════════════════════════════════════════════════════
    
    NUTRIENT_EDUCATION = """
    UNWIND $nutrients AS nut_name
    CALL db.index.fulltext.queryNodes("nutrient_full_search", nut_name) 
    YIELD node AS nut, score
    WHERE score > 0.5
    WITH nut ORDER BY score DESC LIMIT 1
            
    // 2. Colectăm sursele de hrană
    OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
    WITH nut, collect(DISTINCT food.dietary_source) AS food_sources

    // 3. Colectăm Side Effects ale SUPLIMENTĂRII (nu ale deficienței!)
    OPTIONAL MATCH (nut)-[:Has_Side_Effect]->(se:SideEffect)
    WITH nut, food_sources, collect(DISTINCT se.side_effect) AS side_effects_list
            
    // 4. Agregare Finală - DOAR INFORMAȚII EDUCAȚIONALE
    RETURN {
        nutrient_info: {
            name: nut.name,
            overview: nut.overview,
            biological_function: nut.biological_function_effect
        },
        
        supplementation: {
            recommended_forms: nut.forms,
            daily_allowance: nut.rda,
            // Efecte adverse dacă iei PREA MULT supliment
            side_effects_if_overdosed: side_effects_list[0..5]
        },
        
        dietary_sources: food_sources[0..10]           
    } AS context
    """
    
    CONNECTION_VALIDATION = """
// 1. ÎNTÂI găsim medicamentul (doar unul)
        UNWIND $medications AS med_input
        CALL db.index.fulltext.queryNodes('medicament_full_search', med_input)
        YIELD node AS med, score AS med_score
        WHERE med_score > 0.2
        WITH med ORDER BY med_score DESC LIMIT 1
        
        // 2. APOI verificăm FIECARE simptom din input
        UNWIND $symptoms AS sym_input
        
        // 3. Căutăm conexiunea pentru acest simptom
        MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
        MATCH (de)-[:Has_Symptom]->(real_symptom:Symptom)
        WHERE toLower(real_symptom.name) CONTAINS toLower(sym_input)
        OR toLower(sym_input) CONTAINS toLower(real_symptom.name)
        
        // 4. Colectăm toate match-urile pentru acest simptom
        WITH med, sym_input,
            collect(DISTINCT {
                nutrient: nut.name,
                graph_symptom: real_symptom.name
            }) AS matches_for_symptom
        WHERE size(matches_for_symptom) > 0
        
        // 5. Agregăm rezultatele pentru TOATE simptomele
        WITH med, collect({
            user_symptom: sym_input,
            matched_nutrients: [m IN matches_for_symptom | m.nutrient],
            matched_graph_symptoms: [m IN matches_for_symptom | m.graph_symptom]
        }) AS all_symptom_matches
        
        // 6. Extragem lista unică de nutrienți
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
    WHERE score > 4
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
 
 
    # Fallback: Direct match queries (if fulltext index doesn't exist)
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
 
 