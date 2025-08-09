GEMINI_DATA_POINT_SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "string"},
        "llm_confidence": {"type": "number"},
        "llm_confidence_reason": {"type": "string"}
    }
}

GEMINI_PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "roles": {"type": "array", "items": GEMINI_DATA_POINT_SCHEMA},
        "divisions": {"type": "array", "items": GEMINI_DATA_POINT_SCHEMA},
        "phone_number": GEMINI_DATA_POINT_SCHEMA,
        "email": GEMINI_DATA_POINT_SCHEMA,
        "website": GEMINI_DATA_POINT_SCHEMA,
        "start_date": GEMINI_DATA_POINT_SCHEMA,
        "end_date": GEMINI_DATA_POINT_SCHEMA
    },
    "required": ["name"]
}

GEMINI_PEOPLE_ARRAY_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {"type": "array", "items": GEMINI_PERSON_SCHEMA},
        "thought": {"type": "string", "description": "Thoughts or reasoning behind the response"}
    },
    "required": ["people"]
}