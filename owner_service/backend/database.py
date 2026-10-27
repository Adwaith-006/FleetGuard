"""
Database persistence layer for Owner Management Service.
Uses MongoDB via PyMongo for scalable, document-oriented fleet event storage.
Collections:
  - drivers
  - drowsiness_events
  - ai_analyses
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    import pymongo
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    pymongo = None
    PYMONGO_AVAILABLE = False

logger = logging.getLogger("OwnerDatabase")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "driver_safety_db")

_client: Optional[Any] = None
_db: Optional[Any] = None


def get_client() -> Any:
    """Returns singleton MongoDB client with connection pooling and fast server selection."""
    global _client
    if _client is None:
        if not PYMONGO_AVAILABLE:
            raise RuntimeError("PyMongo is not installed. Run: pip install pymongo")
        _client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    return _client


def set_client(custom_client: Any):
    """Allows injecting mock client (such as mongomock) for unit testing."""
    global _client, _db
    _client = custom_client
    _db = _client[DB_NAME] if _client is not None else None


def get_database() -> Any:
    """Returns the driver_safety_db database instance."""
    global _db
    if _db is None:
        client = get_client()
        _db = client[DB_NAME]
    return _db


def parse_utc_datetime(val: Any) -> datetime:
    """Parses ISO strings or existing datetimes into guaranteed UTC datetime objects."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(val, str) and val.strip():
        try:
            # Handle ISO-8601 with or without Z
            cleaned = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def sanitize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Converts MongoDB BSON types (like ObjectId and datetime) to JSON-serializable primitives."""
    if not doc:
        return None
    out = dict(doc)
    if "_id" in out:
        out["_id"] = str(out["_id"])
    for k, v in list(out.items()):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            iso_str = v.astimezone(timezone.utc).isoformat()
            if iso_str.endswith("+00:00"):
                iso_str = iso_str[:-6] + "Z"
            out[k] = iso_str
        elif isinstance(v, dict):
            out[k] = sanitize_doc(v)
    return out


def init_db():
    """
    Initializes MongoDB collections, establishes performance indexes,
    and seeds initial prototype fleet drivers if the collection is empty.
    """
    try:
        db = get_database()
        
        # 1. drowsiness_events indexes
        events_col = db["drowsiness_events"]
        events_col.create_index([("event_id", pymongo.ASCENDING)], unique=True)
        events_col.create_index([("driver_id", pymongo.ASCENDING)])
        events_col.create_index([("timestamp", pymongo.DESCENDING)])
        events_col.create_index([("severity", pymongo.ASCENDING)])
        events_col.create_index([("event_type", pymongo.ASCENDING)])

        # 2. drivers indexes
        drivers_col = db["drivers"]
        drivers_col.create_index([("driver_id", pymongo.ASCENDING)], unique=True)
        drivers_col.create_index([("status", pymongo.ASCENDING)])

        # 3. ai_analyses indexes
        analyses_col = db["ai_analyses"]
        analyses_col.create_index([("analysis_id", pymongo.ASCENDING)], unique=True)
        analyses_col.create_index([("driver_id", pymongo.ASCENDING)])
        analyses_col.create_index([("event_id", pymongo.ASCENDING)])
        analyses_col.create_index([("created_at", pymongo.DESCENDING)])

        # 4. urgent_alerts indexes
        alerts_col = db["urgent_alerts"]
        alerts_col.create_index([("alert_id", pymongo.ASCENDING)], unique=True)
        alerts_col.create_index([("driver_id", pymongo.ASCENDING)])
        alerts_col.create_index([("created_at", pymongo.DESCENDING)])
        alerts_col.create_index([("status", pymongo.ASCENDING)])

        # 5. Seed initial demo driver if empty (only DRV001 preserved for testing)
        if drivers_col.count_documents({}) == 0:
            initial_drivers = [
                {
                    "driver_id": "DRV001",
                    "driver_name": "Prototype Driver (Demo Test)",
                    "vehicle_id": "VEH001",
                    "vehicle_no": "Cabin Rig",
                    "status": "ACTIVE",
                    "monitoring_state": "Normal",
                    "total_events": 0,
                    "drowsiness_count": 0,
                    "phone_count": 0,
                    "yawning_count": 0,
                    "head_down_count": 0,
                    "warning_count": 0,
                    "critical_count": 0,
                    "last_active_utc": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            ]
            drivers_col.insert_many(initial_drivers)
            logger.info("Seeded prototype demo driver DRV001 in MongoDB.")

        logger.info(f"MongoDB initialized. Database: {DB_NAME} at {MONGODB_URI}")
        return True
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB during init_db: {e}. Start MongoDB with: mongod")
        return False


def save_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts or updates a driver safety event in the drowsiness_events collection.
    Also updates driver activity counters in the drivers collection.
    """
    db = get_database()
    event_id = event_dict.get("event_id") or f"evt_{uuid.uuid4().hex[:8]}"

    # Ensure UTC datetimes
    start_dt = parse_utc_datetime(event_dict.get("start_time"))
    end_dt = parse_utc_datetime(event_dict.get("end_time") or event_dict.get("timestamp"))
    ts_dt = parse_utc_datetime(event_dict.get("timestamp") or end_dt)

    event_type = event_dict.get("event_type", "UNKNOWN")
    severity = (event_dict.get("severity") or "WARNING").upper()
    status = event_dict.get("status") or "OBSERVED"
    driver_id = event_dict.get("driver_id", "DRV001")
    vehicle_id = event_dict.get("vehicle_id", "VEH001")
    driver_name = event_dict.get("driver_name", "Fleet Driver")
    vehicle_no = event_dict.get("vehicle_no", "Cabin Rig")
    session_id = event_dict.get("session_id", "sess_default")

    doc = {
        "event_id": event_id,
        "driver_id": driver_id,
        "driver_name": driver_name,
        "vehicle_id": vehicle_id,
        "vehicle_no": vehicle_no,
        "session_id": session_id,
        "event_type": event_type,
        "start_time": start_dt,
        "end_time": end_dt,
        "timestamp": ts_dt,
        "duration": float(event_dict.get("duration", 0.0)),
        "severity": severity,
        "status": status,
        "confidence": event_dict.get("confidence"),
        "metrics": event_dict.get("metrics", {}),
        "explanation": event_dict.get("explanation"),
        "created_at": datetime.now(timezone.utc)
    }

    # Upsert into drowsiness_events
    events_col = db["drowsiness_events"]
    existing_event = events_col.find_one({"event_id": event_id})
    is_new_event = existing_event is None

    events_col.update_one(
        {"event_id": event_id},
        {"$set": doc},
        upsert=True
    )

    # Update driver status and counters idempotently
    try:
        drivers_col = db["drivers"]
        driver_status = "ALERT" if severity in ("CRITICAL", "WARNING") else "ACTIVE"
        
        inc_fields = {}
        # Only increment counters if the event has never been recorded before
        if is_new_event:
            inc_fields["total_events"] = 1
            if severity == "CRITICAL":
                inc_fields["critical_count"] = 1
            elif severity == "WARNING":
                inc_fields["warning_count"] = 1
                
            if "DROWSINESS" in event_type:
                inc_fields["drowsiness_count"] = 1
            elif "PHONE" in event_type:
                inc_fields["phone_count"] = 1
            elif "YAWN" in event_type:
                inc_fields["yawning_count"] = 1
            elif "HEAD" in event_type or "LAY" in event_type:
                inc_fields["head_down_count"] = 1

        driver_update_body: Dict[str, Any] = {
            "$set": {
                "vehicle_id": vehicle_id,
                "vehicle_no": vehicle_no,
                "status": driver_status,
                "latest_event_type": event_type,
                "latest_severity": severity,
                "last_active_utc": ts_dt,
                "updated_at": datetime.now(timezone.utc)
            },
            "$setOnInsert": {
                "driver_name": driver_name,
                "created_at": datetime.now(timezone.utc),
                "total_events": 0,
                "drowsiness_count": 0,
                "phone_count": 0,
                "yawning_count": 0,
                "head_down_count": 0,
                "critical_count": 0,
                "warning_count": 0
            }
        }
        if inc_fields:
            driver_update_body["$inc"] = inc_fields

        drivers_col.update_one(
            {"driver_id": driver_id},
            driver_update_body,
            upsert=True
        )
    except Exception as e:
        logger.debug(f"Driver collection update notice: {e}")

    saved = events_col.find_one({"event_id": event_id})
    return sanitize_doc(saved) or sanitize_doc(doc)


