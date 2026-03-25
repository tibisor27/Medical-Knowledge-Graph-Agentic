#!/usr/bin/env python3
"""
Simple test to verify the Supervisor + Workers graph compiles and runs.

No InputGateway, no SafetyAgent — just core flow:
  Supervisor → Worker → ... → Synthesis → Guardrail → END
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from langchain_core.messages import HumanMessage
from src.multi_agent.graph import build_multi_agent_graph

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_graph_compilation():
    """Test 1: Graph compiles without errors."""
    logger.info("=" * 80)
    logger.info("TEST 1: Graph Compilation")
    logger.info("=" * 80)
    
    try:
        graph = build_multi_agent_graph()
        logger.info("✓ Graph compiled successfully!")
        return graph
    except Exception as e:
        logger.error(f"✗ Graph compilation failed: {e}", exc_info=True)
        return None


def test_graph_invoke(graph):
    """Test 2: Graph can be invoked with a simple message."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Graph Invocation with Simple Message")
    logger.info("=" * 80)
    
    if not graph:
        logger.error("✗ Graph not available (compilation failed)")
        return False
    
    try:
        # Simple greeting query
        input_state = {
            "messages": [HumanMessage(content="Hello, I'm here to learn about my medications.")],
            "session_id": "test_001",
            "detected_language": "en",
            "safety_flags": [],
            "persisted_medications": [],
            "persisted_symptoms": [],
            "persisted_nutrients": [],
            "persisted_products": [],
        }
        
        logger.info(f"Invoking graph with: {input_state['messages']}")
        result = graph.invoke(input_state)
        
        logger.info("✓ Graph invocation completed!")
        logger.info(f"Result keys: {result.keys()}")
        
        final_response = result.get("final_response", "")
        if final_response:
            logger.info(f"Final response: {final_response[:200]}...")
            return True
        else:
            logger.warning("✗ No final_response in result")
            return False
            
    except Exception as e:
        logger.error(f"✗ Graph invocation failed: {e}", exc_info=True)
        return False


def main():
    logger.info("Starting Multi-Agent Graph Tests...\n")
    
    graph = test_graph_compilation()
    if graph:
        success = test_graph_invoke(graph)
        if success:
            logger.info("\n" + "=" * 80)
            logger.info("✓ ALL TESTS PASSED")
            logger.info("=" * 80)
        else:
            logger.info("\n" + "=" * 80)
            logger.info("✗ INVOCATION TEST FAILED")
            logger.info("=" * 80)
    else:
        logger.info("\n" + "=" * 80)
        logger.info("✗ COMPILATION TEST FAILED")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
