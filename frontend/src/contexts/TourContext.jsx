/**
 * TourContext — guided walkthrough state.
 *
 * Rules:
 *  - Auto-starts ONCE, on first-ever login only (login_count === 1).
 *  - After skip / finish / close → permanent flag set → never auto-starts again.
 *  - Manual startTour() via ? button always works regardless of flags.
 *  - resetTour() clears the permanent flag (used by ? + admin reset button).
 */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import { useAuth } from "./AuthContext";

const TourContext = createContext(null);

const loginCountKey = (u) => `rd_login_count_${u}`;
const tourDoneKey   = (u) => `rd_tour_done_${u}`;

export function TourProvider({ children }) {
  const [running, setRunning] = useState(false);
  // Incrementing key forces Joyride to fully remount on each startTour() call.
  const [joyKey,  setJoyKey]  = useState(0);
  const { user } = useAuth();

  // Never resets on route change — one auto-start attempt per session max.
  const autoStartFired = useRef(false);

  // ── helpers ──────────────────────────────────────────────────────────────
  const isDone = useCallback(() => {
    if (!user?.username) return true;
    return localStorage.getItem(tourDoneKey(user.username)) === "1";
  }, [user]);

  const getLoginCount = useCallback(() => {
    if (!user?.username) return 0;
    return parseInt(localStorage.getItem(loginCountKey(user.username)) || "0", 10);
  }, [user]);

  const markDone = useCallback(() => {
    if (user?.username) localStorage.setItem(tourDoneKey(user.username), "1");
  }, [user]);

  // ── auto-start: first login only, once per session ───────────────────────
  useEffect(() => {
    if (!user)                  return;
    if (autoStartFired.current) return;   // already fired this session
    if (isDone())               return;   // user skipped / finished before
    if (getLoginCount() !== 1)  return;   // second+ login → never auto-start

    autoStartFired.current = true;
    const t = setTimeout(() => {
      setJoyKey(k => k + 1);
      setRunning(true);
    }, 1200);
    return () => clearTimeout(t);
    // location.pathname intentionally NOT in deps — fires once on user load,
    // not on every route change.
  }, [user, isDone, getLoginCount]);

  // ── public API ────────────────────────────────────────────────────────────

  /** Manual trigger from ? button — always works. */
  const startTour = useCallback(() => {
    setJoyKey(k => k + 1);
    setRunning(true);
  }, []);

  /** User skipped mid-tour. Mark done so auto-start never fires again. */
  const skipTour = useCallback(() => {
    setRunning(false);
    markDone();
  }, [markDone]);

  /** User completed all steps. Mark done. */
  const finishTour = useCallback(() => {
    setRunning(false);
    markDone();
  }, [markDone]);

  /** Clear done flag — lets ? button replay the tour fresh. */
  const resetTour = useCallback(() => {
    if (user?.username) localStorage.removeItem(tourDoneKey(user.username));
    autoStartFired.current = false;
  }, [user]);

  return (
    <TourContext.Provider value={{ running, joyKey, startTour, skipTour, finishTour, resetTour }}>
      {children}
    </TourContext.Provider>
  );
}

export function useTour() {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used inside TourProvider");
  return ctx;
}
