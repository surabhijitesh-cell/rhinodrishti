import { Component } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

/** Keeps one broken page from blanking the whole app; the menu stays usable. */
export default class PageErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="flex flex-col items-start gap-3 p-4 border border-amber-500/40 bg-amber-500/5 text-amber-400" role="alert" data-testid="page-error">
        <div className="flex items-center gap-2 text-sm"><AlertTriangle size={16} /> This page hit a problem and could not be shown.</div>
        <p className="text-xs text-muted-foreground">Other pages still work from the menu. If this keeps happening, tell your administrator which page it was.</p>
        <button onClick={() => window.location.reload()} className="inline-flex items-center gap-1 text-xs border border-amber-500/40 px-2 py-1 hover:bg-amber-500/10">
          <RotateCcw size={12} /> Reload page
        </button>
      </div>
    );
  }
}
