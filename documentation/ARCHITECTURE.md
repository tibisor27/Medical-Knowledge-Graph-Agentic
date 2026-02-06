# Architecture Overview

This document describes the system architecture of the Medical Chatbot, an AI-powered application that identifies medication-induced nutrient depletions and recommends supplements.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │   Streamlit UI  │    │   API Clients   │    │    Neo4j Browser        │  │
│  │   (Port 8501)   │    │   (REST API)    │    │    (Port 7474)          │  │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────────────┘  │
│           │                      │                                          │
│           └──────────────────────┘                                          │
│                      │                                                      │
└──────────────────────┼──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Application (Port 8000)                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │    │
│  │  │ /api/chat    │  │ /api/health  │  │ /docs (Swagger UI)       │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT LAYER (LangGraph)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────────┐                                                 │
│   │ conversation_analyzer │ ──► Routes to:                                  │
│   │                       │        • response_synthesizer (NO_RETRIEVAL)    │
│   │  - Intent detection   │        • entity_extractor (RETRIEVAL needed)    │
│   │  - Entity accumulation|                                                 │
│   │  - Pronoun resolution │                                                 │
│   └───────────────────────┘                                                 │
│            │                                                                │
│            ▼ (if retrieval needed)                                          │
│   ┌─────────────────────┐                                                   │
│   │  entity_extractor   │ ──► Resolves entities against Neo4j               │
│   │                     │     (medications, symptoms, nutrients)            │
│   │  - 3-tier matching: │                                                   │
│   │    1. Exact match   │                                                   │
│   │    2. Full-text     │                                                   │
│   │    3. Embeddings    │                                                   │
│   └─────────────────────┘                                                   │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────┐                                                   │
│   │   graph_executor    │ ──► Executes Cypher queries                       │
│   │                     │     based on retrieval type                       │
│   └─────────────────────┘                                                   │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────┐                                                   │
│   │ response_synthesizer│ ──► Generates final response                      │
│   │                     │     with context and sources                      │
│   └─────────────────────┘                                                   │
│            │                                                                │
│            ▼                                                                │
│          [END]                                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │      Neo4j Database                 │    │      Azure OpenAI                   │ │
│  │                                     │    │                                     │ │
│  │  Nodes:                             │    │  • GPT-4.1-mini                     │ │
│  │   - Medicament                      │    │  • text-embedding-ada-002           │ │
│  │   - DepletionEvent                  │    │                                     │ │
│  │   - Nutrient                        │    │                                     │ │
│  │   - Symptom                         │    │                                     │ │
│  │   - Study                           │    │                                     │ │
│  │   - SideEffect                      │    │                                     │ │
│  │   - FoodSource                      │    │                                     │ │
│  │   - PharmacologicClass              │    │                                     │ │
│  │   - BeLifeProduct                   │    │                                     │ │
│  │                                     │    │                                     │ │
│  │  Relationships:                     │    │                                     │ │
│  │   - (Med)-[:CAUSES]->(Event)        │    │                                     │ │
│  │   - (Event)-[:DEPLETES]->           │    │                                     │ │
│  │     (Nutrient)                      │    │                                     │ │
│  │   - (Event)-[:Has_Symptom]->        │    │                                     │ │
│  │     (Symptom)                       │    │                                     │ │
│  │   - (Event)-[:Has_Evidence]->       │    │                                     │ │
│  │     (Study)                         │    │                                     │ │
│  │   - (Medicament)-[:Belogns_To]->    │    │                                     │ │
│  │     (PharmClass)                    │    │                                     │ │
│  │   - (Nutrient)-[:Found_In]->        │    │                                     │ │
│  │     (FoodSource)                    │    │                                     │ │
│  │   - (Nutrient)-[:Has_Side_Effect]-> │    │                                     │ │
│  │     (SideEffect)                    │    │                                     │ │
│  │   - (BeLifeProduct)-[:CONTAINS]->   │    │                                     │ │
│  │     (Nutrient)                      │    │                                     │ │
│  │                                     │    │                                     │ │
│  │  Indexes:                           │    │                                     │ │
│  │   - Full-text search                │    │                                     │ │
│  │   - Vector (embeddings)             │    │                                     │ │
│  └─────────────────────────────────────┘    └─────────────────────────────────────┘ │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │                         Langfuse (Optional)                         │            │
│  │    • Prompt versioning                                              │            │
│  │    • Tracing and monitoring                                         │            │
│  │    • Performance analytics                                          │            │
│  └─────────────────────────────────────────────────────────────────────┘            │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Agent Node Details

### 1. Conversation Analyzer

**Purpose:** Understands user intent and maintains conversation context.

**Key Functions:**
- **Intent Classification:** Determines retrieval type (medication lookup, symptom investigation, nutrient education, conection_validation-between medicaments and symptoms, product_recommendation.)
- **Entity Accumulation:** Tracks all medications, symptoms, and nutrients mentioned throughout the conversation
- **Pronoun Resolution:** Resolves references like "it", "that drug" to actual entities
- **Clarification Logic:** Asks follow-up questions when information is insufficient

