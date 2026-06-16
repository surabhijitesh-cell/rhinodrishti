import { useState } from "react";
import { Flag } from "lucide-react";
import Tip from "./Tip";
import { useAuth } from "../contexts/AuthContext";
import FlagArticleModal from "./FlagArticleModal";

export default function FlagButton({ item, api }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  const canFlag = user && (user.role === "analyst" || user.role === "admin");
  if (!canFlag) return null;

  return (
    <>
      <Tip text="Flag this item for another analyst" side="left">
        <button
          onClick={(e) => { e.stopPropagation(); setOpen(true); }}
          className="p-1 text-muted-foreground/40 hover:text-violet-400 transition-colors"
          data-testid={`flag-btn-${item.id}`}
        >
          <Flag size={12} />
        </button>
      </Tip>

      {open && (
        <FlagArticleModal
          item={item}
          api={api}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
