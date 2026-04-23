import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "./AuthContext";
import { Bell, ChevronRight, X } from "lucide-react";

const UpdateContext = createContext(null);

export function UpdateNotificationProvider({ children, api }) {
  const { user, isAuthenticated } = useAuth();
  const [showMoreModal, setShowMoreModal] = useState(false);
  const [totalMajor, setTotalMajor] = useState(0);
  const checkedRef = useRef(false);

  const checkUpdates = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    try {
      const res = await axios.get(`${api}/app/updates`);
      const { notifications, has_more, total_major } = res.data;
      if (!notifications || notifications.length === 0) return;

      setTotalMajor(total_major);
      // Queue-based toast display
      showToastQueue(notifications, has_more);

      // Acknowledge after showing
      await axios.post(`${api}/app/updates/acknowledge`);
    } catch (e) {
      console.error("Update check failed:", e);
    }
  }, [isAuthenticated, user, api]);

  const showToastQueue = (notifications, hasMore) => {
    let delay = 500;
    const TOAST_DURATION = 5000;
    const GAP = 800;

    notifications.forEach((notif, i) => {
      setTimeout(() => {
        if (notif.priority === "major") {
          toast(notif.message, {
            description: `v${notif.version}`,
            duration: TOAST_DURATION,
            icon: <Bell size={16} className="text-primary" />,
            className: "border-l-4 border-l-primary",
          });
        } else {
          toast(notif.message, {
            description: `v${notif.version}`,
            duration: TOAST_DURATION,
          });
        }
      }, delay + i * (TOAST_DURATION + GAP));
    });

    // Show "More Updates" modal after all toasts
    if (hasMore) {
      const modalDelay = delay + notifications.length * (TOAST_DURATION + GAP) + 500;
      setTimeout(() => setShowMoreModal(true), modalDelay);
    }
  };

  // Check updates once after login
  useEffect(() => {
    if (isAuthenticated && user && !checkedRef.current) {
      checkedRef.current = true;
      // Small delay to let the UI settle after login
      const t = setTimeout(checkUpdates, 1500);
      return () => clearTimeout(t);
    }
    if (!isAuthenticated) {
      checkedRef.current = false;
    }
  }, [isAuthenticated, user, checkUpdates]);

  return (
    <UpdateContext.Provider value={{ checkUpdates }}>
      {children}
      {showMoreModal && (
        <MoreUpdatesModal
          totalMajor={totalMajor}
          onViewAll={() => {
            setShowMoreModal(false);
            window.location.href = "/updates";
          }}
          onDismiss={() => setShowMoreModal(false)}
        />
      )}
    </UpdateContext.Provider>
  );
}

function MoreUpdatesModal({ totalMajor, onViewAll, onDismiss }) {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4" data-testid="more-updates-modal">
      <div className="bg-card border border-border rounded-none w-full max-w-sm shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell size={16} className="text-primary" />
            <h3 className="text-sm font-bold uppercase tracking-wider font-['Barlow_Condensed']">
              More Updates Available
            </h3>
          </div>
          <button onClick={onDismiss} className="text-muted-foreground hover:text-foreground" data-testid="dismiss-more-updates">
            <X size={16} />
          </button>
        </div>
        <div className="p-4">
          <p className="text-sm text-muted-foreground">
            You have <span className="text-foreground font-semibold">{totalMajor}</span> major updates total.
            Only the latest 3 were shown. View the full update log to see everything.
          </p>
        </div>
        <div className="p-4 pt-0 flex gap-2">
          <button
            onClick={onViewAll}
            className="flex-1 bg-primary text-primary-foreground px-4 py-2 text-xs uppercase tracking-wider font-bold flex items-center justify-center gap-1 hover:bg-primary/90 transition-colors"
            data-testid="view-all-updates-btn"
          >
            View All Updates <ChevronRight size={14} />
          </button>
          <button
            onClick={onDismiss}
            className="px-4 py-2 text-xs uppercase tracking-wider font-mono border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            data-testid="dismiss-updates-btn"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export function useUpdates() {
  const ctx = useContext(UpdateContext);
  return ctx || {};
}
