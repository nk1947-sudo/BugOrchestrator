// Package httpapi wires the scan-worker's HTTP endpoints. Every scan
// endpoint runs through a bounded semaphore (Config.MaxConcurrency) so a
// burst of requests can't fork unbounded nmap/httpx/nuclei processes on the
// host.
package httpapi

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"aegis-mesh/scan-worker/internal/models"
	"aegis-mesh/scan-worker/internal/runner"
)

type Config struct {
	NmapBinPath     string
	HTTPXBinPath    string
	NucleiBinPath   string
	NucleiTemplates string
	DefaultTimeout  time.Duration
	MaxConcurrency  int
}

type Server struct {
	cfg  Config
	sema chan struct{}
}

func NewServer(cfg Config) *Server {
	if cfg.MaxConcurrency <= 0 {
		cfg.MaxConcurrency = 5
	}
	return &Server{cfg: cfg, sema: make(chan struct{}, cfg.MaxConcurrency)}
}

func (s *Server) Routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.handleHealth)
	mux.HandleFunc("POST /scan/nmap", s.handleNmap)
	mux.HandleFunc("POST /scan/httpx", s.handleHTTPX)
	mux.HandleFunc("POST /scan/nuclei", s.handleNuclei)
	return mux
}

func (s *Server) acquire() func() {
	s.sema <- struct{}{}
	return func() { <-s.sema }
}

func (s *Server) timeoutFor(requested int) time.Duration {
	if requested > 0 {
		return time.Duration(requested) * time.Second
	}
	return s.cfg.DefaultTimeout
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		log.Printf("failed to encode response: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, models.ErrorResponse{Error: msg})
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, models.HealthResponse{
		Status: "ok",
		Tools: map[string]bool{
			"nmap":   runner.ToolAvailable(s.cfg.NmapBinPath),
			"httpx":  runner.ToolAvailable(s.cfg.HTTPXBinPath),
			"nuclei": runner.ToolAvailable(s.cfg.NucleiBinPath),
		},
	})
}

func (s *Server) handleNmap(w http.ResponseWriter, r *http.Request) {
	var req models.NmapRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body: "+err.Error())
		return
	}
	if req.Target == "" {
		writeError(w, http.StatusBadRequest, "target is required")
		return
	}

	release := s.acquire()
	defer release()

	ctx, cancel := context.WithTimeout(r.Context(), s.timeoutFor(req.TimeoutSeconds)+5*time.Second)
	defer cancel()

	resp := runner.RunNmap(ctx, s.cfg.NmapBinPath, req.Target, req.Args, s.timeoutFor(req.TimeoutSeconds))
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleHTTPX(w http.ResponseWriter, r *http.Request) {
	var req models.HTTPXRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body: "+err.Error())
		return
	}
	if len(req.Targets) == 0 {
		writeError(w, http.StatusBadRequest, "targets is required and must be non-empty")
		return
	}

	release := s.acquire()
	defer release()

	ctx, cancel := context.WithTimeout(r.Context(), s.timeoutFor(req.TimeoutSeconds)+5*time.Second)
	defer cancel()

	resp := runner.RunHTTPX(ctx, s.cfg.HTTPXBinPath, req.Targets, req.Args, s.timeoutFor(req.TimeoutSeconds))
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleNuclei(w http.ResponseWriter, r *http.Request) {
	var req models.NucleiRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body: "+err.Error())
		return
	}
	if req.Target == "" {
		writeError(w, http.StatusBadRequest, "target is required")
		return
	}

	release := s.acquire()
	defer release()

	ctx, cancel := context.WithTimeout(r.Context(), s.timeoutFor(req.TimeoutSeconds)+5*time.Second)
	defer cancel()

	resp := runner.RunNuclei(ctx, s.cfg.NucleiBinPath, req.Target, req.Templates, req.Args, s.cfg.NucleiTemplates, s.timeoutFor(req.TimeoutSeconds))
	writeJSON(w, http.StatusOK, resp)
}
