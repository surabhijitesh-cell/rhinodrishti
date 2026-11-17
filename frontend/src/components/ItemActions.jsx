import { ExternalLink } from "lucide-react";
import FeedbackWidget from "./FeedbackWidget";
import { useAuth } from "../contexts/AuthContext";
import FlagButton from "./FlagButton";

/**
 * The three things an analyst can do with any item wherever it is read:
 * rate it, flag it, and open the original article. Mount it only when a row
 * is opened — the rating part loads the item's ratings on mount.
 */
export default function ItemActions({ item, api }) {
  const { user } = useAuth();
  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid={`item-actions-${item.id}`}>
      {user?.role !== "viewer" && (
        <div className="flex-1 min-w-[220px] [&>div]:border-0 [&>div]:pb-0 [&>div]:mb-0">
          <FeedbackWidget itemId={item.id} api={api} compact />
        </div>
      )}
      <FlagButton item={item} api={api} />
      {item.source_url && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-[10px] font-mono uppercase text-primary hover:underline"
          data-testid={`item-open-${item.id}`}
        >
          <ExternalLink size={11} /> Open source
        </a>
      )}
    </div>
  );
}
