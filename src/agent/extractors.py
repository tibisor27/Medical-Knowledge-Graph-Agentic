from langchain_core.messages import AIMessage, ToolMessage 
from src.agent.state import SessionState
import json
import logging

logger = logging.getLogger(__name__)

def extract_final_response(result: dict) -> str:
    
    messages = result.get("messages", [])

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content
    return "I processed your request but I couldn't find any information."



def extract_tool_calls(result: dict) -> list[dict]:
    messages = result.get("messages", [])
    tool_calls = []
    
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "tool": tc.get("name", "unknown_tool"),
                    "args": tc.get("args", {})
                })
    return tool_calls


def extract_entities_from_tools(result: dict, state: SessionState) -> None:
    
    messages = result.get("messages", [])
    
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name")
                tool_args = tc.get("args")
               
                if tool_name in ("medication_lookup", "connection_validation"):
                    med = tool_args.get("medication")
                    state.add_medication(med)

                if tool_name in ("symptom_investigation", "connection_validation"):
                    sym = tool_args.get("symptom")
                    state.add_symptom(sym)

                if tool_name == "nutrient_lookup":
                    nut = tool_args.get("nutrient")
                    state.add_nutrient(nut)

                if tool_name == "find_belife_products":
                    query = tool_args.get("query")
                    state.add_product(query)

                if tool_name == "product_details":
                    prod = tool_args.get("product_name")
                    state.add_product(prod)
                
                if tool_name == "product_catalog":
                    category = tool_args.get("category")
                    logger.debug(f"Product category browse tracked: {category}")
    

def extract_nutrients_from_results(messages: list, state: SessionState) -> None:
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if not msg.content or not msg.content.strip():
                logger.debug("Skipping empty tool message content")
                continue
            
            try:
                data = json.loads(msg.content)  #since msg.content is a string(a dict in string format) we convert it to a dict
                if isinstance(data, list):
                    for item in data:
                        context = item.get("context", item)
                        depletions = context.get("depletions", [])
                        for dep in depletions:
                            nutrient = dep.get("nutrient", "")
                            state.add_nutrient(nutrient)

                elif isinstance(data, dict):
                    context = data.get("context", data)
                    depletions = context.get("depletions", [])
                    for dep in depletions:
                        nutrient = dep.get("nutrient", "")
                        state.add_nutrient(nutrient)
            except json.JSONDecodeError as e:
                logger.debug(f"Tool message not JSON (might be plain text): {msg.content[:100] if msg.content else 'empty'}")
            except (AttributeError, TypeError) as e:
                logger.debug(f"Unexpected data structure in tool result: {str(e)}")


def extract_products_from_results(messages: list, state: SessionState) -> None:
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if not msg.content or not msg.content.strip():
                logger.debug("Skipping empty tool message content")
                continue
            
            try:
                data = json.loads(msg.content)  #since msg.content is a string(a dict in string format) we convert it to a dict
                if isinstance(data, list):
                    for item in data:
                        name = item.get("product_details", {}).get("name")
                        state.add_product(name)

                elif isinstance(data, dict):
                    #if key "product_details" doesnt exsita it will return {}.
                    #since we use .get() method it will return None if the key("name") doesnt exist
                    name = data.get("product_details", {}).get("name")
                    state.add_product(name)

            except json.JSONDecodeError as e:
                logger.debug(f"Tool message not JSON (might be plain text): {msg.content[:100] if msg.content else 'empty'}")
            except (AttributeError, TypeError) as e:
                logger.debug(f"Unexpected data structure in tool result: {str(e)}")


    

    