import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import axios from "axios";
import { ThemeProvider } from "./components/ThemeProvider";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { UpdateNotificationProvider } from "./contexts/UpdateContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import IntelligenceFeed from "./pages/IntelligenceFeed";
import DailyBrief from "./pages/DailyBrief";
import Trends from "./pages/Trends";
import DocumentUpload from "./pages/DocumentUpload";
import Patterns from "./pages/Patterns";
import SettingsPage from "./pages/SettingsPage";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import KeywordEngine from "./pages/KeywordEngine";
import Handbook from "./pages/Handbook";
import TrainingSummary from "./pages/TrainingSummary";
import CrossBorderWatch from "./pages/CrossBorderWatch";
import UserManagement from "./pages/UserManagement";
import UpdatesPage from "./pages/UpdatesPage";
import ReportsPage from "./pages/ReportsPage";
import AdminMonitoring from "./pages/AdminMonitoring";
import FaultlineIntelligence from "./pages/FaultlineIntelligence";
import FaultlineDetail from "./pages/FaultlineDetail";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { TourProvider } from "./contexts/TourContext";
import AppTour from "./components/AppTour";
import { useNotifications } from "./hooks/useNotifications";
import PushPermissionPrompt from "./components/PushPermissionPrompt";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function AppRoutes() {
  const [alertCount, setAlertCount] = useState(0);
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const {
    unreadCount: notifUnreadCount,
    setUnreadCount: setNotifUnreadCount,
    subscribe,
    pushSupported,
    pushSubscribed,
  } = useNotifications();


  const fetchStats = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const res = await axios.get(`${API}/dashboard/stats`);
      setStats(res.data);
      setAlertCount(res.data.critical_count + res.data.high_count);
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleSearch = (query) => {
    if (query) {
      navigate(`/feed?search=${encodeURIComponent(query)}`);
    }
  };

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <PushPermissionPrompt
              pushSupported={pushSupported}
              pushSubscribed={pushSubscribed}
              subscribe={subscribe}
            />
            <Layout
              alertCount={alertCount}
              onSearch={handleSearch}
              notifUnreadCount={notifUnreadCount}
              onResetNotifUnread={() => setNotifUnreadCount(0)}
            >
              <Routes>
                <Route path="/" element={<Dashboard stats={stats} api={API} />} />
                <Route path="/feed" element={<IntelligenceFeed api={API} />} />
                <Route path="/cross-border" element={<CrossBorderWatch api={API} />} />
                <Route path="/daily-brief" element={<DailyBrief api={API} />} />
                <Route path="/trends" element={<Trends api={API} />} />
                <Route path="/weekly-trends" element={<Trends api={API} />} />
                <Route path="/patterns" element={<Patterns api={API} />} />
                <Route path="/knowledge-graph" element={<KnowledgeGraph api={API} />} />
                <Route path="/settings" element={<SettingsPage api={API} />} />
                <Route path="/alerts" element={<IntelligenceFeed api={API} alertsOnly={true} />} />
                <Route path="/keywords" element={<KeywordEngine api={API} />} />
                <Route path="/training" element={<TrainingSummary api={API} />} />
                <Route path="/upload" element={<DocumentUpload api={API} />} />
                <Route path="/handbook" element={<Handbook api={API} />} />
                <Route path="/user-management" element={<UserManagement api={API} />} />
                <Route path="/updates" element={<UpdatesPage api={API} />} />
                <Route path="/reports" element={<ReportsPage api={API} />} />
                <Route path="/admin" element={<AdminMonitoring api={API} />} />
                <Route path="/faultlines" element={<FaultlineIntelligence api={API} />} />
                <Route path="/faultlines/:id" element={<FaultlineDetail api={API} />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={200}>
        <BrowserRouter>
          <AuthProvider api={API}>
            <UpdateNotificationProvider api={API}>
              <TourProvider>
                <AppRoutes />
                <AppTour />
              </TourProvider>
            </UpdateNotificationProvider>
          </AuthProvider>
        </BrowserRouter>
        <Toaster position="top-center" />
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
