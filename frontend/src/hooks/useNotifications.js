import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return new Uint8Array([...raw].map((c) => c.charCodeAt(0)));
}

export function useNotifications() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [prefs, setPrefs] = useState(null);
  const [pushSupported, setPushSupported] = useState(false);
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);
  const swRegRef = useRef(null);

  useEffect(() => {
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const standalone = window.navigator.standalone === true;
    setIsIOS(ios);
    setIsStandalone(standalone);
    setPushSupported("PushManager" in window && "serviceWorker" in navigator);
  }, []);

  // Check existing push subscription on mount
  useEffect(() => {
    if (!pushSupported) return;
    navigator.serviceWorker.ready.then((reg) => {
      swRegRef.current = reg;
      reg.pushManager.getSubscription().then((sub) => {
        setPushSubscribed(!!sub);
      });
    });
  }, [pushSupported]);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const token = localStorage.getItem("rd_token");
      if (!token) return;
      const res = await axios.get(`${API}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUnreadCount(res.data.count || 0);
    } catch (_) {}
  }, []);

  const fetchNotifications = useCallback(async (page = 1, unreadOnly = false) => {
    try {
      const token = localStorage.getItem("rd_token");
      if (!token) return { notifications: [], total: 0 };
      const res = await axios.get(`${API}/notifications`, {
        params: { page, limit: 20, unread_only: unreadOnly },
        headers: { Authorization: `Bearer ${token}` },
      });
      if (page === 1) setNotifications(res.data.notifications || []);
      return res.data;
    } catch (_) {
      return { notifications: [], total: 0 };
    }
  }, []);

  const fetchPrefs = useCallback(async () => {
    try {
      const token = localStorage.getItem("rd_token");
      if (!token) return;
      const res = await axios.get(`${API}/notifications/preferences`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPrefs(res.data);
    } catch (_) {}
  }, []);

  const savePrefs = useCallback(async (updates) => {
    try {
      const token = localStorage.getItem("rd_token");
      const res = await axios.put(`${API}/notifications/preferences`, updates, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPrefs(res.data);
    } catch (_) {}
  }, []);

  const markRead = useCallback(async (notificationId) => {
    try {
      const token = localStorage.getItem("rd_token");
      await axios.post(`${API}/notifications/${notificationId}/read`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications((prev) =>
        prev.map((n) =>
          n.notification_id === notificationId ? { ...n, is_read: true } : n
        )
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (_) {}
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      const token = localStorage.getItem("rd_token");
      await axios.post(`${API}/notifications/read-all`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (_) {}
  }, []);

  const subscribe = useCallback(async () => {
    if (!pushSupported) return { ok: false, error: "Push not supported in this browser" };
    try {
      const token = localStorage.getItem("rd_token");
      const keyRes = await axios.get(`${API}/notifications/vapid-public-key`);
      const publicKey = keyRes.data.public_key;
      if (!publicKey) return { ok: false, error: "VAPID keys not configured on server. Add VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to backend .env and restart." };

      const permission = await Notification.requestPermission();
      if (permission !== "granted") return { ok: false, error: "Notification permission denied. Enable notifications in browser/OS settings." };

      // Timeout so a hung SW registration surfaces as an error instead of silence
      const reg = swRegRef.current || await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Service worker not ready — check DevTools → Application → Service Workers")), 8000)
        ),
      ]);
      swRegRef.current = reg;

      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });

      const subJson = sub.toJSON();
      await axios.post(
        `${API}/notifications/subscribe`,
        {
          endpoint: subJson.endpoint,
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth,
          platform: isIOS ? "ios" : /Android/i.test(navigator.userAgent) ? "android" : "desktop",
          user_agent: navigator.userAgent.slice(0, 200),
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPushSubscribed(true);
      await savePrefs({ push_enabled: true });
      return { ok: true };
    } catch (err) {
      console.warn("Push subscribe failed:", err);
      return { ok: false, error: err?.message || "Push subscription failed" };
    }
  }, [pushSupported, isIOS, savePrefs]);

  const unsubscribe = useCallback(async () => {
    if (!pushSupported) return { ok: false, error: "Push not supported" };
    try {
      const token = localStorage.getItem("rd_token");
      const reg = swRegRef.current || (await navigator.serviceWorker.ready);
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await axios.delete(`${API}/notifications/unsubscribe`, {
          data: { endpoint: sub.endpoint },
          headers: { Authorization: `Bearer ${token}` },
        });
        await sub.unsubscribe();
      }
      setPushSubscribed(false);
      await savePrefs({ push_enabled: false });
      return { ok: true };
    } catch (err) {
      console.warn("Push unsubscribe failed:", err);
      return { ok: false, error: err?.message || "Unsubscribe failed" };
    }
  }, [pushSupported, savePrefs]);

  // Poll unread count every 60s as fallback when WS is down
  useEffect(() => {
    fetchUnreadCount();
    fetchPrefs();
    const id = setInterval(fetchUnreadCount, 60000);
    return () => clearInterval(id);
  }, [fetchUnreadCount, fetchPrefs]);

  return {
    unreadCount,
    setUnreadCount,
    notifications,
    prefs,
    pushSupported,
    pushSubscribed,
    isIOS,
    isStandalone,
    fetchNotifications,
    fetchPrefs,
    savePrefs,
    markRead,
    markAllRead,
    subscribe,
    unsubscribe,
  };
}
