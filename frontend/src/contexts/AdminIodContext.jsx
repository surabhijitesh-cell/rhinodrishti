import { createContext, useContext, useState } from "react";

const STORAGE_KEY = "rd_admin_view_iod";
const AdminIodContext = createContext(null);

export function AdminIodProvider({ children }) {
  const [viewIod, setViewIod] = useState(() => localStorage.getItem(STORAGE_KEY) || "");

  const updateViewIod = (iod) => {
    setViewIod(iod);
    if (iod) localStorage.setItem(STORAGE_KEY, iod);
    else localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <AdminIodContext.Provider value={{ viewIod, setViewIod: updateViewIod }}>
      {children}
    </AdminIodContext.Provider>
  );
}

export function useAdminIod() {
  const ctx = useContext(AdminIodContext);
  if (!ctx) throw new Error("useAdminIod must be used within AdminIodProvider");
  return ctx;
}
