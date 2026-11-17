import { AlertTriangle, RefreshCw } from "lucide-react";

/**
 * Shown in place of a panel's numbers or list when the server could not be
 * reached, so a failure never reads as zeros or "all quiet".
 */
export default function LoadError({ what = "this", onRetry, className = "" }) {
  return (
    <div
      className={`flex items-center gap-3 p-3 border border-amber-500/40 bg-amber-500/5 text-amber-400 ${className}`}
      role="alert"
      data-testid="load-error"
    >
      <AlertTriangle size={14} className="shrink-0" />
      <span className="text-xs">Couldn't load {what}. The numbers here are not zero, they are unknown.</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="ml-auto inline-flex items-center gap-1 text-[10px] font-mono uppercase border border-amber-500/40 px-2 py-1 hover:bg-amber-500/10"
          data-testid="load-error-retry"
        >
          <RefreshCw size={10} /> Retry
        </button>
      )}
    </div>
  );
}
