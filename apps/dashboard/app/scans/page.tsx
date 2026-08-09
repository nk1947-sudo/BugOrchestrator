"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/lib/require-auth";
import { api, ApiError } from "@/lib/api-client";
import type { Scan } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { useLiveEvents } from "@/lib/use-live-events";

function ScansContent() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.listScans().then(setScans).catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load scans"));
  }

  useEffect(load, []);
  useLiveEvents((type) => {
    if (type.startsWith("scan.")) load();
  });

  return (
    <div>
      <h1>Scans</h1>
      <p className="muted">Live status of every OBSERVE → REASON → PLAN → EXECUTE → VERIFY run.</p>
      {error && <div className="form-error">{error}</div>}
      <table className="data-table">
        <thead>
          <tr>
            <th>Scan</th>
            <th>Stage</th>
            <th>Summary</th>
            <th>Started</th>
            <th>Finished</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((s) => (
            <tr key={s.id}>
              <td className="mono">{s.id.slice(0, 8)}</td>
              <td>
                <Badge value={s.stage} />
              </td>
              <td>{s.error ? <span className="text-error">{s.error}</span> : s.summary || "—"}</td>
              <td>{s.started_at ? new Date(s.started_at).toLocaleString() : "—"}</td>
              <td>{s.finished_at ? new Date(s.finished_at).toLocaleString() : "—"}</td>
            </tr>
          ))}
          {scans.length === 0 && (
            <tr>
              <td colSpan={5} className="empty-row">
                No scans yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function ScansPage() {
  return (
    <RequireAuth>
      <ScansContent />
    </RequireAuth>
  );
}
