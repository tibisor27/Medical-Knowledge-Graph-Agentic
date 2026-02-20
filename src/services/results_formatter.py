from typing import Any
 
def clean_results(results: Any) -> list:
    cleaned_results = []
    for record in results:
        if isinstance(record, dict):
            cleaned_record = {
                k: v for k, v in record.items()
                if v is not None and v != "" and v != []
            }
            if cleaned_record:
                cleaned_results.append(cleaned_record)
        else:
            cleaned_results.append(record)
    return cleaned_results