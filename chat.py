#!/usr/bin/env python3
"""
Interactive chat with the Medical Knowledge Graph Agent.

Usage:
    python chat.py                    # Normal mode (clean output)
    python chat.py --debug            # Debug mode (logs to console + file)
    python chat.py --production       # Production mode (logs to file only)
    
    ENVIRONMENT=production python chat.py   # Alternative via env var
"""

import os
import sys
import logging
from dotenv import load_dotenv
load_dotenv()

from src.logging_config import setup_logging, get_environment

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

if "--debug" in sys.argv:
    setup_logging(environment="development")
    print("🔍 DEBUG MODE - Logs: console + logs/agent.log\n")
elif "--production" in sys.argv or get_environment() == "production":
    setup_logging(environment="production")
    # În producție, nu print nimic extra
else:
    # Default: minimal logging
    logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger(__name__)

from src.agent.graph import MedicalChatSession

def main():
    logger.info("=" * 70)
    print("🏥 Medical Knowledge Graph Agent")
    print("=" * 70)
    print("Ask me about medications, nutrients, deficiencies, and symptoms!")
    print("Commands:")
    print("  'quit' or 'exit' - End conversation")
    print("  'clear'          - Clear conversation history")
    print("  'context'        - Show current conversation context")
    print("=" * 70)
    
    session = MedicalChatSession()
    
    while True:
        try:
            # Get user input
            user_input = input("\n👤 You: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye! Stay healthy!")
                break
            
            # Check for clear command
            if user_input.lower() == 'clear':
                session.clear_history()
                print("🗑️  Conversation history cleared.")
                continue
            
            # Check for context command
            if user_input.lower() == 'context':
                ctx = session.get_context()
                print("\n📋 Current Conversation Context:")
                print(f"   Medications: {ctx['medications'] or 'None'}")
                print(f"   Symptoms:    {ctx['symptoms'] or 'None'}")
                print(f"   Nutrients:   {ctx['nutrients'] or 'None'}")
                print(f"   History:     {ctx['history_length']} messages")
                continue
            
            # Skip empty input
            if not user_input:
                continue
            
            # Get response from agent
            print("\n🤖 Agent: ", end="")
            response = session.chat(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


if __name__ == "__main__":
    main()

