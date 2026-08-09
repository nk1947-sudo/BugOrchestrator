const COLORS: Record<string, string> = {
  critical: "badge-critical",
  high: "badge-high",
  medium: "badge-medium",
  low: "badge-low",
  info: "badge-info",
  confirmed: "badge-critical",
  unconfirmed: "badge-medium",
  false_positive: "badge-low",
  pending: "badge-medium",
  approved: "badge-ok",
  rejected: "badge-low",
  expired: "badge-low",
  active: "badge-ok",
  paused: "badge-medium",
  archived: "badge-low",
  done: "badge-ok",
  failed: "badge-critical",
  awaiting_approval: "badge-medium",
  admin_access: "badge-high",
  destructive_state_change: "badge-critical",
  aggressive_payload: "badge-high",
  waf_bypass: "badge-critical",
  "mode: passive": "badge-ok",
  "mode: active": "badge-high",
};

export function Badge({ value }: { value: string }) {
  const cls = COLORS[value] || "badge-info";
  return <span className={`badge ${cls}`}>{value.replace(/_/g, " ")}</span>;
}
