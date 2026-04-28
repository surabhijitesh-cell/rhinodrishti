/**
 * TourContext — manages the guided walkthrough state.
 *
 * - Auto-starts on first login (per username, stored in localStorage)
 * - Admin (or any user) can re-trigger via startTour()
 * - Page-aware: each route has its own step set
 */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

const TourContext = createContext(null);

export function TourProvider({ children }) {
  const [running, setRunning]     = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  // Incrementing this forces Joyride to fully remount, resetting its
  // internal state so the tour plays correctly every time startTour() fires.
  const [joyKey, setJoyKey]       = useState(0);
  const { user } = useAuth();
  const location = useLocation();
  const autoStarted = useRef(false);

  const storageKey = user?.username ? `tour_seen_${user.username}_${location.pathname}` : null;

  // Auto-start for first-time users on this page
  useEffect(() => {
    if (!user || !storageKey || autoStarted.current) return;
    autoStarted.current = true;
    const seen = localStorage.getItem(storageKey);
    if (!seen) {
      // Small delay so page renders first
      const t = setTimeout(() => {
        setStepIndex(0);
        setJoyKey(k => k + 1);
        setRunning(true);
      }, 1200);
      return () => clearTimeout(t);
    }
  }, [user, storageKey]);

  // Reset autoStarted ref when route changes so each page can auto-trigger once
  useEffect(() => {
    autoStarted.current = false;
  }, [location.pathname]);

  const startTour = useCallback(() => {
    // Stop first so Joyride fully unmounts, then restart on next tick
    setRunning(false);
    setStepIndex(0);
    setJoyKey(k => k + 1);   // new key → Joyride remounts fresh
    setTimeout(() => setRunning(true), 50);
  }, []);

  const stopTour = useCallback(() => {
    setRunning(false);
    if (storageKey) localStorage.setItem(storageKey, "1");
  }, [storageKey]);

  const markSeen = useCallback(() => {
    if (storageKey) localStorage.setItem(storageKey, "1");
  }, [storageKey]);

  const resetAllTours = useCallback(() => {
    if (!user?.username) return;
    Object.keys(localStorage)
      .filter(k => k.startsWith(`tour_seen_${user.username}`))
      .forEach(k => localStorage.removeItem(k));
  }, [user]);

  return (
    <TourContext.Provider value={{ running, stepIndex, setStepIndex, startTour, stopTour, markSeen, resetAllTours, joyKey }}>
      {children}
    </TourContext.Provider>
  );
}

export function useTour() {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used inside TourProvider");
  return ctx;
}
