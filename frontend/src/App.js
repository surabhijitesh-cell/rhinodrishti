import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import axios from "axios";
import { ThemeProvider } from "./components/ThemeProvider";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import IntelligenceFeed from "./pages/IntelligenceFeed";
import DailyBrief from "./pages/DailyBrief";
import WeeklyTrends from "./pages/WeeklyTrends";
import DocumentUpload from "./pages/DocumentUpload";
import { Toaster } from "./components/ui/sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function AppRoutes() {
  const [alertCount, setAlertCount] = useState(0);
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/dashboard/stats`);
      setStats(res.data);
      setAlertCount(res.data.critical_count + res.data.high_count);
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }, []);

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
    <Layout alertCount={alertCount} onSearch={handleSearch}>
      <Routes>
        <Route path="/" element={<Dashboard stats={stats} api={API} />} />
        <Route path="/feed" element={<IntelligenceFeed api={API} />} />
        <Route path="/cross-border" element={<IntelligenceFeed api={API} crossBorderOnly={true} />} />
        <Route path="/daily-brief" element={<DailyBrief api={API} />} />
        <Route path="/weekly-trends" element={<WeeklyTrends api={API} />} />
        <Route path="/alerts" element={<IntelligenceFeed api={API} alertsOnly={true} />} />
        <Route path="/upload" element={<DocumentUpload api={API} />} />
      </Routes>
    </Layout>
  );
}

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
