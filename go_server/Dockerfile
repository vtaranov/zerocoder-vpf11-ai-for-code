FROM --platform=$BUILDPLATFORM golang:1.27.3-alpine AS build
ARG TARGETOS TARGETARCH
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -trimpath -o /server ./cmd/server

FROM alpine:3.23
RUN addgroup -S app && adduser -S -G app app && mkdir /data && chown app:app /data
USER app
WORKDIR /data
ENV LISTEN_ADDR=0.0.0.0:8080 DATABASE_PATH=/data/users.db
EXPOSE 8080
ENTRYPOINT ["/server"]
COPY --from=build /server /server
