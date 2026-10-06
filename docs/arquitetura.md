# Arquitetura do Sistema — Projeto “Darwin”

## 1. Visão Geral

O **Darwin** é um ecossistema distribuído de serviços que simulam o comportamento de um sistema “vivo”, capaz de **monitorar seu desempenho, gerar variações de código, testar hipóteses e evoluir de forma autônoma**.

A arquitetura é **modular, desacoplada e containerizada**, construída sobre o conceito de *auto-otimização contínua*.

---

## 2. Macroarquitetura

O sistema é dividido em **quatro camadas principais**:

| Camada | Descrição | Tecnologias |
|--------|-----------|-------------|
| **Runtime & Telemetria** | Executa a aplicação-alvo e coleta métricas de uso. | Spring Boot, Micrometer, Prometheus, Grafana |
| **Análise & Geração** | Detecta gargalos e cria variações de código candidatas. | Python (FastAPI, JavaParser, GitPython) |
| **Avaliação & Orquestração** | Testa, avalia e decide quais versões são promovidas. | FastAPI, Pandas, Docker, GitLab CI/CD |
| **Governança & Observabilidade** | Registra decisões, logs, artefatos e auditoria. | MinIO, Jaeger, Loki, Grafana |

---

## 3. Componentes Principais

### 3.1. Runtime App (Organismo Vivo)
- Aplicação base em **Spring Boot**, representando um sistema real (serviços REST, banco de dados, etc.).
- Instrumentado com **Micrometer** para coletar métricas como latência, erro e throughput.
- Arquivo `HttpClientConfig.java` serve como ponto de mutação controlada — o sistema poderá alterar suas configurações automaticamente.

---

### 3.2. Telemetria & Monitoramento
- **Prometheus** coleta métricas expostas pela aplicação (`/actuator/prometheus`).
- **Grafana** visualiza a evolução das métricas.
- **Jaeger** captura traces distribuídos.
- **Loki** centraliza logs.

Esses componentes formam a base para a detecção de *hotspots* e análise de desempenho.

---

### 3.3. Detector (Hotspot Detector)
- Serviço que consulta periodicamente o Prometheus e identifica endpoints ou métodos com degradação de performance.
- Exemplo de regra (PromQL):

```promql
increase(http_server_requests_seconds_count[5m]) > 0
and histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le, method)) > 0.5
```

- Quando um hotspot é detectado, o Detector envia uma requisição POST para o **Orchestrator**, disparando o ciclo de autoajuste.

---

### 3.4. Generator (Gerador de Patches)
- Responsável por criar modificações no código-fonte com base em heurísticas pré-definidas ou IA.
- Utiliza:
    - **JavaParser** para análise e manipulação de AST (Abstract Syntax Tree).
    - **GitPython** para versionamento e criação de branches (`candidate/<id>`).
- Exemplo de heurística: reduzir timeout de `5000ms` para `3000ms` em `HttpClientConfig.java` ao detectar latência excessiva.

---

### 3.5. Sandbox Runner
- Cada `candidate` branch é compilado e testado isoladamente.
- A infraestrutura é gerenciada via **GitLab CI/CD** e **Docker**.
- Executa:
    - Testes unitários (JUnit)
    - Testes de integração (Testcontainers)
    - Testes de carga (k6/Gatling)
- Exporta resultados de métricas para o **Evaluator**.

---

### 3.6. Evaluator
- Analisa os resultados de desempenho do *candidate* versus o *baseline*.
- Calcula um **score de melhoria**, com base em métricas ponderadas:
    - Δ Latência (p95)
    - Δ Taxa de erro
    - Δ Throughput
    - Δ Consumo de recursos
    - Δ Cobertura de testes
- Retorna uma decisão: `approve_auto`, `require_manual_review`, ou `reject`.

---

### 3.7. Orchestrator
- Coordena todo o ciclo:
    1. Recebe alerta do Detector.
    2. Solicita patch ao Generator.
    3. Aciona pipeline Sandbox Runner.
    4. Consulta resultados do Evaluator.
    5. Aplica (ou reverte) via Canary Deployment.
- Implementado em **FastAPI**.
- Possui logs e trilha de auditoria em **MinIO**.

---

### 3.8. Governance & Audit
- Registra todas as execuções, decisões e artefatos.
- Garante:
    - Reprodutibilidade
    - Transparência
    - Possibilidade de rollback
- Dados são versionados e armazenados no **MinIO** (S3-like storage).

---

## 4. Fluxo de Execução

1. O runtime expõe métricas (Micrometer → Prometheus).  
2. O Detector identifica anomalias.  
3. O Orchestrator solicita modificação ao Generator.  
4. O Generator cria um patch (`candidate` branch).  
5. O pipeline Sandbox Runner executa testes.  
6. O Evaluator compara métricas.  
7. O Orchestrator decide aplicar via Canary Deployment.  
8. Tudo é registrado no MinIO/Auditor.

---

## 5. Comunicação entre Serviços

| Origem | Destino | Protocolo | Porta | Finalidade |
|--------|---------|-----------|-------|------------|
| App | Prometheus | HTTP | 8080 → 9090 | Métricas |
| Detector | Orchestrator | REST | 5002 | Alertas de hotspot |
| Orchestrator | Generator | REST | 5000 | Solicitação de patch |
| Orchestrator | Evaluator | REST | 5001 | Envio de resultados |
| Sandbox Runner | Evaluator | REST | 5001 | Métricas de teste |
| Orchestrator | MinIO | S3 API | 9000 | Logs e snapshots |

---

## 6. Escalabilidade e Extensões Futuras

- Uso de **Kubernetes (k3s)** para escalar runners e serviços.
- Integração com **TinyLlama** para geração inteligente de código.
- Indexação histórica de commits em **FAISS/SQLite** para aprendizado incremental.
- Interface de revisão humana (UI web) para auditoria.

---

## 7. Segurança e Ética

- Nenhum patch é aplicado em módulos críticos sem revisão manual.
- Patches são limitados a escopo local (1–2 métodos).
- Logs imutáveis e rastreáveis.
- Uso opcional de revisão humana (Human-in-loop).

---

> _“O software que se reescreve é o primeiro passo para sistemas que aprendem a evoluir.”_
