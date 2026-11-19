import { useState, useEffect } from "react";
import { Flag } from "lucide-react";
import Tip from "./Tip";
import { useAuth } from "../contexts/AuthContext";
import FlagArticleModal from "./FlagArticleModal";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Module-level cache of the signed-in person's flagged ids. It belongs to one
// user: it is emptied on logout / 401 / login (the "rd-session-cleared" event)
// and whenever a different user asks for it.
const _flaggedIds = new Set();
let _fetchPromise = null;
let _cacheUserId = null;
let _generation = 0;

export function clearFlaggedCache() {
  _flaggedIds.clear();
  _fetchPromise = null;
  _cacheUserId = null;
  _generation += 1; // makes any answer still in flight get ignored
}

if (typeof window !== "undefined") {
  window.addEventListener("rd-session-cleared", clearFlaggedCache);
}

function fetchFlaggedIds(userId) {
  if (_cacheUserId !== userId) clearFlaggedCache();
  if (_fetchPromise) return _fetchPromise;
  const token = localStorage.getItem("rd_token");
  if (!token) return Promise.resolve();
  _cacheUserId = userId;
  const gen = _generation;
  _fetchPromise = fetch(`${BACKEND_URL}/api/flags/sent-article-ids`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((r) => r.json())
    .then((data) => {
      if (gen !== _generation) return; // user changed meanwhile
      (data.article_ids || []).forEach((id) => _flaggedIds.add(id));
    })
    .catch(() => { if (gen === _generation) _fetchPromise = null; });
  return _fetchPromise;
}

export default function FlagButton({ item, api }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const userId = user?.id || user?.username || null;
  const [flagged, setFlagged] = useState(() => _cacheUserId === userId && _flaggedIds.has(item.id));

  const canFlag = user && (user.role === "analyst" || user.role === "admin");

  useEffect(() => {
    setFlagged(false);
    if (!canFlag) return;
    fetchFlaggedIds(userId).then(() => {
      if (_cacheUserId === userId && _flaggedIds.has(item.id)) setFlagged(true);
    });
  }, [canFlag, item.id, userId]);

  if (!canFlag) return null;

  const handleFlagged = () => {
    if (_cacheUserId === userId) _flaggedIds.add(item.id);
    setFlagged(true);
  };

  return (
    <>
      <Tip text={flagged ? "Already flagged for an analyst" : "Flag this item for another analyst"} side="left">
        <button
          onClick={(e) => { e.stopPropagation(); setOpen(true); }}
          className={`p-1 transition-colors ${flagged ? "text-red-500" : "text-muted-foreground/40 hover:text-violet-400"}`}
          data-testid={`flag-btn-${item.id}`}
        >
          <Flag size={12} fill={flagged ? "currentColor" : "none"} />
        </button>
      </Tip>

      {open && (
        <FlagArticleModal
          item={item}
          api={api}
          onFlagged={handleFlagged}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
