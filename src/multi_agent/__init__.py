"""
Multi-Agent Medical Chatbot — Supervisor + Workers Architecture.

Graph: Supervisor ↔ Workers → SynthesisAgent → Guardrail → END
"""

__all__ = ["build_multi_agent_graph"]


def build_multi_agent_graph():
    """Lazy import to avoid triggering all tool imports at package level."""
    from src.multi_agent.graph import build_multi_agent_graph as _build
    return _build()
