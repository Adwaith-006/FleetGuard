"""
Pydantic payload models for Owner Management Service APIs.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class SafetyEventPayload(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type: str
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration: float = 0.0
    timestamp: Optional[str] = None
    severity: Optional[str] = "WARNING"
    status: Optional[str] = "OBSERVED"
    confidence: Optional[float] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    driver_id: Optional[str] = "DRV001"
    driver_name: Optional[str] = "Fleet Driver"
    vehicle_id: Optional[str] = "VEH001"
    vehicle_no: Optional[str] = "Cabin Rig"
    session_id: Optional[str] = "sess_default"
    explanation: Optional[str] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("event_type must not be empty.")
        return v.strip().upper()

    @field_validator("driver_id")
    @classmethod
    def validate_driver_id(cls, v: Optional[str]) -> str:
        if v is not None and not v.strip():
            raise ValueError("driver_id must not be empty or whitespace.")
        return (v or "DRV001").strip()


class AnalyzeRequest(BaseModel):
    event_id: str
    model: Optional[str] = None


ExplanationRequest = AnalyzeRequest


class AskSafetyQuestionPayload(BaseModel):
    driver_id: str = "DRV001"
    question: str
    time_range: Optional[str] = "30m"
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)

    @field_validator("driver_id")
    @classmethod
    def validate_driver_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("driver_id must not be empty.")
        return v.strip()

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty.")
        if len(v) > 2000:
            raise ValueError("question exceeds maximum allowed length of 2000 characters.")
        return v.strip()


class SafetySummaryRequestPayload(BaseModel):
    driver_id: str = "DRV001"
    time_range: Optional[str] = "today"

    @field_validator("driver_id")
    @classmethod
    def validate_driver_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("driver_id must not be empty.")
        return v.strip()


class DriverStatusUpdatePayload(BaseModel):
    driver_id: str = "DRV001"
    driver_name: Optional[str] = "Fleet Driver"
    vehicle_id: Optional[str] = "VEH001"
    vehicle_no: Optional[str] = "Cabin Rig"
    status: str = "Attentive"
    monitoring_state: Optional[str] = "Monitoring running normally"
    metrics: Dict[str, Any] = Field(default_factory=dict)


class DriverStatusResponse(BaseModel):
    driver_id: str
    driver_name: str
    vehicle_id: str
    vehicle_no: Optional[str] = None
    status: str = "ACTIVE"
    monitoring_state: Optional[str] = "Normal"
    total_events: int = 0
    drowsiness_count: int = 0
    phone_count: int = 0
    yawning_count: int = 0
    head_down_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    last_active_utc: Optional[str] = None