**Output:** `ConversationAnalysis` pydantic object with routing decision

### 2. Entity Extractor

**Purpose:** Resolves text entities to nodes in the knowledge graph.

**Matching Strategy (3-tier):**
1. **Exact Match:** Direct name comparison
2. **Full-Text Search:** Synonyms and brand names via Neo4j indexes
3. **Embeddings Search:** Semantic similarity for symptoms (threshold: 0.75 cosine)

**Output:** List of `ResolvedEntity` pydantic objects with match scores & type (direct, full-text, embeddings)

### 3. Graph Executor

**Purpose:** Executes Cypher queries based on the retrieval type.

**Query Types:**
- `MEDICATION_LOOKUP`: Get medication details and depletions
- `SYMPTOM_INVESTIGATION`: Find medications causing symptoms
- `CONNECTION_VALIDATION`: Validate med-symptom connections
- `NUTRIENT_EDUCATION`: Get nutrient information
- `NO_RETRIEVAL`: No Data Retrival is needed
- `PRODUCT_RECOMMENDATION`: Find products covering deficiencies

**Output:** Query results as structured json data

### 4. Response Synthesizer

**Purpose:** Generates natural language responses with proper citations.

**Features:**
- Context-aware responses
- Source attribution
- Safety disclaimers for medical content

## Data Flow Example

```
User: "I'm taking Metformin and feel tired lately"

1. conversation_analyzer
   └── Intent: CONNECTION_VALIDATION
   └── Entities: medication="Metformin", symptom="fatigue"

2. entity_extractor
   └── Resolved: "Metformin" → "Glyburide And Metformin" Medicament node (direct)
   └── Resolved: "fatigue" → "Fatigue" Symptom node (fulltext)

3. graph_executor
   └── Query: Find if this medicines depletes nutrients that match this symptoms 
   └── Result: if connection is found return a list of nutrient that need to be taken 

4. response_synthesizer
   └── Response: "Based on the information I have, taking Metformin (often combined with Glyburide) can lead to depletion of important nutrients like Vitamin B12, Folic Acid, and Coenzyme Q10. These deficiencies are known to cause fatigue, which matches the tiredness you're experiencing. Addressing these nutrient gaps with appropriate supplements might help improve your energy levels."
```

## State Management

The agent uses `MedicalAgentState` (TypedDict) to maintain context:

```python
{
    user_message: str,
    conversation_history: Annotated[List[BaseMessage], add_messages]
    conversation_analysis: Optional[ConversationAnalysis],        
    persisted_medications: List[str],
    persisted_nutrients: List[str],
    persisted_symptoms: List[str],
    resolved_entities: List[ResolvedEntity],
    graph_results: List[Dict[str, Any]],
    has_results: bool,
    execution_error: Optional[str],
    final_response: str,
    execution_path: List[str],
    errors: List[str]
}
```

The  `MedicalAgentState ` uses  `ConversationAnalysis ` state to maintain context of each conversation turn:

**Important:** It represents the AI's interpretation of that specific turn (NOT persistent)

```python
ConversationAnalysis State:

{
    step_by_step_reasoning: str,
    has_sufficient_info: bool,
    retrieval_type: RetrievalType,
    needs_clarification: bool,
    clarification_question: Optional[str],
    accumulated_medications: List[str],
    accumulated_symptoms: List[str],
    accumulated_nutrients: List[str],
    query_medications: List[str],
    query_symptoms: List[str],
    query_nutrients: List[str],
}

RetrivalType State:

{
    MEDICATION_LOOKUP = "MEDICATION_LOOKUP"
    SYMPTOM_INVESTIGATION = "SYMPTOM_INVESTIGATION"
    CONNECTION_VALIDATION = "CONNECTION_VALIDATION"
    NUTRIENT_EDUCATION = "NUTRIENT_EDUCATION"
    NO_RETRIEVAL = "NO_RETRIEVAL"
    PRODUCT_RECOMMENDATION = "PRODUCT_RECOMMENDATION"
}

```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                       │
│              (medical-network bridge)                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐                 │
│  │    neo4j     │◄────►│ medical-api  │                 │
│  │   :7474      │      │   :8000      │                 │
│  │   :7687      │      │              │                 │
│  └──────────────┘      └──────┬───────┘                 │
│                               │                         │
│                               ▼                         │
│                        ┌──────────────┐                 │
│                        │ medical-ui   │                 │
│                        │   :8501      │                 │
│                        │ (Streamlit)  │                 │
│                        └──────────────┘                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Ingestion Pipeline

The `ingest_service/` handles data population:

```
Raw Data → Parsers → Validation → Neo4j Import

Sources:
- medicamente_versiune_finala.json (Medications)
- nutrients_validated.json (Nutrients)
- belife_products.json (Products in structured format)
- beLife-1.md (Products in markdown format)
```

## Security Considerations

- **CORS:** Configured for cross-origin requests (restrict in production)
- **Input Validation:** Pydantic models for all API inputs
- **Medical Disclaimer:** Responses include appropriate medical disclaimers
