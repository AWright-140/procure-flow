import { useQuery } from "@tanstack/react-query";
import { fetchAgencies, fetchCategories } from "../api";
import { Search, X } from "lucide-react";

export default function FilterBar({ filters, setFilters, onReset }) {
  const { data: agencies = [] } = useQuery({
    queryKey: ["agencies"],
    queryFn: fetchAgencies,
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  const set = (key) => (e) =>
    setFilters((f) => ({ ...f, [key]: e.target.value, page: 1 }));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Search */}
        <div className="relative lg:col-span-2">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search title, agency, reference…"
            value={filters.search || ""}
            onChange={set("search")}
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gov-green"
          />
        </div>

        {/* Agency */}
        <select
          value={filters.agency || ""}
          onChange={set("agency")}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        >
          <option value="">All Agencies</option>
          {agencies.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>

        {/* Category */}
        <select
          value={filters.category || ""}
          onChange={set("category")}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        {/* Status */}
        <select
          value={filters.status || ""}
          onChange={set("status")}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
          <option value="awarded">Awarded</option>
        </select>

        {/* Deadline from */}
        <input
          type="date"
          value={filters.deadline_from || ""}
          onChange={set("deadline_from")}
          title="Deadline from"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        />

        {/* Deadline to */}
        <input
          type="date"
          value={filters.deadline_to || ""}
          onChange={set("deadline_to")}
          title="Deadline to"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        />

        {/* Amount min */}
        <input
          type="number"
          placeholder="Min amount (JMD)"
          value={filters.amount_min || ""}
          onChange={set("amount_min")}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
        />

        {/* Amount max */}
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Max amount (JMD)"
            value={filters.amount_max || ""}
            onChange={set("amount_max")}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gov-green"
          />
          <button
            onClick={onReset}
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
            title="Clear filters"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
