# Observability Integrations

Django Matt integrates with popular observability platforms for production monitoring.

## Supported Platforms

| Platform | Tracing | Metrics | Logging |
|----------|---------|---------|---------|
| Datadog | Yes | Yes | Yes |
| New Relic | Yes | Yes | Yes |
| Jaeger | Yes | - | - |
| Grafana (Tempo/Loki/Prometheus) | Yes | Yes | Yes |
| AWS X-Ray | Yes (via OTLP) | - | - |
| Honeycomb | Yes (via OTLP) | - | - |

## Datadog

Full APM integration with tracing, metrics, and logging.

### Installation

```bash
pip install ddtrace
```

### Configuration

```python
# settings.py
import os

DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": os.environ.get("DD_SERVICE", "myapp"),
    "EXPORTER": "datadog",
}

DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",
    "EXTRA_FIELDS": {
        "dd.service": os.environ.get("DD_SERVICE", "myapp"),
        "dd.env": os.environ.get("DD_ENV", "production"),
        "dd.version": os.environ.get("DD_VERSION", "1.0.0"),
    },
}
```

### Environment Variables

```bash
# Datadog configuration
export DD_SERVICE=myapp
export DD_ENV=production
export DD_VERSION=1.0.0
export DD_AGENT_HOST=localhost
export DD_TRACE_AGENT_PORT=8126
export DD_LOGS_INJECTION=true
export DD_PROFILING_ENABLED=true
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    environment:
      - DD_SERVICE=myapp
      - DD_ENV=production
      - DD_VERSION=1.0.0
      - DD_AGENT_HOST=datadog-agent
      - DD_TRACE_AGENT_PORT=8126
      - DD_LOGS_INJECTION=true
    depends_on:
      - datadog-agent

  datadog-agent:
    image: gcr.io/datadoghq/agent:latest
    environment:
      - DD_API_KEY=${DD_API_KEY}
      - DD_SITE=datadoghq.com  # or datadoghq.eu
      - DD_APM_ENABLED=true
      - DD_LOGS_ENABLED=true
      - DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true
      - DD_PROCESS_AGENT_ENABLED=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
    ports:
      - "8126:8126"  # APM
      - "8125:8125/udp"  # DogStatsD
```

### Datadog-Specific Tracing

Use the Datadog tracer directly:

```python
from django_matt.observability import datadog_trace, get_datadog_tracer

@datadog_trace("custom_operation", service="payment-service")
def process_payment(order):
    """Traced with Datadog tracer."""
    return payment_gateway.charge(order.total)

# Access tracer directly
dd_tracer = get_datadog_tracer()
if dd_tracer:
    with dd_tracer.trace("manual_span"):
        do_something()
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      labels:
        tags.datadoghq.com/env: production
        tags.datadoghq.com/service: myapp
        tags.datadoghq.com/version: "1.0.0"
    spec:
      containers:
        - name: app
          env:
            - name: DD_SERVICE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/service']
            - name: DD_ENV
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/env']
            - name: DD_VERSION
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/version']
            - name: DD_AGENT_HOST
              valueFrom:
                fieldRef:
                  fieldPath: status.hostIP
```

## New Relic

Full observability with APM, infrastructure, and logging.

### Installation

```bash
pip install newrelic
pip install opentelemetry-exporter-otlp  # For OTLP export
```

### Configuration

```python
# settings.py
import os

DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": os.environ.get("NEW_RELIC_APP_NAME", "myapp"),
    "EXPORTER": "newrelic",
    "ENDPOINT": "https://otlp.nr-data.net:4317",
    "HEADERS": {
        "api-key": os.environ.get("NEW_RELIC_LICENSE_KEY"),
    },
}
```

### Environment Variables

```bash
export NEW_RELIC_LICENSE_KEY=your-license-key
export NEW_RELIC_APP_NAME=myapp
export NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true
```

### Using newrelic.ini

Create `newrelic.ini` in your project root:

```ini
[newrelic]
license_key = YOUR_LICENSE_KEY
app_name = My Django App
distributed_tracing.enabled = true
monitor_mode = true
log_level = info
high_security = false
transaction_tracer.enabled = true
error_collector.enabled = true
```

### Application Startup

```python
# wsgi.py
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
application = newrelic.agent.WSGIApplicationWrapper(application)
```

### New Relic Specific Tracing

```python
from django_matt.observability import newrelic_trace

@newrelic_trace("custom_operation")
def process_order(order):
    """Traced with New Relic agent."""
    return process(order)
```

### Docker Compose Setup

```yaml
# docker-compose.yml
services:
  app:
    build: .
    environment:
      - NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}
      - NEW_RELIC_APP_NAME=myapp
      - NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true
    volumes:
      - ./newrelic.ini:/app/newrelic.ini:ro
```

## Jaeger

Open-source distributed tracing platform.

### Installation

```bash
pip install opentelemetry-exporter-jaeger
```

### Configuration

```python
# settings.py
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "jaeger",
    "ENDPOINT": "localhost:6831",  # Jaeger agent UDP port
}
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    environment:
      - DJANGO_MATT_TRACING__ENABLED=true
      - DJANGO_MATT_TRACING__EXPORTER=jaeger
      - DJANGO_MATT_TRACING__ENDPOINT=jaeger:6831
    depends_on:
      - jaeger

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"  # Thrift compact (agent)
      - "6832:6832/udp"  # Thrift binary (agent)
      - "16686:16686"    # UI
      - "14268:14268"    # HTTP collector
      - "14250:14250"    # gRPC collector
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411
```

### Access Jaeger UI

Open http://localhost:16686 to view traces.

### Production Jaeger with Elasticsearch

