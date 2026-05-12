import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "../contexts/AuthContext";
import {
  Shield, LayoutDashboard, Newspaper, FileText, TrendingUp,
  Globe, Bell, ChevronLeft, ChevronRight, Sun, Moon, Search,
  Activity, Menu, X, Upload, GitBranch, Settings, Network, Key, BookOpen, Brain,
  LogOut, Users, Megaphone, HelpCircle, RotateCcw
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import Tip from "./Tip";
import { useTour } from "../contexts/TourContext";

const ALL_NAV_ITEMS = [
  {
    path: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "analyst", "viewer"],
    tooltip: "Command centre — live intelligence stats, source scanner panel, NER map and latest items.",
  },
  {
    path: "/feed", label: "Intelligence Feed", icon: Newspaper, roles: ["admin", "analyst", "viewer"],
    tooltip: "Full searchable, filterable list of all AI-classified intelligence items. Rate, sort and export.",
  },
  {
    path: "/cross-border", label: "Cross-Border", icon: Globe, roles: ["admin", "analyst", "viewer"],
    tooltip: "Bangladesh & Myanmar intelligence grouped by Diplomatic, Defence, Internal Politics and Economics.",
  },
  {
    path: "/daily-brief", label: "Daily Brief", icon: FileText, roles: ["admin", "analyst", "viewer"],
    tooltip: "AI-generated daily intelligence summary compiled at 06:00 IST. Exportable as PDF.",
  },
  {
    path: "/weekly-trends", label: "Weekly Trends", icon: TrendingUp, roles: ["admin", "analyst", "viewer"],
    tooltip: "7-day severity trend charts, threat category breakdown and state-wise activity analysis.",
  },
  {
    path: "/patterns", label: "Patterns", icon: GitBranch, roles: ["admin", "analyst", "viewer"],
    tooltip: "Automatically detected recurring threat clusters with escalation risk levels (CRITICAL → LOW).",
  },
  {
    path: "/knowledge-graph", label: "Knowledge Graph", icon: Network, roles: ["admin", "analyst", "viewer"],
    tooltip: "Actor-location relationship network extracted from the entire intelligence corpus.",
  },
  {
    path: "/alerts", label: "Alerts", icon: Bell, roles: ["admin", "analyst", "viewer"],
    tooltip: "CRITICAL and HIGH severity items only. ACK button marks each alert as reviewed.",
  },
  {
    path: "/keywords", label: "Keyword Engine", icon: Key, roles: ["admin", "analyst", "viewer"],
    tooltip: "AI-managed keyword bank driving intelligence detection. Add keywords manually or via AI refresh.",
  },
  {
    path: "/training", label: "Training & Feedback", icon: Brain, roles: ["admin", "analyst", "viewer"],
    tooltip: "Rate articles 1-6 to shape AI priorities. Upload URLs/documents to the training pipeline.",
  },
  {
    path: "/upload", label: "Manual Int Uploads", icon: Upload, roles: ["admin", "analyst", "viewer"],
    tooltip: "Upload PDFs/DOCX, analyze article URLs with AI, or add items directly to the intelligence feed.",
  },
  {
    path: "/reports", label: "Reports", icon: FileText, roles: ["admin", "analyst", "viewer"],
    tooltip: "Generate and download PDF reports — Regional Threat Summary, Cross-Border SITREP or Custom.",
  },
  {
    path: "/user-management", label: "User Management", icon: Users, roles: ["admin"],
    tooltip: "Admin only — create, deactivate and reset passwords for Analyst and Viewer accounts.",
  },
  {
    path: "/admin", label: "API & Pipeline Monitor", icon: Activity, roles: ["admin"],
    tooltip: "Admin only — live API spend (Anthropic + Gemini + OpenAI) and filter cascade funnel stats.",
  },
  {
    path: "/settings", label: "Settings", icon: Settings, roles: ["admin"],
    tooltip: "Admin only — configure retention window, feedback bias, RSS feeds and local database setup.",
  },
  {
    path: "/updates", label: "Platform Updates", icon: Megaphone, roles: ["admin", "analyst", "viewer"],
    tooltip: "Full version history and update notifications. Admins can publish new update announcements.",
  },
  {
    path: "/handbook", label: "User Handbook", icon: BookOpen, roles: ["admin", "analyst", "viewer"],
    tooltip: "Complete user guide covering every feature, role permission and AI pipeline detail.",
  },
];

const NEW_BADGE_PATHS = ["/reports", "/updates"];
const NEW_BADGE_DISMISS_COUNT = 3;

function useNewBadge(path) {
  const key = `new_badge_${path}`;
  const [count, setCount] = useState(() => {
    try { return parseInt(localStorage.getItem(key) || "0", 10); } catch { return 0; }
  });
  const dismiss = () => {
    const next = count + 1;
    setCount(next);
    localStorage.setItem(key, String(next));
  };
  return { show: count < NEW_BADGE_DISMISS_COUNT, dismiss };
}

