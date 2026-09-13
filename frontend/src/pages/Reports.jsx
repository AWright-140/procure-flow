import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";
import StatCard from "../components/StatCard";
import { TrendingUp, Building2, DollarSign, FileText } from "lucide-react";

const COLORS = [
  "#007A33", "#FFC72C", "#1D6FA4", "#C0392B",
  "#8E44AD", "#16A085", "#E67E22", "#2C3E50",
  "#27AE60", "#2980B9",
];

function fmtAmt(n) {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `JMD ${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `JMD ${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `JMD ${(n / 1_000).toFixed(0)}K`;
  return `JMD ${n.toFixed(0)}`;
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg text-sm">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

export default function Reports() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 120_000,
  });

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading reports…
      </div>
    );

  const monthData = (stats?.by_month || []).map((m) => ({
    month: m.month,
    Notices: m.count,
  }));

  const agencyPieData = (stats?.by_agency || []).slice(0, 8).map((a) => ({
    name: a.agency.length > 30 ? a.agency.slice(0, 30) + "…" : a.agency,
    value: a.count,
  }));

  const agencyBarData = (stats?.by_agency || []).slice(0, 10).map((a) => ({
    agency: a.agency.length > 25 ? a.agency.slice(0, 25) + "…" : a.agency,
    Notices: a.count,
  }));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports & Analytics</h1>
        <p className="text-gray-500 text-sm">Statistics across all scraped procurement notices</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Notices"
          value={stats?.total_tenders?.toLocaleString()}
          Icon={FileText}
          color="green"
        />
        <StatCard
          label="Open Notices"
          value={stats?.open_tenders?.toLocaleString()}
          Icon={TrendingUp}
          color="green"
        />
        <StatCard
          label="Agencies"
          value={stats?.by_agency?.length?.toLocaleString()}
          Icon={Building2}
          color="blue"
        />
        <StatCard
          label="Avg Contract Value"
          value={fmtAmt(stats?.average_amount)}
          Icon={DollarSign}
          color="gold"
        />
      </div>

      {/* Notices over time */}
      {monthData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h2 className="text-base font-semibold text-gray-800 mb-4">
            Notices Scraped Over Time (by month)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={monthData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="Notices"
                stroke="#007A33"
                strokeWidth={2.5}
                dot={{ r: 3, fill: "#007A33" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Agency charts */}
      {agencyBarData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Bar chart */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              Top 10 Agencies by Notices
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={agencyBarData}
                layout="vertical"
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis
                  type="category"
                  dataKey="agency"
                  tick={{ fontSize: 10 }}
                  width={160}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="Notices" fill="#007A33" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Pie chart */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              Agency Distribution (Top 8)
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={agencyPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  outerRadius={100}
                  label={({ name, percent }) =>
                    percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ""
                  }
                >
                  {agencyPieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  formatter={(v) => (
                    <span className="text-xs text-gray-600">{v}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Amount stats */}
      {stats?.tenders_with_amounts > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Contract Value Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Minimum</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">
                {fmtAmt(stats.min_amount)}
              </p>
            </div>
            <div className="text-center border-x border-gray-100">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Average</p>
              <p className="text-2xl font-bold text-gov-green mt-1">
                {fmtAmt(stats.average_amount)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Maximum</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">
                {fmtAmt(stats.max_amount)}
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-400 text-center mt-4">
            Based on {stats.tenders_with_amounts} notices that include contract values (
            {Math.round((stats.tenders_with_amounts / stats.total_tenders) * 100)}% of total)
          </p>
        </div>
      )}

      {/* Empty state */}
      {stats?.total_tenders === 0 && (
        <div className="bg-gov-green-light border border-gov-green rounded-xl p-8 text-center">
          <p className="text-gov-green font-semibold text-lg mb-2">No data to report</p>
          <p className="text-gray-600 text-sm">
            Run the scraper from the sidebar to populate your database.
          </p>
        </div>
      )}
    </div>
  );
}
