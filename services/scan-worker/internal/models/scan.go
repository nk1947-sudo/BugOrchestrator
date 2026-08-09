// Package models holds the JSON request/response contracts for the
// scan-worker HTTP API. Every response includes `available` (whether the
// underlying binary was found on PATH) separately from `success` (whether
// the run completed without error), so callers can distinguish "tool not
// installed" from "tool ran and found nothing" from "tool errored".
package models

type NmapPort struct {
	Port     int    `json:"port"`
	Protocol string `json:"protocol"`
	State    string `json:"state"`
	Service  string `json:"service,omitempty"`
	Product  string `json:"product,omitempty"`
	Version  string `json:"version,omitempty"`
}

type NmapHost struct {
	Address string     `json:"address"`
	Status  string     `json:"status"`
	Ports   []NmapPort `json:"ports"`
}

type NmapRequest struct {
	Target         string   `json:"target"`
	Args           []string `json:"args,omitempty"`
	TimeoutSeconds int      `json:"timeout_seconds,omitempty"`
}

type NmapResponse struct {
	Tool       string     `json:"tool"`
	Available  bool       `json:"available"`
	Success    bool       `json:"success"`
	Target     string     `json:"target"`
	DurationMs int64      `json:"duration_ms"`
	Error      string     `json:"error,omitempty"`
	RawOutput  string     `json:"raw_output,omitempty"`
	Hosts      []NmapHost `json:"hosts"`
}

type HTTPXRequest struct {
	Targets        []string `json:"targets"`
	Args           []string `json:"args,omitempty"`
	TimeoutSeconds int      `json:"timeout_seconds,omitempty"`
}

type HTTPXResult struct {
	URL           string   `json:"url"`
	StatusCode    int      `json:"status_code,omitempty"`
	Title         string   `json:"title,omitempty"`
	Webserver     string   `json:"webserver,omitempty"`
	Technologies  []string `json:"tech,omitempty"`
	ContentLength int      `json:"content_length,omitempty"`
}

type HTTPXResponse struct {
	Tool       string        `json:"tool"`
	Available  bool          `json:"available"`
	Success    bool          `json:"success"`
	DurationMs int64         `json:"duration_ms"`
	Error      string        `json:"error,omitempty"`
	RawOutput  string        `json:"raw_output,omitempty"`
	Results    []HTTPXResult `json:"results"`
}

type NucleiRequest struct {
	Target         string   `json:"target"`
	Templates      []string `json:"templates,omitempty"`
	Args           []string `json:"args,omitempty"`
	TimeoutSeconds int      `json:"timeout_seconds,omitempty"`
}

type NucleiFinding struct {
	TemplateID  string `json:"template_id"`
	Name        string `json:"name,omitempty"`
	Severity    string `json:"severity,omitempty"`
	MatchedAt   string `json:"matched_at,omitempty"`
	Description string `json:"description,omitempty"`
}

type NucleiResponse struct {
	Tool       string          `json:"tool"`
	Available  bool            `json:"available"`
	Success    bool            `json:"success"`
	Target     string          `json:"target"`
	DurationMs int64           `json:"duration_ms"`
	Error      string          `json:"error,omitempty"`
	RawOutput  string          `json:"raw_output,omitempty"`
	Findings   []NucleiFinding `json:"findings"`
}

type HealthResponse struct {
	Status string          `json:"status"`
	Tools  map[string]bool `json:"tools"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}
