/**
 * Tip — lightweight tooltip wrapper (auto-dismisses after `duration` ms)
 *
 * Usage:
 *   <Tip text="Refresh the data feed">
 *     <Button>...</Button>
 *   </Tip>
 *
 * Props:
 *   text      — tooltip string (required)
 *   side      — "top" | "bottom" | "left" | "right"  (default "top")
 *   duration  — ms before auto-close even if cursor stays (default 3000)
 *   disabled  — suppress the tooltip
 */
import { useRef, useState } from "react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "./ui/tooltip";

export default function Tip({ text, children, side = "top", duration = 3000, disabled = false }) {
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  if (disabled || !text) return children;

  const show = () => {
    setOpen(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(false), duration);
  };

  const hide = () => {
    setOpen(false);
    clearTimeout(timer.current);
  };

  return (
    <Tooltip open={open} delayDuration={200}>
      <TooltipTrigger
        asChild
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={hide}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent
        side={side}
        className="max-w-[220px] text-center text-[11px] leading-snug font-mono px-2.5 py-1.5 rounded-none border border-primary/30 bg-card text-foreground shadow-lg z-[9999]"
      >
        {text}
      </TooltipContent>
    </Tooltip>
  );
}
