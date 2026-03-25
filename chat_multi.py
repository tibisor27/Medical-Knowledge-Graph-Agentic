"""
Interactive CLI for the Multi-Agent Yoboo chatbot.

Uses the Supervisor + Workers architecture:
  InputGateway → Supervisor ↔ Workers → SynthesisAgent → Guardrail → END
"""
import os
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)

from src.multi_agent.session import MultiAgentSession


def main():
    print("=" * 70)
    print("  Yoboo — Wellbeing Energy Coach (Multi-Agent Architecture)")
    print("=" * 70)
    print("Ask me about medications, nutrients, deficiencies, and symptoms!")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("Type 'clear' to clear conversation history.")
    print("Type 'path' after a response to see the execution path.")
    print("=" * 70)

    session = MultiAgentSession()
    last_result = None

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Stay healthy! 💚")
                break

            if user_input.lower() == 'clear':
                session.clear_history()
                print("Conversation history cleared.")
                continue

            if user_input.lower() == 'path' and last_result:
                path = last_result.get("execution_path", [])
                print(f"\n📍 Execution path: {' → '.join(path)}")
                print(f"   Meds: {last_result.get('medications', [])}")
                print(f"   Symptoms: {last_result.get('symptoms', [])}")
                print(f"   Nutrients: {last_result.get('nutrients', [])}")
                print(f"   Products: {last_result.get('products', [])}")
                continue

            if not user_input:
                continue

            print("\nYoboo: ", end="")
            last_result = session.run(user_input)
            print(last_result.get("final_response", "Sorry, something went wrong."))

        except KeyboardInterrupt:
            print("\n\nGoodbye! 💚")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue


if __name__ == "__main__":
    main()
