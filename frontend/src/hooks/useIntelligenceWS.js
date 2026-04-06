import { useEffect, useRef, useState, useCallback } from "react";

/**
 * Custom hook for WebSocket connection to the intelligence feed.
 * Provides real-time new items, critical alerts, and scan status.
 */
export function useIntelligenceWS(apiUrl) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [newItems, setNewItems] = useState([]);
  const [criticalAlerts, setCriticalAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const pingTimer = useRef(null);

  const connect = useCallback(() => {
    if (!apiUrl) return;

    // Convert http(s) URL to ws(s) URL — /api prefix for K8s routing
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws/intelligence";

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // Send ping every 30s to keep alive
        pingTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "pong") return;

          setLastMessage(data);

          if (data.type === "new_item" && data.item) {
            setNewItems((prev) => [data.item, ...prev].slice(0, 50));
          }

          if ((data.type === "elite_alert" || data.type === "critical_alert") && data.item) {
            setCriticalAlerts((prev) => [data.item, ...prev].slice(0, 20));
          }
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        clearInterval(pingTimer.current);
        // Reconnect after 5s
        reconnectTimer.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      // Reconnect on error
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, [apiUrl]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearInterval(pingTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const clearAlerts = useCallback(() => setCriticalAlerts([]), []);
  const clearNewItems = useCallback(() => setNewItems([]), []);

  return {
    connected,
    lastMessage,
    newItems,
    criticalAlerts,
    clearAlerts,
    clearNewItems,
  };
}