def get_event_by_id(event_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single safety event by its unique ID from MongoDB."""
    db = get_database()
    doc = db["drowsiness_events"].find_one({"event_id": event_id})
    return sanitize_doc(doc)


def get_all_events(
    limit: int = 100,
    skip: int = 0,
    driver_id: Optional[str] = None,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Retrieves list of safety events with pagination and optional filtering."""
    db = get_database()
    query: Dict[str, Any] = {}
    if driver_id:
        query["driver_id"] = driver_id
    if severity:
        query["severity"] = severity.upper()
    if event_type:
        query["event_type"] = event_type.upper()
    if start_time or end_time:
        ts_filter: Dict[str, Any] = {}
        if start_time:
            ts_filter["$gte"] = start_time
        if end_time:
            ts_filter["$lte"] = end_time
        query["timestamp"] = ts_filter

    cursor = db["drowsiness_events"].find(query).sort("timestamp", pymongo.DESCENDING).skip(skip).limit(limit)
    return [sanitize_doc(d) for d in cursor]


def update_event_explanation(event_id: str, explanation: str, ai_analysis: Optional[Dict[str, Any]] = None):
    """Updates AI-generated Gemma explanation and structured analysis for a specific event."""
    db = get_database()
    update_data: Dict[str, Any] = {"explanation": explanation}
    if ai_analysis:
        update_data["ai_analysis"] = ai_analysis

    db["drowsiness_events"].update_one(
        {"event_id": event_id},
        {"$set": update_data}
    )


def save_ai_analysis(analysis_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Saves a structured Gemma AI analysis report to the ai_analyses collection."""
    db = get_database()
    analysis_id = analysis_dict.get("analysis_id") or f"ana_{uuid.uuid4().hex[:8]}"

    created_at = parse_utc_datetime(analysis_dict.get("created_at") or datetime.now(timezone.utc))

    doc = {
        "analysis_id": analysis_id,
        "event_id": analysis_dict.get("event_id"),
        "driver_id": analysis_dict.get("driver_id", "DRV001"),
        "model_used": analysis_dict.get("model_used", "gemma4:e4b"),
        "question": analysis_dict.get("question"),
        "analysis_type": analysis_dict.get("analysis_type", "EVENT_ANALYSIS" if analysis_dict.get("event_id") else "SAFETY_CHAT"),
        "time_range": analysis_dict.get("time_range", "recent"),
        "summary": analysis_dict.get("summary", ""),
        "answer": analysis_dict.get("answer", analysis_dict.get("summary", "")),
        "risk_level": analysis_dict.get("risk_level", "LOW"),
        "supporting_evidence": analysis_dict.get("supporting_evidence", []),
        "recommended_action": analysis_dict.get("recommended_action", ""),
        "evidence_event_ids": analysis_dict.get("evidence_event_ids", []),
        "facts": analysis_dict.get("facts", {}),
        "status": analysis_dict.get("status", "completed"),
        "created_at": created_at
    }

    db["ai_analyses"].update_one(
        {"analysis_id": analysis_id},
        {"$set": doc},
        upsert=True
    )
    saved = db["ai_analyses"].find_one({"analysis_id": analysis_id})
    return sanitize_doc(saved) or sanitize_doc(doc)


def get_all_analyses(
    limit: int = 50,
    skip: int = 0,
    event_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    analysis_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves stored Gemma AI analyses ordered by timestamp with optional event_id, driver_id, or analysis_type filter."""
    db = get_database()
    query: Dict[str, Any] = {}
    if event_id:
        query["event_id"] = event_id
    if driver_id:
        query["driver_id"] = driver_id
    if analysis_type:
        query["analysis_type"] = analysis_type

    cursor = db["ai_analyses"].find(query).sort("created_at", pymongo.DESCENDING).skip(skip).limit(limit)
    return [sanitize_doc(d) for d in cursor]


def get_drivers_status() -> List[Dict[str, Any]]:
    """Retrieves all drivers with their latest fleet monitoring status and counters."""
    db = get_database()
    cursor = db["drivers"].find({}).sort("driver_id", pymongo.ASCENDING)
    drivers = [sanitize_doc(d) for d in cursor]
    if not drivers:
        init_db()
        cursor = db["drivers"].find({}).sort("driver_id", pymongo.ASCENDING)
        drivers = [sanitize_doc(d) for d in cursor]
    return drivers


def get_driver_by_id(driver_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single fleet driver by unique driver_id."""
    db = get_database()
    doc = db["drivers"].find_one({"driver_id": driver_id})
    return sanitize_doc(doc)


def update_driver_status(driver_id: str, status_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates driver's live monitoring status and active state."""
    db = get_database()
    drivers_col = db["drivers"]
    status = status_data.get("status", "ACTIVE")
    vehicle_id = status_data.get("vehicle_id")
    vehicle_no = status_data.get("vehicle_no")
    monitoring_state = status_data.get("monitoring_state", status)

    set_fields: Dict[str, Any] = {
        "status": status,
        "monitoring_state": monitoring_state,
        "last_active_utc": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    if vehicle_id:
        set_fields["vehicle_id"] = vehicle_id
    if vehicle_no:
        set_fields["vehicle_no"] = vehicle_no
    if "metrics" in status_data:
        set_fields["latest_metrics"] = status_data["metrics"]

    drivers_col.update_one(
        {"driver_id": driver_id},
        {"$set": set_fields},
        upsert=True
    )
    doc = drivers_col.find_one({"driver_id": driver_id})
    return sanitize_doc(doc)


def check_health() -> Dict[str, Any]:
    """Validates connectivity to MongoDB and returns version information."""
    if not PYMONGO_AVAILABLE:
        return {
            "status": "unavailable",
            "engine": "MongoDB",
            "message": "PyMongo is not installed."
        }
    try:
        client = get_client()
        info = client.server_info()
        return {
            "status": "connected",
            "engine": "MongoDB",
            "database": DB_NAME,
            "uri": MONGODB_URI.split("@")[-1], # Mask credentials if any
            "version": info.get("version", "unknown")
        }
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return {
            "status": "disconnected",
            "engine": "Database",
            "message": "Database service is currently unreachable."
        }


def save_urgent_alert(alert_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Saves or updates an urgent alert document in urgent_alerts collection."""
    db = get_database()
    alert_id = alert_dict.get("alert_id") or f"alt_{uuid.uuid4().hex[:8]}"
    created_at = parse_utc_datetime(alert_dict.get("timestamp") or alert_dict.get("created_at"))

    doc = {
        "alert_id": alert_id,
        "driver_id": alert_dict.get("driver_id", "DRV001"),
        "vehicle_id": alert_dict.get("vehicle_id", "VEH001"),
        "risk_level": alert_dict.get("risk_level", "HIGH").upper(),
        "alert_type": alert_dict.get("alert_type", "SUSTAINED_DROWSINESS"),
        "trigger_reason": alert_dict.get("trigger_reason", ""),
        "timestamp": created_at,
        "evidence": alert_dict.get("evidence", {}),
        "explanation": alert_dict.get("explanation", ""),
        "recommendations": alert_dict.get("recommendations", []),
        "status": alert_dict.get("status", "ACTIVE").upper(),
        "created_at": created_at,
        "updated_at": datetime.now(timezone.utc)
    }

    db["urgent_alerts"].update_one(
        {"alert_id": alert_id},
        {"$set": doc},
        upsert=True
    )
    saved = db["urgent_alerts"].find_one({"alert_id": alert_id})
    return sanitize_doc(saved) or sanitize_doc(doc)


def get_urgent_alerts(
    driver_id: Optional[str] = None,
    limit: int = 50,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves list of urgent safety alerts sorted by creation time descending."""
    db = get_database()
    query: Dict[str, Any] = {}
    if driver_id:
        query["driver_id"] = driver_id
    if status:
        query["status"] = status.upper()
    cursor = db["urgent_alerts"].find(query).sort("created_at", pymongo.DESCENDING).limit(limit)
    return [sanitize_doc(d) for d in cursor]


def get_active_alert(driver_id: str) -> Optional[Dict[str, Any]]:
    """Fetches the latest currently ACTIVE urgent alert for a driver, if any."""
    db = get_database()
    doc = db["urgent_alerts"].find_one(
        {"driver_id": driver_id, "status": "ACTIVE"},
        sort=[("created_at", pymongo.DESCENDING)]
    )
    return sanitize_doc(doc)


def resolve_urgent_alert(alert_id: str, resolution_status: str = "RESOLVED") -> bool:
    """Marks an active urgent alert as RESOLVED or RECOVERED."""
    db = get_database()
    res = db["urgent_alerts"].update_one(
        {"alert_id": alert_id},
        {"$set": {"status": resolution_status.upper(), "resolved_at": datetime.now(timezone.utc)}}
    )
    return res.modified_count > 0


def update_alert_explanation(alert_id: str, explanation: str, recommendations: Optional[List[str]] = None) -> bool:
    """Updates AI-enriched explanation and recommendations for an alert."""
    db = get_database()
    update_data: Dict[str, Any] = {"explanation": explanation, "updated_at": datetime.now(timezone.utc)}
    if recommendations is not None:
        update_data["recommendations"] = recommendations
    res = db["urgent_alerts"].update_one(
        {"alert_id": alert_id},
        {"$set": update_data}
    )
    return res.modified_count > 0

