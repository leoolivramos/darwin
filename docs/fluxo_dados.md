# Fluxo de Dados — Sistema “Darwin”

## Visão Resumida

O fluxo de dados descreve o caminho desde a execução da aplicação principal (runtime) até a decisão de aplicar uma modificação em produção. É um ciclo de feedback fechado — cada saída influencia a próxima iteração.

---

## Runtime → Telemetria

A aplicação principal (Spring Boot) expõe métricas via Micrometer no endpoint `/actuator/prometheus`. Essas métricas incluem:

- Latência média e p95/p99 de endpoints;
- Taxa de erros (`error_rate`);
- Consumo de CPU e memória;
- Tempo médio de queries SQL.

O Prometheus realiza scrapes periódicos dessas métricas.

---

## Telemetria → Detector

O serviço `detector` consulta o Prometheus (`/api/v1/query`) usando consultas .promql, por exemplo:

- `latency_query.promql`
- `error_query.promql`
- `cpu_usage.promql`

As consultas são avaliadas em intervalos (ex.: 30s). Se o detector identificar degradação acima do limiar (ex.: `http_server_requests_seconds_p95 > 0.5`), ele dispara um evento de hotspot via REST para o Orchestrator.

---

## Detector → Generator

O `orchestrator` recebe o evento de hotspot e repassa para o serviço `generator`. Exemplo do payload:

```json
{
    "file": "/repo/src/main/java/com/example/darwin/config/HttpClientConfig.java",
    "reason": "High latency detected in /api/checkout"
}
```

O `generator` analisa o código-fonte e aplica heurísticas (AST) para criar um patch candidate. Um novo branch Git é criado (por exemplo `candidate_20251010_140200`).

---

## Generator → Sandbox Runner

Ao criar o patch, o `generator` aciona o pipeline do GitLab CI/CD, que builda e executa o candidato em ambiente isolado. Durante a execução:

- Testes unitários e de carga são executados;
- Métricas do candidato são coletadas e exportadas para Prometheus;
- Resultados e artefatos são armazenados no Silo (ex.: `/artifacts/tests/...`).

---

## Sandbox → Evaluator

O `evaluator` recebe métricas baseline e candidate em JSON, por exemplo:

```json
{
    "baseline": {"p95": 480, "error_rate": 0.01},
    "candidate": {"p95": 420, "error_rate": 0.01}
}
```

Ele calcula:

- Delta de desempenho (Δp95);
- Delta de erros (Δerror_rate);
- Score composto com pesos configuráveis.

A decisão é classificada como:

- `approve_auto`
- `require_review`
- `reject`

---

## Evaluator → Orchestrator → Deployer

Se a decisão for `approve_auto`, o `orchestrator` aciona o Canary Deployer:

- Cria um rollout inicial com 5% do tráfego;
- Monitora métricas por 5, 15 e 60 minutos;
- Se estável → amplia para 25%, 50% e 100%;
- Se ocorrer regressão → rollback automático.

---

## Auditoria e Registro

Cada decisão e execução são registradas no Silo e no banco de auditoria:

- Patch aplicado;
- Métricas comparativas;
- Logs de CI;
- Hash do commit e diff;
- Timestamp e score.

Esses dados podem ser consultados via painel Grafana ou API interna do `orchestrator`.

---

## Fechando o Ciclo

O sistema retorna ao início, reiniciando o monitoramento com a nova versão. Cada iteração representa uma “geração evolutiva” do software.

---