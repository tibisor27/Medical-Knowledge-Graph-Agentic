from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════
 
class ResolvedEntity(BaseModel):
    """An entity that has been matched to a node in the knowledge graph."""
    original_text: str           # Original text from query ("Tylenol")
    resolved_name: str           # Canonical name in graph ("Acetaminophen")
    node_type: str               # Neo4j label: Medicament, Nutrient, Symptom
    match_score: float           # Full-text search score
    match_method: str            # How it was matched: "exact", "fulltext", "synonym", "brand_name"



class ConversationState:
    def __init__(self, session_id: str | None = None):
        self.history : list[BaseMessage] = []
        self.medications : list[str] = []
        self.symptoms : list[str] = []
        self.nutrients : list[str] = []
        self.products : list[str] = []
        self.session_id = session_id

    def add_medication(self, medication: str):
        if medication and medication not in self.medications:
            self.medications.append(medication)

    def add_symptom(self, symptom: str):
        if symptom and symptom not in self.symptoms:
            self.symptoms.append(symptom)

    def add_nutrient(self, nutrient: str):
        if nutrient and nutrient not in self.nutrients:
            self.nutrients.append(nutrient)

    def add_product(self, product: str):
        if product and product not in self.products:
            self.products.append(product)

    def update_history(self, user_message: str, ai_response: str):
        self.history.append(HumanMessage(content=user_message))
        self.history.append(AIMessage(content=ai_response))

    def build_context_string(self) -> str:
        context = []
        if self.medications:
            context.append(f"Medications user takes: {', '.join(self.medications)}")
        else:
            context.append("Medications: None confirmed yet")
       
        if self.symptoms:
            context.append(f"Symptoms user reported: {', '.join(self.symptoms)}")
        else:
            context.append("Symptoms: None reported yet")
       
        if self.nutrients:
            context.append(f"Nutrients identified as relevant: {', '.join(self.nutrients)}")
        else:
            context.append("Nutrients: None identified yet")
            
        if self.products:
            context.append(f"Products discussed/recommended recently: {', '.join(self.products[-5:])}")
        else:
            context.append("Products: None discussed yet")
       
        context.append(f"Conversation turns so far: {len(self.history) // 2}")
       
        return "\n".join(context)

    def clear_history(self):
        self.history = []
        self.medications = []
        self.symptoms = []
        self.nutrients = []
        self.products = []
