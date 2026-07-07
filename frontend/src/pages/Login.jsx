import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Eye, EyeOff, Shield, AlertTriangle } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  // Shown once when the user was bounced here by an expired session (set by
  // the axios 401 interceptor in AuthContext). Read-and-clear so it doesn't
  // linger after a fresh visit.
  const [notice] = useState(() => {
    if (sessionStorage.getItem("rd_session_expired")) {
      sessionStorage.removeItem("rd_session_expired");
      return "Your session expired. Please sign in again.";
    }
    return "";
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Username and password are required");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const user = await login(username.trim(), password);
      if (user.role === "analyst") {
        navigate("/feed", { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } catch (err) {
      const msg = err.response?.data?.detail || "Authentication failed";
      setError(msg);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0d08] p-4" data-testid="login-page">
      <div className="w-full max-w-sm space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Shield size={28} className="text-primary" />
            <h1 className="text-2xl font-bold uppercase tracking-wider font-['Barlow_Condensed'] text-primary">
              Rhino Drishti
            </h1>
          </div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-mono">
            NER Intelligence Platform
          </p>
          <div className="h-px bg-border mt-4" />
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mt-2">
            Classification: Restricted
          </p>
        </div>

        {notice && (
          <div className="flex items-center gap-2 text-amber-300 text-xs bg-amber-500/10 border border-amber-500/25 px-3 py-2" data-testid="login-notice">
            <AlertTriangle size={14} />
            <span>{notice}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1.5">
              Username or Email
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-card border border-border px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-primary transition-colors"
              placeholder="Enter username or email"
              autoComplete="username"
              autoFocus
              data-testid="login-username"
            />
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1.5">
              Password
            </label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-card border border-border px-3 py-2.5 text-sm font-mono pr-10 focus:outline-none focus:border-primary transition-colors"
                placeholder="Enter password"
                autoComplete="current-password"
                data-testid="login-password"
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                data-testid="password-toggle"
              >
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 px-3 py-2" data-testid="login-error">
              <AlertTriangle size={14} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-primary-foreground py-2.5 text-xs uppercase tracking-widest font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="login-submit"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-3 h-3 border border-primary-foreground border-t-transparent rounded-full animate-spin" />
                Authenticating...
              </span>
            ) : (
              "Authenticate"
            )}
          </button>
        </form>

        <p className="text-[9px] text-center text-muted-foreground/40 font-mono uppercase tracking-wider">
          Authorized Personnel Only
        </p>
      </div>
    </div>
  );
}
