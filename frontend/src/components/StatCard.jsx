import clsx from "clsx";

export default function StatCard({ label, value, sub, color = "green", Icon }) {
  const colors = {
    green: "bg-gov-green-light border-gov-green text-gov-green",
    gold: "bg-yellow-50 border-gov-gold text-gov-gold-dark",
    blue: "bg-blue-50 border-blue-400 text-blue-600",
    gray: "bg-gray-100 border-gray-300 text-gray-600",
  };

  return (
    <div className={clsx("rounded-xl border-l-4 p-4 shadow-sm bg-white", "border-l-4", colors[color])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value ?? "—"}</p>
          {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
        </div>
        {Icon && (
          <div className={clsx("p-2 rounded-lg opacity-80", colors[color])}>
            <Icon size={20} />
          </div>
        )}
      </div>
    </div>
  );
}
