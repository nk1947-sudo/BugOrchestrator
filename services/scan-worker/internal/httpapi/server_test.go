package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"bugorchestrator/scan-worker/internal/models"
)

func testServer() *Server {
	return NewServer(Config{
		NmapBinPath:    "definitely-not-a-real-binary-xyz",
		HTTPXBinPath:   "definitely-not-a-real-binary-xyz",
		NucleiBinPath:  "definitely-not-a-real-binary-xyz",
		DefaultTimeout: 5 * time.Second,
		MaxConcurrency: 2,
	})
}

func TestHealthReportsUnavailableTools(t *testing.T) {
	s := testServer()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var body models.HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if body.Tools["nmap"] {
		t.Fatalf("expected nmap to be reported unavailable")
	}
}

func TestNmapMissingTargetReturns400(t *testing.T) {
	s := testServer()
	req := httptest.NewRequest(http.MethodPost, "/scan/nmap", strings.NewReader(`{}`))
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestNmapReportsToolUnavailableNotServerError(t *testing.T) {
	s := testServer()
	body := `{"target": "scanme.example.test"}`
	req := httptest.NewRequest(http.MethodPost, "/scan/nmap", strings.NewReader(body))
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 (tool-unavailable is reported in the body, not as an HTTP error), got %d", rec.Code)
	}
	var resp models.NmapResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if resp.Available {
		t.Fatalf("expected available=false for a nonexistent binary")
	}
}

func TestHTTPXRequiresNonEmptyTargets(t *testing.T) {
	s := testServer()
	req := httptest.NewRequest(http.MethodPost, "/scan/httpx", strings.NewReader(`{"targets": []}`))
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}
