import { useState, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { triggerScrape } from "../api";
import { RefreshCw, CheckCircle2, XCircle, Loader2 } from "lucide-react";

export default function ScrapePanel() {
  const [state, setState] = useState("idle"); // idle | running | done | error
  const [log, setLog] = useState([]);
  const [progress, setProgress] = useState({ found: 0, done: 0 });
  const esRef = useRef(null);
  const qc = useQueryClient();

  const startScrape = useCallback(async () => {
    if (state === "running") return;
    setState("running");
    setLog([]);
    setProgress({ found: 0, done: 0 });

    try {
      await triggerScrape();
    } catch (e) {
      setState("error");
      setLog(["Failed to start scrape: " + e.message]);
      return;
    }

    // Open SSE connection
    const es = new EventSource("/api/scrape/stream");
    esRef.current = es;

    es.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "heartbeat") return;

      if (msg.type === "total_urls") {
        setProgress((p) => ({ ...p, found: msg.count }));
        setLog((l) => [...l, `Found ${msg.count} notices`]);
      } else if (msg.type === "upserted") {
        setProgress((p) => ({ ...p, done: msg.idx }));
        if (msg.created) setLog((l) => [...l.slice(-19), `+ ${msg.title}`]);
      } else if (msg.type === "error") {
        setLog((l) => [...l, `⚠ ${msg.url}`]);
      } else if (msg.type === "done") {
        setLog((l) => [
          ...l,
          `Done — ${msg.tenders_new} new, ${msg.tenders_updated} updated`,
        ]);
        setState(msg.error ? "error" : "done");
        es.close();
        qc.invalidateQueries();
      }
    };

    es.onerror = () => {
      setState("error");
      es.close();
    };
  }, [state, qc]);

  const icon =
    state === "running" ? (
      <Loader2 size={15} className="animate-spin" />
    ) : state === "done" ? (
      <CheckCircle2 size={15} className="text-gov-gold" />
    ) : state === "error" ? (
      <XCircle size={15} className="text-red-400" />
    ) : (
      <RefreshCw size={15} />
    );

  const pct =
    progress.found > 0
      ? Math.round((progress.done / progress.found) * 100)
      : 0;

  return (
    <div>
      <button
        onClick={startScrape}
        disabled={state === "running"}
        className="w-full flex items-center justify-center gap-2 bg-gov-gold text-gov-green font-bold text-sm py-2.5 rounded-lg hover:bg-gov-gold-dark transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
      >
        {icon}
        {state === "running" ? "Scraping…" : "Run Scraper Now"}
      </button>

      {state === "running" && progress.found > 0 && (
        <div className="mt-2">
          <div className="flex justify-between text-xs text-green-300 mb-1">
            <span>
              {progress.done}/{progress.found} notices
            </span>
            <span>{pct}%</span>
          </div>
          <div className="h-1.5 bg-green-900 rounded-full overflow-hidden">
            <div
              className="h-full bg-gov-gold transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {log.length > 0 && (
        <div className="mt-2 max-h-28 overflow-y-auto scrollbar-thin text-xs text-green-200 space-y-0.5">
          {log.slice(-12).map((line, i) => (
            <p key={i} className="truncate">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
