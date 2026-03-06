"""
MultiAgentState — Shared state for the Supervisor + Workers architecture.

Graph pattern:
    InputGateway → Supervisor ←→ Workers → SynthesisAgent → Guardrail → END

The Supervisor is a structured-output LLM that routes to deterministic workers.
Workers call Neo4j tools directly (zero LLM cost) and return raw data.
The SynthesisAgent is the ONLY node that generates user-facing natural language.

Fields with Annotated[list, operator.add] APPEND (not replace).
Regular fields are REPLACED by the returning node.
"""

from __future__ import annotations

import operator
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MultiAgentState(dict):
    """
    Shared state flowing through every node in the graph.

    ┌────────────────────────────────────────────────────────────────────┐
    │                        MultiAgentState                            │
    │                                                                    │
    │  messages: [HumanMessage, AIMessage, ...]  ← conversation         │
    │  session_id: "user123"                                            │
    │  detected_language: "ro"                                          │
    │                                                                    │
    │  ── Safety (from InputGateway) ──                                 │
    │  safety_flags: ["caution:pregnan"]                                │
    │                                                                    │
    │  ── Supervisor ↔ Worker Communication ──                          │
    │  next_action: "call_medical"                                      │
    │  worker_task_type: "med_lookup"                                   │
    │  worker_instructions: {"medication": "Metformin"}                 │
    │  worker_results: [{...raw Neo4j data...}]  ← accumulates         │
    │  supervisor_reasoning: ["User mentioned Metformin..."]            │
    │  supervisor_loop_count: 1                                         │
    │                                                                    │
    │  ── Persisted Context (across turns) ──                           │
    │  persisted_medications: ["Metformin"]                             │
    │  persisted_symptoms: ["fatigue"]                                  │
    │  persisted_nutrients: ["Vitamin B12"]                             │
    │  persisted_products: ["BeLife B-Complex"]                         │
    │                                                                    │
    │  ── Output ──                                                     │
    │  final_response: "According to my database..."                    │
    │  guardrail_pass: True                                             │
    │  guardrail_retry_count: 0                                         │
    │  guardrail_feedback: ""                                           │
    │  execution_path: ["gateway", "supervisor", "medical_worker", ...] │
    └────────────────────────────────────────────────────────────────────┘
    """
    __annotations__ = {
        # ── Conversation ──
        "messages": Annotated[list[BaseMessage], add_messages],
        "session_id": str,
        "detected_language": str,

        # ── Safety (from InputGateway) ──
        "safety_flags": Annotated[list[str], operator.add],

        # ── Supervisor ↔ Worker Communication ──
        "next_action": str,              # "call_medical" | "call_product" | "call_nutrient" | "respond"
        "worker_task_type": str,         # Specific task: "med_lookup" | "symptom_inv" | "connection" | "search" | "details" | "catalog" | "nutrient_edu"
        "worker_instructions": dict,     # Parameters for the worker: {"medication": "Metformin"} etc.
        "worker_results": Annotated[list, operator.add],  # Accumulate results across worker calls
        "supervisor_reasoning": Annotated[list[str], operator.add],  # For observability
        "supervisor_loop_count": int,    # Prevent infinite loops (max 3)

        # ── Persisted Context (survives across conversation turns via session) ──
        "persisted_medications": list[str],
        "persisted_symptoms": list[str],
        "persisted_nutrients": list[str],
        "persisted_products": list[str],

        # ── Output ──
        "final_response": str,
        "guardrail_pass": bool,
        "guardrail_retry_count": int,
        "guardrail_feedback": str,

        # ── Observability ──
        "execution_path": Annotated[list[str], operator.add],
    }
