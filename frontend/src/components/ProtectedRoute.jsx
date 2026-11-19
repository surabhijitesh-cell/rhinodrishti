import { Navigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

// roles (optional): only these roles may open the screen; others see a plain notice.
export default function ProtectedRoute({ children, roles }) {
  const { isAuthenticated, loading, user } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs uppercase tracking-widest text-muted-foreground font-mono">Authenticating</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(user?.role)) {
    return (
      <div className="p-8 text-center space-y-3" data-testid="not-available-for-role">
        <p className="text-sm font-semibold">Not available for your role</p>
        <Link to="/" className="text-xs text-primary hover:underline">Back to the Dashboard</Link>
      </div>
    );
  }

  return children;
}
