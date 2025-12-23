from src.agent.nodes.user_profile import ConversationAnalysis, RetrievalType
from src.database.neo4j_client import Neo4jManager

class DecisionEngine:
    """
    Decide ce query Cypher să execute bazat pe analiza conversației.
    """
    
    def __init__(self, neo4j_client: Neo4jManager):
        self.neo4j_client = neo4j_client

    
    def _run_query(self, query: str, params: dict) -> dict:
        """
        Execută query-ul folosind funcția ta 'run_safe_query' și curăță rezultatul.
        """
        # 1. Apelăm funcția ta specifică
        raw_results = self.neo4j_client.run_safe_query(query, params)
        
        # 2. Gestionăm erorile sau listele goale
        if not raw_results or isinstance(raw_results, str):
            return {}
            
        # 3. Despachetarea (Unpacking)
        # Neo4j returnează o listă: [{'context': {...date...}}]
        first_record = raw_results[0]
        
        # Dacă query-ul returnează un obiect sub cheia 'context' (cum fac query-urile tale)
        if 'context' in first_record:
            return first_record['context']
            
        # Altfel returnăm tot rândul
        return first_record
    
    def execute_retrieval(self, analysis: ConversationAnalysis) -> dict:
        """
        Execută retrieval-ul bazat pe decizia din analiză.
        """
        retrieval_type = analysis.retrieval_decision.primary_retrieval.type
        target = analysis.retrieval_decision.primary_retrieval.target_entities
        
        # ═══════════════════════════════════════════════════════════════
        # ROUTING BAZAT PE TIP
        # ═══════════════════════════════════════════════════════════════
        
        if retrieval_type == RetrievalType.MEDICATION_LOOKUP:
            return self._medication_lookup(target)
        
        elif retrieval_type == RetrievalType.SYMPTOM_INVESTIGATION:
            return self._symptom_investigation(target)
        
        elif retrieval_type == RetrievalType.CONNECTION_VALIDATION:
            return self._connection_validation(target)
        
        elif retrieval_type == RetrievalType.NUTRIENT_EDUCATION:
            return self._nutrient_education(target)
        
        elif retrieval_type == RetrievalType.TRIGGER_PHASE_2:
            return {"trigger_phase_2": True, "profile": analysis.user_profile}
        
        else:
            return {"no_retrieval": True}
    
    def _medication_lookup(self, medications: list[str]) -> dict:
        """
        TYPE 1: User a menționat medicament
        Returnează: ce depletează + simptome de întrebat
        """
        
        query = """
            UNWIND $medications AS med_name
            
            // 1. Căutare
            CALL db.index.fulltext.queryNodes('medicament_full_search', med_name) 
            YIELD node AS med, score
            WHERE score > 0.5
            WITH med, score ORDER BY score DESC LIMIT 1
            
            // 2. Expansiune
            MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
            OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
            
            // 3. FIX: Pregătim obiectele pentru agregare
            WITH med, 
                 {
                    nutrient: nut.name,
                    severity: de.severity,
                    mechanism: de.mechanism
                 } AS depletion_data,
                 sym
            
            // 4. FIX: Agregăm AICI (înainte de return), grupând explicit după 'med'
            WITH med, 
                 collect(DISTINCT depletion_data) AS depletions_list,
                 collect(DISTINCT sym.name) AS symptoms_list
            
            // 5. Construcția finală a JSON-ului (acum e sigură)
            RETURN {
                medication: {
                    name: med.name,
                    class: med.pharmacologic_class
                },
                depletions: depletions_list,
                symptoms_to_ask: symptoms_list[0..5],
                
                suggested_question: "Ați observat simptome precum " + 
                    substring(
                        reduce(s = "", x IN symptoms_list[0..3] | s + x + ", "),
                        0, 80
                    ) + "?"
            } AS context
            """
        
        return self._run_query(query, {"medications": medications})
    
    def _symptom_investigation(self, symptoms: list[str]) -> dict:
        """
        TYPE 2: User a raportat simptom fără medicament cunoscut
        Returnează: ce deficiențe cauzează + ce medicamente să întreb
        """
        
        query = """
        UNWIND $symptoms AS symptom_name
        
        CALL db.index.fulltext.queryNodes('symptom_full_search', symptom_name) 
        YIELD node AS sym, score
        WHERE score > 0.3
        WITH sym ORDER BY score DESC LIMIT 3
        
        // Ce deficiențe cauzează
        MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
        MATCH (de)-[:DEPLETES]->(nut:Nutrient)
        
        // Ce medicamente sunt implicate
        MATCH (med:Medicament)-[:CAUSES]->(de)
        
        RETURN {
            symptom: sym.name,
            
            possible_causes: collect(DISTINCT {
                nutrient: nut.name,
                common_drugs: collect(DISTINCT med.name)[0..5]
            }),
            
            drugs_to_ask_about: collect(DISTINCT med.name)[0..5],
            
            suggested_question: "Luați cumva vreunul dintre aceste medicamente: " +
                substring(
                    reduce(s = "", x IN collect(DISTINCT med.name)[0..4] | s + x + ", "),
                    0, 100
                ) + "?"
        } AS context
        """
        
        return self._run_query(query, {"symptoms": symptoms})
    
    def _connection_validation(self, target: dict) -> dict:
        """
        TYPE 3: Ai ambele - medicament ȘI simptome
        Verifică dacă există calea în graf
        """
        
        medications = target.get("medications", [])
        symptoms = target.get("symptoms", [])
        
        query = """
        UNWIND $medications AS med_name
        UNWIND $symptoms AS symptom_name
        
        MATCH (med:Medicament)
        WHERE toLower(med.name) CONTAINS toLower(med_name)
        
        MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
        MATCH (de)-[:Has_Symptom]->(sym:Symptom)
        WHERE toLower(sym.name) CONTAINS toLower(symptom_name)
           OR toLower(symptom_name) CONTAINS toLower(sym.name)
        
        WITH med, nut, sym, de
        
        RETURN {
            connection_found: true,
            
            validated_path: {
                medication: med.name,
                nutrient: nut.name,
                symptom: sym.name,
                mechanism: de.mechanism,
                severity: de.severity
            },
            
            confidence: CASE de.severity 
                WHEN 'HIGH' THEN 'HIGH'
                WHEN 'MODERATE' THEN 'MODERATE'
                ELSE 'LOW'
            END,
            
            explanation: med.name + " reduce absorbția de " + nut.name + 
                        ", ceea ce poate cauza " + sym.name,
            
            other_symptoms_to_check: [
                s IN [(de)-[:Has_Symptom]->(os:Symptom) | os.name] 
                WHERE s <> sym.name
            ][0..3],
            
            nutrient_for_phase_2: nut.name
            
        } AS validation
        """
        
        return self._run_query(query, {
            "medications": medications,
            "symptoms": symptoms
        })
    
    def _nutrient_education(self, nutrients: list[str]) -> dict:
        """
        TYPE 4: Conexiune validată, aduci info educațional
        """
        
        query = """
        UNWIND $nutrients AS nut_name
        
        MATCH (nut:Nutrient)
        WHERE toLower(nut.name) CONTAINS toLower(nut_name)
        
        OPTIONAL MATCH (de:DepletionEvent)-[:DEPLETES]->(nut)
        OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
        OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
        
        RETURN {
            education: {
                name: nut.name,
                overview: nut.overview,
                why_important: nut.why_important,
                biological_function: nut.biological_function_effect
            },
            
            what_user_needs: {
                optimal_forms: nut.optimal_forms,
                why_form_matters: nut.why_form_matters,
                therapeutic_dose: nut.therapeutic_dose,
                rda: nut.rda
            },
            
            all_deficiency_symptoms: collect(DISTINCT sym.name),
            dietary_sources: collect(DISTINCT food.dietary_source)[0..5],
            
            key_message: "Vitamina " + nut.name + " este esențială pentru " +
                        coalesce(nut.why_important, "funcționarea optimă a organismului")
                        
        } AS nutrient_context
        """
        
        return self._run_query(query, {"nutrients": nutrients})