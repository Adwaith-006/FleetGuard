/**
 * Formats a UTC or ISO date string reliably in the user's local timezone.
 * Handles strings with or without 'Z' / offset to prevent naive UTC being treated as local.
 */
export function formatDateTime(val) {
  if (!val) return 'N/A';
  try {
    let s = String(val).trim();
    // If ISO-like string without timezone offset or Z, append Z so JS treats it as UTC
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(s) && !s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
      s += 'Z';
    }
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(val);
    return d.toLocaleString();
  } catch (err) {
    return String(val);
  }
}
