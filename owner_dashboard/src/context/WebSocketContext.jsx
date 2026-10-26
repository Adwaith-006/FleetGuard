import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false);
  const [latestEvent, setLatestEvent] = useState(null);
  const [liveEventsList, setLiveEventsList] = useState([]);
  const [toastAlert, setToastAlert] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    let wsUrl = `ws://${window.location.hostname}:8000/ws`;
    
    function connect() {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          console.log("[WebSocket] Connected to AI Driver Monitoring Backend");
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'NEW_SAFETY_EVENT' && data.event) {
              const newEvt = data.event;
              setLatestEvent(newEvt);
              setLiveEventsList(prev => [newEvt, ...prev.filter(e => e.event_id !== newEvt.event_id)]);

              // Trigger real-time toast alert
              setToastAlert({
                id: Date.now(),
                type: newEvt.event_type,
                duration: newEvt.duration,
                status: newEvt.status || 'OBSERVED',
                timestamp: newEvt.start_time ? new Date(newEvt.start_time).toLocaleTimeString() : new Date().toLocaleTimeString()
              });

              // Clear toast alert after 5 seconds
              setTimeout(() => {
                setToastAlert(null);
              }, 6000);
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

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        latestEvent,
        liveEventsList,
        toastAlert,
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
