import { useState, useEffect } from "react";
import { Flag } from "lucide-react";
import Tip from "./Tip";
import { useAuth } from "../contexts/AuthContext";
import FlagArticleModal from "./FlagArticleModal";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Module-level cache: survives re-mounts, reset on page load
const _flaggedIds = new Set();
let _fetchPromise = null;

function fetchFlaggedIds() {
  if (_fetchPromise) return _fetchPromise;
  const token = localStorage.getItem("rd_token");
  if (!token) return Promise.resolve();
  _fetchPromise = fetch(`${BACKEND_URL}/api/flags/sent-article-ids`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((r) => r.json())
    .then((data) => {
      (data.article_ids || []).forEach((id) => _flaggedIds.add(id));
    })
    .catch(() => {});
  return _fetchPromise;
}

export default function FlagButton({ item, api }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [flagged, setFlagged] = useState(() => _flaggedIds.has(item.id));

  const canFlag = user && (user.role === "analyst" || user.role === "admin");

  useEffect(() => {
    if (!canFlag) return;
    fetchFlaggedIds().then(() => {
      if (_flaggedIds.has(item.id)) setFlagged(true);
    });
  }, [canFlag, item.id]);

  if (!canFlag) return null;

  const handleFlagged = () => {
    _flaggedIds.add(item.id);
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
