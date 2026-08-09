FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -o /out/scan-worker ./cmd/worker

FROM alpine:3.20
# nmap/httpx/nuclei are intentionally NOT baked into this image - install
# them explicitly in environments where you want them available, so the
# image's capabilities are an explicit choice rather than a hidden default.
RUN apk add --no-cache ca-certificates nmap
COPY --from=build /out/scan-worker /usr/local/bin/scan-worker
EXPOSE 8090
ENTRYPOINT ["/usr/local/bin/scan-worker"]
