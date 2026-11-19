import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const AuthContext = createContext(null);

const WARN_BEFORE_MS = 10 * 60 * 1000;
const MAX_TIMER_MS = 2147483647;

/** Reads the expiry time (ms) from a login token without checking its signature. */
export function getTokenExpiryMs(token) {
  try {
    const part = String(token || "").split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4))
        .split("").map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    );
    const exp = Number(JSON.parse(json).exp);
    return Number.isFinite(exp) ? exp * 1000 : null;
  } catch {
    return null;
  }
}

/** "ok" | "expiring" (within 10 minutes) | "expired" */
export function sessionStateAt(expiryMs, now = Date.now()) {
  if (!expiryMs) return "ok";
  if (now >= expiryMs) return "expired";
  return expiryMs - now <= WARN_BEFORE_MS ? "expiring" : "ok";
}

const clearSessionCaches = () => window.dispatchEvent(new Event("rd-session-cleared"));

export function AuthProvider({ children, api }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState({ state: "ok", expiresAt: null });

  // Axios interceptor — attach token to every request
  useEffect(() => {
    const reqInterceptor = axios.interceptors.request.use((config) => {
      const token = localStorage.getItem("rd_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    const resInterceptor = axios.interceptors.response.use(
      (response) => {
        window.dispatchEvent(new Event("rd-server-up"));
        return response;
      },
      (error) => {
        // No answer, or the host's "starting up" codes: the server is waking, not refusing us.
        if (!error.response || [502, 503, 504].includes(error.response.status)) {
          window.dispatchEvent(new Event("rd-server-down"));
        }
        if (error.response?.status === 401) {
          localStorage.removeItem("rd_token");
          localStorage.removeItem("rd_user");
          clearSessionCaches();
          setUser(null);
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(reqInterceptor);
      axios.interceptors.response.eject(resInterceptor);
    };
  }, []);

  // Check existing token on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("rd_token");
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await axios.get(`${api}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setUser(res.data);
      } catch (e) {
        if (e.response?.status === 401) {
          localStorage.removeItem("rd_token");
          localStorage.removeItem("rd_user");
        } else {
          // Server asleep or unreachable: keep the session; the server checks the token on every request.
          try { setUser(JSON.parse(localStorage.getItem("rd_user") || "null")); } catch { /* stays logged out */ }
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, [api]);

  const login = useCallback(async (username, password) => {
    const res = await axios.post(`${api}/auth/login`, { username, password });
    const { token, user: userData } = res.data;
    localStorage.setItem("rd_token", token);
    localStorage.setItem("rd_user", JSON.stringify(userData));
    clearSessionCaches();
    // Increment login count — used by TourContext to suppress auto-tour after first login.
    const countKey = `rd_login_count_${userData.username}`;
    const prev = parseInt(localStorage.getItem(countKey) || "0", 10);
    localStorage.setItem(countKey, String(prev + 1));
    setUser(userData);
    return userData;
  }, [api]);

  const logout = useCallback(() => {
    // Best-effort — marks the session's precise end time for the activity
    // report / Currently Online view. Fire-and-forget: logout must not wait
    // on the network, and clearing the token below happens regardless.
    axios.post(`${api}/auth/logout`).catch(() => {});
    localStorage.removeItem("rd_token");
    localStorage.removeItem("rd_user");
    clearSessionCaches();
    setUser(null);
  }, [api]);

  // Tell the person before the login runs out; never log them out early.
  useEffect(() => {
    if (!user) { setSession({ state: "ok", expiresAt: null }); return undefined; }
    const expiresAt = getTokenExpiryMs(localStorage.getItem("rd_token"));
    if (!expiresAt) return undefined;
    let timer;
    let last = null;
    const tick = () => {
      const state = sessionStateAt(expiresAt);
      setSession({ state, expiresAt });
      if (state !== last && state === "expiring") {
        toast.warning("Your login ends in about 10 minutes. Save your work, then sign in again.");
      }
      if (state !== last && state === "expired") {
        toast.error("Your login has expired. Please sign in again.");
      }
      last = state;
      if (state === "expired") return;
      const next = state === "ok" ? expiresAt - WARN_BEFORE_MS : expiresAt;
      timer = setTimeout(tick, Math.min(Math.max(next - Date.now(), 1000), MAX_TIMER_MS));
    };
    tick();
    return () => clearTimeout(timer);
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAuthenticated: !!user, session }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