```yaml
# docker-compose.prod.yml
services:
  jaeger-collector:
    image: jaegertracing/jaeger-collector:latest
    environment:
      - SPAN_STORAGE_TYPE=elasticsearch
      - ES_SERVER_URLS=http://elasticsearch:9200
    ports:
      - "14268:14268"
      - "14250:14250"

  jaeger-query:
    image: jaegertracing/jaeger-query:latest
    environment:
      - SPAN_STORAGE_TYPE=elasticsearch
      - ES_SERVER_URLS=http://elasticsearch:9200
    ports:
      - "16686:16686"

  elasticsearch:
    image: elasticsearch:7.17.0
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
    volumes:
      - es_data:/usr/share/elasticsearch/data

volumes:
  es_data:
```

## Grafana Stack

Complete observability with Grafana, Tempo (tracing), Loki (logging), and Prometheus (metrics).

### Installation

```bash
pip install opentelemetry-exporter-otlp
pip install prometheus-client
```

### Configuration

```python
# settings.py
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://otel-collector:4317",
}

DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
}

DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",
}
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_MATT_TRACING__ENABLED=true
      - DJANGO_MATT_TRACING__EXPORTER=otlp
      - DJANGO_MATT_TRACING__ENDPOINT=http://otel-collector:4317
    depends_on:
      - otel-collector

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics

  # Grafana Tempo (Tracing)
  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
      - tempo_data:/tmp/tempo
    ports:
      - "3200:3200"   # Tempo API
      - "9095:9095"   # gRPC

  # Grafana Loki (Logging)
  loki:
    image: grafana/loki:latest
    command: ["-config.file=/etc/loki/local-config.yaml"]
    ports:
      - "3100:3100"

  # Prometheus (Metrics)
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  # Grafana (Visualization)
  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
      - tempo
      - loki

volumes:
  tempo_data:
```

### OpenTelemetry Collector Config

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

  prometheus:
    endpoint: "0.0.0.0:8889"

  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

### Tempo Config

```yaml
# tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

ingester:
  trace_idle_period: 10s
  max_block_bytes: 1_000_000
  max_block_duration: 5m

compactor:
  compaction:
    compacted_block_retention: 1h

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/blocks
```

### Prometheus Config

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'django-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/_matt/metrics'

  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
```

### Grafana Datasource Provisioning

```yaml
# grafana/provisioning/datasources/datasources.yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      tracesToLogs:
        datasourceUid: loki
        tags: ['job', 'instance']
        mappedTags: [{ key: 'service.name', value: 'service' }]
        mapTagNamesEnabled: true
        spanStartTimeShift: '1h'
        spanEndTimeShift: '1h'

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      derivedFields:
        - datasourceUid: tempo
          matcherRegex: '"trace_id":"(\w+)"'
          name: TraceID
          url: '$${__value.raw}'
```

## AWS X-Ray

Using OTLP with AWS Distro for OpenTelemetry.

### Configuration

```python
# settings.py
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://localhost:4317",  # ADOT collector
}
```

### AWS Distro Collector

```yaml
# docker-compose.yml
services:
  adot-collector:
    image: amazon/aws-otel-collector:latest
    command: ["--config=/etc/ecs/ecs-default-config.yaml"]
    environment:
      - AWS_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    ports:
      - "4317:4317"
      - "4318:4318"
```

## Honeycomb

Using OTLP export to Honeycomb.

### Configuration

```python
# settings.py
import os

DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "https://api.honeycomb.io:443",
    "HEADERS": {
        "x-honeycomb-team": os.environ.get("HONEYCOMB_API_KEY"),
        "x-honeycomb-dataset": os.environ.get("HONEYCOMB_DATASET", "myapp"),
    },
}
```

## Custom OTLP Backend

For any OTLP-compatible backend:

```python
# settings.py
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "https://your-otlp-endpoint:4317",
    "HEADERS": {
        "Authorization": f"Bearer {os.environ.get('OTLP_TOKEN')}",
        "X-Custom-Header": "value",
    },
}
```

## Verifying Integration

### Check Dependencies

```python
from django_matt.observability import (
    HAS_OPENTELEMETRY,
    HAS_PROMETHEUS,
    HAS_JAEGER,
    HAS_OTLP,
    HAS_DATADOG,
    HAS_NEWRELIC,
)

print(f"OpenTelemetry: {HAS_OPENTELEMETRY}")
print(f"Prometheus: {HAS_PROMETHEUS}")
print(f"Jaeger: {HAS_JAEGER}")
print(f"OTLP: {HAS_OTLP}")
print(f"Datadog: {HAS_DATADOG}")
print(f"New Relic: {HAS_NEWRELIC}")
```

### Check Info Endpoint

```bash
curl http://localhost:8000/_matt/info | jq .dependencies
```

### Verify Traces

```bash
# Make a request
curl http://localhost:8000/api/users

# Check Jaeger/Tempo/Datadog UI for traces
```

### Verify Metrics

```bash
# Check metrics endpoint
curl http://localhost:8000/_matt/metrics | head -50

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

## Troubleshooting

### No Traces Appearing

1. Check tracing is enabled:
```python
from django_matt.observability import tracing_config
print(f"Enabled: {tracing_config.enabled}")
print(f"Exporter: {tracing_config.exporter}")
```

2. Use console exporter for debugging:
```python
DJANGO_MATT_TRACING = {"EXPORTER": "console"}
```

3. Check network connectivity to collector

### Metrics Not Scraped

1. Verify metrics endpoint responds:
```bash
curl http://localhost:8000/_matt/metrics
```

2. Check Prometheus scrape config

3. Verify service discovery

### Logs Not Appearing

1. Check log format:
```python
DJANGO_MATT_LOGGING = {"FORMAT": "json"}
```

2. Verify log shipper configuration

3. Check index/stream in log platform
