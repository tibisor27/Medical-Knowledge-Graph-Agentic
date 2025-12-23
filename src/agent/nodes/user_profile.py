from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class RetrievalType(str, Enum):
    MEDICATION_LOOKUP = "MEDICATION_LOOKUP"
    SYMPTOM_INVESTIGATION = "SYMPTOM_INVESTIGATION"
    CONNECTION_VALIDATION = "CONNECTION_VALIDATION"
    NUTRIENT_EDUCATION = "NUTRIENT_EDUCATION"
    TRIGGER_PHASE_2 = "TRIGGER_PHASE_2"
    NO_RETRIEVAL = "NO_RETRIEVAL"

class ConversationState(str, Enum):
    GREETING = "GREETING"
    GATHERING = "GATHERING"
    VALIDATING = "VALIDATING"
    EDUCATING = "EDUCATING"
    READY_FOR_RECOMMENDATION = "READY_FOR_RECOMMENDATION"

class NextAction(str, Enum):
    RETRIEVE_AND_RESPOND = "RETRIEVE_AND_RESPOND"
    RESPOND_WITHOUT_RETRIEVAL = "RESPOND_WITHOUT_RETRIEVAL"
    TRIGGER_PHASE_2 = "TRIGGER_PHASE_2"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"

# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTED ENTITIES
# ═══════════════════════════════════════════════════════════════════════════════
class ReferenceItem(BaseModel):
    original_text: str = Field(description="Textul original, ex: 'acea pastila'")
    resolved_entity: str = Field(description="Entitatea rezolvată, ex: 'Metformin'")
    
class ExtractedEntities(BaseModel):
    new_medications: list[str] = Field(
        default_factory=list,
        description="Medicamente NOI menționate în mesajul curent"
    )
    new_symptoms: list[str] = Field(
        default_factory=list,
        description="Simptome NOI menționate în mesajul curent"
    )
    new_conditions: list[str] = Field(
        default_factory=list,
        description="Condiții medicale NOI (diabet, hipertensiune, etc.)"
    )
    resolved_references: list[ReferenceItem] = Field(
            default_factory=list,
            description="Lista de referințe rezolvate"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL DECISION
# ═══════════════════════════════════════════════════════════════════════════════

class RetrievalQuery(BaseModel):
    type: RetrievalType
    target_entities: list[str] | dict[str, list[str]] = Field(
        description="Entitățile pentru care facem retrieval"
    )
    reasoning: str = Field(
        description="De ce facem acest retrieval"
    )

class RetrievalDecision(BaseModel):
    primary_retrieval: Optional[RetrievalQuery] = None
    secondary_retrieval: Optional[RetrievalQuery] = None

# ═══════════════════════════════════════════════════════════════════════════════
# USER PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class ValidatedConnection(BaseModel):
    medication: str
    nutrient: str
    symptoms: list[str]
    confidence: Literal["HIGH", "MODERATE", "LOW"]
    mechanism: Optional[str] = None

class UserHealthProfile(BaseModel):
    # Medicamente
    medications_confirmed: list[str] = Field(
        default_factory=list,
        description="Medicamente pe care userul CONFIRMĂ că le ia"
    )
    medications_mentioned: list[str] = Field(
        default_factory=list,
        description="Medicamente doar menționate/întrebate (neconfirmate)"
    )
    
    # Simptome
    symptoms_reported: list[str] = Field(
        default_factory=list,
        description="Simptome menționate de user"
    )
    symptoms_confirmed: list[str] = Field(
        default_factory=list,
        description="Simptome confirmate explicit de user"
    )
    
    # Condiții și context
    conditions: list[str] = Field(
        default_factory=list,
        description="Condiții medicale (diabet, etc.)"
    )
    treatment_duration: Optional[str] = Field(
        default=None,
        description="De cât timp ia medicamentele"
    )
    
    # Insight-uri din graf
    deficiencies_identified: list[str] = Field(
        default_factory=list,
        description="Deficiențe identificate din knowledge graph"
    )
    connections_validated: list[ValidatedConnection] = Field(
        default_factory=list,
        description="Conexiuni validate: med → nutrient → symptom"
    )
    
    # Meta
    profile_completeness: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Cât de complet e profilul (0-100%)"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION ANALYSIS (Output Prompt 1)
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationAnalysis(BaseModel):
    step_by_step_reasoning: str = Field(
        description="Raționamentul pas cu pas al analizei"
    )
    
    extracted_entities: ExtractedEntities
    
    retrieval_decision: RetrievalDecision
    
    user_profile: UserHealthProfile
    
    conversation_state: ConversationState
    
    ready_for_recommendation: bool = Field(
        default=False,
        description="True dacă putem trece la Faza 2"
    )
    
    next_action: NextAction

# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE GENERATION (Output Prompt 2)
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileUpdates(BaseModel):
    symptoms_confirmed: list[str] = Field(default_factory=list)
    medications_confirmed: list[str] = Field(default_factory=list)
    deficiencies_identified: list[str] = Field(default_factory=list)
    new_insight: Optional[str] = None

class ResponseGeneration(BaseModel):
    response_text: str = Field(
        description="Răspunsul conversațional pentru user"
    )
    
    follow_up_questions: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="Întrebări de follow-up (max 2)"
    )
    
    profile_updates: ProfileUpdates
    
    conversation_state: ConversationState
    
    ready_for_phase_2: bool
    
    internal_notes: Optional[str] = Field(
        default=None,
        description="Note interne pentru debugging/logging"
    )