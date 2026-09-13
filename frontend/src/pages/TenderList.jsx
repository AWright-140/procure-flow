import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { fetchTenders, buildExportUrl, batchPdf } from "../api";
import FilterBar from "../components/FilterBar";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  ExternalLink,
  FileText,
  CheckSquare,
  Square,
} from "lucide-react";
import { format, parseISO } from "date-fns";

const DEFAULT_FILTERS = {
  page: 1,
  page_size: 25,
  search: "",
  agency: "",
  category: "",
  status: "",
  deadline_from: "",
  deadline_to: "",
  amount_min: "",
  amount_max: "",
  sort_by: "last_updated_at",
  sort_dir: "desc",
  active_only: true,
};

function fmtDate(d) {
  if (!d) return "—";
  try {
    return format(parseISO(d), "dd MMM yyyy");
  } catch {
    return d;
  }
}

function fmtAmt(n, currency) {
  if (n == null) return "—";
  return `${currency || "JMD"} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function TenderList() {
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState({
    ...DEFAULT_FILTERS,
    agency: searchParams.get("agency") || "",
  });
  const [selected, setSelected] = useState(new Set());

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["tenders", filters],
    queryFn: () => fetchTenders(cleanFilters(filters)),
    keepPreviousData: true,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  function cleanFilters(f) {
    const out = {};
    for (const [k, v] of Object.entries(f)) {
      if (v !== "" && v != null) out[k] = v;
    }
    return out;
  }

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setSelected(new Set());
  }, []);

  const toggleSelect = (id) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const toggleAll = () =>
    setSelected((s) =>
      s.size === items.length ? new Set() : new Set(items.map((t) => t.id))
    );

  const exportUrl = (fmt) => buildExportUrl(fmt, cleanFilters(filters));

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Procurement Notices</h1>
          <p className="text-gray-500 text-sm">
            {total.toLocaleString()} result{total !== 1 ? "s" : ""}
            {isFetching && !isLoading && (
              <span className="ml-2 text-gov-green animate-pulse">Refreshing…</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Active-only toggle */}
          <button
            onClick={() =>
              setFilters((f) => ({ ...f, active_only: !f.active_only, page: 1 }))
            }
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
              filters.active_only
                ? "bg-gov-green text-white border-gov-green"
                : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
            }`}
            title={filters.active_only ? "Showing active notices only — click to show all" : "Showing all notices — click to show active only"}
          >
            {filters.active_only ? "Active only" : "All notices"}
          </button>

          {selected.size > 0 && (
            <button
              onClick={() => batchPdf([...selected])}
              className="flex items-center gap-1.5 px-3 py-2 bg-gov-green text-white rounded-lg text-sm font-medium hover:bg-gov-green-dark transition-colors"
            >
              <FileText size={15} />
              PDF ({selected.size})
            </button>
          )}
          <a
            href={exportUrl("csv")}
            download
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Download size={15} />
            CSV
          </a>
          <a
            href={exportUrl("excel")}
            download
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <FileSpreadsheet size={15} />
            Excel
          </a>
        </div>
      </div>

      {/* Filters */}
      <FilterBar filters={filters} setFilters={setFilters} onReset={resetFilters} />

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="py-24 text-center text-gray-400">Loading…</div>
        ) : items.length === 0 ? (
          <div className="py-24 text-center text-gray-400">
            <FileText size={40} className="mx-auto mb-3 opacity-30" />
            <p>No notices found.</p>
            <p className="text-sm mt-1">Try clearing filters or running the scraper.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 w-10">
                  <button onClick={toggleAll} className="text-gray-400 hover:text-gov-green">
                    {selected.size === items.length && items.length > 0 ? (
                      <CheckSquare size={16} />
                    ) : (
                      <Square size={16} />
                    )}
                  </button>
                </th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Title</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600 hidden md:table-cell">
                  Agency
                </th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600 hidden lg:table-cell">
                  Deadline
                </th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600 hidden lg:table-cell">
                  Amount
                </th>
                <th className="px-4 py-3 text-center font-semibold text-gray-600 hidden xl:table-cell">
                  Status
                </th>
                <th className="px-4 py-3 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((t) => (
                <tr
                  key={t.id}
                  className={`hover:bg-gray-50 transition-colors ${t.is_new ? "bg-gov-green-light/40" : ""}`}
                >
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleSelect(t.id)}
                      className="text-gray-400 hover:text-gov-green"
                    >
                      {selected.has(t.id) ? (
                        <CheckSquare size={16} className="text-gov-green" />
                      ) : (
                        <Square size={16} />
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/tenders/${t.id}`}
                      className="font-medium text-gray-900 hover:text-gov-green line-clamp-2"
                    >
                      {t.is_new && (
                        <span className="inline-block mr-1.5 px-1.5 py-0.5 bg-gov-gold text-gov-green text-xs font-bold rounded">
                          NEW
                        </span>
                      )}
                      {t.title}
                    </Link>
                    {t.reference_number && (
                      <p className="text-xs text-gray-400 mt-0.5">Ref: {t.reference_number}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 hidden md:table-cell max-w-xs truncate">
                    {t.buyer_agency || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 hidden lg:table-cell whitespace-nowrap">
                    {fmtDate(t.deadline)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700 hidden lg:table-cell whitespace-nowrap font-mono text-xs">
                    {fmtAmt(t.estimated_amount, t.currency)}
                  </td>
                  <td className="px-4 py-3 text-center hidden xl:table-cell">
                    {t.status && (
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                          t.status.toLowerCase().includes("open")
                            ? "bg-green-100 text-green-700"
                            : t.status.toLowerCase().includes("close")
                            ? "bg-red-50 text-red-600"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {t.status}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-gray-400 hover:text-gov-green"
                      title="Open on GOJEP"
                    >
                      <ExternalLink size={15} />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <p>
            Page {filters.page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              disabled={filters.page <= 1}
              onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
              className="flex items-center gap-1 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={15} /> Prev
            </button>
            <button
              disabled={filters.page >= totalPages}
              onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
              className="flex items-center gap-1 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
