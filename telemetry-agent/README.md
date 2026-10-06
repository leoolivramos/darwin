# 📊 Telemetry Agent — Coletor de Observabilidade

O **Telemetry Agent** é um serviço Python responsável por coletar métricas, logs e traces distribuídos da aplicação e exportá-los para os sistemas de observabilidade (Prometheus, Loki, Jaeger).

## 🎯 Responsabilidades

- Coletar métricas da aplicação via Micrometer/client libraries
- Exportar métricas para Prometheus
- Agregar e exportar logs estruturados para Loki
- Rastrear distribuído com Jaeger
- Garantir coleta sem perda de dados

## 🛠️ Stack Técnico

- **Framework**: Instrumentation Agent / OpenTelemetry SDK
- **Exportadores**: Prometheus, Loki, Jaeger
- **Linguagem**: Python 3.10+
- **Protocolos**: gRPC, HTTP, UDP

## 📋 Instalação

```bash
cd telemetry-agent
pip install -r requirements.txt
```

## ⚙️ Configuração

Variáveis de ambiente:

```env
JAEGER_ENDPOINT=http://jaeger:14268/api/traces
LOKI_ENDPOINT=http://loki:3100
PROMETHEUS_ENDPOINT=http://prometheus:9090
LOG_LEVEL=INFO
```

## 🚀 Execução

### Local

```bash
python src/telemetry_collector.py
```

### Docker

```bash
docker build -t darwin-telemetry .
docker run -e JAEGER_ENDPOINT=http://jaeger:14268/api/traces \
           -e LOKI_ENDPOINT=http://loki:3100 \
           darwin-telemetry
```

## 📡 Exportadores

### Prometheus Exporter
- Porta: 8000
- Endpoint: `/metrics`
- Formato: Prometheus text format

### Jaeger Exporter
- Endpoint: http://jaeger:14268/api/traces
- Protocolo: HTTP Thrift
- Taxa de amostragem: configurável

### Loki Exporter
- Endpoint: http://loki:3100
- Protocolo: HTTP Push
- Rótulos: service, environment, level

## 🔍 Métricas Coletadas

- **HTTP**: latência, status codes, throughput
- **JVM**: heap, threads, GC
- **Database**: conexões, queries lentas
- **Cache**: hit rate, evictions
- **Custom**: métricas da aplicação

## 🧪 Testes

```bash
pytest tests/unit -v
pytest tests/integration -v
```

## 🔐 Segurança

- TLS opcional para OTLP
- Validação de endpoints
- Sem PII nos logs/traces
- Redação de dados sensíveis

## 📚 Documentação Adicional

- [OpenTelemetry](https://opentelemetry.io)
- [Jaeger Documentation](https://www.jaegertracing.io/docs)
- [Loki Documentation](https://grafana.com/docs/loki)