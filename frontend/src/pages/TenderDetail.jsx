import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate, Link } from "react-router-dom";
import { fetchTender, downloadTenderPdf, deleteTender } from "../api";
import {
  ArrowLeft,
  FileDown,
  ExternalLink,
  Building2,
  Calendar,
  DollarSign,
  Tag,
  Hash,
  BookOpen,
  ClipboardList,
  Phone,
  Trash2,
  AlertCircle,
} from "lucide-react";
import { format, parseISO } from "date-fns";

function Field({ icon: Icon, label, value }) {
  if (!value) return null;
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 text-gov-green shrink-0">
        <Icon size={16} />
      </div>
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
        <p className="text-gray-800 mt-0.5 leading-relaxed">{value}</p>
      </div>
    </div>
  );
}

function fmtDate(d) {
  if (!d) return null;
  try {
    return format(parseISO(d), "EEEE, dd MMMM yyyy");
  } catch {
    return d;
  }
}

function fmtAmt(n, currency) {
  if (n == null) return null;
  return `${currency || "JMD"} ${n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function TenderDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: tender, isLoading, error } = useQuery({
    queryKey: ["tender", id],
    queryFn: () => fetchTender(id),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteTender(id),
    onSuccess: () => {
      qc.invalidateQueries(["tenders"]);
      navigate("/tenders");
    },
  });

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading notice…
      </div>
    );

  if (error || !tender)
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400 gap-3">
        <AlertCircle size={32} />
        <p>Notice not found.</p>
        <Link to="/tenders" className="text-gov-green hover:underline text-sm">
          Back to list
        </Link>
      </div>
    );

  const deadline = fmtDate(tender.deadline);
  const amount = fmtAmt(tender.estimated_amount, tender.currency);

  const isExpired =
    tender.deadline && new Date(tender.deadline) < new Date();

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <Link
        to="/tenders"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gov-green"
      >
        <ArrowLeft size={15} /> Back to tenders
      </Link>

      {/* Header card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="bg-gov-green px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              {tender.is_new && (
                <span className="inline-block mb-2 px-2 py-0.5 bg-gov-gold text-gov-green text-xs font-bold rounded">
                  NEW
                </span>
              )}
              <h1 className="text-white text-xl font-bold leading-tight">{tender.title}</h1>
              {tender.reference_number && (
                <p className="text-green-300 text-sm mt-1">Ref: {tender.reference_number}</p>
              )}
            </div>
            {tender.status && (
              <span
                className={`shrink-0 px-3 py-1 rounded-full text-sm font-semibold ${
                  tender.status.toLowerCase().includes("open")
                    ? "bg-gov-gold text-gov-green"
                    : "bg-white/20 text-white"
                }`}
              >
                {tender.status}
              </span>
            )}
          </div>
        </div>

        {/* Action bar */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex flex-wrap gap-2">
          <button
            onClick={() => downloadTenderPdf(tender.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gov-green text-white rounded-lg text-sm font-medium hover:bg-gov-green-dark transition-colors"
          >
            <FileDown size={15} />
            Download PDF
          </button>
          <a
            href={tender.source_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <ExternalLink size={15} />
            View on GOJEP
          </a>
          <button
            onClick={() => {
              if (window.confirm("Delete this tender from the database?")) {
                deleteMut.mutate();
              }
            }}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 border border-red-200 rounded-lg text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 size={15} />
            Delete
          </button>
        </div>

        {/* Key fields grid */}
        <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field icon={Building2} label="Issuing Agency" value={tender.buyer_agency} />
          <Field
            icon={Calendar}
            label="Submission Deadline"
            value={
              deadline
                ? isExpired
                  ? `${deadline} (expired)`
                  : deadline
                : undefined
            }
          />
          <Field icon={DollarSign} label="Estimated Contract Value" value={amount} />
          <Field icon={Tag} label="Category" value={tender.category} />
        </div>
      </div>

      {/* Description */}
      {tender.description && (
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800 mb-4">
            <BookOpen size={17} className="text-gov-green" />
            Description
          </h2>
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">
            {tender.description}
          </div>
        </section>
      )}

      {/* Instructions */}
      {tender.instructions && (
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800 mb-4">
            <ClipboardList size={17} className="text-gov-green" />
            Submission Instructions
          </h2>
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">
            {tender.instructions}
          </div>
        </section>
      )}

      {/* Contact */}
      {tender.contact_details && (
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-800 mb-4">
            <Phone size={17} className="text-gov-green" />
            Contact Information
          </h2>
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">
            {tender.contact_details}
          </div>
        </section>
      )}

      {/* Metadata footer */}
      <div className="text-xs text-gray-400 space-y-1 pb-6">
        <p>First scraped: {fmtDate(tender.first_scraped_at)}</p>
        <p>Last updated: {fmtDate(tender.last_updated_at)}</p>
        <p>
          Source:{" "}
          <a
            href={tender.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-gov-green hover:underline"
          >
            {tender.source_url}
          </a>
        </p>
      </div>
    </div>
  );
}