export default function Layout({ children, alertCount = 0, onSearch }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchVal, setSearchVal] = useState("");
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { startTour, resetTour } = useTour();

  const userRole = user?.role || "viewer";
  const navItems = ALL_NAV_ITEMS.filter((item) => item.roles.includes(userRole));

  const reportsBadge = useNewBadge("/reports");
  const updatesBadge = useNewBadge("/updates");
  const badgeMap = { "/reports": reportsBadge, "/updates": updatesBadge };

  const handleSearch = (e) => {
    e.preventDefault();
    if (onSearch) onSearch(searchVal);
  };

  const SidebarContent = () => (
    <nav className="flex flex-col gap-0 mt-2 px-2" data-testid="sidebar-nav" data-tour="sidebar-nav">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = location.pathname === item.path;
        const badge = badgeMap[item.path];
        return (
          <Tip key={item.path} text={item.tooltip || item.label} side="right">
          <Link
            to={item.path}
            data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            onClick={() => { setMobileOpen(false); if (badge) badge.dismiss(); }}
            className={`sidebar-nav-item ${isActive ? "active" : "text-muted-foreground"}`}
          >
            <Icon size={18} />
            {!collapsed && <span>{item.label}</span>}
            {badge?.show && !collapsed && (
              <span className="ml-auto text-[9px] font-bold uppercase tracking-wider text-emerald-400 animate-pulse" data-testid={`new-badge-${item.path.slice(1)}`}>
                New
              </span>
            )}
            {badge?.show && collapsed && (
              <span className="absolute top-0 right-0 w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            )}
            {item.path === "/alerts" && alertCount > 0 && !collapsed && !badge?.show && (
              <Badge className="ml-auto severity-critical text-[10px] rounded-none px-1.5" data-testid="alert-count-badge">
                {alertCount}
              </Badge>
            )}
          </Link>
          </Tip>
        );
      })}
    </nav>
  );

  return (
    <div className="flex h-screen overflow-hidden" data-testid="app-layout">
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col border-r border-border bg-card transition-all duration-100 ${collapsed ? "w-16" : "w-60"}`}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-3 py-4 border-b border-border">
          <Shield size={24} className="text-primary shrink-0" />
          {!collapsed && (
            <div>
              <h1 className="text-lg font-bold uppercase tracking-wider font-['Barlow_Condensed']" data-testid="app-title">
                Rhino Drishti
              </h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-mono">
                NER Intel Platform
              </p>
            </div>
          )}
        </div>

        <SidebarContent />

        {/* Collapse toggle */}
        <div className="mt-auto p-2 border-t border-border">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="w-full justify-center"
            data-testid="sidebar-toggle"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </Button>
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 bg-card border-r border-border z-10">
            <div className="flex items-center justify-between px-3 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Shield size={24} className="text-primary" />
                <h1 className="text-lg font-bold uppercase tracking-wider font-['Barlow_Condensed']">
                  Rhino Drishti
                </h1>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setMobileOpen(false)} data-testid="mobile-close">
                <X size={18} />
              </Button>
            </div>
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-border bg-card" data-testid="top-bar">
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden"
            onClick={() => setMobileOpen(true)}
            data-testid="mobile-menu-btn"
          >
            <Menu size={20} />
          </Button>

          <div className="flex items-center gap-2 text-muted-foreground">
            <Activity size={16} className="text-primary animate-pulse" />
            <span className="text-xs font-mono uppercase tracking-wider hidden sm:inline">Live Monitoring</span>
          </div>

          <form onSubmit={handleSearch} className="flex-1 max-w-md mx-auto" data-testid="search-form">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search intelligence..."
                value={searchVal}
                onChange={(e) => setSearchVal(e.target.value)}
                className="pl-9 bg-background/50 border-input rounded-none text-sm"
                data-testid="search-input"
              />
            </div>
          </form>

          <div className="flex items-center gap-2">
            <Tip text="Toggle dark / light theme" side="bottom">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleTheme}
                data-testid="theme-toggle"
                className="text-muted-foreground hover:text-foreground"
              >
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
            </Tip>

            <Tip text={alertCount > 0 ? `${alertCount} unacknowledged critical/high alerts` : "No active alerts"} side="bottom">
              <Link to="/alerts">
                <Button variant="ghost" size="sm" className="relative" data-testid="alerts-bell">
                  <Bell size={18} />
                  {alertCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
                      {alertCount > 9 ? "9+" : alertCount}
                    </span>
                  )}
                </Button>
              </Link>
            </Tip>

            {/* Tour button — visible to all users */}
            <Tip text="Start guided walkthrough for this page" side="bottom">
              <Button
                variant="ghost"
                size="sm"
                onClick={startTour}
                className="text-muted-foreground hover:text-primary"
                data-testid="tour-btn"
              >
                <HelpCircle size={16} />
              </Button>
            </Tip>

            {/* Reset all tours — admin only */}
            {user?.role === "admin" && (
              <Tip text="Reset all page tours (re-enables auto-walkthrough on every page)" side="bottom">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { resetTour(); startTour(); }}
                  className="text-muted-foreground hover:text-amber-400"
                  data-testid="reset-tour-btn"
                >
                  <RotateCcw size={14} />
                </Button>
              </Tip>
            )}

            {/* User info + Logout */}
            {user && (
              <div className="flex items-center gap-2 ml-1 pl-2 border-l border-border">
                <div className="hidden sm:block text-right">
                  <p className="text-xs font-mono leading-tight" data-testid="user-display-name">{user.name || user.username}</p>
                  <p className="text-[9px] uppercase tracking-widest text-muted-foreground">{user.role}</p>
                </div>
                <Tip text="Log out of Rhino Drishti" side="bottom">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={logout}
                    className="text-muted-foreground hover:text-red-400"
                    data-testid="logout-btn"
                  >
                    <LogOut size={16} />
                  </Button>
                </Tip>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6" data-testid="main-content">
          <div className="max-w-[1600px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
