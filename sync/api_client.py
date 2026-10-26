import json
import threading
import urllib.request
from utils.logger import logger

BACKEND_API_URL = "http://localhost:8000/api/events"

def send_event_to_backend_async(event_dict: dict):
    """Sends completed event dict to FastAPI backend in a non-blocking background thread."""
    def _worker(data: dict):
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                BACKEND_API_URL,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    logger.info(f"[API SYNC SUCCESS] Event {data.get('event_id')} sent to FastAPI backend.")
        except Exception as e:
            logger.warning(f"[API SYNC NOTICE] Could not connect to FastAPI backend at {BACKEND_API_URL}: {e}")

    threading.Thread(target=_worker, args=(event_dict,), daemon=True).start()
