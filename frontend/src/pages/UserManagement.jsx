import { useState, useEffect, useCallback } from "react";
import { Users, Plus, Key, Trash2, Eye, EyeOff, Copy, RefreshCw, Check, Shield } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";

const ROLE_BADGES = {
  admin: "bg-red-500/20 text-red-400 border-red-500/30",
  analyst: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  viewer: "bg-green-500/20 text-green-400 border-green-500/30",
};

function generatePassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%";
  let pwd = "";
  for (let i = 0; i < 14; i++) pwd += chars[Math.floor(Math.random() * chars.length)];
  return pwd;
}

export default function UserManagement({ api }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [resetUserId, setResetUserId] = useState(null);

  // Create form state
  const [form, setForm] = useState({ username: "", email: "", name: "", password: "", role: "analyst" });
  const [showFormPass, setShowFormPass] = useState(false);
  const [creating, setCreating] = useState(false);

  // Reset form state
  const [resetPass, setResetPass] = useState("");
  const [showResetPass, setShowResetPass] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/users`);
      setUsers(res.data.users || []);
    } catch (err) {
      toast.error("Failed to fetch users");
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password.trim()) {
      toast.error("Username and password are required");
      return;
    }
    if (form.password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${api}/users`, form);
      toast.success(`User "${form.username}" created`);
      setForm({ username: "", email: "", name: "", password: "", role: "analyst" });
      setShowCreate(false);
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create user");
    }
    setCreating(false);
  };

  const handleResetPassword = async () => {
    if (!resetPass || resetPass.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setResetting(true);
    try {
      await axios.put(`${api}/users/${resetUserId}/password`, { new_password: resetPass });
      toast.success("Password reset successfully");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to reset password");
    }
    setResetting(false);
  };

  const handleToggleActive = async (user) => {
    try {
      await axios.put(`${api}/users/${user.id}`, { is_active: !user.is_active });
      toast.success(`User ${user.is_active ? "deactivated" : "activated"}`);
      fetchUsers();
    } catch (err) {
      toast.error("Failed to update user");
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user "${user.username}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${api}/users/${user.id}`);
      toast.success(`User "${user.username}" deleted`);
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete user");
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Password copied to clipboard");
  };

  return (
    <div className="space-y-6" data-testid="user-management-page">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
            User Management
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            {users.length} users registered
          </p>
        </div>
        <Button
          onClick={() => setShowCreate(!showCreate)}
          className="uppercase text-xs font-bold tracking-wider rounded-none"
          data-testid="create-user-btn"
        >
          <Plus size={14} className="mr-2" />
          {showCreate ? "Cancel" : "Create User"}
        </Button>
      </div>

      {/* Create User Form */}
      {showCreate && (
        <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary" data-testid="create-user-form">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Plus size={16} className="text-primary" /> New User
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Username</label>
                <input
                  type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary"
                  required data-testid="new-username"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Email</label>
                <input
                  type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary"
                  data-testid="new-email"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Full Name</label>
                <input
                  type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary"
                  data-testid="new-name"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Role</label>
                <select
                  value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary"
                  data-testid="new-role"
                >
                  <option value="admin">Admin</option>
                  <option value="analyst">Analyst</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Password</label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showFormPass ? "text" : "password"} value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      className="w-full bg-background border border-border px-3 py-2 text-sm font-mono pr-10 focus:outline-none focus:border-primary"
                      required minLength={8} data-testid="new-password"
                    />
                    <button type="button" onClick={() => setShowFormPass(!showFormPass)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1">
                      {showFormPass ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                  <Button type="button" variant="outline" className="rounded-none text-xs shrink-0"
                    onClick={() => { const p = generatePassword(); setForm({ ...form, password: p }); setShowFormPass(true); }}
                    data-testid="generate-password-btn"
                  >
                    <RefreshCw size={12} className="mr-1" /> Generate
                  </Button>
                  {form.password && (
                    <Button type="button" variant="outline" className="rounded-none text-xs shrink-0"
                      onClick={() => copyToClipboard(form.password)} data-testid="copy-password-btn"
                    >
                      {copied ? <Check size={12} /> : <Copy size={12} />}
                    </Button>
                  )}
                </div>
                <p className="text-[9px] text-amber-400/70 mt-1 font-mono">Passwords shown only once — copy before closing</p>
              </div>
              <div className="md:col-span-2 flex justify-end">
                <Button type="submit" disabled={creating} className="rounded-none uppercase text-xs tracking-wider" data-testid="submit-create-user">
                  {creating ? "Creating..." : "Create User"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Password Reset Modal */}
      {resetUserId && (
        <Card className="border border-border rounded-none bg-card border-l-4 border-l-amber-500" data-testid="reset-password-form">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Key size={16} className="text-amber-400" />
              Reset Password — {users.find(u => u.id === resetUserId)?.username}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="flex gap-2 items-end">
              <div className="relative flex-1">
                <input
                  type={showResetPass ? "text" : "password"} value={resetPass}
                  onChange={(e) => setResetPass(e.target.value)}
                  className="w-full bg-background border border-border px-3 py-2 text-sm font-mono pr-10 focus:outline-none focus:border-primary"
                  placeholder="New password (min 8 chars)" minLength={8} data-testid="reset-password-input"
                />
                <button type="button" onClick={() => setShowResetPass(!showResetPass)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1">
                  {showResetPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <Button type="button" variant="outline" className="rounded-none text-xs shrink-0"
                onClick={() => { const p = generatePassword(); setResetPass(p); setShowResetPass(true); }}
              >
                <RefreshCw size={12} className="mr-1" /> Generate
              </Button>
              {resetPass && (
                <Button type="button" variant="outline" className="rounded-none text-xs shrink-0"
                  onClick={() => copyToClipboard(resetPass)}
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                </Button>
              )}
              <Button onClick={handleResetPassword} disabled={resetting} className="rounded-none uppercase text-xs tracking-wider shrink-0">
                {resetting ? "Resetting..." : "Reset"}
              </Button>
              <Button variant="outline" onClick={() => { setResetUserId(null); setResetPass(""); setShowResetPass(false); }}
                className="rounded-none text-xs shrink-0">
                Cancel
              </Button>
            </div>
            <p className="text-[9px] text-amber-400/70 mt-2 font-mono">Password shown only once — copy before closing</p>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Users size={16} className="text-primary" /> Registered Users
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground text-sm">Loading...</div>
          ) : users.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No users found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="users-table">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="text-left px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Username</th>
                    <th className="text-left px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Name</th>
                    <th className="text-left px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Role</th>
                    <th className="text-left px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Status</th>
                    <th className="text-left px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Last Login</th>
                    <th className="text-right px-4 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-muted/10 transition-colors">
                      <td className="px-4 py-2.5 font-mono text-sm">{u.username}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{u.name || "—"}</td>
                      <td className="px-4 py-2.5">
                        <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${ROLE_BADGES[u.role] || ROLE_BADGES.viewer}`}>
                          {u.role?.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => handleToggleActive(u)}
                          className={`text-[10px] uppercase tracking-widest font-mono cursor-pointer ${u.is_active ? "text-green-400" : "text-red-400"}`}
                          data-testid={`toggle-active-${u.username}`}
                        >
                          {u.is_active ? "Active" : "Inactive"}
                        </button>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground font-mono">
                        {u.last_login ? new Date(u.last_login).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }) : "Never"}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0"
                            onClick={() => { setResetUserId(u.id); setResetPass(""); setShowResetPass(false); }}
                            title="Reset password" data-testid={`reset-btn-${u.username}`}
                          >
                            <Key size={13} />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-400 hover:text-red-300"
                            onClick={() => handleDelete(u)} title="Delete user" data-testid={`delete-btn-${u.username}`}
                          >
                            <Trash2 size={13} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
