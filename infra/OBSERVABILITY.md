# Observability Stack

This directory contains the OpenTelemetry observability stack configuration.

## Services

### OpenTelemetry Collector
- **Ports**: 
  - `4317` - OTLP gRPC receiver
  - `4318` - OTLP HTTP receiver  
  - `8889` - Prometheus metrics endpoint
- **Config**: `otel-collector-config.yaml`
- Receives metrics and logs from the API
- Exports metrics to Prometheus
- Exports logs to Loki

### Loki
- **Port**: `3100`
- Log aggregation system
- Receives logs from OTEL Collector
- Stores logs for querying in Grafana

### Prometheus
- **Port**: `9090`
- **Config**: `prometheus.yml`
- Scrapes metrics from the OTEL Collector
- Stores time-series metrics data

### Grafana
- **Port**: `3001`
- **Default credentials**: `admin` / `admin` (set via `GRAFANA_USER` and `GRAFANA_PASSWORD` env vars)
- **Dashboards**: Pre-configured dashboard at `/var/lib/grafana/dashboards/application-metrics.json`
- Visualizes metrics from Prometheus

## Usage

### Starting the Stack

```bash
# Start all services including observability stack
docker compose -f infra/docker-compose.yml up -d

# Or start just the observability services
docker compose -f infra/docker-compose.yml up -d otel-collector prometheus grafana
```

### Accessing Dashboards

- **Grafana**: http://localhost:3001
  - Login with default credentials: `admin` / `admin`
  - The "Application Metrics" dashboard should be available automatically
  - **Logs**: Navigate to "Explore" and select "Loki" datasource to query logs
  - Example log queries:
    - `{service_name="CE Ireland Zone"}` - All logs from the service
    - `{level="ERROR"}` - Error logs only
    - `{request_id="..."}` - Logs for a specific request

- **Prometheus**: http://localhost:9090
  - Query interface for raw metrics
  - Example queries:
    - `rate(http_requests_total[5m])`
    - `histogram_quantile(0.95, rate(http_request_duration_ms_bucket[5m]))`

- **Loki**: http://localhost:3100
  - Log query API (typically accessed via Grafana)

### Configuration

The API automatically sends metrics and logs to the OTEL Collector when:
- `OTEL_EXPORTER_OTLP_ENDPOINT` is set (defaults to `http://otel-collector:4318` in docker-compose)
- `ENABLE_METRICS=true` (default)
- `LOG_FORMAT=json` (default) - Structured JSON logging is required for proper parsing

**Logging**:
- Logs are already structured JSON format
- OpenTelemetry LoggingInstrumentor automatically captures Python logging
- Logs are sent via OTLP to the collector, which forwards them to Loki
- Logs are also still written to stdout for local viewing

### Metrics Available

The following metrics are automatically emitted:

- **HTTP Metrics**:
  - `http_requests_total` - Total HTTP requests (counter)
  - `http_request_duration_ms` - Request duration histogram
  - `http_active_requests` - Active concurrent requests (up/down counter)

- **Database Metrics**:
  - `database_queries_total` - Total database queries (counter)
  - `database_query_duration_ms` - Query duration histogram

- **Redis Metrics**:
  - `redis_operations_total` - Total Redis operations (counter)
  - `redis_operation_duration_ms` - Operation duration histogram

- **Error Metrics**:
  - `errors_total` - Total errors (counter)

- **Business Metrics**:
  - `business_metrics_total` - Custom business events (counter)

### Query Parameters

Query parameters are included in HTTP metrics as attributes (limited to 5 parameters to avoid high cardinality). They appear as `http.query.{param_name}` attributes.

### Active Requests Tracking

Active requests are tracked using an UpDownCounter:
- Incremented when a request starts
- Decremented when a request completes
- Provides real-time gauge of concurrent requests

## Troubleshooting

### Metrics Not Appearing

1. Check that `ENABLE_METRICS=true` in your environment
2. Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is set correctly
3. Check OTEL Collector logs: `docker compose -f infra/docker-compose.yml logs otel-collector`
4. Verify Prometheus is scraping: http://localhost:9090/targets

### Grafana Not Showing Data

1. Verify Prometheus datasource is configured (should be automatic)
2. Check Prometheus has data: http://localhost:9090/graph?g0.expr=up
3. Check Grafana logs: `docker compose -f infra/docker-compose.yml logs grafana`

## Customization

### Adding Custom Dashboards

Place JSON dashboard files in `grafana/dashboards/` - they will be automatically loaded.

### Modifying Metrics Export

Edit `otel-collector-config.yaml` to add additional exporters (e.g., CloudWatch, Datadog, etc.).

### Changing Scrape Interval

Edit `prometheus.yml` to modify the `scrape_interval` and `evaluation_interval`.

