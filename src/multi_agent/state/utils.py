import logging
from typing import Any

logger = logging.getLogger(__name__)

def log_state_summary(state: dict, title: str = "STATE SUMMARY") -> None:

    lines = [f"\n{'='*20} {title} {'='*20}"]
    
    for key, value in state.items():
        if value is None:
            lines.append(f"  {key}: None")
        
        elif key == "messages":
            if not value:
                lines.append(f"  {key}: []")
            else:
                last_msg_type = type(value[-1]).__name__
                lines.append(f"  {key}: [{len(value)} message(s)] - Last is {last_msg_type}")
                lines.append(f" Last user message: {value[-1].content}")
        elif key in ["medical_worker_results", "product_worker_results", "nutrient_worker_results"]:
            count = len([r for r in value if r and r != "CLEAR"]) if value else 0
            lines.append(f"  {key}: [{count} result(s)]")

            
        elif key == "previous_decisions":
            actions = []
            for d in value:
                if hasattr(d, "action"):
                    val = d.action.value if hasattr(d.action, "value") else d.action
                    actions.append(str(val))
                else:
                    actions.append(str(d))
            lines.append(f"  {key}: {actions}")
            
        elif isinstance(value, list):
            if not value:
                lines.append(f"  {key}: []")
            else:
                if len(value) <= 5:
                    lines.append(f"  {key}: {value}")
                else:
                    lines.append(f"  {key}: [{len(value)} items] {value[:3]} ...")
                    
        elif isinstance(value, str):
            if len(value) > 80:
                lines.append(f"  {key}: '{value[:77]}...'")
            else:
                lines.append(f"  {key}: '{value}'")
                
        else:
            lines.append(f"  {key}: {value}")
            
    lines.append(f"{'='*(42 + len(title))}\n")
    logger.info("\n".join(lines))
