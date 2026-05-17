/**
 * AppTour — Joyride v3 guided walkthrough for every page.
 *
 * Steps are keyed by route pathname.
 * Targets use data-tour="<name>" attributes placed on DOM elements.
 *
 * react-joyride v3 API notes (breaking changes from v2):
 *   - callback  → onEvent
 *   - styles.options.* → separate `options` prop
 *   - buttonNext → buttonPrimary in styles
 *   - showSkipButton → add "skip" to options.buttons
 *   - disableScrollParentFix → removed
 *   - skipBeacon defaults false; set true so tooltips appear without beacon click
 */
import { Joyride, ACTIONS, STATUS } from "react-joyride";
import { useLocation } from "react-router-dom";
import { useTour } from "../contexts/TourContext";
import { toast } from "sonner";

// ─── Step definitions per route ──────────────────────────────────────────────

const PAGE_STEPS = {
  "/": [
    {
      target: "[data-tour='dashboard-title']",
      title: "Intelligence Overview",
      content: "Your central command hub. This dashboard aggregates real-time intelligence from all 6 source types — RSS, YouTube, Facebook, Telegram, X/Twitter and Firecrawl — and presents the operational picture for the North East Region.",
      placement: "bottom",
    },
    {
      target: "[data-tour='stat-total']",
      title: "Total Intelligence Items",
      content: "Total processed intelligence items within your retention window. Each item has been AI-classified for relevance, severity, threat category and geographic state.",
      placement: "bottom",
    },
    {
      target: "[data-tour='stat-critical']",
      title: "Critical Alerts",
      content: "Items the AI has scored at CRITICAL severity — immediate threats requiring urgent analyst attention. Click to filter the feed to critical items only.",
      placement: "bottom",
    },
    {
      target: "[data-tour='stat-high']",
      title: "High-Priority Items",
      content: "HIGH severity items — significant events that warrant priority review. Both CRITICAL and HIGH items appear in the Unacknowledged Alerts panel.",
      placement: "bottom",
    },
    {
      target: "[data-tour='fetch-intel-btn']",
      title: "Fetch Intel Button",
      content: "Triggers a full sweep of ALL 6 intelligence sources simultaneously — RSS feeds and all social/web sources fire in parallel. Use this for an immediate refresh outside the automatic schedule.",
      placement: "left",
    },
    {
      target: "[data-tour='source-scanners']",
      title: "Source Scanner Panel",
      content: "Live status for every intelligence source. Each card shows last-fetch time, item count, and a FETCH button for per-source manual triggers. Click a card to see the individual sites, channels or accounts being monitored. 'Scan Social Media' triggers all 5 non-RSS sources.",
      placement: "bottom",
    },
    {
      target: "[data-tour='ner-map']",
      title: "NER Situation Map",
      content: "Interactive map of North East India. States are colour-coded by alert density — darker red means more critical/high items. Click any state to filter the intelligence feed to that region.",
      placement: "right",
    },
    {
      target: "[data-tour='recent-intel']",
      title: "Recent Intelligence Feed",
      content: "The latest processed intelligence items. Each card shows title, source, AI-assigned severity, threat category, and state. Click any card for full details. Items are filtered to your retention window.",
      placement: "top",
    },
    {
      target: "[data-tour='sidebar-nav']",
      title: "Navigation Sidebar",
      content: "Access all platform modules here. The sidebar collapses to icons to save screen space. The red badge on Alerts shows unacknowledged critical/high items.",
      placement: "right",
    },
    {
      target: "[data-tour='custom-analytics']",
      title: "Custom Analytics Workspace",
      content: "Build your own intelligence view: pick widgets (heatmap, actor tracker, velocity, hotspots, etc.), filter by state / category / actor / severity / range, save Command Views (COIN, Cross-Border, Manipur Monitor…), and export any widget as PNG.",
      placement: "top",
    },
  ],

  "/feed": [
    {
      target: "[data-tour='feed-title']",
      title: "Intelligence Feed",
      content: "The complete, filterable list of all processed intelligence items. Use the filter controls to narrow by severity, threat category, region or date range.",
      placement: "bottom",
    },
    {
      target: "[data-tour='feed-filters']",
      title: "Filter Controls",
      content: "Filter items by Severity (critical/high/medium/low), Threat Category (insurgency, crime, political, etc.), and State/Region. Filters combine — select multiple to narrow results.",
      placement: "bottom",
    },
    {
      target: "[data-tour='feed-sort']",
      title: "Sort & Search",
      content: "Sort items by date, priority score or severity. The search bar performs semantic search — it understands meaning, not just keywords. Type a concept like 'border infiltration' to find related items.",
      placement: "bottom",
    },
    {
      target: "[data-tour='feed-items']",
      title: "Intelligence Cards",
      content: "Each card shows the AI-extracted title, source, severity badge, threat category, and affected state. The priority score (0-100) reflects AI confidence. Rate items with the thumbs up/down to train the AI.",
      placement: "top",
    },
  ],

  "/cross-border": [
    {
      target: "[data-tour='cross-border-title']",
      title: "Cross-Border Watch",
      content: "Dedicated view for intelligence items involving cross-border movement — from Bangladesh, Myanmar and China. The AI flags items with explicit cross-border indicators.",
      placement: "bottom",
    },
    {
      target: "[data-tour='cross-border-map']",
      title: "Cross-Border Map",
      content: "Visual representation of cross-border threat vectors. Items with identified countries of origin are mapped to their entry corridors into the NER.",
      placement: "right",
    },
  ],

  "/daily-brief": [
    {
      target: "[data-tour='brief-title']",
      title: "Daily Intelligence Brief",
      content: "Auto-generated intelligence summary compiled at 06:00 IST every day. The AI reads all overnight intelligence items and writes an executive summary for each threat category and region.",
      placement: "bottom",
    },
    {
      target: "[data-tour='brief-generate']",
      title: "Generate Brief",
      content: "Generate a fresh brief on-demand using all intelligence collected since the last brief. Useful after a major incident or when you need an immediate assessment.",
      placement: "left",
    },
    {
      target: "[data-tour='brief-export']",
      title: "Export Brief",
      content: "Download the current brief as a formatted PDF for distribution. The PDF includes the full text, key indicators and the date/time stamp.",
      placement: "left",
    },
  ],

  "/trends": [
    {
      target: "[data-tour='trends-title']",
      title: "Trends Intelligence Center",
      content: "Multi-timeframe operational analysis (7d / 30d / 90d / 1y). Severity evolution per state, intelligence velocity, cross-border correlation, and Strategic Stability Index ranking.",
      placement: "bottom",
    },
    {
      target: "[data-tour='trends-range']",
      title: "Timeframe Selector",
      content: "Switch between week / month / quarter / year views. Charts adapt automatically to data availability.",
      placement: "bottom",
    },
    {
      target: "[data-tour='trends-stability']",
      title: "Strategic Stability Index",
      content: "Composite 0-100 score per state. Lower = higher operational concern. Composed of severity load (40%), velocity (25%), actor spread (20%), and cross-border share (15%).",
      placement: "top",
    },
    {
      target: "[data-tour='trends-drilldown']",
      title: "State Drill-Down",
      content: "Click any state to highlight top critical/high severity locations, dominant actors, and category breakdown for that state.",
      placement: "top",
    },
  ],

  "/patterns": [
    {
      target: "[data-tour='patterns-title']",
      title: "Pattern Detection",
      content: "The AI automatically identifies recurring threat patterns across the intelligence corpus — e.g. 'Road blockades correlate with election periods in Manipur'. Each pattern has a risk level and supporting evidence.",
      placement: "bottom",
    },
  ],

  "/knowledge-graph": [
    {
      target: "[data-tour='kg-title']",
      title: "Knowledge Graph",
      content: "A network visualisation of entities and their relationships extracted from intelligence items. Nodes are actors, locations, events or organisations. Edges represent documented relationships.",
      placement: "bottom",
    },
  ],

  "/alerts": [
    {
      target: "[data-tour='feed-title']",
      title: "Alerts View",
      content: "Filtered view of CRITICAL and HIGH severity items only. Use the ACK button on each item to acknowledge you have reviewed it — this removes it from the unacknowledged count in the sidebar.",
      placement: "bottom",
    },
  ],

  "/keywords": [
    {
      target: "[data-tour='keywords-title']",
      title: "Keyword Engine",
      content: "Define custom keyword groups. When intelligence items containing these keywords arrive, the AI applies additional attention and can trigger priority escalation.",
      placement: "bottom",
    },
  ],

  "/training": [
    {
      target: "[data-tour='training-title']",
      title: "Training & Feedback",
      content: "Review how analyst ratings are influencing the AI classification pipeline. High feedback influence means analyst corrections are strongly shaping future classifications.",
      placement: "bottom",
    },
  ],

  "/upload": [
    {
      target: "[data-tour='upload-title']",
      title: "Manual Intelligence Upload",
      content: "Upload intelligence documents (PDF, DOCX, images) directly into the platform. The AI extracts, classifies and integrates them into the intelligence feed automatically.",
      placement: "bottom",
    },
  ],

  "/settings": [
    {
      target: "[data-tour='settings-title']",
      title: "Platform Settings",
      content: "Administrator-only control panel for configuring the intelligence platform.",
      placement: "bottom",
    },
    {
      target: "[data-tour='local-db-card']",
      title: "Database Storage",
      content: "Shows whether the platform is storing data on MongoDB Atlas (cloud) or your local 1TB hard disk. Use the installer wizard to migrate to local storage for data sovereignty.",
      placement: "bottom",
    },
    {
      target: "[data-tour='rss-manager']",
      title: "RSS Feed Management",
      content: "Add or remove RSS news sources. The platform ships with 89 built-in NER intelligence feeds. Custom feeds are scanned on the same schedule as built-in feeds.",
      placement: "bottom",
    },
    {
      target: "[data-tour='retention-card']",
      title: "Data Retention Window",
      content: "Controls how many days of intelligence are visible in the feed and stats. Older items stay in the database but are hidden. Increase for historical analysis, decrease for a sharper operational focus.",
      placement: "top",
    },
    {
      target: "[data-tour='bias-card']",
      title: "Feedback Bias Configuration",
      content: "Controls how strongly analyst ratings influence the AI pipeline. 'Light' means AI judgment dominates; 'High' means analyst consensus strongly shapes future classifications. Use 'Rolling 30 Days' to keep the AI current.",
      placement: "top",
    },
    {
      target: "[data-tour='source-effectiveness']",
      title: "Source Effectiveness",
      content: "Shows which non-RSS sources are producing actionable intelligence. Each row shows item count, severity distribution bar, AI processing rate, and the latest catch. High-value = Critical + High items combined.",
      placement: "top",
    },
  ],

  "/reports": [
    {
      target: "[data-tour='reports-title']",
      title: "Reports",
      content: "Generate and download formatted intelligence reports. Reports can be time-bounded, filtered by region or threat category, and exported as PDF.",
      placement: "bottom",
    },
  ],

  "/user-management": [
    {
      target: "[data-tour='users-title']",
      title: "User Management",
      content: "Admin-only. Create and manage analyst accounts. Roles: Admin (full access + settings), Analyst (read/write intel, rate items), Viewer (read-only). Deactivate accounts without deleting them.",
      placement: "bottom",
    },
  ],
};

