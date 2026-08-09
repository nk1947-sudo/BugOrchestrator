package runner

import (
	"context"
	"encoding/xml"
	"time"

	"bugorchestrator/scan-worker/internal/models"
)

type nmapXMLRun struct {
	Hosts []nmapXMLHost `xml:"host"`
}

type nmapXMLHost struct {
	Status  nmapXMLStatus    `xml:"status"`
	Address []nmapXMLAddress `xml:"address"`
	Ports   nmapXMLPorts     `xml:"ports"`
}

type nmapXMLStatus struct {
	State string `xml:"state,attr"`
}

type nmapXMLAddress struct {
	Addr     string `xml:"addr,attr"`
	AddrType string `xml:"addrtype,attr"`
}

type nmapXMLPorts struct {
	Port []nmapXMLPort `xml:"port"`
}

type nmapXMLPort struct {
	Protocol string         `xml:"protocol,attr"`
	PortID   int            `xml:"portid,attr"`
	State    nmapXMLState   `xml:"state"`
	Service  nmapXMLService `xml:"service"`
}

type nmapXMLState struct {
	State string `xml:"state,attr"`
}

type nmapXMLService struct {
	Name    string `xml:"name,attr"`
	Product string `xml:"product,attr"`
	Version string `xml:"version,attr"`
}

// RunNmap runs `nmap -oX - <extraArgs...> <target>` and parses the XML
// output. extraArgs is appended before the target, so callers can pass
// scan-type/timing flags (-sV, -Pn, -T4, ...); -oX - is always forced so the
// worker can parse the result regardless of what the caller passed.
func RunNmap(ctx context.Context, binPath, target string, extraArgs []string, timeout time.Duration) models.NmapResponse {
	resp := models.NmapResponse{Tool: "nmap", Target: target, Hosts: []models.NmapHost{}}

	if !ToolAvailable(binPath) {
		resp.Available = false
		resp.Error = ErrToolUnavailable.Error()
		return resp
	}
	resp.Available = true

	args := append([]string{"-oX", "-"}, extraArgs...)
	args = append(args, target)

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

	var parsed nmapXMLRun
	if xmlErr := xml.Unmarshal([]byte(stdout), &parsed); xmlErr != nil {
		resp.Success = false
		resp.Error = "failed to parse nmap XML output: " + xmlErr.Error()
		return resp
	}

	for _, h := range parsed.Hosts {
		host := models.NmapHost{Status: h.Status.State, Ports: []models.NmapPort{}}
		for _, a := range h.Address {
			if a.AddrType == "ipv4" || a.AddrType == "ipv6" || host.Address == "" {
				host.Address = a.Addr
			}
		}
		for _, p := range h.Ports.Port {
			host.Ports = append(host.Ports, models.NmapPort{
				Port:     p.PortID,
				Protocol: p.Protocol,
				State:    p.State.State,
				Service:  p.Service.Name,
				Product:  p.Service.Product,
				Version:  p.Service.Version,
			})
		}
		resp.Hosts = append(resp.Hosts, host)
	}

	resp.Success = true
	return resp
}
