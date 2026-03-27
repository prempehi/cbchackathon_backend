import os
import json
import uuid
from datetime import datetime
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from models import TriageResponse, UrgencyLevel, HospitalRecommendation

# 1. Initialize the Async Anthropic Client
# It will automatically look for ANTHROPIC_API_KEY in your environment variables
anthropic_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Requirement 1, 2, & 3: The System Prompt
SYSTEM_PROMPT = """
You are a Senior Emergency Triage Officer in Ghana. 
Your objective is to evaluate patient symptoms and route them to the optimal available hospital.

LOGIC REQUIREMENTS:
1. Cross-reference the patient's symptoms with the 'active_wards' of the provided hospitals (e.g., labor -> MATERNITY, severe trauma -> ICU/EMERGENCY).
2. NEVER recommend a hospital if its status is 'RED'.
3. Select the best hospital based on required ward availability, current capacity, and status.
4. Provide clinical, 2-sentence reasoning for your primary recommendation.

OUTPUT FORMAT:
You must return strictly valid JSON matching this exact structure:
{
  "urgency_level": "CRITICAL" | "URGENT" | "STANDARD",
  "severity_score": <int 1-5>,
  "ambulance_required": <boolean>,
  "recommendations": [
    {
      "hospital_id": "<string>",
      "hospital_name": "<string>",
      "eta_minutes": <int, estimate based on urgency/distance>,
      "distance_km": <float, estimate>,
      "reasoning": "<string, 2 sentences max>",
      "is_primary": true
    }
  ]
}
"""

# ---------------------------------------------------------------------------
# AI Generation with Exponential Backoff
# ---------------------------------------------------------------------------

# Requirement 5: Retries up to 4 times, waiting 2s, 4s, 8s between failures.
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(4))
async def _call_ai_triage(prompt_text: str) -> dict:
    """Internal function to handle the actual API call and retries."""
    
    response = await anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0.1,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": prompt_text},
            # Pro-tip: Prefilling the assistant's response with a bracket forces Claude 
            # to skip conversational text and immediately write JSON.
            {"role": "assistant", "content": "{"}
        ]
    )
    
    # Because we forced Claude to start with "{", that character won't be in its output.
    # We must prepend it back to reconstruct the valid JSON string.
    raw_json_string = "{" + response.content[0].text
    
    return json.loads(raw_json_string)

# ---------------------------------------------------------------------------
# Main Service Execution
# ---------------------------------------------------------------------------

async def evaluate_symptoms(symptom_text: str, available_hospitals: list) -> TriageResponse:
    """
    Takes the user's symptoms and the raw list of hospitals from Firestore,
    passes them to the AI, and returns a strictly validated Pydantic response.
    """
    
    # 1. Build the dynamic payload
    prompt = f"""
    PATIENT SYMPTOMS:
    {symptom_text}

    AVAILABLE HOSPITALS (JSON):
    {json.dumps(available_hospitals, default=str)}
    """

    # 2. Call the AI engine
    ai_result = await _call_ai_triage(prompt)

    # 3. Requirement 4: Map the AI's JSON into our strict Pydantic model
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