# 📘 Design Decisions — Darwin (ADRs)

## ADR-001 — Linguagens e Frameworks

**Decisão:**  
Utilizar Spring Boot (Java) como aplicação-alvo e Python (FastAPI) para microserviços auxiliares (generator, evaluator, orchestrator).

**Motivo:**  
Java reflete um ambiente corporativo real; Python oferece agilidade para prototipagem e integração com bibliotecas de análise.

---

## ADR-002 — Comunicação entre serviços

**Decisão:**  
Usar REST APIs sobre HTTP com endpoints documentados via OpenAPI/Swagger.

**Motivo:**  
Simplicidade, interoperabilidade e facilidade de teste/automação.

---

## ADR-003 — Coleta de métricas

**Decisão:**  
Usar Micrometer + Prometheus como backbone de telemetria.

**Motivo:**  
Integração nativa com Spring Boot e compatibilidade com Grafana/Alertmanager.

---

## ADR-004 — Geração de patches

**Decisão:**  
Usar heurísticas AST (JavaParser) em vez de IA nos estágios iniciais.

**Motivo:**  
Maior previsibilidade, segurança e auditabilidade. A IA será incorporada posteriormente como camada opcional.

---

## ADR-005 — Testes de candidatos

**Decisão:**  
Executar testes em sandboxes isoladas via Docker + GitLab CI.

**Motivo:**  
Garantir paridade com produção e evitar interferência no sistema principal.

---

## ADR-006 — Avaliação de resultados

**Decisão:**  
Implementar algoritmo de scoring ponderado no Evaluator.

**Fórmula (exemplo):**
```text
score = 0.5 * perf_improvement - 1.0 * error_penalty + 0.3 * resource_gain + 1.0 * test_pass_rate
```

**Motivo:**  
Balancear ganhos de desempenho com estabilidade e qualidade.

---

## ADR-007 — Armazenamento de artefatos

**Decisão:**  
Usar MinIO como storage local compatível com S3.

**Motivo:**  
Organização de logs, relatórios e diffs com compatibilidade para CI/CD.

---

## ADR-008 — Segurança e Segredos

**Decisão:**  
Manter segredos fora do repositório:

- `.env` apenas para variáveis genéricas;
- Docker Secrets e GitLab Secrets para tokens e chaves.

**Motivo:**  
Evitar exposição acidental de credenciais e seguir boas práticas DevSecOps.

---

## ADR-009 — Deploy Canário e Rollback

**Decisão:**  
Aplicar patches de forma gradual (5% → 25% → 100%) com monitoramento contínuo.

**Motivo:**  
Minimizar risco de regressões e possibilitar rollback automático.

---

## ADR-010 — Objetivo Acadêmico e Científico

**Decisão:**  
O projeto será uma plataforma de pesquisa experimental (não sistema comercial).

**Motivo:**  
Permitir liberdade arquitetural para análise científica de resultados.