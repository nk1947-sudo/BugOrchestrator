"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/lib/require-auth";
import { api, ApiError } from "@/lib/api-client";
import type { Approval, Finding, Scan, Target } from "@/lib/types";

function StatCard({
  label,
  value,
  href,
  highlight,
}: {
  label: string;
  value: number;
  href: string;
  highlight?: boolean;
}) {
  return (
    <Link href={href} className={`stat-card${highlight ? " stat-card-highlight" : ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </Link>
  );
}

function OverviewContent() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listTargets(), api.listScans(), api.listFindings(), api.listApprovals("pending")])
      .then(([t, s, f, a]) => {
        setTargets(t);
        setScans(s);
        setFindings(f);
        setApprovals(a);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load overview"))
      .finally(() => setLoading(false));
  }, []);

  const confirmedCount = findings.filter((f) => f.status === "confirmed").length;
  const activeScans = scans.filter((s) => s.stage !== "done" && s.stage !== "failed").length;

  return (
    <div>
      <h1>Overview</h1>
      <p className="muted">Aegis Mesh authorized security-testing orchestration platform.</p>
      {error && <div className="form-error">{error}</div>}
      {!loading && (
        <div className="stat-grid">
          <StatCard label="Targets" value={targets.length} href="/targets" />
          <StatCard label="Active scans" value={activeScans} href="/scans" />
          <StatCard
            label="Pending approvals"
            value={approvals.length}
            href="/approvals"
            highlight={approvals.length > 0}
          />
          <StatCard
            label="Confirmed findings"
            value={confirmedCount}
            href="/findings"
            highlight={confirmedCount > 0}
          />
        </div>
      )}
    </div>
  );
}

export default function OverviewPage() {
  return (
    <RequireAuth>
      <OverviewContent />
    </RequireAuth>
  );
}
