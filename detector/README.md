# Detector de Hotspots

O Detector de Hotspots é um dos principais módulos do ecossistema Darwin. Monitorando continuamente métricas via Prometheus, identifica pontos críticos de performance (hotspots) e envia eventos ao Orchestrator, que decide quando acionar o Generator/Evaluator.

---

## Função do módulo

- Observa métricas em tempo real no Prometheus.
- Aplica regras heurísticas simples (thresholds).
- Envia eventos HTTP para o Orchestrator (`POST /hotspot`) quando detecta problemas.

Critérios usados (exemplos):
- Latência alta: p95 acima do limiar (ex.: > 2s).
- Taxa de erro alta: non-2xx > 5%.
- Uso elevado de CPU: > 80%.

---

## Arquitetura

Prometheus ──▶ Detector ──▶ Orchestrator ──▶ Generator / Evaluator  
(Queries PromQL personalizadas)

O detector é implementado em FastAPI, roda um loop assíncrono periódico (intervalo configurável via variável de ambiente `CHECK_INTERVAL`) e adota uma abordagem pull-based (consulta direta ao Prometheus).

---

## Estrutura de diretórios

detector/  
├── detector.py               # Código principal (FastAPI + rotina de detecção)  
├── queries/                  # Consultas PromQL reutilizáveis  
│   ├── latency_query.promql  # p95 de latência por endpoint  
│   ├── error_query.promql    # taxa de erro por endpoint  
│   └── cpu_usage.promql      # uso médio de CPU por instância  
├── Dockerfile                # Imagem Docker do serviço  
└── requirements.txt          # Dependências Python

---

## Design Decisions

| Decisão | Descrição | Justificativa |
|---|---:|---|
| FastAPI | Framework web assíncrono em Python | Simples, performático e compatível com Uvicorn |
| PromQL externo | Queries salvas como arquivos `.promql` | Facilita manutenção e versionamento |
| Loop em background | Thread daemon em startup do FastAPI | Evita schedulers externos; simplifica dockerização |
| Comunicação HTTP JSON | Hotspots enviados ao Orchestrator | Baixo acoplamento e interoperabilidade |
| Detecção por thresholds | Limiar fixo (latência >2s, erro >5%, CPU >80%)

PROMETHEUS_URL=http://prometheus:9090
ORCHESTRATOR_URL=http://orchestrator:5003
CHECK_INTERVAL=30

Dockerfile

A imagem do detector é leve, baseada em python:3.11-slim:

FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5004
CMD ["uvicorn", "detector:app", "--host", "0.0.0.0", "--port", "5004"]

Exemplo de Logs

Durante a execução, o detector exibe logs descritivos:

Detector iniciado, monitorando métricas...
Iniciando varredura de métricas no Prometheus...
Nenhum hotspot detectado nesta varredura.
Hotspots detectados: 2
   -> /api/users - p95: 2.45s
   -> instance=node-1 - cpu_usage: 0.87
Enviando relatório ao Orchestrator...

Lógica Simplificada do Detector
while True:
    coletar_métricas_prometheus()
    identificar_hotspots(latência, erro, cpu)
    if hotspots_detectados:
        enviar_para_orchestrator()
    aguardar_intervalo()

 Teste Local

Suba o ambiente:

docker-compose up --build


Acesse o health-check:

curl http://localhost:5004/health


Saída esperada:

{"status": "ok", "interval": 30, "prometheus": "http://prometheus:9090"}


Para verificar consultas no Prometheus:

http://localhost:9090/graph

Cole uma das queries do diretório queries/.

 Integração com o Orchestrator

Quando um hotspot é identificado, o detector envia um POST:

POST /hotspot
Host: orchestrator
Content-Type: application/json


Body exemplo:

{
  "hotspots": [
    {"type": "latency", "endpoint": "/api/users", "p95": 2.4},
    {"type": "cpu_usage", "instance": "node-1", "usage": 0.87}
  ],
  "timestamp": 1739238461.0
}
