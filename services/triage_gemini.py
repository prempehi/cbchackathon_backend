import os
import json
import uuid
from datetime import datetime
# Note the new import path
from google import genai 
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from models import TriageResponse, UrgencyLevel, HospitalRecommendation

# 1. Initialize the new Stateless Client
# It automatically picks up GEMINI_API_KEY from your .env
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
You are a Senior Emergency Triage Officer in Ghana. 
Evaluate symptoms and route to hospitals. NEVER recommend 'RED' status.
Return strictly valid JSON.
"""

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(4))
async def _call_gemini_ai(prompt_text: str) -> dict:
    """Internal function using the new SDK's models service."""
    
    # In the new SDK, we use client.models.generate_content
    # The config is now passed as a structured GenerateContentConfig object
    response = await client.aio.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt_text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type='application/json',
            temperature=0.1
        )
    )
    # The new SDK returns a Pydantic-compatible response object
    return json.loads(response.text)

async def evaluate_symptoms(symptom_text: str, available_hospitals: list) -> TriageResponse:
    prompt = f"SYMPTOMS: {symptom_text}\nHOSPITALS: {json.dumps(available_hospitals)}"
    
    ai_result = await _call_gemini_ai(prompt)

    recommendations = [
        HospitalRecommendation(**rec) for rec in ai_result.get("recommendations", [])
    ]

    return TriageResponse(
        triage_id=str(uuid.uuid4()),
        urgency_level=UrgencyLevel(ai_result.get("urgency_level", "URGENT")),
        severity_score=ai_result.get("severity_score", 3),
        recommendations=recommendations,
        ambulance_required=ai_result.get("ambulance_required", False),
        timestamp=datetime.utcnow()
    )