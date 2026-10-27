"""
Gemma AI Service through local Ollama HTTP API.
Provides natural-language event explanation, risk classification,
and practical recommendations for fleet safety owners.
Operates with non-blocking, graceful fallback when Ollama is offline.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

logger = logging.getLogger("GemmaService")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")


class GemmaService:
    """
    Communicates with locally running Ollama instance hosting the Gemma model.
    
    Resilience Guarantees:
    - 100% Local: Uses Ollama HTTP API, never sends data to external cloud APIs.
    - Zero Frame Leakage: Only receives structured event telemetry, never raw webcam frames.
    - Non-Blocking: Safe timeouts and fallbacks ensure backend endpoints and driver alarms never freeze.
    - Advisory: Analysis is strictly advisory for fleet management, never medical advice.
    """

    def __init__(
        self,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model_name: str = DEFAULT_OLLAMA_MODEL,
        timeout: Optional[float] = None
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout if timeout is not None else float(os.getenv("OLLAMA_TIMEOUT", "120.0"))

    def check_health(self) -> Dict[str, Any]:
        """Checks if local Ollama daemon is reachable and whether Gemma is pulled."""
        url = f"{self.ollama_url}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FleetSafetyBackend"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
                    # Check if target model is present or auto-discover installed Gemma
                    exact_match = any(self.model_name in m for m in models)
                    discovered_gemma = next((m for m in models if "gemma" in m.lower()), None)
                    
                    active_model = self.model_name if exact_match else (discovered_gemma or self.model_name)
                    if discovered_gemma and not exact_match:
                        self.model_name = discovered_gemma

                    return {
                        "available": bool(models),
                        "ollama_running": True,
                        "installed_models": models,
                        "gemma_installed": bool(exact_match or discovered_gemma),
                        "target_model": active_model,
                        "message": "AI service connected successfully."
                    }
        except Exception as e:
            logger.debug(f"AI service health check notice: {e}")
            return {
                "available": False,
                "ollama_running": False,
                "installed_models": [],
                "gemma_installed": False,
                "target_model": self.model_name,
                "message": "AI service is currently offline or unreachable."
            }

    def explain_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generates a concise explanation for a single driver safety event."""
        res = self.analyze_event_structured(event_data)
        if res.get("status") == "success":
            return {
                "status": "success",
                "model": "AI Safety Assistant",
                "explanation": res.get("summary", "") + " Recommendation: " + res.get("recommended_action", ""),
                "summary": res.get("summary", "")
            }
        out = dict(res)
        out["explanation"] = out.get("summary", "Safety event recorded for driver review.")
        return out

    def analyze_event_structured(
        self,
        event_data: Dict[str, Any],
        recent_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Submits structured event data and recent history to Gemma.
        Returns validated JSON with summary, risk_level, supporting_evidence, and recommended_action.
        """
        evt_type = event_data.get("event_type", "UNKNOWN")
        duration = event_data.get("duration", 0.0)
        severity = event_data.get("severity", "WARNING")
        driver_id = event_data.get("driver_id", "DRV001")
        metrics = event_data.get("metrics", {})
        event_id = event_data.get("event_id", "evt_unknown")

        history_summary = ""
        evidence_ids = [event_id]
        if recent_history:
            history_summary = "Recent Prior Events for this Driver:\n"
            for h in recent_history[:4]:
                h_id = h.get("event_id")
                if h_id and h_id != event_id:
                    evidence_ids.append(h_id)
                history_summary += f"- {h.get('event_type')} (Duration: {h.get('duration')}s, Severity: {h.get('severity')})\n"

        prompt = f"""You are an expert commercial fleet safety AI analyst.
Analyze the following telemetry event recorded for driver '{driver_id}':
- Event ID: {event_id}
- Event Type: {evt_type}
- Duration: {duration} seconds
- Severity Level: {severity}
- Quantitative Metrics: {json.dumps(metrics)}
{history_summary}

Respond ONLY with a valid JSON object strictly matching this schema:
{{
  "summary": "1-2 concise professional sentences explaining what happened and why it is a risk",
  "risk_level": "CRITICAL" or "HIGH" or "MEDIUM" or "LOW",
  "supporting_evidence": ["Key telemetry observation 1", "Key observation 2"],
  "recommended_action": "1 practical immediate fleet management recommendation"
}}
Do NOT include markdown fences, extra text, or preamble outside the JSON."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 400,
                "temperature": 0.2
            }
        }

        url = f"{self.ollama_url}/api/generate"
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    text_resp = raw_data.get("response", "").strip()

                    parsed = self._extract_json(text_resp)
                    if parsed:
                        return {
                            "status": "success",
                            "model_used": self.model_name,
                            "summary": parsed.get("summary", text_resp),
                            "risk_level": parsed.get("risk_level", severity),
                            "supporting_evidence": parsed.get("supporting_evidence", [f"Sustained {evt_type} for {duration}s"]),
                            "recommended_action": parsed.get("recommended_action", "Review driver alertness and require mandatory rest break."),
                            "evidence_event_ids": evidence_ids,
                            "disclaimer": "Advisory safety insight. Not a medical evaluation."
                        }
                    else:
                        # Fallback for plain text response
                        return {
                            "status": "success",
                            "model_used": self.model_name,
                            "summary": text_resp,
                            "risk_level": severity,
                            "supporting_evidence": [f"{evt_type} sustained {duration}s"],
                            "recommended_action": "Review driver alertness logs.",
                            "evidence_event_ids": evidence_ids,
                            "disclaimer": "Advisory safety insight. Not a medical evaluation."
                        }

                logger.warning(f"AI service returned HTTP {resp.status} during event analysis")
                return {
                    "status": "error",
                    "model_used": "AI Safety Assistant",
                    "summary": f"{evt_type.replace('_', ' ').title()} event recorded for {driver_id} (duration: {duration}s). Telemetry logged for safety review.",
                    "risk_level": severity,
                    "recommended_action": "Review driver alertness logs."
                }

        except urllib.error.URLError as e:
            logger.warning(f"AI service connection notice during event analysis: {e}")
            return {
                "status": "unavailable",
                "model_used": "AI Safety Assistant",
                "summary": f"{evt_type.replace('_', ' ').title()} event recorded for {driver_id} (duration: {duration}s). Telemetry logged for safety review.",
                "risk_level": severity,
                "supporting_evidence": [f"{evt_type} duration {duration}s"],
                "recommended_action": "Review driver alertness and ensure regular rest intervals.",
                "evidence_event_ids": evidence_ids
            }
        except Exception as e:
            logger.error(f"Unexpected error during event analysis: {e}", exc_info=True)
            return {
                "status": "error",
                "model_used": "AI Safety Assistant",
                "summary": f"{evt_type.replace('_', ' ').title()} event recorded for {driver_id} (duration: {duration}s). Telemetry logged for safety review.",
                "risk_level": severity,
                "recommended_action": "Review driver alertness logs.",
                "evidence_event_ids": evidence_ids
            }

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON object from text or markdown code fence."""
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try finding JSON within markdown code blocks ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try finding raw { ... }
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        return None

    @staticmethod
    def _detect_query_intent(question: str) -> Dict[str, bool]:
        """Classifies the query into greeting, formal report request, or conversational query."""
        q = (question or "").strip().lower()
        clean_q = re.sub(r"[^\w\s]", " ", q).strip()

        # Check for explicit formal report request
        report_keywords = [
            "driving safety evaluation", "detailed safety evaluation", "formal report",
            "complete report", "full report", "detailed report", "safety evaluation",
            "generate report", "formal summary", "detailed evaluation", "comprehensive report",
            "comprehensive driving safety", "summary report", "detailed driving safety evaluation",
            "show all metrics", "list every metric", "every metric", "full metric breakdown"
        ]
        is_formal_report = any(k in q for k in report_keywords)

        # Check if query contains specific fleet safety keywords
        safety_keywords = [
            "drowsiness", "drowsy", "sleepy", "sleeping", "yawn", "yawning",
            "phone", "mobile", "distract", "distraction", "head down", "posture",
            "violation", "alert", "warning", "critical", "incident", "event",
            "score", "rating", "safe", "risk", "status", "vehicle", "driver",
            "minute", "hour", "today", "yesterday", "week", "month", "history",
            "compare", "trend", "breakdown", "telemetry", "attention", "recommend"
        ]
        has_safety_keywords = any(k in q for k in safety_keywords)

        # Greetings with repeated letters (e.g. "hi", "hiii", "hey", "heyy", "hello", "helloo")
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

        is_greeting = (is_greeting_pattern or is_social_phrase or is_ack) and not has_safety_keywords and not is_formal_report

        return {
            "is_greeting": is_greeting,
            "is_formal_report": is_formal_report
        }

    def handle_greeting_or_social(
        self,
        question: str,
        driver_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handles greetings, polite expressions, and social messages without querying or referencing telemetry.
        Never returns driver scores, phone events, risk badges, or safety reports.
        """
        q = (question or "").strip()
        q_lower = q.lower()
        clean_q = re.sub(r"[^\w\s]", "", q_lower).strip()

        # Deterministic high-quality responses matching owner tone
        if re.search(r"^h+i+\b", clean_q):
            matched = re.match(r"^(h+i+)", clean_q)
            prefix = matched.group(1).capitalize() if matched else "Hi"
            fallback_ans = f"{prefix}! 😊 How can I help you today? I can help you review driver safety events, understand risk scores, or investigate fleet trends."
        elif re.search(r"^h+e+y+\b", clean_q):
            fallback_ans = "Hey there! 😊 How can I help you today? I can check safety records, explain driver ratings, or review recent events."
        elif "thank" in clean_q or "thx" in clean_q or "appreciate" in clean_q:
            fallback_ans = "You're very welcome! Let me know if you need any driver safety updates, score analyses, or fleet reports."
        elif "how are you" in clean_q or "how r u" in clean_q:
            fallback_ans = "I'm doing well, thank you! 😊 Ready to help you review driver safety, analyze alerts, or check on your fleet. What would you like to inspect?"
        elif any(p in clean_q for p in ["what can you help", "what can you do", "who are you"]):
            fallback_ans = "Hi! I can help you understand driver safety events, compare drivers, review risk scores, identify recurring patterns, and explain what's happening across your fleet. What would you like to check?"
        elif clean_q in ("bye", "goodbye", "see you"):
            fallback_ans = "Goodbye! Drive safely and let me know if you need further fleet safety assistance."
        else:
            fallback_ans = "Hello! How can I assist you today with fleet safety monitoring or driver performance?"

        # Fast Ollama conversational query (pure chat prompt, zero telemetry)
        ans = fallback_ans
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": f"""You are a friendly, conversational fleet-safety assistant responding like ChatGPT.
The fleet owner said: "{q}"

