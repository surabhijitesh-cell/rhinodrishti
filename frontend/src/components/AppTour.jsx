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
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

// A step may carry `roles: [...]`; only people with one of those roles see it.
// Steps without `roles` are shown to everyone.
const ANALYST_UP = ["admin", "analyst"];
const ADMIN_ONLY = ["admin"];

// ─── Step definitions per route ──────────────────────────────────────────────

const PAGE_STEPS = {
  "/": [
    {
      target: "[data-tour='dashboard-title']",
      title: "Intelligence Overview",
      content: "Your starting page. It brings together everything the platform collects for the North East Region: news sites, YouTube, Telegram, Facebook, Instagram and X (collected through Apify), and other web sources.",
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
      content: "Collects fresh items from all sources right now, instead of waiting for the automatic schedule. Only analysts and admins see this button.",
      placement: "left",
      roles: ANALYST_UP,
    },
    {
      target: "[data-tour='source-scanners']",
      title: "Source Panel",
      content: "Shows each source: when it last ran and how many items it brought in. Click a card to see the sites, channels or accounts being watched. Analysts and admins also get a button to refresh a single source.",
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
      title: "Menu",
      content: "The menu has four groups: Daily work, Analysis, Briefs and reports, and Tools and admin. Settings and API & Pipeline Monitor appear only for admins. The red badge on Alerts counts alerts nobody has handled yet.",
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
      content: "Every item the platform has collected and sorted. Use the filters and the search box at the top to narrow by severity, threat type, state or date. Each card shows the headline, source, severity and state. Analysts and admins can rate a card with thumbs up or down to help the platform learn.",
      placement: "bottom",
    },
  ],

  "/cross-border": [
    {
      target: "[data-tour='cross-border-title']",
      title: "Cross-Border Watch",
      content: "Items about activity across the border with Bangladesh, Myanmar and China, grouped by country and entry route.",
      placement: "bottom",
    },
  ],

  "/daily-brief": [
    {
      target: "[data-tour='brief-title']",
      title: "Periodic Briefs",
      content: "Your briefs live here. The tabs are Daily, Fortnightly and Monthly, plus Past briefs for earlier ones. The Daily brief is written each morning from what was collected overnight.",
      placement: "bottom",
    },
    {
      target: "[data-testid='brief-tabs']",
      title: "Brief Tabs",
      content: "Switch between Daily, Fortnightly and Monthly briefs. Open Past briefs to find and download any earlier brief.",
      placement: "bottom",
    },
    {
      target: "[data-testid='brief-date']",
      title: "Date Picker",
      content: "Pick a date to see the Daily brief for that day.",
      placement: "bottom",
    },
    {
      target: "[data-tour='brief-generate']",
      title: "Generate Brief",
      content: "Writes a fresh brief now, using everything collected since the last one. Handy after a major incident. Only analysts and admins see this button.",
      placement: "left",
      roles: ANALYST_UP,
    },
    {
      target: "[data-tour='brief-export']",
      title: "Download PDF",
      content: "Downloads the brief as a PDF you can print or send on.",
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
      target: "[data-testid='knowledge-graph-page']",
      title: "Knowledge Graph",
      content: "A web of the people, groups, places and events that appear in the reports, with lines showing how they are connected.",
      placement: "bottom",
    },
  ],

  "/alerts": [
    {
      target: "[data-tour='feed-title']",
      title: "Alerts View",
      content: "Only the most serious items (Critical and High). Mark an alert as handled once you have reviewed it, and it drops out of the count on the menu.",
      placement: "bottom",
    },
  ],

  "/keywords": [
    {
      target: "[data-testid='keyword-engine-page']",
      title: "Keyword Engine",
      content: "Keep lists of words you care about. Items that mention them get extra attention.",
      placement: "bottom",
    },
  ],

  "/training": [
    {
      target: "[data-tour='training-title']",
      title: "Training & Feedback",
      content: "See how analyst ratings and corrections are helping the platform sort items better over time.",
      placement: "bottom",
    },
  ],

  "/upload": [
    {
      target: "[data-testid='document-analysis-page']",
      title: "Manual Int Uploads",
      content: "Add your own documents (PDF, Word, images). The platform reads them, sorts them and adds them to your feed.",
      placement: "bottom",
    },
  ],

  "/settings": [
    {
      target: "[data-tour='settings-title']",
      title: "Platform Settings",
      content: "For admins only. Analysts and viewers do not see Settings in their menu. This is where sources and data settings are managed.",
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
      title: "News Sites",
      content: "Add or remove news websites the platform reads. Your additions are collected on the same schedule as the built-in ones.",
      placement: "bottom",
    },
    {
      target: "[data-tour='retention-card']",
      title: "Data Retention Window",
      content: "How many days of items show in the feed and counts. Older items are kept but hidden. Raise it for history, lower it for a sharper focus on recent events.",
      placement: "top",
    },
    {
      target: "[data-tour='bias-card']",
      title: "Feedback Bias Configuration",
      content: "How strongly analyst ratings shape the platform's sorting. Light means the platform mostly decides on its own; High means analyst ratings count for a lot.",
      placement: "top",
    },
    {
      target: "[data-tour='source-effectiveness']",
      title: "Source Effectiveness",
      content: "Shows which social and web sources (YouTube, Telegram, Facebook, Instagram, X and others) are giving useful items, and how many are Critical or High.",
      placement: "top",
    },
  ],

  "/reports": [
    {
      target: "[data-testid='reports-page']",
      title: "Reports",
      content: "Create and download reports as PDF: by state, by country, or a custom one using your own dates and filters.",
      placement: "bottom",
    },
  ],

  "/faultlines": [
    {
      target: "[data-testid^='faultline-card-']",
      title: "Faultlines",
      content: "Each card is a long-running tension in the region with its current level. The card also shows when it was last scored. Click a card for its articles and history.",
      placement: "bottom",
    },
    {
      target: "[data-testid='run-daily-btn']",
      title: "Run Scoring Now",
      content: "Updates every faultline's score right away instead of waiting for the daily run. Only analysts and admins see this button.",
      placement: "bottom",
      roles: ANALYST_UP,
    },
  ],

  "/admin": [
    {
      target: "[data-testid='source-health-panel']",
      title: "Source Health",
      content: "Shows whether each source is working and when it last brought in items. Check here first if a source looks quiet. Admin only.",
      placement: "bottom",
      roles: ADMIN_ONLY,
    },
    {
      target: "[data-testid='model-trial-panel']",
      title: "Model Trial",
      content: "Try the platform's sorting on a small sample to compare how it performs. Admin only.",
      placement: "top",
      roles: ADMIN_ONLY,
    },
  ],

  "/user-management": [
    {
      target: "[data-testid='user-management-page']",
      title: "User Management",
      content: "For admins only. Create and manage accounts. Admin has full access, Analyst can read and rate items and run updates, Viewer can only read. Accounts can be switched off without deleting them.",
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

  const { user } = useAuth();

  // Hide steps the person's role cannot see, and drop our own `roles` field.
  const steps = (PAGE_STEPS[location.pathname] || [])
    .filter((s) => !s.roles || s.roles.includes(user?.role))
    // Skip steps whose target is not on screen (e.g. no brief yet), so the tour never stalls.
    .filter((s) => s.target === "body" || (running && document.querySelector(s.target)))
    .map(({ roles, ...step }) => step);

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
