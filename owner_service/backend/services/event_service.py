"""
Event processing service.
Coordinates MongoDB persistence, status classification, WebSocket notifications,
and on-demand or background AI analysis via local Gemma.
"""

import threading
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from shared.event_schema import EventStatusClassifier
from owner_service.backend.database import (
    save_event,
    get_all_events,
    get_event_by_id,
    update_event_explanation,
    save_ai_analysis,
    get_all_analyses,
    get_drivers_status,
    get_driver_by_id,
    update_driver_status
)
from owner_service.backend.websocket import manager
from owner_service.ai.gemma_service import GemmaService

logger = logging.getLogger("EventService")
gemma_service = GemmaService()


class EventService:
    @staticmethod
    def process_incoming_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes ingested safety event from driver monitoring service:
        1. Ensures status classification is applied.
        2. Persists to MongoDB database.
        3. If CRITICAL, asynchronously schedules Gemma analysis in background.
        """
        duration = float(event_dict.get("duration", 0.0))
        evt_type = event_dict.get("event_type", "UNKNOWN")
        severity = (event_dict.get("severity") or "WARNING").upper()

        if not event_dict.get("status") or event_dict.get("status") == "OBSERVED":
            event_dict["status"] = EventStatusClassifier.classify_status(
                event_type=evt_type,
                duration=duration,
                severity=severity
            )

        # 1. Persist to MongoDB
        saved = save_event(event_dict)

        # 2. For CRITICAL events, asynchronously run Gemma analysis without blocking HTTP response
        if severity == "CRITICAL":
            def _async_explain(data: Dict[str, Any]):
                try:
                    res = EventService.analyze_event_now(data["event_id"])
                    if res.get("status") == "success":
                        logger.info(f"Background Gemma analysis completed for event: {data['event_id']}")
                except Exception as e:
                    logger.debug(f"Background Gemma worker note: {e}")

            threading.Thread(target=_async_explain, args=(saved,), daemon=True).start()

        return saved

    @staticmethod
    def list_events(
        limit: int = 100,
        skip: int = 0,
        driver_id: Optional[str] = None,
        severity: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return get_all_events(
            limit=limit,
            skip=skip,
            driver_id=driver_id,
            severity=severity,
            event_type=event_type
        )

    @staticmethod
    def get_event(event_id: str) -> Optional[Dict[str, Any]]:
        return get_event_by_id(event_id)

    @staticmethod
    def analyze_event_now(event_id: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Synchronously requests structured Gemma AI analysis for an existing event.
        Fetches event data and recent driver history from MongoDB, submits to Gemma,
        stores the result in ai_analyses, and updates the event record.
        """
        event = get_event_by_id(event_id)
        if not event:
            return {
                "status": "not_found",
                "message": f"Event '{event_id}' not found in MongoDB."
            }

        # Fetch recent event history for driver to establish pattern context
        driver_id = event.get("driver_id", "DRV001")
        recent_history = get_all_events(limit=5, driver_id=driver_id)

        # Run Gemma analysis
        if model:
            gemma_service.model_name = model

        analysis = gemma_service.analyze_event_structured(event, recent_history=recent_history)

        # Store in MongoDB ai_analyses collection
        analysis_record = {
            "event_id": event_id,
            "driver_id": driver_id,
            "model_used": analysis.get("model_used", gemma_service.model_name),
            "summary": analysis.get("summary", ""),
            "risk_level": analysis.get("risk_level", event.get("severity", "WARNING")),
            "supporting_evidence": analysis.get("supporting_evidence", []),
            "recommended_action": analysis.get("recommended_action", ""),
            "evidence_event_ids": analysis.get("evidence_event_ids", [event_id]),
            "created_at": datetime.now(timezone.utc)
        }
        saved_analysis = save_ai_analysis(analysis_record)

        # Update explanation on the event itself
        explanation_summary = analysis.get("summary", "")
        update_event_explanation(event_id, explanation_summary, ai_analysis=saved_analysis)

        # Broadcast update to connected dashboard clients
        try:
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            broadcast_msg = {
                "type": "AI_ANALYSIS_COMPLETED",
                "event_id": event_id,
                "analysis": saved_analysis
            }
            if loop and loop.is_running():
                asyncio.create_task(manager.broadcast(broadcast_msg))
            else:
                asyncio.run(manager.broadcast(broadcast_msg))
        except Exception as e:
            logger.debug(f"Analysis WebSocket broadcast note: {e}")

        return EventService.sanitize_public_response(saved_analysis)

    @staticmethod
    def calculate_safety_score_backend(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates deterministic safety score (0-100) identical to frontend rules.
        Prevents LLM hallucination by computing score strictly in code.
        """
        score = 100
        for evt in events:
            evt_type = (evt.get("event_type") or "").upper()
            severity = (evt.get("severity") or "").upper()
            if "DROWSINESS" in evt_type:
                score -= 20 if severity == "CRITICAL" else 10
            elif "PHONE" in evt_type:
                score -= 15
            elif "YAWN" in evt_type:
                score -= 10 if severity == "CRITICAL" else 5
            else:
                score -= 5
        score = max(0, min(100, score))

        if score < 70:
            status = "HIGH RISK"
            color = "text-rose-600 bg-rose-50 border-rose-200"
        elif score < 90:
            status = "WARNING"
            color = "text-amber-600 bg-amber-50 border-amber-200"
        else:
            status = "SAFE"
            color = "text-emerald-600 bg-emerald-50 border-emerald-200"

        return {
            "score": score,
            "status": status,
            "color": color
        }

    @staticmethod
    def get_driver_telemetry_facts(
        driver_id: str,
        time_range: str = "30m",
        question: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queries MongoDB for driver safety events within a bounded time range,
        computes verified statistical facts, duration metrics, and deterministic safety score.
        """
        now = datetime.now(timezone.utc)
        tr = (time_range or "").lower().strip()

        start_dt = None
        end_dt = now

        if tr in ("30m", "30_mins", "30 mins", "30 minutes"):
            start_dt = now - timedelta(minutes=30)
        elif tr in ("1h", "1 hour", "60m"):
            start_dt = now - timedelta(hours=1)
        elif tr in ("today", "24h"):
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif tr in ("yesterday", "prior_day", "prev_day"):
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = today_start - timedelta(days=1)
            end_dt = today_start
        elif tr in ("7d", "7 days", "week", "last 7 days"):
            start_dt = now - timedelta(days=7)
        elif tr in ("14d", "14 days"):
            start_dt = now - timedelta(days=14)
        elif tr == "all":
            start_dt = None

        events = get_all_events(
            driver_id=driver_id,
            start_time=start_dt,
            end_time=end_dt,
            limit=250
        )

        total_events = len(events)
        drowsiness_count = len([e for e in events if "DROWSINESS" in (e.get("event_type") or "")])
        yawning_count = len([e for e in events if "YAWN" in (e.get("event_type") or "")])
        phone_count = len([e for e in events if "PHONE" in (e.get("event_type") or "")])
        head_down_count = len([e for e in events if "HEAD" in (e.get("event_type") or "") or "LAY" in (e.get("event_type") or "")])
        critical_count = len([e for e in events if (e.get("severity") or "").upper() == "CRITICAL"])
        warning_count = len([e for e in events if (e.get("severity") or "").upper() == "WARNING"])

        score_info = EventService.calculate_safety_score_backend(events)

        durations = [float(e.get("duration", 0.0)) for e in events if e.get("duration")]
        avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0
        max_dur = round(max(durations), 2) if durations else 0.0

        facts: Dict[str, Any] = {
            "driver_id": driver_id,
            "time_range": time_range,
            "window_start": start_dt.isoformat() if start_dt else "ALL_TIME",
            "window_end": end_dt.isoformat(),
            "total_events": total_events,
            "drowsiness_count": drowsiness_count,
            "yawning_count": yawning_count,
            "phone_count": phone_count,
            "head_down_count": head_down_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "avg_duration_sec": avg_dur,
            "max_duration_sec": max_dur,
            "safety_score": score_info["score"],
            "rating_status": score_info["status"],
            "recent_events": events[:15]
        }

        # Check for comparative queries (yesterday or 7-day)
        q_lower = (question or "").lower()
        if "compare" in q_lower and "yesterday" in q_lower:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            prev_events = get_all_events(
                driver_id=driver_id,
                start_time=yesterday_start,
                end_time=today_start,
                limit=250
            )
            prev_score_info = EventService.calculate_safety_score_backend(prev_events)
            facts["period_comparison"] = {
                "current_period": f"Today ({total_events} events, score {score_info['score']}/100)",
                "previous_period": f"Yesterday ({len(prev_events)} events, score {prev_score_info['score']}/100)",
                "trend": "improving" if score_info['score'] > prev_score_info['score'] else (
                    "declining" if score_info['score'] < prev_score_info['score'] else "stable"
                ),
                "previous_total_events": len(prev_events),
                "previous_drowsiness": len([e for e in prev_events if "DROWSINESS" in (e.get("event_type") or "")]),
                "previous_phone": len([e for e in prev_events if "PHONE" in (e.get("event_type") or "")]),
                "previous_yawning": len([e for e in prev_events if "YAWN" in (e.get("event_type") or "")])
            }
        elif "compare" in q_lower and ("7" in q_lower or "seven" in q_lower or "week" in q_lower):
            prev_start = now - timedelta(days=14)
            prev_end = now - timedelta(days=7)
            prev_events = get_all_events(
                driver_id=driver_id,
                start_time=prev_start,
                end_time=prev_end,
                limit=250
            )
            prev_score_info = EventService.calculate_safety_score_backend(prev_events)
            facts["period_comparison"] = {
                "current_period": f"Last 7 Days ({total_events} events, score {score_info['score']}/100)",
                "previous_period": f"Prior 7 Days ({len(prev_events)} events, score {prev_score_info['score']}/100)",
                "trend": "improving" if score_info['score'] > prev_score_info['score'] else (
                    "declining" if score_info['score'] < prev_score_info['score'] else "stable"
                ),
                "previous_total_events": len(prev_events),
                "previous_drowsiness": len([e for e in prev_events if "DROWSINESS" in (e.get("event_type") or "")]),
                "previous_phone": len([e for e in prev_events if "PHONE" in (e.get("event_type") or "")]),
                "previous_yawning": len([e for e in prev_events if "YAWN" in (e.get("event_type") or "")])
            }

        return facts

    @staticmethod
    def classify_user_intent(question: str) -> str:
        """
        Classifies user input into:
        - FORMAL_REPORT: Explicit requests for driving safety evaluations or metric breakdowns.
        - GREETING_OR_SOCIAL: Greetings (Hi, Hiii, Hello, Good morning), courtesies (Thank you, How are you), and general capability queries.
        - FLEET_SAFETY_QUESTION: Inquiries about drivers, incidents, violations, scores, durations, or comparisons.
        - AMBIGUOUS: Short or unrecognized expressions where clarification is needed.
        """
        import re
        q = (question or "").strip().lower()
        clean_q = re.sub(r"[^\w\s]", " ", q).strip()
        words = clean_q.split()

        # 1. Formal Report Requests
        report_keywords = [
            "driving safety evaluation", "detailed safety evaluation", "formal report",
            "complete report", "full report", "detailed report", "safety evaluation",
            "generate report", "formal summary", "detailed evaluation", "comprehensive report",
            "comprehensive driving safety", "summary report", "detailed driving safety evaluation",
            "show all metrics", "list every metric", "every metric", "full metric breakdown"
        ]
        if any(k in q for k in report_keywords):
            return "FORMAL_REPORT"

        # 2. Specific Fleet Safety Domain Keywords
        safety_keywords = [
            "drowsiness", "drowsy", "sleepy", "sleeping", "yawn", "yawning",
            "phone", "mobile", "distract", "distraction", "head down", "posture",
            "violation", "alert", "warning", "critical", "incident", "event",
            "score", "rating", "safe", "risk", "status", "vehicle", "driver",
            "minute", "hour", "today", "yesterday", "week", "month", "history",
            "compare", "trend", "breakdown", "telemetry", "attention", "recommend"
        ]
        has_safety_keywords = any(k in q for k in safety_keywords)

        # 3. Greeting and Social Courtesy Patterns
        greeting_patterns = [
            r"^h+i+\b",
            r"^h+e+y+\b",
            r"^h+e+l+l*o+\b",
            r"^h+o+w+d+y+\b",
            r"^greetings?\b",
            r"^good\s+(morning|afternoon|evening|day|night)\b",
            r"^what['’]?s\s+up\b",
            r"^sup\b"
        ]
        is_greeting_pattern = any(re.search(pat, clean_q) for pat in greeting_patterns)

        social_phrases = [
            "how are you", "how r u", "how do you do", "how are things",
            "thank you", "thanks", "thx", "thank u", "appreciate it",
            "what can you help", "how can you help", "what can you do", "what do you do",
            "who are you", "help me"
        ]
        is_social_phrase = any(phrase in q for phrase in social_phrases)
        ack_words = {"ok", "okay", "cool", "great", "awesome", "perfect", "got it", "understood", "bye", "goodbye"}
        is_ack = clean_q in ack_words

        if (is_greeting_pattern or is_social_phrase or is_ack) and not has_safety_keywords:
            return "GREETING_OR_SOCIAL"

        if has_safety_keywords or len(words) >= 3:
            return "FLEET_SAFETY_QUESTION"

        return "AMBIGUOUS"

    @staticmethod
    def sanitize_public_response(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitizes owner-facing response dictionary to ensure zero internal system information,
        database implementation details, internal URLs, or infrastructure errors leak to the UI.
        """
        import re
        if not isinstance(data, dict):
            return {}

        out = dict(data)

        # Standardize public model label
        if "model_used" in out:
            out["model_used"] = "AI Safety Assistant"

        # Sanitize string fields
        text_fields = ["answer", "summary", "executive_summary", "recommended_action", "disclaimer", "message"]
        for field in text_fields:
            val = out.get(field)
            if isinstance(val, str) and val:
                # Remove localhost/ip/port leaks
                val = re.sub(r"(?:https?://)?(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?", "", val)
                val = re.sub(r"\b(?:127\.0\.0\.1|localhost|0\.0\.0\.0)\b", "", val)
                val = re.sub(r"\bport\s+\d+\b", "", val, flags=re.IGNORECASE)
                val = re.sub(r"\b(?:11434|27017|8000)\b", "", val)
                # Remove technical offline / synthesis explanations
                val = re.sub(r"\(Ollama is currently unreachable[^\)]*\)", "", val, flags=re.IGNORECASE)
                val = re.sub(r"\*\(Ollama is currently unreachable[^\)]*\)\*", "", val, flags=re.IGNORECASE)
                val = re.sub(r"\(Ollama is offline[^\)]*\)", "", val, flags=re.IGNORECASE)
                val = re.sub(r"response synthesized directly from MongoDB records\.?", "", val, flags=re.IGNORECASE)
                val = re.sub(r"Ollama", "AI Assistant", val)
                val = re.sub(r"MongoDB", "fleet safety records", val)
                val = re.sub(r"driver_safety_db", "fleet records", val)
                val = re.sub(r"ai_analyses", "safety evaluations", val)
                val = re.sub(r"Traceback \(most recent call last\):.*", "", val, flags=re.DOTALL)
                out[field] = val.strip()

        # Sanitize list fields
        list_fields = ["key_findings", "recommendations", "supporting_evidence", "suggested_followups"]
        for field in list_fields:
            items = out.get(field)
            if isinstance(items, list):
                cleaned_items = []
                for item in items:
                    if isinstance(item, str):
                        s = re.sub(r"(?:https?://)?(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?", "", item)
                        s = re.sub(r"\b(?:127\.0\.0\.1|localhost|0\.0\.0\.0)\b", "", s)
                        s = re.sub(r"\bport\s+\d+\b", "", s, flags=re.IGNORECASE)
                        s = re.sub(r"\b(?:11434|27017|8000)\b", "", s)
                        s = re.sub(r"Ollama", "AI Assistant", s)
                        s = re.sub(r"MongoDB", "fleet safety records", s)
                        s = re.sub(r"driver_safety_db", "fleet records", s)
                        s = re.sub(r"ai_analyses", "safety evaluations", s)
                        cleaned_items.append(s.strip())
                    else:
                        cleaned_items.append(item)
                out[field] = cleaned_items

        # Ensure friendly message on error or empty answer
        if out.get("status") == "error" or not out.get("answer"):
            if not out.get("answer") or "error" in str(out.get("answer")).lower():
                out["answer"] = "I couldn't complete that request just now. Please try again."

        return out

    @staticmethod
    def ask_driver_question(
        driver_id: str,
        question: str,
        time_range: str = "30m",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Coordinates full driver safety Q&A with local Gemma LLM:
        1. Classifies intent BEFORE retrieving telemetry.
        2. Handles greetings and social conversation immediately without querying telemetry or scores.
        3. For fleet safety questions, retrieves verified MongoDB telemetry and grounds responses.
        4. Saves completed analysis in MongoDB ai_analyses collection.
        """
        import re
        q_lower = (question or "").lower()

        # Contextual Driver Detection (e.g. "What about DRV002?")
        target_driver_id = driver_id
        driver_match = re.search(r"\b(drv\d+)\b", q_lower)
        if driver_match:
            target_driver_id = driver_match.group(1).upper()

        # Contextual Time Range Detection
        effective_time_range = time_range
        if any(p in q_lower for p in ["last 30 minutes", "last 30 min", "past 30 minutes", "in the 30m window", "in the last 30m"]):
            effective_time_range = "30m"
        elif any(p in q_lower for p in ["last hour", "past hour", "last 1 hour", "last 60 min"]):
            effective_time_range = "1h"
        elif any(p in q_lower for p in ["today", "last 24 hours", "past 24h"]):
            effective_time_range = "today"
        elif any(p in q_lower for p in ["yesterday", "prior day"]):
            effective_time_range = "yesterday"
        elif any(p in q_lower for p in ["last 7 days", "past 7 days", "last week"]):
            effective_time_range = "7d"
        elif any(p in q_lower for p in ["all time", "entire history", "overall history"]):
            effective_time_range = "all"

        driver = get_driver_by_id(target_driver_id)
        if not driver:
            existing_evts = get_all_events(driver_id=target_driver_id, limit=1)
            if not existing_evts and target_driver_id != "DRV001":
                return {
                    "status": "not_found",
                    "message": f"Driver '{target_driver_id}' not found in fleet records."
                }
            driver = {
                "driver_id": target_driver_id,
                "driver_name": f"Driver {target_driver_id}",
                "vehicle_id": "VEH001",
                "vehicle_no": "Cabin Rig",
                "status": "ACTIVE"
            }

        # Intent Classification FIRST
        intent = EventService.classify_user_intent(question)

        # 1. GREETINGS & SOCIAL CONVERSATION: Do NOT query telemetry, scores, or phone events
        if intent == "GREETING_OR_SOCIAL":
            greeting_resp = gemma_service.handle_greeting_or_social(
                question=question,
                driver_profile=driver
            )
            analysis_record = {
                "driver_id": target_driver_id,
                "question": question,
                "analysis_type": "CONVERSATIONAL_CHAT",
                "time_range": effective_time_range,
                "summary": greeting_resp.get("answer", ""),
                "answer": greeting_resp.get("answer", ""),
                "risk_level": None,
                "supporting_evidence": [],
                "recommended_action": "",
                "recommendations": [],
                "evidence_event_ids": [],
                "facts": None,
                "model_used": greeting_resp.get("model_used", gemma_service.model_name),
                "status": "completed",
                "created_at": datetime.now(timezone.utc)
            }
            saved_doc = save_ai_analysis(analysis_record)

            out = dict(greeting_resp)
            out["analysis_id"] = saved_doc.get("analysis_id")
            out["driver_id"] = target_driver_id
            out["time_range"] = effective_time_range
            out["question"] = question
            out["created_at"] = saved_doc.get("created_at")
            return EventService.sanitize_public_response(out)

        # 2. AMBIGUOUS QUERIES: Ask for concise clarification without telemetry
        if intent == "AMBIGUOUS":
            clarification_ans = (
                f"Could you please specify what you'd like to check? For example, you can ask "
                f"'What happened in the last 30 minutes?' or 'Why is this driver's safety rating low?'."
            )
            return EventService.sanitize_public_response({
                "status": "success",
                "model_used": "AI Safety Assistant",
                "answer": clarification_ans,
                "intent": "AMBIGUOUS",
                "is_formal_report": False,
                "risk_level": None,
                "telemetry_facts": None,
                "relevant_events": [],
                "relevant_event_ids": [],
                "evidence_event_ids": [],
                "suggested_followups": [
                    "What happened in the last 30 minutes?",
                    "Why is this driver's safety rating low?",
                    "Compare today with yesterday"
                ],
                "driver_id": target_driver_id,
                "time_range": effective_time_range,
                "question": question,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        # 3. FLEET SAFETY QUESTIONS & FORMAL REPORTS: Retrieve verified telemetry
        try:
            facts = EventService.get_driver_telemetry_facts(
                driver_id=target_driver_id,
                time_range=effective_time_range,
                question=question
            )

            ai_resp = gemma_service.ask_driver_safety_question(
                driver_id=target_driver_id,
                driver_profile=driver,
                telemetry_facts=facts,
                question=question,
                time_range=effective_time_range,
                conversation_history=conversation_history,
                is_formal_report=(intent == "FORMAL_REPORT")
            )

            analysis_record = {
                "driver_id": target_driver_id,
                "question": question,
                "analysis_type": "SAFETY_REPORT" if intent == "FORMAL_REPORT" else "SAFETY_CHAT",
                "time_range": effective_time_range,
                "summary": ai_resp.get("executive_summary") or ai_resp.get("summary", ""),
                "answer": ai_resp.get("answer", ""),
                "risk_level": ai_resp.get("risk_level", facts.get("rating_status", "SAFE")),
                "supporting_evidence": ai_resp.get("key_findings", []),
                "recommended_action": ai_resp.get("recommended_action", ""),
                "recommendations": ai_resp.get("recommendations", []),
                "evidence_event_ids": ai_resp.get("evidence_event_ids", []),
                "facts": facts,
                "model_used": ai_resp.get("model_used", gemma_service.model_name),
                "status": "completed" if ai_resp.get("status") == "success" else ai_resp.get("status", "completed"),
                "created_at": datetime.now(timezone.utc)
            }
            saved_doc = save_ai_analysis(analysis_record)

            # Attach real event objects for relevant_event_ids
            rel_ids = set(ai_resp.get("relevant_event_ids", []) or ai_resp.get("evidence_event_ids", [])[:3])
            relevant_events = []
            for ev in facts.get("recent_events", []):
                if ev.get("event_id") in rel_ids:
                    relevant_events.append({
                        "event_id": ev.get("event_id"),
                        "event_type": ev.get("event_type"),
                        "severity": ev.get("severity", "WARNING"),
                        "duration": ev.get("duration", 0.0),
                        "timestamp": ev.get("timestamp") or ev.get("start_time"),
                        "metrics": ev.get("metrics", {})
                    })

            out = dict(ai_resp)
            out["analysis_id"] = saved_doc.get("analysis_id")
            out["driver_id"] = target_driver_id
            out["time_range"] = effective_time_range
            out["question"] = question
            out["intent"] = intent
            out["relevant_events"] = relevant_events
            out["created_at"] = saved_doc.get("created_at")
            return EventService.sanitize_public_response(out)
        except Exception as e:
            logger.error(f"Unrecoverable error in ask_driver_question: {e}", exc_info=True)
            return EventService.sanitize_public_response({
                "status": "error",
                "model_used": "AI Safety Assistant",
                "answer": "I couldn't complete that request just now. Please try again.",
                "summary": "I couldn't complete that request just now. Please try again.",
                "risk_level": None,
                "telemetry_facts": None,
                "relevant_events": [],
                "relevant_event_ids": [],
                "evidence_event_ids": [],
                "suggested_followups": ["What happened in the last 30 minutes?"],
                "driver_id": target_driver_id,
                "time_range": effective_time_range,
                "question": question,
                "created_at": datetime.now(timezone.utc).isoformat()
            })


    @staticmethod
    def generate_driver_summary(
        driver_id: str,
        time_range: str = "today"
    ) -> Dict[str, Any]:
        """
        Generates a periodic safety summary report for a driver and persists to MongoDB.
        """
        driver = get_driver_by_id(driver_id)
        if not driver:
            existing_evts = get_all_events(driver_id=driver_id, limit=1)
            if not existing_evts and driver_id != "DRV001":
                return {
                    "status": "not_found",
                    "message": f"Driver '{driver_id}' not found in fleet records."
                }
            driver = {
                "driver_id": driver_id,
                "driver_name": f"Driver {driver_id}",
                "vehicle_id": "VEH001",
                "vehicle_no": "Cabin Rig",
                "status": "ACTIVE"
            }

        facts = EventService.get_driver_telemetry_facts(
            driver_id=driver_id,
            time_range=time_range
        )

        ai_resp = gemma_service.generate_safety_summary(
            driver_id=driver_id,
            driver_profile=driver,
            telemetry_facts=facts,
            time_range=time_range
        )

        analysis_record = {
            "driver_id": driver_id,
            "question": f"Safety summary report for {time_range}",
            "analysis_type": "PERIODIC_SUMMARY",
            "time_range": time_range,
            "summary": ai_resp.get("executive_summary") or ai_resp.get("summary", ""),
            "answer": ai_resp.get("answer", ""),
            "risk_level": ai_resp.get("risk_level", facts.get("rating_status", "SAFE")),
            "supporting_evidence": ai_resp.get("key_findings", []),
            "recommended_action": ai_resp.get("recommended_action", ""),
            "recommendations": ai_resp.get("recommendations", []),
            "evidence_event_ids": ai_resp.get("evidence_event_ids", []),
            "facts": facts,
            "model_used": ai_resp.get("model_used", gemma_service.model_name),
            "status": "completed" if ai_resp.get("status") == "success" else ai_resp.get("status", "completed"),
            "created_at": datetime.now(timezone.utc)
        }
        saved_doc = save_ai_analysis(analysis_record)

        out = dict(ai_resp)
        out["analysis_id"] = saved_doc.get("analysis_id")
        out["driver_id"] = driver_id
        out["time_range"] = time_range
        out["analysis_type"] = "PERIODIC_SUMMARY"
        out["created_at"] = saved_doc.get("created_at")
        return EventService.sanitize_public_response(out)

    @staticmethod
    def list_analyses(
        limit: int = 50,
        skip: int = 0,
        event_id: Optional[str] = None,
        driver_id: Optional[str] = None,
        analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        analyses = get_all_analyses(
            limit=limit,
            skip=skip,
            event_id=event_id,
            driver_id=driver_id,
            analysis_type=analysis_type
        )
        return [EventService.sanitize_public_response(a) for a in analyses]

    @staticmethod
    def get_drivers() -> List[Dict[str, Any]]:
        drivers = get_drivers_status()
        for d in drivers:
            d_id = d.get("driver_id")
            evts = get_all_events(driver_id=d_id, limit=200)
            score_info = EventService.calculate_safety_score_backend(evts)
            d["safety_score"] = score_info["score"]
            d["rating_status"] = score_info["status"]
            d["rating_color"] = score_info["color"]
            d["total_violations"] = len(evts)
        return drivers

    @staticmethod
    def get_driver(driver_id: str) -> Optional[Dict[str, Any]]:
        d = get_driver_by_id(driver_id)
        if d:
            evts = get_all_events(driver_id=driver_id, limit=200)
            score_info = EventService.calculate_safety_score_backend(evts)
            d["safety_score"] = score_info["score"]
            d["rating_status"] = score_info["status"]
            d["rating_color"] = score_info["color"]
            d["total_violations"] = len(evts)
        return d

    @staticmethod
    def update_driver(driver_id: str, status_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return update_driver_status(driver_id, status_data)
