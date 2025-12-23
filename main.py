import asyncio
import os
from dotenv import load_dotenv

# Importuri locale
from src.engine import Phase1ConversationEngine
from src.models import UserHealthProfile
from src.database.neo4j_client import get_neo4j_client # Clientul tau existent
from src.utils.get_llm import get_llm_5_1_chat         # LLM-ul tau existent

async def main():
    load_dotenv()
    print("🚀 System Starting (Refactored)...")
    
    # 1. Setup
    neo4j_client = get_neo4j_client()
    llm = get_llm_5_1_chat()
    
    engine = Phase1ConversationEngine(llm, neo4j_client)
    
    # 2. State
    profile = UserHealthProfile()
    history = []
    
    print("✅ Ready. Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ["exit", "quit"]: break
            
            print("   (Thinking...)")
            response, updated_profile = await engine.process_message(user_input, history, profile)
            
            print(f"Agent: {response}")
            
            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            profile = updated_profile
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())