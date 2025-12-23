from src.database.neo4j_client import Neo4jManager
from src.agent.nodes.decision_engine import DecisionEngine
from src.agent.nodes.user_profile import UserHealthProfile, ConversationState, ConversationAnalysis
from src.prompts.conv_analyz_simple import CONVERSATION_ANALYZER_PROMPT, RESPONSE_SYNTHESIZER_PROMPT
import json

class Phase1ConversationEngine:
    """
    Engine-ul complet pentru Faza 1: Discovery
    
    Două LLM calls per turn:
    1. Analyzer: Extrage, decide retrieval
    2. Synthesizer: Generează răspuns natural
    """
    
    def __init__(self, analyzer_llm, synthesizer_llm, neo4j_client: Neo4jManager):
        self.analyzer = analyzer_llm
        self.synthesizer = synthesizer_llm
        self.decision_engine = DecisionEngine(neo4j_client)
    
    async def process_message(self,user_message: str,conversation_history: list[dict], user_profile: UserHealthProfile
    ) -> tuple[str, UserHealthProfile]:
        """
        Procesează un mesaj și returnează răspuns + profil actualizat.
        """
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: LLM CALL #1 - ANALYZER
        # ═══════════════════════════════════════════════════════════════
        
        analysis = await self._analyze_conversation(
            user_message=user_message,
            history=conversation_history,
            profile=user_profile
        )
        
        # Check dacă trecem la Faza 2
        if analysis.ready_for_recommendation:
            return await self._trigger_phase_2(analysis.user_profile)
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 2: EXECUTE RETRIEVAL (dacă e necesar)
        # ═══════════════════════════════════════════════════════════════
        
        medical_context = {}
        
        if analysis.retrieval_decision.primary_retrieval:
            medical_context = self.decision_engine.execute_retrieval(analysis)
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 3: LLM CALL #2 - SYNTHESIZER
        # ═══════════════════════════════════════════════════════════════
        
        response = await self._synthesize_response(
            user_message=user_message,
            history=conversation_history,
            profile=analysis.user_profile,
            medical_context=medical_context,
            conversation_state=analysis.conversation_state
        )
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 4: UPDATE PROFILE & RETURN
        # ═══════════════════════════════════════════════════════════════
        
        updated_profile = self._merge_profile_updates(
            base_profile=analysis.user_profile,
            response_updates=response.get("profile_updates", {})
        )
        
        return response["synthesized_response"], updated_profile
    
    async def _analyze_conversation(self,user_message: str,history: list[dict],profile: UserHealthProfile) -> ConversationAnalysis:
        """
        LLM Call #1: Analizează conversația și decide retrieval.
        """
        
        prompt = CONVERSATION_ANALYZER_PROMPT.format(
            user_message=user_message,
            conversation_history=self._format_history(history),
            current_profile=profile.model_dump_json(indent=2)
        )
        
        response = await self.analyzer.generate(
            prompt=prompt,
            response_format=ConversationAnalysis  # Structured output
        )
        
        return response
    
    async def _synthesize_response(
        self,
        user_message: str,
        history: list[dict],
        profile: UserHealthProfile,
        medical_context: dict,
        conversation_state: ConversationState
    ) -> dict:
        """
        LLM Call #2: Sintetizează răspuns natural bazat pe context.
        """
        
        prompt = RESPONSE_SYNTHESIZER_PROMPT.format(
            user_message=user_message,
            conversation_history=self._format_history(history),
            medications_confirmed=profile.medications_confirmed,
            medications_mentioned=profile.medications_mentioned,
            symptoms_reported=profile.symptoms_reported,
            conditions=profile.conditions,
            symptoms_confirmed=profile.symptoms_confirmed,
            profile_completeness=profile.profile_completeness,
            treatment_duration=profile.treatment_duration,
            deficiencies_identified=profile.deficiencies_identified,
            connections_validated=[c.model_dump() for c in profile.connections_validated],
            conversation_state=conversation_state.value,
            medical_context=json.dumps(medical_context, indent=2)
        )
        
        response = await self.synthesizer.generate(prompt=prompt)
        
        return json.loads(response)
    
    def _format_history(self, history: list[dict]) -> str:
        """Formatează istoricul pentru prompt."""
        
        formatted = []
        for turn in history:
            role = "User" if turn["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {turn['content']}")
        
        return "\n".join(formatted) if formatted else "(Conversație nouă)"
    
    def _merge_profile_updates(
        self,
        base_profile: UserHealthProfile,
        response_updates: dict
    ) -> UserHealthProfile:
        """Merge updates din response în profil."""
        
        # Deep merge logic
        updated = base_profile.model_copy(deep=True)
        
        for key, value in response_updates.items():
            if hasattr(updated, key):
                current = getattr(updated, key)
                if isinstance(current, list) and isinstance(value, list):
                    # Merge lists fără duplicate
                    setattr(updated, key, list(set(current + value)))
                else:
                    setattr(updated, key, value)
        
        # Recalculează completeness
        updated.profile_completeness = self._calculate_completeness(updated)
        
        return updated
    
    def _calculate_completeness(self, profile: UserHealthProfile) -> int:
        score = 0
        
        # Medicament confirmat: +30%
        if profile.medications_confirmed:
            score += 30
        
        # Simptome raportate: +20%
        if profile.symptoms_reported:
            score += 20
        
        # Simptome confirmate: +10%
        if profile.symptoms_confirmed:
            score += 10
        
        # Durată tratament: +10%
        if profile.treatment_duration:
            score += 10
        
        # Deficiențe identificate: +15%
        if profile.deficiencies_identified:
            score += 15
        
        # Conexiuni validate: +15%
        if profile.connections_validated:
            score += 15
        
        return min(score, 100)