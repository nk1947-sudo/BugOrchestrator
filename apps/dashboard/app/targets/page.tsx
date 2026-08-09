"use client";

import { useEffect, useState, type FormEvent } from "react";
import { RequireAuth } from "@/lib/require-auth";
import { api, ApiError } from "@/lib/api-client";
import type { Target } from "@/lib/types";
import { Badge } from "@/components/Badge";

function TargetsContent() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authNote, setAuthNote] = useState("");
  const [passiveOnly, setPassiveOnly] = useState(true);

  function load() {
    api
      .listTargets()
      .then(setTargets)
      .catch((err) => setListError(err instanceof ApiError ? err.message : "Failed to load targets"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await api.createTarget({
        name,
        base_url: baseUrl,
        authorization_note: authNote,
        passive_only: passiveOnly,
      });
      setName("");
      setBaseUrl("");
      setAuthNote("");
      setPassiveOnly(true);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create target");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStartScan(id: string) {
    try {
      await api.startScan(id);
      window.alert("Scan queued - the orchestrator picks it up on its next poll cycle.");
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Failed to start scan");
    }
  }

  async function handleToggleMode(target: Target) {
    const goingActive = target.passive_only;
    if (
      goingActive &&
      !window.confirm(
        `Switch "${target.name}" to ACTIVE mode? The orchestrator will start sending real ` +
          "requests to it (recon probes, and - once approved via the HITL queue - active " +
          "tests). Only do this if you've confirmed the target's authorization explicitly " +
          "permits automated scanning."
      )
    ) {
      return;
    }
    try {
      await api.updateTarget(target.id, { passive_only: !target.passive_only });
      load();
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Failed to update target");
    }
  }

  return (
    <div>
      <h1>Targets</h1>
      <p className="muted">
        Inject a target you are authorized to test. The authorization note is recorded for audit -
        it is not independently verified, so only add targets covered by a program you&rsquo;re
        enrolled in or that you own outright.
      </p>

      <form className="card form-inline" onSubmit={handleCreate}>
        <div className="form-row">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Base URL
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://app.example.com"
              required
            />
          </label>
        </div>
        <label>
          Authorization note
          <textarea
            value={authNote}
            onChange={(e) => setAuthNote(e.target.value)}
            placeholder="HackerOne program h1-example, enrolled 2026-01-15 - or an ownership statement"
            required
            minLength={10}
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={passiveOnly}
            onChange={(e) => setPassiveOnly(e.target.checked)}
          />
          Passive only - no automated scanning (recommended; uncheck only once you&rsquo;ve
          confirmed the target&rsquo;s authorization explicitly permits automated scanning)
        </label>
        {formError && <div className="form-error">{formError}</div>}
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Adding…" : "Inject target"}
        </button>
      </form>

      {loading ? (
        <p className="muted">Loading…</p>
      ) : listError ? (
        <div className="form-error">{listError}</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Base URL</th>
              <th>Status</th>
              <th>Mode</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {targets.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td className="mono">{t.base_url}</td>
                <td>
                  <Badge value={t.status} />
                </td>
                <td>
                  <Badge value={t.passive_only ? "mode: passive" : "mode: active"} />
                </td>
                <td>{new Date(t.created_at).toLocaleString()}</td>
                <td className="row-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => handleStartScan(t.id)}
                    disabled={t.status !== "active"}
                  >
                    Start scan
                  </button>
                  <button className="btn-secondary" onClick={() => handleToggleMode(t)}>
                    {t.passive_only ? "Enable active scanning" : "Switch to passive"}
                  </button>
                </td>
              </tr>
            ))}
            {targets.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-row">
                  No targets yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function TargetsPage() {
  return (
    <RequireAuth>
      <TargetsContent />
    </RequireAuth>
  );
}
