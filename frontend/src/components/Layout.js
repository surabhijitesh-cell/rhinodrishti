import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "./ThemeProvider";
import {
  Shield, LayoutDashboard, Newspaper, FileText, TrendingUp,
  Globe, Bell, ChevronLeft, ChevronRight, Sun, Moon, Search,
  Activity, Menu, X
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/feed", label: "Intelligence Feed", icon: Newspaper },
  { path: "/cross-border", label: "Cross-Border", icon: Globe },
  { path: "/daily-brief", label: "Daily Brief", icon: FileText },
  { path: "/weekly-trends", label: "Weekly Trends", icon: TrendingUp },
  { path: "/alerts", label: "Alerts", icon: Bell },
];

export default function Layout({ children, alertCount = 0, onSearch }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchVal, setSearchVal] = useState("");
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();

  const handleSearch = (e) => {
    e.preventDefault();
    if (onSearch) onSearch(searchVal);
  };

  const SidebarContent = () => (
    <nav className="flex flex-col gap-1 mt-4 px-2" data-testid="sidebar-nav">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = location.pathname === item.path;
        return (
          <Link
            key={item.path}
            to={item.path}
            data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            onClick={() => setMobileOpen(false)}
            className={`sidebar-nav-item ${isActive ? "active" : "text-muted-foreground"}`}
          >
            <Icon size={18} />
            {!collapsed && <span>{item.label}</span>}
            {item.path === "/alerts" && alertCount > 0 && !collapsed && (
              <Badge className="ml-auto severity-critical text-[10px] rounded-none px-1.5" data-testid="alert-count-badge">
                {alertCount}
              </Badge>
            )}
          </Link>
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
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              data-testid="theme-toggle"
              className="text-muted-foreground hover:text-foreground"
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </Button>

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