// ─── react-joyride v3: options separate from styles ──────────────────────────
// primaryColor / backgroundColor / textColor / overlayColor / zIndex / width
// must be in the `options` prop.  styles only handles visual overrides.

const TOUR_OPTIONS = {
  // Skip the beacon entirely for every step — without this, the first
  // step shows a beacon that must be clicked before the tooltip appears.
  // Since we hide beacons via CSS the tour looked like it never started.
  skipBeacon: true,
  // Show Back, Skip, and Next/Done buttons
  buttons: ["back", "skip", "close", "primary"],
  // Theme colours pulled from CSS custom properties
  primaryColor: "hsl(var(--primary))",
  backgroundColor: "hsl(var(--card))",
  textColor: "hsl(var(--foreground))",
  overlayColor: "rgba(0,0,0,0.65)",
  arrowColor: "hsl(var(--card))",
  width: 360,
  zIndex: 10000,
  spotlightPadding: 6,
};

const TOUR_STYLES = {
  tooltip: {
    borderRadius: 0,
    border: "1px solid hsl(var(--border))",
    borderLeft: "3px solid hsl(var(--primary))",
    fontFamily: "'Barlow Condensed', sans-serif",
    padding: "16px 18px",
  },
  tooltipTitle: {
    fontSize: "14px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    marginBottom: "8px",
    color: "hsl(var(--primary))",
  },
  tooltipContent: {
    fontSize: "12px",
    lineHeight: "1.6",
    fontFamily: "ui-monospace, monospace",
    color: "hsl(var(--muted-foreground))",
    padding: "0",
  },
  // In v3 the "Next / Done" button is `buttonPrimary` (was `buttonNext` in v2)
  buttonPrimary: {
    borderRadius: 0,
    backgroundColor: "hsl(var(--primary))",
    color: "hsl(var(--primary-foreground))",
    fontSize: "10px",
    fontFamily: "ui-monospace, monospace",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    padding: "6px 14px",
    border: "none",
  },
  buttonBack: {
    borderRadius: 0,
    color: "hsl(var(--muted-foreground))",
    fontSize: "10px",
    fontFamily: "ui-monospace, monospace",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    marginRight: "8px",
    background: "transparent",
    border: "1px solid hsl(var(--border))",
    padding: "6px 12px",
  },
  buttonSkip: {
    borderRadius: 0,
    color: "hsl(var(--muted-foreground))",
    fontSize: "10px",
    fontFamily: "ui-monospace, monospace",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    background: "transparent",
    padding: "4px 6px",
  },
  buttonClose: {
    color: "hsl(var(--muted-foreground))",
    fontSize: "14px",
    padding: "4px 8px",
    top: 8,
    right: 8,
  },
  spotlight: {
    borderRadius: 0,
  },
  beacon: {
    display: "none", // safety net — skipBeacon:true already prevents beacon rendering
  },
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function AppTour() {
  const location = useLocation();
  const { running, skipTour, finishTour, joyKey } = useTour();

  const steps = PAGE_STEPS[location.pathname] || [];

  const handleEvent = ({ status, action }) => {
    if (status === STATUS.SKIPPED) {
      skipTour();
      toast("Tour skipped. Click the ? button anytime to restart.", {
        duration: 8000,
      });
      return;
    }
    if (status === STATUS.FINISHED || action === ACTIONS.CLOSE) {
      finishTour();
      if (status === STATUS.FINISHED) {
        toast.success("Walkthrough complete. Click ? anytime to replay.");
      }
    }
  };

  // Only mount Joyride when the tour is actively running AND this route has
  // steps.  Conditional mounting guarantees every mount is a brand-new
  // Joyride instance that starts at step 0 with clean internal state.
  // key={joyKey} handles the edge-case where startTour() fires while the
  // tour is already running — the key change forces a full remount.
  if (!running || steps.length === 0) return null;

  return (
    <Joyride
      key={joyKey}
      steps={steps}
      run={true}
      continuous
      showProgress
      options={TOUR_OPTIONS}
      styles={TOUR_STYLES}
      locale={{
        back: "← Back",
        close: "✕",
        last: "Done ✓",
        next: "Next →",
        skip: "Skip Tour",
      }}
      onEvent={handleEvent}
    />
  );
}
