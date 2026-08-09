package runner

import (
	"context"
	"encoding/json"
	"strings"
	"time"

	"bugorchestrator/scan-worker/internal/models"
)

type httpxJSONLine struct {
	URL           string   `json:"url"`
	StatusCode    int      `json:"status_code"`
	Title         string   `json:"title"`
	Webserver     string   `json:"webserver"`
	Tech          []string `json:"tech"`
	ContentLength int      `json:"content_length"`
}

// RunHTTPX runs `httpx -silent -json -l -` feeding targets over stdin (one
// per line) so target count isn't bounded by argv length, and parses the
// JSON-lines output. Malformed lines are skipped rather than failing the
// whole run - httpx occasionally interleaves non-JSON status lines even
// with -silent depending on version/flags.
func RunHTTPX(ctx context.Context, binPath string, targets []string, extraArgs []string, timeout time.Duration) models.HTTPXResponse {
	resp := models.HTTPXResponse{Tool: "httpx", Results: []models.HTTPXResult{}}

	if !ToolAvailable(binPath) {
		resp.Available = false
		resp.Error = ErrToolUnavailable.Error()
		return resp
	}
	resp.Available = true

	args := append([]string{"-silent", "-json", "-l", "-"}, extraArgs...)
	stdin := strings.Join(targets, "\n")

	start := time.Now()
	stdout, stderr, err := RunWithStdin(ctx, binPath, args, stdin, timeout)
	resp.DurationMs = time.Since(start).Milliseconds()
	resp.RawOutput = stdout

	if err != nil {
		resp.Success = false
		resp.Error = err.Error()
		if stderr != "" {
			resp.Error = resp.Error + ": " + stderr
		}
		return resp
	}

	for _, line := range strings.Split(stdout, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var parsed httpxJSONLine
		if jsonErr := json.Unmarshal([]byte(line), &parsed); jsonErr != nil {
			continue
		}
		resp.Results = append(resp.Results, models.HTTPXResult{
			URL:           parsed.URL,
			StatusCode:    parsed.StatusCode,
			Title:         parsed.Title,
			Webserver:     parsed.Webserver,
			Technologies:  parsed.Tech,
			ContentLength: parsed.ContentLength,
		})
	}

	resp.Success = true
	return resp
}
