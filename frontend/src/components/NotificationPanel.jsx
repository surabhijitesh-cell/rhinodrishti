import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  X, Bell, BellOff, CheckCheck, ChevronRight,
  Flag, AlertTriangle, TrendingUp, Info, MapPin,
} from "lucide-react";
import { Button } from "./ui/button";
import { useNotifications } from "../hooks/useNotifications";

const TYPE_ICON = {
  FAULTLINE_ESCALATION: AlertTriangle,
  HIGH_PRIORITY_ARTICLE: TrendingUp,
  PAOI_IMPACT: Bell,
  FLAGGED_NEWS: Flag,
  STATE_ESCALATION: MapPin,
};

const TYPE_COLOR = {
  FAULTLINE_ESCALATION: "text-red-400",
  HIGH_PRIORITY_ARTICLE: "text-orange-400",
  PAOI_IMPACT: "text-amber-400",
  FLAGGED_NEWS: "text-violet-400",
  STATE_ESCALATION: "text-rose-400",
};

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function NotificationPanel({ onClose }) {
  const navigate = useNavigate();
  const {
    notifications, fetchNotifications, markRead, markAllRead,
    pushSupported, pushSubscribed, subscribe, unsubscribe,
    isIOS, isStandalone,
  } = useNotifications();

  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState("all");

  const load = useCallback(async (p = 1, unreadOnly = false) => {
    setLoading(true);
    const res = await fetchNotifications(p, unreadOnly);
    setTotal(res?.total || 0);
    setPage(p);
    setLoading(false);
  }, [fetchNotifications]);

  useEffect(() => {
    load(1, tab === "unread");
  }, [tab, load]);

  const handleClick = async (n) => {
    if (!n.is_read) await markRead(n.notification_id);
    if (n.deep_link) {
      onClose();
      navigate(n.deep_link);
    }
  };

  const handleMarkAll = async () => {
    await markAllRead();
  };

  const showIOSPrompt = isIOS && !isStandalone;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="notification-panel">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-full max-w-sm h-full bg-card border-l border-border flex flex-col shadow-xl animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Bell size={16} className="text-primary" />
            <span className="text-sm font-semibold uppercase tracking-wider">Notifications</span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={handleMarkAll} className="text-xs text-muted-foreground h-7">
              <CheckCheck size={13} className="mr-1" /> Mark all read
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose} data-testid="close-notification-panel">
              <X size={16} />
            </Button>
          </div>
        </div>

        {/* iOS install prompt */}
        {showIOSPrompt && (
          <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20 text-xs text-amber-300 flex items-start gap-2">
            <Info size={13} className="mt-0.5 shrink-0" />
            <span>
              For push notifications on iOS, tap <strong>Share → Add to Home Screen</strong> to install this app, then enable notifications.
            </span>
          </div>
        )}

        {/* Push toggle */}
        {pushSupported && !isIOS && (
          <div className="px-4 py-2 border-b border-border flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Push notifications</span>
            <Button
              variant="ghost"
              size="sm"
              className={`text-xs h-7 ${pushSubscribed ? "text-green-400" : "text-muted-foreground"}`}
              onClick={pushSubscribed ? unsubscribe : subscribe}
            >
              {pushSubscribed ? (
                <><Bell size={12} className="mr-1" /> On</>
              ) : (
                <><BellOff size={12} className="mr-1" /> Off</>
              )}
            </Button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-border">
          {["all", "unread"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-xs uppercase tracking-wider font-mono transition-colors ${
                tab === t
                  ? "text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
              Loading…
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-2 text-muted-foreground">
              <Bell size={24} className="opacity-30" />
              <span className="text-sm">No notifications</span>
            </div>
          ) : (
            <>
              {notifications.map((n) => {
                const Icon = TYPE_ICON[n.notif_type] || Info;
                const color = TYPE_COLOR[n.notif_type] || "text-muted-foreground";
                return (
                  <button
                    key={n.notification_id}
                    onClick={() => handleClick(n)}
                    className={`w-full text-left px-4 py-3 border-b border-border hover:bg-muted/30 transition-colors flex items-start gap-3 ${
                      !n.is_read ? "bg-primary/5" : ""
                    }`}
                    data-testid={`notif-item-${n.notification_id}`}
                  >
                    <Icon size={14} className={`mt-0.5 shrink-0 ${color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <p className={`text-xs font-semibold leading-tight truncate ${!n.is_read ? "text-foreground" : "text-muted-foreground"}`}>
                          {n.title}
                        </p>
                        {!n.is_read && (
                          <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground leading-snug mt-0.5 line-clamp-2">
                        {n.body}
                      </p>
                      <p className="text-[10px] text-muted-foreground/60 font-mono mt-1">
                        {timeAgo(n.created_at)}
                      </p>
                    </div>
                    {n.deep_link && (
                      <ChevronRight size={13} className="text-muted-foreground/40 shrink-0 mt-0.5" />
                    )}
                  </button>
                );
              })}

              {/* Load more */}
              {notifications.length < total && (
                <div className="p-3 text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    onClick={() => load(page + 1, tab === "unread")}
                  >
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
