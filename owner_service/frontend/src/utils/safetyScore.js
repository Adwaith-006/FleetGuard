/**
 * Calculates a transparent Driver Safety Score (0-100) based on behaviour events.
 * 
 * Deductions:
 * - DROWSINESS: -10 pts (WARNING) / -20 pts (CRITICAL)
 * - PHONE_DETECTED: -15 pts (CRITICAL)
 * - YAWNING: -5 pts (WARNING) / -10 pts (CRITICAL)
 */

export function calculateSafetyScore(events = []) {
  let score = 100;

  for (const evt of events) {
    const type = (evt.event_type || "").toUpperCase();
    const severity = (evt.severity || "").toUpperCase();

    if (type === "DROWSINESS") {
      score -= severity === "CRITICAL" ? 20 : 10;
    } else if (type === "PHONE_DETECTED" || type === "PHONE_USAGE") {
      score -= 15;
    } else if (type === "YAWNING") {
      score -= severity === "CRITICAL" ? 10 : 5;
    } else {
      score -= 5;
    }
  }

  score = Math.max(0, Math.min(100, score));

  let status = "SAFE";
  let color = "text-emerald-600 bg-emerald-50 border-emerald-200";
  let badgeColor = "bg-emerald-500";

  if (score < 70) {
    status = "HIGH RISK";
    color = "text-rose-600 bg-rose-50 border-rose-200";
    badgeColor = "bg-rose-500";
  } else if (score < 90) {
    status = "WARNING";
    color = "text-amber-600 bg-amber-50 border-amber-200";
    badgeColor = "bg-amber-500";
  }

  return {
    score,
    status,
    color,
    badgeColor
  };
}
