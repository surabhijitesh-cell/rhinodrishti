import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const AuthContext = createContext(null);

export function AuthProvider({ children, api }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

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
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem("rd_token");
          localStorage.removeItem("rd_user");
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
      } catch {
        localStorage.removeItem("rd_token");
        localStorage.removeItem("rd_user");
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
    // Increment login count — used by TourContext to suppress auto-tour after first login.
    const countKey = `rd_login_count_${userData.username}`;
    const prev = parseInt(localStorage.getItem(countKey) || "0", 10);
    localStorage.setItem(countKey, String(prev + 1));
    setUser(userData);
    return userData;
  }, [api]);

  const logout = useCallback(() => {
    localStorage.removeItem("rd_token");
    localStorage.removeItem("rd_user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
