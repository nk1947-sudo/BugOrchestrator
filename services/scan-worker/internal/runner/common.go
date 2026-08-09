// Package runner shells out to local recon/scan binaries (nmap, httpx,
// nuclei) with a bounded timeout and returns structured results. All
// commands are built as argv slices via exec.CommandContext - arguments are
// never interpolated into a shell string, so there is no shell-injection
// surface regardless of what a caller passes as target/args.
package runner

import (
	"bytes"
	"context"
	"errors"
	"os/exec"
	"time"
)

// ErrToolUnavailable means the configured binary was not found on PATH (or
// at the configured absolute path). Callers should report this as
// `available: false` rather than a hard failure.
var ErrToolUnavailable = errors.New("tool binary not found")

// ErrTimedOut means the command did not finish within the requested timeout.
var ErrTimedOut = errors.New("command timed out")

func ToolAvailable(binPath string) bool {
	_, err := exec.LookPath(binPath)
	return err == nil
}

// Run executes binPath with args, capturing stdout/stderr separately, bounded
// by timeout. It does not treat a non-zero exit code as an error by itself -
// nmap/nuclei/httpx commonly exit non-zero on "no results" or partial
// failures - the caller decides how to interpret exit code + stderr.
func Run(ctx context.Context, binPath string, args []string, timeout time.Duration) (stdout string, stderr string, err error) {
	return RunWithStdin(ctx, binPath, args, "", timeout)
}

// RunWithStdin is Run, plus stdin content piped to the child process (used
// by httpx, which reads its target list from stdin with `-l -`).
func RunWithStdin(ctx context.Context, binPath string, args []string, stdin string, timeout time.Duration) (stdout string, stderr string, err error) {
	if !ToolAvailable(binPath) {
		return "", "", ErrToolUnavailable
	}

	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(runCtx, binPath, args...)
	var outBuf, errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	if stdin != "" {
		cmd.Stdin = bytes.NewBufferString(stdin)
	}

	runErr := cmd.Run()
	stdout, stderr = outBuf.String(), errBuf.String()

	if runCtx.Err() == context.DeadlineExceeded {
		return stdout, stderr, ErrTimedOut
	}
	if runErr != nil {
		var exitErr *exec.ExitError
		if errors.As(runErr, &exitErr) {
			// Non-zero exit: return output as-is, let the caller decide.
			return stdout, stderr, nil
		}
		return stdout, stderr, runErr
	}
	return stdout, stderr, nil
}
