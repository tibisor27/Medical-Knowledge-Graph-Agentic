"""
Multi-Agent Medical Chatbot — Supervisor + Workers Architecture.

Graph: InputGateway → Supervisor ↔ Workers → SynthesisAgent → Guardrail → END

The Supervisor routes to deterministic workers (zero LLM cost).
The SynthesisAgent is the only node that generates user-facing text.
"""

from src.multi_agent.graph import build_multi_agent_graph

__all__ = ["build_multi_agent_graph"]
