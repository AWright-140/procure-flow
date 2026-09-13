import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchStats, fetchScrapeRuns } from "../api";
import StatCard from "../components/StatCard";
import { FileText, Building2, DollarSign, Clock, CheckCircle, History } from "lucide-react";
import { format, parseISO } from "date-fns";

function fmtAmt(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `JMD ${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `JMD ${(n / 1_000).toFixed(0)}K`;
  return `JMD ${n.toFixed(2)}`;
}

function fmtDate(s) {
  if (!s) return "Never";
  try {
    return format(parseISO(s), "dd MMM yyyy, HH:mm");
  } catch {
    return s;
  }
}

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 60_000,
  });
  const { data: runs = [] } = useQuery({
    queryKey: ["scrapeRuns"],
    queryFn: () => fetchScrapeRuns(20),
  });

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading dashboard…
      </div>
    );

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">
          Last scraped:{" "}
          <span className="font-medium text-gray-700">{fmtDate(stats?.last_scraped)}</span>
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Notices"
          value={stats?.total_tenders?.toLocaleString()}
          Icon={FileText}
          color="green"
        />
        <StatCard
          label="Open"
          value={stats?.open_tenders?.toLocaleString()}
          sub="Currently open"
          Icon={CheckCircle}
          color="green"
        />
        <StatCard
          label="New Since Last Visit"
          value={stats?.new_since_last_visit?.toLocaleString()}
          Icon={Clock}
          color="gold"
        />
        <StatCard
          label="With Amounts"
          value={stats?.tenders_with_amounts?.toLocaleString()}
          sub={`Avg: ${fmtAmt(stats?.average_amount)}`}
          Icon={DollarSign}
          color="blue"
        />
      </div>

      {/* Amount range */}
      {(stats?.min_amount || stats?.max_amount) && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Contract Value Range
          </h2>
          <div className="flex gap-8">
            <div>
              <p className="text-xs text-gray-400">Minimum</p>
              <p className="text-lg font-bold text-gray-800">{fmtAmt(stats?.min_amount)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Average</p>
              <p className="text-lg font-bold text-gray-800">{fmtAmt(stats?.average_amount)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Maximum</p>
              <p className="text-lg font-bold text-gray-800">{fmtAmt(stats?.max_amount)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Top agencies + Recent runs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top agencies */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <Building2 size={15} />
            Top Agencies
          </h2>
          {stats?.by_agency?.length === 0 ? (
            <p className="text-gray-400 text-sm">No data yet — run the scraper first.</p>
          ) : (
            <div className="space-y-2">
              {stats?.by_agency?.slice(0, 8).map((a) => {
                const maxCount = stats.by_agency[0]?.count || 1;
                const pct = Math.round((a.count / maxCount) * 100);
                return (
                  <div key={a.agency}>
                    <div className="flex justify-between text-sm mb-0.5">
                      <Link
                        to={`/tenders?agency=${encodeURIComponent(a.agency)}`}
                        className="text-gov-green hover:underline truncate mr-2"
                      >
                        {a.agency}
                      </Link>
                      <span className="text-gray-500 shrink-0">{a.count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gov-green rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent scrape runs */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <History size={15} />
            Recent Scrape Runs
          </h2>
          {runs.length === 0 ? (
            <p className="text-gray-400 text-sm">No runs yet.</p>
          ) : (
            <div className="space-y-2">
              {runs.slice(0, 8).map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-gray-100 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        r.status === "done"
                          ? "bg-gov-green"
                          : r.status === "failed"
                          ? "bg-red-400"
                          : "bg-gov-gold animate-pulse"
                      }`}
                    />
                    <span className="text-gray-600">{fmtDate(r.started_at)}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-gray-500">
                      +{r.tenders_new} new · {r.tenders_updated} upd
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CTA if empty */}
      {stats?.total_tenders === 0 && (
        <div className="bg-gov-green-light border border-gov-green rounded-xl p-6 text-center">
          <p className="text-gov-green font-semibold text-lg mb-2">No procurement notices yet</p>
          <p className="text-gray-600 mb-4 text-sm">
            Click <strong>Run Scraper Now</strong> in the sidebar to fetch notices from GOJEP.
          </p>
        </div>
      )}
    </div>
  );
}
