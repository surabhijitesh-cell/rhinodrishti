import { useState, useEffect, useCallback } from "react";
import { Star, Lock, Check, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import axios from "axios";

const RATING_LABELS = {
  1: "Entirely Irrelevant",
  2: "Mostly Irrelevant",
  3: "Slightly Relevant",
  4: "Moderately Relevant",
  5: "Highly Relevant",
  6: "Extremely Relevant",
};

const RATING_COLORS = {
  1: "text-red-500",
  2: "text-orange-500",
  3: "text-yellow-500",
  4: "text-blue-400",
  5: "text-emerald-400",
  6: "text-primary",
};

function getDeviceId() {
  const KEY = "rhino_drishti_device_id";
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = "dev_" + crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}

export default function FeedbackWidget({ itemId, api, compact = false, initialData }) {
  const [rating, setRating] = useState(null);
  const [hover, setHover] = useState(0);
  const [total, setTotal] = useState(0);
  const [avg, setAvg] = useState(0);
  const [maxLimit, setMaxLimit] = useState(20);
  const [limitReached, setLimitReached] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const deviceId = getDeviceId();

  const loadData = useCallback((data) => {
    if (!data) return;
    setTotal(data.total_ratings || 0);
    setAvg(data.avg_rating || 0);
    setMaxLimit(data.max_limit || 20);
    setLimitReached(data.limit_reached || false);
    if (data.user_rating) setRating(data.user_rating);
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (initialData) {
      loadData(initialData);
      return;
    }
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${api}/feedback/${itemId}?device_id=${deviceId}`);
        loadData(res.data);
      } catch {
        setLoaded(true);
      }
    };
    fetchStatus();
  }, [itemId, api, deviceId, initialData, loadData]);

  const submitRating = async (value) => {
    if (limitReached && !rating) return;
    setSubmitting(true);
    try {
      const res = await axios.post(`${api}/feedback`, {
        intelligence_id: itemId,
        device_id: deviceId,
        rating: value,
      });
      setRating(value);
      if (res.data.action === "created") {
        setTotal((p) => p + 1);
      }
      // Recalculate avg roughly
      const newTotal = res.data.action === "created" ? total + 1 : total;
      if (newTotal > 0) {
        const oldSum = avg * total;
        const newSum = res.data.action === "created"
          ? oldSum + value
          : oldSum - (rating || 0) + value;
        setAvg(Math.round((newSum / newTotal) * 100) / 100);
      }
      toast.success(res.data.action === "updated" ? "Rating updated" : "Rating submitted");
    } catch (e) {
      const msg = e.response?.data?.detail || "Failed to submit rating";
      toast.error(msg);
    }
    setSubmitting(false);
  };

  if (!loaded) return null;

  const isLocked = limitReached && !rating;

  return (
    <div
      className={compact ? "flex items-center justify-between gap-2 border-b border-border pb-2 mb-2" : "border-t border-border pt-3 mt-3"}
      data-testid={`feedback-widget-${itemId}`}
    >
      {/* Label + Stats */}
      <div className={compact ? "flex items-center gap-2" : "flex items-center justify-between mb-2"}>
        <span className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono font-semibold whitespace-nowrap">
          {compact ? "Rate" : "Relevance (Alpha Feedback)"}
        </span>
        {!compact && (
          <div className="flex items-center gap-2">
            {avg > 0 && (
              <span className="text-xs font-mono text-amber-400" data-testid={`feedback-avg-${itemId}`}>
                {avg.toFixed(1)}
              </span>
            )}
            <span
              className={`text-[10px] font-mono ${limitReached ? "text-red-400" : "text-muted-foreground"}`}
              data-testid={`feedback-count-${itemId}`}
            >
              {total}/{maxLimit}
            </span>
            {isLocked && <Lock size={10} className="text-red-400" />}
          </div>
        )}
      </div>

      {/* Stars Row + Hover Label */}
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5, 6].map((val) => {
          const isActive = rating === val;
          const isHovered = hover >= val;
          const filled = isActive || (hover > 0 && isHovered);
          return (
            <button
              key={val}
              disabled={isLocked || submitting}
              onMouseEnter={() => !isLocked && setHover(val)}
              onMouseLeave={() => setHover(0)}
              onClick={() => submitRating(val)}
              className={`
                group relative p-0.5 transition-all duration-150
                ${isLocked ? "opacity-30 cursor-not-allowed" : "cursor-pointer hover:scale-110"}
                ${isActive ? "scale-110" : ""}
              `}
              data-testid={`feedback-star-${itemId}-${val}`}
              title={RATING_LABELS[val]}
            >
              <Star
                size={compact ? 13 : 16}
                className={`transition-colors duration-150 ${
                  filled ? RATING_COLORS[val] || "text-primary" : "text-muted-foreground/30"
                }`}
                fill={filled ? "currentColor" : "none"}
              />
              {isActive && (
                <Check size={7} className="absolute -top-0.5 -right-0.5 text-primary" />
              )}
            </button>
          );
        })}
        {submitting && <Loader2 size={10} className="animate-spin text-muted-foreground ml-1" />}
        {/* Hover relevance label — always visible */}
        {hover > 0 && !isLocked && (
          <span className={`text-[10px] font-mono ml-1.5 whitespace-nowrap ${RATING_COLORS[hover]}`}>
            {RATING_LABELS[hover]}
          </span>
        )}
        {hover === 0 && rating && compact && (
          <span className={`text-[10px] font-mono ml-1.5 whitespace-nowrap ${RATING_COLORS[rating]}`}>
            {RATING_LABELS[rating]}
          </span>
        )}
      </div>

      {/* Compact inline stats */}
      {compact && (
        <div className="flex items-center gap-2 shrink-0">
          {avg > 0 && (
            <span className="text-[10px] font-mono text-amber-400" data-testid={`feedback-avg-${itemId}`}>
              {avg.toFixed(1)}
            </span>
          )}
          <span
            className={`text-[10px] font-mono ${limitReached ? "text-red-400" : "text-muted-foreground"}`}
            data-testid={`feedback-count-${itemId}`}
          >
            {total}/{maxLimit}
          </span>
          {isLocked && <Lock size={10} className="text-red-400" />}
        </div>
      )}

      {!compact && hover > 0 && !isLocked && (
        <p className={`text-[10px] font-mono mt-1 ${RATING_COLORS[hover]}`}>
          {hover}: {RATING_LABELS[hover]}
        </p>
      )}

      {!compact && rating && hover === 0 && (
        <p className={`text-[10px] font-mono mt-1 ${RATING_COLORS[rating]}`}>
          Your rating: {rating} - {RATING_LABELS[rating]}
        </p>
      )}

      {!compact && isLocked && (
        <p className="text-[10px] text-red-400 font-mono mt-1">
          Maximum feedback limit reached for this item
        </p>
      )}
    </div>
  );
}
