import { useEffect, useRef, useState, useCallback } from "react";
import { toast } from "sonner";

// Wait 2 s after the first failure, doubling each time, never more than 60 s.
export function reconnectDelay(attempt) {
  return Math.min(60000, 2000 * 2 ** Math.max(0, attempt));
}

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
  const reconnectTimer = useRef(null);
  const pingTimer = useRef(null);
  const onNotificationRef = useRef(onNotification);
  onNotificationRef.current = onNotification;

  useEffect(() => {
    if (!apiUrl) return undefined;
    let stopped = false; // set on unmount so nothing reconnects afterwards
    let attempt = 0;
    let ws = null;

    const connect = () => {
      if (stopped) return;
      // Convert http(s) URL to ws(s) URL — /api prefix for K8s routing
      const token = localStorage.getItem("rd_token") || "";
      const base = apiUrl.replace(/^http/, "ws") + "/ws/intelligence";
      const wsUrl = token ? `${base}?token=${encodeURIComponent(token)}` : base;

      const retry = () => {
        if (stopped) return;
        reconnectTimer.current = setTimeout(connect, reconnectDelay(attempt));
        attempt += 1;
      };

      try {
        ws = new WebSocket(wsUrl);
      } catch (e) {
        retry();
        return;
      }
      const mine = ws;

      mine.onopen = () => {
        attempt = 0;
        setConnected(true);
        // Send ping every 30s to keep alive
        pingTimer.current = setInterval(() => {
          if (mine.readyState === WebSocket.OPEN) mine.send("ping");
        }, 30000);
      };

      mine.onmessage = (event) => {
        if (stopped) return;
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
              // Same id means a repeat shows once, not twice.
              id: n.id || `${n.title}|${n.body}`,
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

      mine.onclose = () => {
        clearInterval(pingTimer.current);
        if (stopped) return;
        setConnected(false);
        retry();
      };

      mine.onerror = () => {
        mine.close();
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(reconnectTimer.current);
      clearInterval(pingTimer.current);
      if (ws) {
        ws.onclose = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.close();
      }
    };
  }, [apiUrl]);

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
