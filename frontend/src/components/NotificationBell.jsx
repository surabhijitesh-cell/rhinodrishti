import { useState } from "react";
import { Bell } from "lucide-react";
import { Button } from "./ui/button";
import Tip from "./Tip";
import NotificationPanel from "./NotificationPanel";

export default function NotificationBell({ unreadCount, onResetUnread }) {
  const [open, setOpen] = useState(false);

  const handleOpen = () => {
    setOpen(true);
    if (onResetUnread) onResetUnread();
  };

  return (
    <>
      <Tip text={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"} side="bottom">
        <Button
          variant="ghost"
          size="sm"
          className="relative"
          onClick={handleOpen}
          data-testid="notification-bell"
        >
          <Bell size={18} />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-violet-500 text-white text-[10px] rounded-full flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </Tip>

      {open && <NotificationPanel onClose={() => setOpen(false)} />}
    </>
  );
}
