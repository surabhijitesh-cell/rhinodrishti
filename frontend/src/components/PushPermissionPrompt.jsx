import { useState, useEffect } from "react";
import { Bell, X } from "lucide-react";
import { Button } from "./ui/button";

const SNOOZE_KEY = "rd_push_snoozed_until";
const SNOOZE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export default function PushPermissionPrompt({ pushSupported, pushSubscribed, subscribe }) {
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!pushSupported || pushSubscribed) return;
    if (typeof Notification === "undefined") return;
    if (Notification.permission !== "default") return;

    const snoozedUntil = localStorage.getItem(SNOOZE_KEY);
    if (snoozedUntil && Date.now() < Number(snoozedUntil)) return;

    // 3-second delay so it doesn't flash on page load
    const t = setTimeout(() => setVisible(true), 3000);
    return () => clearTimeout(t);
  }, [pushSupported, pushSubscribed]);

  if (!visible) return null;

  const handleEnable = async () => {
    setLoading(true);
    await subscribe();
    setLoading(false);
    setVisible(false);
    // If user clicked Deny in the OS dialog, snooze for a year (effectively permanent)
    if (typeof Notification !== "undefined" && Notification.permission === "denied") {
      localStorage.setItem(SNOOZE_KEY, String(Date.now() + 365 * 24 * 60 * 60 * 1000));
    }
  };

  const handleDismiss = () => {
    localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_MS));
    setVisible(false);
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 w-76 bg-card border border-border shadow-2xl animate-slide-in">
      <div className="flex items-start gap-3 p-4">
        <div className="shrink-0 mt-0.5 w-8 h-8 bg-primary/10 flex items-center justify-center">
          <Bell size={14} className="text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold font-['Barlow_Condensed'] uppercase tracking-wide leading-tight">
            Enable Push Notifications
          </p>
          <p className="text-xs text-muted-foreground mt-1 leading-snug">
            Get real-time alerts for critical intel, faultline spikes, and priority area events — even when the app is in the background.
          </p>
          <div className="flex gap-2 mt-3">
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={handleEnable}
              disabled={loading}
            >
              <Bell size={11} className="mr-1" />
              {loading ? "Enabling…" : "Enable"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs text-muted-foreground"
              onClick={handleDismiss}
            >
              Not now
            </Button>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
          aria-label="Dismiss"
        >
          <X size={13} />
        </button>
      </div>
    </div>
  );
}
