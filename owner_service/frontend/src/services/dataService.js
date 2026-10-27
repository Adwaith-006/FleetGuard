// Data service providing driver profiles, vehicle data, safety events, and AI insights from backend APIs
const API_BASE = "/api";

export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("Could not reach backend health check:", err);
  }
  return {
    status: "offline",
    database: { status: "disconnected" },
    ai: { status: "unavailable" }
  };
}

export async function fetchDrivers() {
  try {
    const res = await fetch(`${API_BASE}/drivers`);
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        return data;
      }
    }
  } catch (err) {
    console.warn("Could not fetch drivers from API:", err);
  }
  return [];
}

export async function fetchDriverById(driverId) {
  try {
    const res = await fetch(`${API_BASE}/drivers/${driverId}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn(`Could not fetch driver ${driverId} from API:`, err);
  }
  return null;
}

export async function fetchVehicles() {
  try {
    const drivers = await fetchDrivers();
    const map = new Map();
    for (const d of drivers) {
      const vId = d.vehicle_id || 'VEH001';
      if (!map.has(vId)) {
        map.set(vId, {
          id: vId,
          vehicleNo: d.vehicle_no || 'Cabin Rig',
          model: 'Fleet AI Safety Rig',
          driverId: d.driver_id,
          driverName: d.driver_name,
          status: d.status === 'ACTIVE' ? 'ON_ROAD' : 'PARKED'
        });
      }
    }
    return Array.from(map.values());
  } catch (err) {
    console.warn("Could not fetch vehicles from API:", err);
    return [];
  }
}

export async function fetchEvents(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.limit) params.append("limit", filters.limit);
    if (filters.skip) params.append("skip", filters.skip);
    if (filters.driver_id) params.append("driver_id", filters.driver_id);
    if (filters.severity) params.append("severity", filters.severity);
    if (filters.event_type) params.append("event_type", filters.event_type);

    const url = `${API_BASE}/events${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await fetch(url);
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data)) {
        return data;
      }
    }
  } catch (err) {
    console.warn("Could not fetch live events from API:", err);
  }
  return [];
}

export async function fetchEventById(eventId) {
  try {
    const res = await fetch(`${API_BASE}/events/${eventId}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.error(`Failed to fetch event ${eventId}:`, err);
  }
  return null;
}

export async function requestAiAnalysis(eventId, model = null) {
  try {
    const payload = { event_id: eventId };
    if (model) payload.model = model;

    const res = await fetch(`${API_BASE}/ai/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      return await res.json();
    }
    return {
      status: "error",
      summary: "I couldn't complete that request just now. Please try again."
    };
  } catch (err) {
    return {
      status: "error",
      summary: "I couldn't complete that request just now. Please try again."
    };
  }
}

export async function askSafetyQuestion(driverId, question, timeRange = "30m", conversationHistory = []) {
  try {
    const payload = {
      driver_id: driverId,
      question: question,
      time_range: timeRange,
      conversation_history: conversationHistory
    };

    const res = await fetch(`${API_BASE}/ai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      return await res.json();
    }
    return {
      status: "error",
      answer: "I couldn't complete that request just now. Please try again.",
      summary: "I couldn't complete that request just now. Please try again."
    };
  } catch (err) {
    return {
      status: "error",
      answer: "I couldn't complete that request just now. Please try again.",
      summary: "I couldn't complete that request just now. Please try again."
    };
  }
}

export async function generateSafetySummary(driverId, timeRange = "today") {
  try {
    const payload = {
      driver_id: driverId,
      time_range: timeRange
    };

    const res = await fetch(`${API_BASE}/ai/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      return await res.json();
    }
    return {
      status: "error",
      answer: "I couldn't complete that request just now. Please try again.",
      summary: "I couldn't complete that request just now. Please try again."
    };
  } catch (err) {
    return {
      status: "error",
      answer: "I couldn't complete that request just now. Please try again.",
      summary: "I couldn't complete that request just now. Please try again."
    };
  }
}

export async function fetchAiAnalyses(limit = 50, eventId = null, driverId = null, analysisType = null) {
  try {
    const params = new URLSearchParams();
    params.append("limit", limit);
    if (eventId) params.append("event_id", eventId);
    if (driverId) params.append("driver_id", driverId);
    if (analysisType) params.append("analysis_type", analysisType);

    const res = await fetch(`${API_BASE}/ai/analyses?${params.toString()}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("Could not fetch historical AI analyses:", err);
  }
  return [];
}
