import { useRef, useState } from "react";
import { Download, EyeOff, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import Tip from "../Tip";
import { exportWidgetAsPNG } from "../../lib/widgetExport";

/**
 * Reusable wrapper for custom-analytics widgets.
 * Provides: title, tooltip, PNG export, hide button.
 */
export default function WidgetCard({
  title, tip, icon: Icon, onHide, children, loading, error, testId,
}) {
  const containerRef = useRef(null);
  const [exportErr, setExportErr] = useState(null);

  const handleExport = async () => {
    setExportErr(null);
    try {
      const safe = title.replace(/[^a-z0-9_-]/gi, "_").toLowerCase();
      await exportWidgetAsPNG(containerRef.current,
        `rhinodrishti_${safe}_${new Date().toISOString().slice(0,10)}.png`);
    } catch (e) {
      setExportErr(e.message || "Export failed");
      setTimeout(() => setExportErr(null), 3000);
    }
  };

  return (
    <Card className="border border-border rounded-none bg-card" data-testid={testId}>
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <Tip text={tip || ""} side="top">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
            {Icon && <Icon size={16} className="text-primary" />}
            {title}
          </CardTitle>
        </Tip>
        <div className="flex items-center gap-1">
          <button
            onClick={handleExport}
            title="Export as PNG"
            className="p-1 text-muted-foreground hover:text-primary transition-colors"
            data-testid="widget-export-btn"
          >
            <Download size={13} />
          </button>
          {onHide && (
            <button
              onClick={onHide}
              title="Hide widget"
              className="p-1 text-muted-foreground hover:text-red-400 transition-colors"
              data-testid="widget-hide-btn"
            >
              <EyeOff size={13} />
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-4" ref={containerRef}>
        {loading ? (
          <div className="h-[260px] flex items-center justify-center text-muted-foreground text-xs font-mono">
            Loading…
          </div>
        ) : error ? (
          <div className="h-[260px] flex items-center justify-center text-red-400 text-xs gap-2 font-mono">
            <AlertCircle size={14} /> {error}
          </div>
        ) : children}
        {exportErr && (
          <div className="mt-2 text-[10px] font-mono text-amber-400">{exportErr}</div>
        )}
      </CardContent>
    </Card>
  );
}
