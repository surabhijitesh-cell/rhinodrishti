import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import axios from "axios";
import { toast } from "sonner";
import { Flag, X, Send, Users } from "lucide-react";
import { Button } from "./ui/button";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function FlagArticleModal({ item, api, onClose, onFlagged }) {
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState([]);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("rd_token");
    axios
      .get(`${BACKEND_URL}/api/users/active`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => {
        let currentUsername = null;
        try {
          const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          currentUsername = payload.sub;
        } catch (_) {}
        setUsers(
          (res.data.users || []).filter(
            (u) => !currentUsername || u.username !== currentUsername
          )
        );
      })
      .catch(() => toast.error("Could not load users"))
      .finally(() => setLoadingUsers(false));
  }, []);

  const toggleUser = (userId) => {
    setSelected((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : prev.length < 10
        ? [...prev, userId]
        : prev
    );
  };

  const handleSubmit = async () => {
    if (selected.length === 0) {
      toast.error("Select at least one recipient");
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem("rd_token");
      await axios.post(
        `${BACKEND_URL}/api/flags`,
        {
          article_id: item.id,
          article_title: item.title || "",
          flagged_for_user_ids: selected,
          message: note.trim() || undefined,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Flagged for ${selected.length} recipient${selected.length > 1 ? "s" : ""}`);
      onFlagged?.();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Flag failed");
    }
    setSubmitting(false);
  };

  const modal = (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      data-testid="flag-modal"
    >
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card border border-border w-full max-w-md rounded shadow-xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Flag size={14} className="text-violet-400" />
            <span className="text-sm font-semibold">Flag for analyst</span>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>

        {/* Article title preview */}
        <div className="px-4 py-2 border-b border-border bg-muted/20">
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-0.5">Item</p>
          <p className="text-sm line-clamp-2">{item.title}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Recipients */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Users size={12} className="text-muted-foreground" />
              <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono">
                Recipients ({selected.length}/10)
              </p>
            </div>

            {loadingUsers ? (
              <p className="text-xs text-muted-foreground">Loading users…</p>
            ) : users.length === 0 ? (
              <p className="text-xs text-muted-foreground">No other users found</p>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {users.map((u) => {
                  const isSelected = selected.includes(u.id || u._id);
                  const userId = u.id || u._id;
                  return (
                    <button
                      key={userId}
                      onClick={() => toggleUser(userId)}
                      className={`w-full text-left flex items-center gap-3 px-3 py-2 border rounded-sm transition-colors text-sm ${
                        isSelected
                          ? "border-violet-500/60 bg-violet-500/10 text-violet-200"
                          : "border-border hover:border-border/80 hover:bg-muted/20 text-foreground"
                      }`}
                    >
                      <div className={`w-4 h-4 border rounded-sm flex items-center justify-center shrink-0 ${
                        isSelected ? "border-violet-400 bg-violet-500" : "border-border"
                      }`}>
                        {isSelected && <span className="text-white text-[10px]">✓</span>}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold truncate">{u.name || u.username}</p>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{u.role}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Optional note */}
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground font-mono mb-1.5">
              Note (optional)
            </p>
            <textarea
              className="w-full p-2 text-sm bg-background border border-border rounded-sm resize-none focus:outline-none focus:border-violet-400 text-foreground font-mono"
              rows={3}
              placeholder="Add context for the recipients…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={500}
            />
            <p className="text-[10px] text-muted-foreground/60 font-mono text-right">{note.length}/500</p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-border flex items-center justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-sm">
            Cancel
          </Button>
          <Button
            size="sm"
            className="text-sm bg-violet-600 hover:bg-violet-500 text-white"
            onClick={handleSubmit}
            disabled={submitting || selected.length === 0}
            data-testid="flag-submit"
          >
            {submitting ? (
              "Sending…"
            ) : (
              <><Send size={13} className="mr-1" /> Flag ({selected.length})</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
