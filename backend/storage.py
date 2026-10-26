import os
import json
import logging
from typing import List, Dict, Any
try:
    from backend.config import EVENTS_FILE_PATH, DATA_DIR
except ImportError:
    from config import EVENTS_FILE_PATH, DATA_DIR

logger = logging.getLogger("BackendStorage")

def ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(EVENTS_FILE_PATH):
        with open(EVENTS_FILE_PATH, "w") as f:
            json.dump([], f, indent=4)

def get_all_events() -> List[Dict[str, Any]]:
    ensure_storage()
    try:
        with open(EVENTS_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading events storage: {e}")
        return []

def save_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    ensure_storage()
    events = get_all_events()
    event_id = event_dict.get("event_id")

    # Prevent duplicate records if event already exists
    existing_idx = None
    if event_id:
        for idx, evt in enumerate(events):
            if evt.get("event_id") == event_id:
                existing_idx = idx
                break

    if existing_idx is not None:
        events[existing_idx].update(event_dict)
    else:
        events.append(event_dict)

    try:
        with open(EVENTS_FILE_PATH, "w") as f:
            json.dump(events, f, indent=4)
        logger.info(f"Event {event_id} saved/updated in local storage.")
    except Exception as e:
        logger.error(f"Error writing event to storage: {e}")
    return event_dict
