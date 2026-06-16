import { useEffect, useRef, useState, useCallback } from "react";
import { toast } from "sonner";

/**
 * Custom hook for WebSocket connection to the intelligence feed.
 * Provides real-time new items, critical alerts, scan status, and targeted notifications.
 */
export function useIntelligenceWS(apiUrl, { onNotification } = {}) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [newItems, setNewItems] = useState([]);
  const [criticalAlerts, setCriticalAlerts] = useState([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const pingTimer = useRef(null);
  const onNotificationRef = useRef(onNotification);
  onNotificationRef.current = onNotification;

  const connect = useCallback(() => {
    if (!apiUrl) return;

    // Convert http(s) URL to ws(s) URL — /api prefix for K8s routing
    const token = localStorage.getItem("rd_token") || "";
    const base = apiUrl.replace(/^http/, "ws") + "/ws/intelligence";
    const wsUrl = token ? `${base}?token=${encodeURIComponent(token)}` : base;

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

          if (data.type === "notification" && data.notification) {
            setUnreadNotifCount((c) => c + 1);
            const n = data.notification;
            toast(n.title, {
              description: n.body,
              action: n.deep_link
                ? { label: "View", onClick: () => { window.location.href = n.deep_link; } }
                : undefined,
              duration: 6000,
            });
            if (onNotificationRef.current) {
              onNotificationRef.current(n);
            }
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
  const incrementUnread = useCallback((n) => setUnreadNotifCount((c) => c + n), []);
  const resetUnread = useCallback(() => setUnreadNotifCount(0), []);

  return {
    connected,
    lastMessage,
    newItems,
    criticalAlerts,
    unreadNotifCount,
    clearAlerts,
    clearNewItems,
    incrementUnread,
    resetUnread,
  };
}
