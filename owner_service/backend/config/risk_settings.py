"""
Configurable Risk Evaluation Settings.
Engineering parameters for deterministic sustained high-risk and critical-risk detection.
Note: These are prototype software engineering parameters for testing and tuning,
not clinically or medically established danger thresholds.
"""

import os

# Rolling temporal window for driver behavior accumulation (seconds)
ROLLING_WINDOW_SECONDS: float = float(os.getenv("RISK_ROLLING_WINDOW_SECONDS", "120.0"))

# Minimum valid face-visible observations required before evaluating rolling ratio
MIN_VALID_OBSERVATIONS: int = int(os.getenv("RISK_MIN_VALID_OBSERVATIONS", "30"))

# Sustained drowsiness ratio threshold (closed_eye_frames / valid_face_frames)
HIGH_RISK_DROWSINESS_RATIO: float = float(os.getenv("RISK_HIGH_DROWSINESS_RATIO", "0.30"))

# Consecutive eye closure threshold for HIGH risk (seconds)
HIGH_RISK_CONSECUTIVE_CLOSURE_SEC: float = float(os.getenv("RISK_HIGH_CONSECUTIVE_CLOSURE_SEC", "3.0"))

# Number of completed drowsiness events within rolling window required for multi-event HIGH risk
HIGH_RISK_MIN_DROWSINESS_EVENTS: int = int(os.getenv("RISK_HIGH_MIN_DROWSINESS_EVENTS", "2"))

# Extreme continuous eye closure for immediate CRITICAL risk (seconds)
CRITICAL_RISK_CONTINUOUS_CLOSURE_SEC: float = float(os.getenv("RISK_CRITICAL_CLOSURE_SEC", "4.5"))

# Sustained abnormal head posture (slumped/down) for CRITICAL risk (seconds)
CRITICAL_RISK_HEAD_DOWN_SEC: float = float(os.getenv("RISK_CRITICAL_HEAD_DOWN_SEC", "8.0"))

# Seconds of consecutive normal, attentive behavior required to recover an active alert
RECOVERY_STREAK_SECONDS: float = float(os.getenv("RISK_RECOVERY_STREAK_SECONDS", "15.0"))

# Allow escalating from an active HIGH risk alert to CRITICAL
ESCALATION_ENABLED: bool = os.getenv("RISK_ESCALATION_ENABLED", "True").lower() in ("1", "true", "yes")
