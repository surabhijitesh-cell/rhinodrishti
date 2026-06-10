import { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { Star, TrendingUp, TrendingDown, Minus } from "lucide-react";

const LEVEL_COLOR = {
  CRITICAL: "#ef4444",
  ELEVATED: "#f59e0b",
  MONITOR:  "#eab308",
  STABLE:   "#a3e635",
};

function Delta({ delta }) {
  if (delta == null) return <Minus size={10} className="text-muted-foreground" />;
  if (delta > 2) return <TrendingUp size={10} className="text-red-400" />;
  if (delta < -2) return <TrendingDown size={10} className="text-green-400" />;
  return <Minus size={10} className="text-muted-foreground" />;
}

export default function WatchlistStrip({ api }) {
  const navigate = useNavigate();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${api}/watchlist/me`)
      .then((r) => { if (!cancelled) setEntries(r.data.entries || []); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api]);

  if (loading || entries.length === 0) return null;

  return (
    <div className="border border-border bg-background px-4 py-2">
      <div className="flex items-center gap-2 mb-1.5">
        <Star size={11} className="text-yellow-400 fill-yellow-400" />
        <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
          My Watchlist
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {entries.slice(0, 5).map((entry) => {
          const fl = entry.faultline || {};
          const score = fl.latest_score?.score ?? null;
          const level = fl.latest_score?.level || "STABLE";
          const color = LEVEL_COLOR[level] || "#a3e635";
          return (
            <button
              key={entry.faultline_id}
              onClick={() => navigate(`/faultlines/${entry.faultline_id}`)}
              className="shrink-0 border border-border bg-muted/30 px-3 py-2 text-left hover:bg-muted/60 transition-colors min-w-[140px]"
            >
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-[9px] font-mono text-yellow-400">#{entry.rank}</span>
                <span className="text-[9px] font-mono text-muted-foreground truncate">{fl.state}</span>
              </div>
              <p className="text-[11px] font-semibold leading-tight line-clamp-2 mb-1">{fl.name || entry.faultline_id}</p>
              <div className="flex items-center gap-1.5">
                {score != null && (
                  <span className="text-sm font-bold font-['Barlow_Condensed']" style={{ color }}>
                    {Math.round(score)}
                  </span>
                )}
                <span className="text-[9px] font-mono" style={{ color }}>{level}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
