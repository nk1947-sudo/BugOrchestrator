package runner

import (
	"context"
	"encoding/json"
	"strings"
	"time"

	"aegis-mesh/scan-worker/internal/models"
)

type nucleiJSONLine struct {
	TemplateID string `json:"template-id"`
	Info       struct {
		Name        string `json:"name"`
		Severity    string `json:"severity"`
		Description string `json:"description"`
	} `json:"info"`
	MatchedAt string `json:"matched-at"`
}

// RunNuclei runs `nuclei -jsonl -silent -target <target> [-t <template>]...`
// and parses the JSON-lines output. Nuclei's own template set already
// enforces non-destructive, read-only checks by convention; this worker adds
// no extra safety beyond passing through whatever templates/args the caller
// selects, so template/category selection is where an operator keeps a scan
// non-destructive.
func RunNuclei(ctx context.Context, binPath, target string, templates []string, extraArgs []string, templatesPath string, timeout time.Duration) models.NucleiResponse {
	resp := models.NucleiResponse{Tool: "nuclei", Target: target, Findings: []models.NucleiFinding{}}

	if !ToolAvailable(binPath) {
		resp.Available = false
		resp.Error = ErrToolUnavailable.Error()
		return resp
	}
	resp.Available = true

	args := []string{"-jsonl", "-silent", "-target", target}
	if templatesPath != "" {
		args = append(args, "-templates-dir", templatesPath)
	}
	for _, t := range templates {
		args = append(args, "-t", t)
	}
	args = append(args, extraArgs...)

	start := time.Now()
	stdout, stderr, err := Run(ctx, binPath, args, timeout)
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
		var parsed nucleiJSONLine
		if jsonErr := json.Unmarshal([]byte(line), &parsed); jsonErr != nil {
			continue
		}
		resp.Findings = append(resp.Findings, models.NucleiFinding{
			TemplateID:  parsed.TemplateID,
			Name:        parsed.Info.Name,
			Severity:    parsed.Info.Severity,
			MatchedAt:   parsed.MatchedAt,
			Description: parsed.Info.Description,
		})
	}

	resp.Success = true
	return resp
}
