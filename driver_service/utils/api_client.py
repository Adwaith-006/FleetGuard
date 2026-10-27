import json
import queue
import sys
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, Any

try:
    from config.settings import BACKEND_API_URL, BACKEND_STATUS_URL
    from utils.logger import logger
except ImportError:
    from driver_service.config.settings import BACKEND_API_URL, BACKEND_STATUS_URL
    from driver_service.utils.logger import logger

# Bounded queue to retain up to 50 events during temporary network hiccups
_event_queue: queue.Queue = queue.Queue(maxsize=50)
_worker_started = False
_worker_lock = threading.Lock()


def _delivery_worker():
    """Background daemon worker for non-blocking event and status delivery with bounded retries."""
    while True:
        try:
            item = _event_queue.get()
            if item is None:
                break

            if len(item) == 3:
                data, retries, target_url = item
            else:
                data, retries = item
                target_url = BACKEND_API_URL

            is_status_msg = (target_url == BACKEND_STATUS_URL)
            event_id = data.get("event_id", "status_telemetry" if is_status_msg else "evt_unknown")
            event_type = data.get("event_type", data.get("status", "TELEMETRY"))

            success = False
            try:
                payload = json.dumps(
                    data,
                    default=lambda o: o.item() if hasattr(o, "item") else str(o)
                ).encode("utf-8")
                req = urllib.request.Request(
                    target_url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    if resp.status in (200, 201):
                        if sys is not None and hasattr(sys, "is_finalizing") and not sys.is_finalizing():
                            if sys.stdout and not getattr(sys.stdout, "closed", False):
                                if not is_status_msg:
                                    logger.info(f"[API SYNC SUCCESS] Event {event_id} ({event_type}) delivered to owner backend.")
                                else:
                                    logger.debug(f"[STATUS SYNC SUCCESS] Driver live status updated: {event_type}")
                        success = True
                    else:
                        if sys is not None and hasattr(sys, "is_finalizing") and not sys.is_finalizing():
                            if sys.stdout and not getattr(sys.stdout, "closed", False):
                                logger.warning(f"[API SYNC REJECTED] Owner backend returned HTTP {resp.status} for {event_id}.")
            except urllib.error.URLError as e:
                if sys is not None and hasattr(sys, "is_finalizing") and not sys.is_finalizing():
                    if sys.stdout and not getattr(sys.stdout, "closed", False):
                        if not is_status_msg:
                            logger.info(f"[API SYNC NOTICE] Owner backend unreachable at {target_url}: {e.reason}. Driver monitoring and local alarm continue unaffected.")
            except Exception as e:
                if sys is not None and hasattr(sys, "is_finalizing") and not sys.is_finalizing():
                    if sys.stdout and not getattr(sys.stdout, "closed", False):
                        if not is_status_msg:
                            logger.info(f"[API SYNC NOTICE] Could not transmit {event_id}: {e}")

            max_retries = 1 if is_status_msg else 2
            if not success and retries < max_retries:
                # Re-queue for a single retry after brief pause
                time.sleep(1.0)
                try:
                    _event_queue.put_nowait((data, retries + 1, target_url))
                except queue.Full:
                    pass

            _event_queue.task_done()
        except Exception as e:
            logger.debug(f"Exception in delivery worker loop: {e}")


def _ensure_worker_running():
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            t = threading.Thread(target=_delivery_worker, daemon=True)
            t.start()
            _worker_started = True


def send_event_to_backend_async(event_dict: Dict[str, Any]):
    """
    Submits a completed safety event to the asynchronous delivery queue.
    Executes 100% in the background; never blocks or degrades camera capture,
    face tracking, or local audio alarms if the backend is offline.
    """
    _ensure_worker_running()
    try:
        _event_queue.put_nowait((event_dict, 0, BACKEND_API_URL))
    except queue.Full:
        try:
            # Drop oldest event to prioritize recent safety telemetry
            _event_queue.get_nowait()
            _event_queue.put_nowait((event_dict, 0, BACKEND_API_URL))
        except Exception:
            pass


def send_status_to_backend_async(status_dict: Dict[str, Any]):
    """
    Submits a lightweight driver monitoring status telemetry update to the backend.
    Runs asynchronously and never blocks real-time video inference.
    """
    _ensure_worker_running()
    try:
        _event_queue.put_nowait((status_dict, 0, BACKEND_STATUS_URL))
    except queue.Full:
        pass


send_event_async = send_event_to_backend_async

