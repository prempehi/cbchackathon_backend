from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

# --- Enums for Strict Validation ---

class HospitalStatus(str, Enum):
    GREEN = "GREEN"      # High availability
    YELLOW = "YELLOW"    # Moderate availability
    ORANGE = "ORANGE"    # Near capacity
    RED = "RED"          # Critically full / No-Bed Syndrome alert

class WardType(str, Enum):
    ICU = "ICU"
    EMERGENCY = "EMERGENCY"
    MATERNITY = "MATERNITY"
    PAEDIATRIC = "PAEDIATRIC"
    SURGICAL = "SURGICAL"
    GENERAL = "GENERAL"

class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"
    URGENT = "URGENT"
    STANDARD = "STANDARD"

# --- Helper Models ---

class GeoLocation(BaseModel):
    lat: float = Field(..., example=5.6037)
    lng: float = Field(..., example=-0.1870)

# --- Hospital & Inventory Models ---

class Ward(BaseModel):
    ward_type: WardType
    beds_available: int = Field(ge=0)
    total_beds: int = Field(gt=0)
    oxygen_status: bool = True
    ventilators_available: Optional[int] = 0

class Hospital(BaseModel):
    id: str
    name: str
    location: GeoLocation
    status: HospitalStatus
    last_updated: datetime
    phone_number: str
    is_public: bool = True
    active_wards: List[Ward]

# --- Triage Engine Models ---

class TriageRequest(BaseModel):
    """
    Input model for the AI Triage Engine.
    Accepts transcribed voice or manually typed text.
    """
    symptom_text: str = Field(..., min_length=5, description="Transcribed voice or typed description of emergency")
    user_location: GeoLocation
    age_group: Optional[str] = "adult" # child, teen, adult, senior
    tags: Optional[List[str]] = []

    @validator('symptom_text')
    def text_must_be_meaningful(cls, v):
        if len(v.strip()) < 5:
            raise ValueError('Emergency description is too short to evaluate.')
        return v

class HospitalRecommendation(BaseModel):
    """
    Individual hospital recommendation returned by the AI.
    """
    hospital_id: str
    hospital_name: str
    eta_minutes: int
    distance_km: float
    reasoning: str = Field(..., description="2-sentence clinical reasoning for this choice")
    is_primary: bool

class TriageResponse(BaseModel):
    """
    Final output sent back to the EMT or Public Portal.
    """
    triage_id: str
    urgency_level: UrgencyLevel
    severity_score: int = Field(ge=1, le=5)
    recommendations: List[HospitalRecommendation]
    ambulance_required: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --- Hospital Admin Update Models ---

class CapacityUpdate(BaseModel):
    """
    Lightweight model for the '30-second update' on the Admin Dashboard.
    """
    ward_updates: List[Dict[str, int]] # e.g. [{"ward_type": "ICU", "beds": 2}]
    oxygen_functional: Optional[bool]
    staffing_level_alert: Optional[bool] = False