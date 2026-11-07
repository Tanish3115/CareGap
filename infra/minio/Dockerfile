# Build the official, pinned source release; upstream public images are unavailable.
FROM golang:1.25-bookworm AS builder
ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z
RUN git clone --depth 1 --branch ${MINIO_RELEASE} https://github.com/minio/minio.git /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -o /out/minio .

FROM debian:bookworm-slim
RUN mkdir -p /data && chown 10001:10001 /data
COPY --from=builder /out/minio /usr/local/bin/minio
USER 10001:10001
EXPOSE 9000
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
