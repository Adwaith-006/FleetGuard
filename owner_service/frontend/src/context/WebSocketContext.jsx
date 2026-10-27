import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false);
  const [latestEvent, setLatestEvent] = useState(null);
  const [liveEventsList, setLiveEventsList] = useState([]);
  const [latestDriverStatus, setLatestDriverStatus] = useState(null);
  const [driverStatuses, setDriverStatuses] = useState({});
  const [toastAlert, setToastAlert] = useState(null);
  const [urgentAlert, setUrgentAlert] = useState(null);
  const wsRef = useRef(null);

  // Fetch any active alert on mount / reconnection
  const checkActiveAlert = () => {
    fetch(`http://${window.location.hostname}:8000/api/alerts/active?driver_id=DRV001`)
      .then(res => res.json())
      .then(data => {
        if (data && data.active && data.alert) {
          setUrgentAlert(data.alert);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    checkActiveAlert();
    let wsUrl = `ws://${window.location.hostname}:8000/ws`;
    
    function connect() {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          console.log("[WebSocket] Connected to AI Driver Monitoring Backend");
          checkActiveAlert();
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'URGENT_SAFETY_ALERT' && data.alert) {
              setUrgentAlert(data.alert);
            } else if (data.type === 'ALERT_EXPLANATION_UPDATED') {
              setUrgentAlert(prev => {
                if (prev && prev.alert_id === data.alert_id) {
                  return {
                    ...prev,
                    explanation: data.explanation || prev.explanation,
                    recommendations: data.recommendations || prev.recommendations
                  };
                }
                return prev;
              });
            } else if (data.type === 'URGENT_SAFETY_ALERT_RECOVERED') {
              setUrgentAlert(prev => {
                if (prev && prev.alert_id === data.alert_id) {
                  return null;
                }
                return prev;
              });
            } else if (data.type === 'NEW_SAFETY_EVENT' && data.event) {
              const newEvt = data.event;
              setLatestEvent(newEvt);
              setLiveEventsList(prev => [newEvt, ...prev.filter(e => e.event_id !== newEvt.event_id)]);
            } else if (data.type === 'AI_ANALYSIS_COMPLETED' && data.analysis) {
              const analysis = data.analysis;
              const eventId = data.event_id || analysis.event_id;
              setLiveEventsList(prev => prev.map(e => {
                if (e.event_id === eventId) {
                  return { ...e, ai_analysis: analysis, explanation: analysis.summary };
                }
                return e;
              }));
            } else if (data.type === 'DRIVER_STATUS_UPDATE') {
              setLatestDriverStatus(data);
              if (data.driver_id) {
                setDriverStatuses(prev => ({
                  ...prev,
                  [data.driver_id]: data
                }));
              }
            }
          } catch (e) {
            console.error("Error parsing WebSocket message:", e);
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          console.log("[WebSocket] Connection closed. Reconnecting in 3s...");
          setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.warn("[WebSocket] Connection error:", err);
          ws.close();
        };
      } catch (err) {
        console.warn("[WebSocket] Setup error:", err);
      }
    }

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const dismissUrgentAlert = async (alertId) => {
    try {
      if (alertId) {
        await fetch(`http://${window.location.hostname}:8000/api/alerts/${alertId}/resolve`, {
          method: 'POST'
        });
      }
    } catch (e) {
      console.debug("Dismiss alert error:", e);
    }
    setUrgentAlert(null);
  };

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        latestEvent,
        liveEventsList,
        latestDriverStatus,
        driverStatuses,
        toastAlert,
        urgentAlert,
        dismissUrgentAlert,
        clearToast: () => setToastAlert(null)
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}
