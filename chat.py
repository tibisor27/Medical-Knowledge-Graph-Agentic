import os
from dotenv import load_dotenv
load_dotenv()
 
from src.agent.graph import MedicalChatSession
 
 
def main():
    print("=" * 70)
    print("Medical Knowledge Graph Agent")
    print("=" * 70)
    print("Ask me about medications, nutrients, deficiencies, and symptoms!")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("Type 'clear' to clear conversation history.")
    print("=" * 70)
   
    session = MedicalChatSession()
   
    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()
           
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Stay healthy!")
                break
           
            # Check for clear command
            if user_input.lower() == 'clear':
                session.clear_history()
                print("Conversation history cleared.")
                continue
           
            # Skip empty input
            if not user_input:
                continue
           
            # Get response from agent
            print("\nAgent: ", end="")
            response = session.chat(user_input)
            print(response)
           
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue
 
 
if __name__ == "__main__":
    main()