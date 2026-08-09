"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/lib/require-auth";
import { api, ApiError } from "@/lib/api-client";
import type { Finding, FindingStatus } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { useLiveEvents } from "@/lib/use-live-events";

const FILTERS: { label: string; value: FindingStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Unconfirmed", value: "unconfirmed" },
  { label: "False positive", value: "false_positive" },
];

function FindingsContent() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [filter, setFilter] = useState<FindingStatus | "all">("all");
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .listFindings(filter === "all" ? undefined : { status: filter })
      .then(setFindings)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load findings"));
  }

  useEffect(load, [filter]);
  useLiveEvents((type) => {
    if (type.startsWith("finding.")) load();
  });

  return (
    <div>
      <h1>Findings</h1>
      <div className="filter-row">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={filter === f.value ? "filter-btn active" : "filter-btn"}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="finding-list">
        {findings.map((f) => (
          <div key={f.id} className="finding-card">
            <div className="finding-header">
              <Badge value={f.severity} />
              <Badge value={f.status} />
              <span className="finding-category">{f.category.replace(/_/g, " ")}</span>
            </div>
            <h3>{f.title}</h3>
            <p>{f.summary}</p>
            {f.evidence_path && <p className="mono muted">Evidence: {f.evidence_path}</p>}
            <p className="muted">{new Date(f.created_at).toLocaleString()}</p>
          </div>
        ))}
        {findings.length === 0 && <p className="empty-row">No findings yet</p>}
      </div>
    </div>
  );
}

export default function FindingsPage() {
  return (
    <RequireAuth>
      <FindingsContent />
    </RequireAuth>
  );
}
