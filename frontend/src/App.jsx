import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "./api";
import TenderList from "./pages/TenderList";
import TenderDetail from "./pages/TenderDetail";
import Dashboard from "./pages/Dashboard";
import Reports from "./pages/Reports";
import ScrapePanel from "./components/ScrapePanel";
import { LayoutDashboard, List, BarChart3, RefreshCw } from "lucide-react";

const navItems = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard, end: true },
  { to: "/tenders", label: "Tenders", Icon: List },
  { to: "/reports", label: "Reports", Icon: BarChart3 },
];

export default function App() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats, refetchInterval: 60_000 });

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-60 bg-gov-green text-white flex flex-col shadow-xl shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-green-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gov-gold rounded flex items-center justify-center shrink-0">
              <span className="text-gov-green font-black text-sm">JA</span>
            </div>
            <div>
              <p className="font-bold text-sm leading-tight">GOJEP</p>
              <p className="text-green-300 text-xs">Procurement Dashboard</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-white/20 text-white"
                    : "text-green-200 hover:bg-white/10 hover:text-white"
                }`
              }
            >
              <Icon size={18} />
              {label}
              {label === "Tenders" && stats?.new_since_last_visit > 0 && (
                <span className="ml-auto bg-gov-gold text-gov-green text-xs font-bold px-1.5 py-0.5 rounded-full">
                  {stats.new_since_last_visit}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Scrape button */}
        <div className="p-3 border-t border-green-700">
          <ScrapePanel />
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tenders" element={<TenderList />} />
          <Route path="/tenders/:id" element={<TenderDetail />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
