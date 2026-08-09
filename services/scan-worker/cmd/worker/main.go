package main

import (
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"bugorchestrator/scan-worker/internal/httpapi"
)

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		log.Printf("invalid int for %s=%q, using default %d", key, v, fallback)
		return fallback
	}
	return n
}

func main() {
	host := env("SCAN_WORKER_HOST", "0.0.0.0")
	port := env("SCAN_WORKER_PORT", "8090")
	defaultTimeout := envInt("SCAN_WORKER_DEFAULT_TIMEOUT_SECONDS", 300)
	maxConcurrency := envInt("SCAN_WORKER_MAX_CONCURRENCY", 5)

	cfg := httpapi.Config{
		NmapBinPath:     env("NMAP_BIN_PATH", "nmap"),
		HTTPXBinPath:    env("HTTPX_BIN_PATH", "httpx"),
		NucleiBinPath:   env("NUCLEI_BIN_PATH", "nuclei"),
		NucleiTemplates: env("NUCLEI_TEMPLATES_PATH", ""),
		DefaultTimeout:  time.Duration(defaultTimeout) * time.Second,
		MaxConcurrency:  maxConcurrency,
	}

	server := httpapi.NewServer(cfg)
	addr := host + ":" + port

	httpServer := &http.Server{
		Addr:              addr,
		Handler:           server.Routes(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	log.Printf("bugorchestrator scan-worker listening on %s (max_concurrency=%d, default_timeout=%s)", addr, maxConcurrency, cfg.DefaultTimeout)
	if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server error: %v", err)
	}
}
