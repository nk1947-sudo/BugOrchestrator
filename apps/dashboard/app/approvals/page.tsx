"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/lib/require-auth";
import { api, ApiError } from "@/lib/api-client";
import type { Approval } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { useLiveEvents } from "@/lib/use-live-events";

function ApprovalsContent() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  function load() {
    api
      .listApprovals("pending")
      .then(setApprovals)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load approvals"));
  }

  useEffect(load, []);
  useLiveEvents((type) => {
    if (type.startsWith("approval.")) load();
  });

  async function decide(id: string, approve: boolean) {
    setBusyId(id);
    setError(null);
    try {
      await api.decideApproval(id, approve, notes[id]);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to record decision");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1>Approvals</h1>
      <p className="muted">
        Every high-impact action - admin-route access, destructive state changes, aggressive
        payloads, and WAF/access-control bypass attempts - waits here for a human decision before
        the orchestrator executes it.
      </p>
      {error && <div className="form-error">{error}</div>}
      <div className="approval-list">
        {approvals.map((a) => (
          <div key={a.id} className="approval-card">
            <div className="finding-header">
              <Badge value={a.category} />
              <span className="muted">{new Date(a.requested_at).toLocaleString()}</span>
            </div>
            <p>{a.action_description}</p>
            {a.planned_request && <pre className="mono planned-request">{a.planned_request}</pre>}
            <textarea
              placeholder="Optional decision note"
              value={notes[a.id] || ""}
              onChange={(e) => setNotes((n) => ({ ...n, [a.id]: e.target.value }))}
            />
            <div className="approval-actions">
              <button className="btn-primary" disabled={busyId === a.id} onClick={() => decide(a.id, true)}>
                Approve
              </button>
              <button className="btn-danger" disabled={busyId === a.id} onClick={() => decide(a.id, false)}>
                Reject
              </button>
            </div>
          </div>
        ))}
        {approvals.length === 0 && <p className="empty-row">No pending approvals</p>}
      </div>
    </div>
  );
}

export default function ApprovalsPage() {
  return (
    <RequireAuth>
      <ApprovalsContent />
    </RequireAuth>
  );
}