Respond warmly, naturally, and concisely in 1-2 friendly sentences. Greet the owner back (matching their tone) and offer to help them review driver safety events, understand risk scores, or investigate fleet trends.
CRITICAL:
- Do NOT output any safety evaluation reports, scores, numbers, or violation counts.
- Respond ONLY with valid JSON: {{"answer": "Your friendly, conversational response..."}}
Do NOT output markdown fences or text outside the JSON.""",
            "stream": False,
            "options": {
                "num_predict": 100,
                "temperature": 0.4
            }
        }

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    text_resp = raw_data.get("response", "").strip()
                    parsed = self._extract_json(text_resp)
                    if parsed and parsed.get("answer"):
                        ans = parsed.get("answer").strip()
                    elif text_resp and not text_resp.startswith("{"):
                        ans = text_resp
        except Exception:
            pass

        return {
            "status": "success",
            "model_used": "AI Safety Assistant",
            "answer": ans,
            "intent": "GREETING_OR_SOCIAL",
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
            "disclaimer": None
        }

    def ask_driver_safety_question(
        self,
        driver_id: str,
        driver_profile: Dict[str, Any],
        telemetry_facts: Dict[str, Any],
        question: str,
        time_range: str = "30m",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        is_formal_report: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Submits a natural-language driver safety query to local Gemma via Ollama.
        Responds naturally like a friendly, accurate, conversational ChatGPT-style assistant.
        Binds all factual claims strictly to verified telemetry facts from MongoDB to prevent hallucinations.
        Avoids rigid report templates unless explicitly requested.
        """
        # Intent detection
        intent = self._detect_query_intent(question)
        if intent["is_greeting"]:
            return self.handle_greeting_or_social(question, driver_profile)

        driver_name = driver_profile.get("driver_name") or driver_profile.get("name", "Driver")
        vehicle_no = driver_profile.get("vehicle_no") or driver_profile.get("vehicleNo", "Cabin Rig")
        status = driver_profile.get("status", "ACTIVE")

        score = telemetry_facts.get("safety_score", 100)
        score_status = telemetry_facts.get("rating_status", "SAFE")
        total_events = telemetry_facts.get("total_events", 0)
        drowsiness = telemetry_facts.get("drowsiness_count", 0)
        yawning = telemetry_facts.get("yawning_count", 0)
        phone = telemetry_facts.get("phone_count", 0)
        head_down = telemetry_facts.get("head_down_count", 0)
        critical = telemetry_facts.get("critical_count", 0)
        warning = telemetry_facts.get("warning_count", 0)
        recent_events = telemetry_facts.get("recent_events", [])
        period_comparison = telemetry_facts.get("period_comparison")

        is_greeting = False
        is_formal = is_formal_report if is_formal_report is not None else intent["is_formal_report"]

        # Default fallbacks grounded in verified telemetry
        default_findings = [
            f"{total_events} confirmed safety event(s) in {time_range}.",
            f"Official deterministic safety rating: {score}/100 ({score_status}).",
            f"Drowsiness: {drowsiness}, Yawning: {yawning}, Phone: {phone}, Head Down: {head_down}"
        ]
        if total_events == 0:
            default_recs = [
                "Maintain scheduled monitoring and shift rotations.",
                "Acknowledge driver for compliant, attentive driving performance."
            ]
        else:
            default_recs = [
                "Require immediate 15-minute rest break if fatigue indicators persist.",
                "Inspect in-cab phone lock policy and verify driver camera alignment."
            ]

        evidence_ids = [ev.get("event_id") for ev in recent_events if ev.get("event_id")]

        # Format events summary for grounding
        if recent_events:
            event_lines = []
            for ev in recent_events[:15]:
                ev_ts = ev.get("timestamp") or ev.get("end_time") or "N/A"
                event_lines.append(
                    f"- [{ev.get('event_id', 'evt')}] [{ev_ts}] {ev.get('event_type')} | "
                    f"Duration: {ev.get('duration', 0.0)}s | Severity: {ev.get('severity', 'WARNING')}"
                )
            events_text = "\n".join(event_lines)
        else:
            events_text = "No safety violation events recorded during this time window."

        comp_text = ""
        if period_comparison:
            comp_text = f"\nComparative Period Data:\n{json.dumps(period_comparison, indent=2)}\n"

        history_text = ""
        if conversation_history:
            history_text = "\nPrior Conversation Context:\n"
            for msg in conversation_history[-4:]:
                role = (msg.get("role") or "user").upper()
                content = msg.get("content", "")
                history_text += f"{role}: {content}\n"

        # Construct Prompt tailored to intent
        if is_greeting:
            prompt = f"""You are a friendly, accurate, conversational fleet-safety assistant. Respond naturally, like a helpful ChatGPT assistant.
The fleet owner said: "{question}"

First, greet the owner warmly and answer directly in 1-2 friendly sentences. Explain that you can help them understand driver safety events, compare drivers, review risk scores, identify recurring patterns, and explain what's happening across their fleet.
CRITICAL:
- Do NOT generate a driving safety evaluation report.
- Do NOT output any violation counts or status blocks for a simple greeting.

Respond in valid JSON matching this schema:
{{
  "answer": "Hi! I can help you understand driver safety events, compare drivers, review risk scores, identify recurring patterns, and explain what's happening across your fleet. What would you like to check?",
  "suggested_followups": [
    "What happened in the last 30 minutes?",
    "Why is this driver's safety rating low?",
    "Compare today with yesterday"
  ]
}}
Do NOT output markdown fences or text outside the JSON."""

        elif is_formal:
            prompt = f"""You are an expert commercial fleet safety AI analyst.
The fleet owner explicitly requested a comprehensive formal driving safety evaluation report:
"{question}"

VERIFIED DRIVER TELEMETRY:
- Driver ID: {driver_id} | Name: {driver_name} | Assigned Vehicle: {vehicle_no}
- Operational Status: {status}
- Analysis Time Window: {time_range}
- Deterministic Safety Rating: {score}/100 ({score_status})
- Total Safety Violations: {total_events} (Critical: {critical}, Warnings: {warning})
- Violation Breakdown: Drowsiness: {drowsiness}, Yawning: {yawning}, Phone Distraction: {phone}, Head Down: {head_down}
{comp_text}
Recorded Safety Events in Window:
{events_text}
{history_text}

Provide a well-structured formal driving safety evaluation report.
Respond with a valid JSON object matching this schema:
{{
  "answer": "Comprehensive markdown report starting with '### Driving Safety Evaluation for {driver_name} ({driver_id})', with telemetry status, event breakdown, key observations, and actionable recommendations.",
  "is_formal_report": true,
  "executive_summary": "1-2 sentence high-level executive overview directly addressing the evaluation request",
  "risk_level": "{score_status}",
  "key_findings": ["Point 1 grounded in telemetry", "Point 2 grounded in telemetry"],
  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],
  "relevant_event_ids": ["evt_..."],
  "suggested_followups": ["Follow-up question 1", "Follow-up question 2"]
}}
Do NOT output any markdown fences or commentary outside the JSON."""

        else:
            prompt = f"""You are a friendly, accurate, conversational fleet-safety assistant. Respond naturally, like a helpful ChatGPT assistant.

First, answer the owner's actual question directly in the first sentence. Use clear, concise, professional English. Adapt the length and structure to the question. For ordinary questions, use natural conversational responses instead of formal reports.

Use only the verified fleet evidence supplied below for factual claims about drivers, events, scores, timestamps, and trends. Never invent or modify evidence. Explain important findings in simple language, distinguish recorded facts from interpretations, and provide relevant evidence references when useful.

CRITICAL FORMATTING RULES:
1. Do NOT automatically produce a driving safety evaluation, telemetry status block, complete metric breakdown, recommendations section, or standard disclaimer.
2. Only generate a formal report when the owner explicitly requests one or the request clearly requires it.
3. Do NOT repeat irrelevant metrics or add generic sections merely to fill a template.
4. If evidence is missing or zero events occurred, state that clearly and concisely without apology.
5. If the question is ambiguous, ask a concise clarification.
6. The backend's deterministic safety scores and configured risk rules are authoritative. Do not invent scoring rules or medical diagnoses. Explain the available data accurately and recommend proportionate safety follow-up when appropriate.

VERIFIED DRIVER TELEMETRY:
- Driver: {driver_name} ({driver_id}) | Assigned Vehicle: {vehicle_no}
- Active Analysis Window: {time_range}
- Deterministic Safety Rating: {score}/100 ({score_status})
- Confirmed Safety Violations in Window: {total_events} (Critical: {critical}, Warnings: {warning})
- Recorded Violation Breakdown:
  * Drowsiness Events: {drowsiness}
  * Yawning (Fatigue) Events: {yawning}
  * Mobile Phone Distraction: {phone}
  * Head Slump / Unsafe Posture: {head_down}
{comp_text}
Recorded Incidents in Window:
{events_text}
{history_text}
FLEET OWNER QUESTION:
"{question}"

Respond with a valid JSON object matching this schema:
{{
  "answer": "Direct conversational response answering the question naturally. The first sentence must answer the question directly. Be concise by default. Mention only the metrics or incidents relevant to this specific question. Do NOT include report titles, telemetry status blocks, or disclaimer footers.",
  "risk_level": "{score_status}",
  "relevant_event_ids": ["evt_..."],
  "suggested_followups": ["Follow-up question 1", "Follow-up question 2"]
}}
Do NOT output any markdown fences or commentary outside the JSON."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 450,
                "temperature": 0.2
            }
        }

        url = f"{self.ollama_url}/api/generate"
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    text_resp = raw_data.get("response", "").strip()

                    parsed = self._extract_json(text_resp)
                    if parsed:
                        ans = (parsed.get("answer") or parsed.get("summary") or text_resp).strip()
                        is_formal = bool(parsed.get("is_formal_report", is_formal))
                        exec_sum = (parsed.get("executive_summary") or "").strip()
                        risk_lvl = parsed.get("risk_level") or score_status
                        findings = parsed.get("key_findings") or parsed.get("supporting_evidence") or []
                        recs = parsed.get("recommendations") or ([parsed.get("recommended_action")] if parsed.get("recommended_action") else [])
                        rel_ids = parsed.get("relevant_event_ids") or parsed.get("evidence_event_ids") or []
                        followups = parsed.get("suggested_followups") or []
                    else:
                        ans = text_resp.strip()
                        exec_sum = ""
                        risk_lvl = score_status
                        findings = []
                        recs = []
                        rel_ids = []
                        followups = []

                    # If answer is empty or missing, provide clean conversational fallback
                    if not ans:
                        if is_greeting:
                            ans = "Hi! I can help you understand driver safety events, compare drivers, review risk scores, identify recurring patterns, and explain what's happening across your fleet. What would you like to check?"
                        elif is_formal:
                            rec_bullets = "\n".join(f"- {r}" for r in default_recs)
                            ans = (
                                f"### Driving Safety Evaluation for {driver_name} ({driver_id})\n\n"
                                f"**Telemetry Status: {score_status} ({score}/100)**\n\n"
                                f"During the requested **{time_range}** period, {total_events} safety event(s) were recorded.\n\n"
                                f"**Key Recommendations:**\n{rec_bullets}"
                            )
                        else:
                            if total_events == 0:
                                ans = f"No safety violations or fatigue events were recorded in the {time_range} window for {driver_name} ({driver_id}). The driver has an official safety rating of {score}/100 ({score_status})."
                            else:
                                parts = []
                                if drowsiness > 0: parts.append(f"{drowsiness} drowsiness event{'s' if drowsiness > 1 else ''}")
                                if phone > 0: parts.append(f"{phone} phone distraction event{'s' if phone > 1 else ''}")
                                if yawning > 0: parts.append(f"{yawning} yawning event{'s' if yawning > 1 else ''}")
                                if head_down > 0: parts.append(f"{head_down} head slump event{'s' if head_down > 1 else ''}")
                                breakdown_str = ", ".join(parts) if parts else f"{total_events} safety event(s)"
                                ans = f"{total_events} safety event(s) were recorded in the {time_range} window for {driver_name}: {breakdown_str}. The driver's official safety rating is {score}/100 ({score_status}). You can open the recorded incident details to review timestamps."

                    # Remove unwanted report templates if accidentally returned for normal queries
                    if not is_formal:
                        ans = re.sub(r"^###\s*Driving Safety Evaluation[^\n]*\n+", "", ans, flags=re.IGNORECASE)
                        ans = re.sub(r"\*\*Telemetry Status:[^\n]*\n+", "", ans, flags=re.IGNORECASE)
                        ans = re.sub(r"Advisory safety insight[^\n]*$", "", ans, flags=re.IGNORECASE).strip()

                    # Dynamic follow-up queries if not provided
                    if not followups:
                        if total_events > 0:
                            followups = [
                                "Why is this driver's safety rating low?",
                                "Which events require immediate attention?",
                                "Compare today with yesterday"
                            ]
                        else:
                            followups = [
                                "What happened in the last 30 minutes?",
                                "Summarize today's driving safety events",
                                "Compare the last seven days with the previous seven days"
                            ]

                    # Filter valid event IDs
                    valid_ids = [ev_id for ev_id in rel_ids if ev_id in evidence_ids] if rel_ids else evidence_ids[:3]

                    return {
                        "status": "success",
                        "model_used": "AI Safety Assistant",
                        "answer": ans,
                        "is_formal_report": is_formal,
                        "executive_summary": exec_sum or ans[:150],
                        "summary": exec_sum or ans,
                        "risk_level": risk_lvl,
                        "key_findings": findings or default_findings,
                        "supporting_evidence": findings or default_findings,
                        "recommendations": recs or default_recs,
                        "recommended_action": (recs or default_recs)[0] if (recs or default_recs) else "Monitor driver activity.",
                        "relevant_event_ids": valid_ids,
                        "evidence_event_ids": evidence_ids,
                        "suggested_followups": followups[:3],
                        "telemetry_facts": telemetry_facts,
                        "disclaimer": "Advisory safety insight. Not a medical evaluation or legal finding." if is_formal else None
                    }

                logger.warning(f"AI service returned HTTP error status {resp.status}")
                if total_events == 0:
                    ans = f"No safety events were recorded for {driver_name} during the {time_range} period. The recorded safety score is {score}/100."
                else:
                    ans = f"{total_events} safety event(s) were recorded for {driver_name} during the {time_range} period. The driver's safety rating is {score}/100 ({score_status})."
                return {
                    "status": "unavailable",
                    "model_used": "AI Safety Assistant",
                    "answer": ans,
                    "is_formal_report": is_formal,
                    "executive_summary": ans,
                    "summary": ans,
                    "risk_level": score_status,
                    "key_findings": default_findings,
                    "supporting_evidence": default_findings,
                    "recommendations": default_recs,
                    "recommended_action": default_recs[0] if default_recs else "Review driver status in dashboard.",
                    "relevant_event_ids": evidence_ids[:3],
                    "evidence_event_ids": evidence_ids,
                    "suggested_followups": [
                        "What happened in the last 30 minutes?",
                        "Check current safety score"
                    ],
                    "telemetry_facts": telemetry_facts,
                    "disclaimer": "Advisory safety insight based on deterministic telemetry." if is_formal else None
                }

        except urllib.error.URLError as e:
            logger.warning(f"AI service unavailable during query: {e}")
            # Deterministic, seamless conversational fallback when LLM is unavailable
            if is_greeting:
                offline_ans = "Hi! I can help you understand driver safety events, compare drivers, and review risk scores across your fleet. What would you like to check?"
            elif is_formal:
                rec_bullets = "\n".join(f"- {r}" for r in default_recs)
                offline_ans = (
                    f"### Driving Safety Evaluation for {driver_name} ({driver_id})\n\n"
                    f"**Telemetry Status: {score_status} ({score}/100)**\n\n"
                    f"During the requested **{time_range}** period, {total_events} confirmed safety event(s) were recorded.\n"
                    f"- Critical Alerts: {critical} | Warnings: {warning}\n"
                    f"- Drowsiness: {drowsiness} | Yawning: {yawning} | Phone Distraction: {phone} | Head Down: {head_down}\n\n"
                    f"**Key Recommendations:**\n{rec_bullets}"
                )
            else:
                if total_events == 0:
                    offline_ans = f"No safety events were recorded for this driver during the last {time_range if time_range != '30m' else '30 minutes'}. The recorded safety score for the selected period is {score}/100."
                else:
                    parts = []
                    if drowsiness > 0: parts.append(f"{drowsiness} drowsiness event{'s' if drowsiness > 1 else ''}")
                    if phone > 0: parts.append(f"{phone} phone distraction event{'s' if phone > 1 else ''}")
                    if yawning > 0: parts.append(f"{yawning} yawning event{'s' if yawning > 1 else ''}")
                    if head_down > 0: parts.append(f"{head_down} head slump event{'s' if head_down > 1 else ''}")
                    breakdown_str = ", ".join(parts) if parts else f"{total_events} safety event(s)"
                    offline_ans = f"During the {time_range} window, {total_events} safety event(s) were recorded for {driver_name}: {breakdown_str}. The official safety rating is {score}/100 ({score_status}). You can open the recorded incident details to review timestamps."

            return {
                "status": "unavailable",
                "model_used": "AI Safety Assistant",
                "answer": offline_ans,
                "is_formal_report": is_formal,
                "executive_summary": offline_ans[:150],
                "summary": offline_ans,
                "risk_level": score_status,
                "key_findings": default_findings,
                "supporting_evidence": default_findings,
                "recommendations": default_recs,
                "recommended_action": default_recs[0] if default_recs else "Review driver status in dashboard.",
                "relevant_event_ids": evidence_ids[:3],
                "evidence_event_ids": evidence_ids,
                "suggested_followups": [
                    "What happened in the last 30 minutes?",
                    "Why is this driver's safety rating low?",
                    "Compare today with yesterday"
                ],
                "telemetry_facts": telemetry_facts,
                "disclaimer": "Advisory safety insight based on deterministic telemetry." if is_formal else None
            }
        except Exception as e:
            logger.error(f"Unexpected error in ask_driver_safety_question: {e}", exc_info=True)
            # Seamless generic fallback without exposing internal stack trace or exception
            if telemetry_facts and "safety_score" in telemetry_facts:
                if total_events == 0:
                    fallback_ans = f"No safety events were recorded for this driver during the last {time_range if time_range != '30m' else '30 minutes'}. The recorded safety score is {score}/100."
                else:
                    fallback_ans = f"{total_events} safety event(s) were recorded for {driver_name} during the {time_range} window. The recorded safety score is {score}/100 ({score_status})."
            else:
                fallback_ans = "I couldn't complete that request just now. Please try again."

            return {
                "status": "error",
                "model_used": "AI Safety Assistant",
                "answer": fallback_ans,
                "is_formal_report": is_formal,
                "executive_summary": fallback_ans,
                "summary": fallback_ans,
                "risk_level": score_status,
                "key_findings": default_findings,
                "supporting_evidence": default_findings,
                "recommendations": default_recs,
                "recommended_action": default_recs[0] if default_recs else "Review driver status in dashboard.",
                "relevant_event_ids": evidence_ids[:3],
                "evidence_event_ids": evidence_ids,
                "suggested_followups": ["What happened in the last 30 minutes?"],
                "telemetry_facts": telemetry_facts,
                "disclaimer": None
            }

    def generate_safety_summary(
        self,
        driver_id: str,
        driver_profile: Dict[str, Any],
        telemetry_facts: Dict[str, Any],
        time_range: str = "today"
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive driving safety summary report for a driver over a specified time window.
        """
        question = (
            f"Generate a comprehensive driving safety summary report for driver '{driver_id}' during the '{time_range}' period. "
            "Analyze the overall observed safety pattern, confirmed violation trends, potential risks, and practical recommendations."
        )
        res = self.ask_driver_safety_question(
            driver_id=driver_id,
            driver_profile=driver_profile,
            telemetry_facts=telemetry_facts,
            question=question,
            time_range=time_range,
            is_formal_report=True
        )
        res["analysis_type"] = "PERIODIC_SUMMARY"
        return res

    def explain_urgent_alert(
        self,
        alert_data: Dict[str, Any],
        recent_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generates an evidence-grounded explanation and recommended actions for a HIGH/CRITICAL alert.
        Adheres strictly to safety protocols:
        - Never hallucinates unobserved events.
        - Avoids diagnosing medical conditions (heart attacks, strokes).
        - If Ollama is offline or times out, returns deterministic explanation immediately.
        """
        driver_id = alert_data.get("driver_id", "DRV001")
        risk_level = alert_data.get("risk_level", "HIGH")
        alert_type = alert_data.get("alert_type", "SUSTAINED_DROWSINESS")
        evidence = alert_data.get("evidence", {})

        # Build deterministic fallback explanation
        ratio = float(evidence.get("drowsiness_ratio") or 0.0)
        closed_sec = float(evidence.get("closed_eye_seconds") or evidence.get("consecutive_closed_sec") or 0.0)
        events_count = int(evidence.get("recent_drowsiness_count") or 0)

        if risk_level == "CRITICAL":
            fallback_exp = f"CRITICAL safety risk detected for driver {driver_id}: prolonged eye closure ({closed_sec:.1f}s) or sustained slump. Immediate fleet intervention required."
            fallback_rec = [
                "Contact driver immediately via cabin radio or cellular call",
                "Instruct driver to pull over at the nearest safe rest stop",
                "Dispatch emergency roadside assistance if driver remains unresponsive"
            ]
        else:
            fallback_exp = f"HIGH risk sustained drowsiness observed for driver {driver_id}: rolling drowsiness ratio reached {int(ratio*100)}% with {events_count} recorded safety incident(s)."
            fallback_rec = [
                "Radio the driver and recommend taking an immediate 15-minute rest break",
                "Verify vehicle ventilation and cabin temperature",
                "Monitor driver telemetry closely over the next 30 minutes"
            ]

        prompt = f"""You are an expert commercial fleet safety AI advisor.
An urgent safety alert has been triggered for driver '{driver_id}'.
Risk Classification: {risk_level}
Alert Trigger: {alert_type}
Verified Telemetry Evidence:
- Rolling Drowsiness Ratio: {ratio:.1%} (closed eye frames / valid face visible frames)
- Consecutive Closed Eye Duration: {closed_sec:.1f}s
- Recent Completed Incidents in Window: {events_count}
- Driver Posture: {evidence.get('head_pose', 'UPRIGHT')}

IMPORTANT SAFETY INSTRUCTIONS:
1. Ground your explanation strictly on the verified telemetry above. Do NOT invent events, timestamps, or measurements.
2. Do NOT diagnose specific medical conditions such as a heart attack or stroke. If sustained abnormal posture or unresponsiveness is present, describe it strictly as an unconfirmed safety concern.
3. Provide 1-2 clear, concise sentences explaining the evidence, followed by practical immediate fleet actions.

Respond ONLY with a valid JSON object matching this schema:
{{
  "explanation": "1-2 concise professional sentences summarizing why this meets the high-risk criteria based on the verified evidence",
  "recommendations": ["Immediate action 1", "Immediate action 2"]
}}
Do NOT include markdown fences, extra text, or preamble outside the JSON."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 300,
                "temperature": 0.2
            }
        }

        url = f"{self.ollama_url}/api/generate"
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"}
            )
            timeout = min(self.timeout, 12.0)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    text_resp = raw_data.get("response", "").strip()
                    parsed = self._extract_json(text_resp)
                    if parsed and "explanation" in parsed:
                        recs = parsed.get("recommendations", [])
                        if isinstance(recs, str):
                            recs = [recs]
                        return {
                            "status": "success",
                            "explanation": parsed["explanation"].strip(),
                            "recommendations": recs or fallback_rec
                        }
        except Exception as e:
            logger.debug(f"Gemma urgent alert analysis fallback: {e}")

        return {
            "status": "deterministic_fallback",
            "explanation": fallback_exp,
            "recommendations": fallback_rec
        }


