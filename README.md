# Darwin

Plataforma que detecta gargalos de performance em uma aplicação Spring Boot, gera patches de código, valida o resultado em sandbox e só promove o que melhora as métricas.

## Fluxo

```
Detector -> Orchestrator -> Generator -> Sandbox Runner -> Evaluator -> promote / rollback
```

1. O **Detector** consulta o Prometheus e identifica hotspots (latência, erros, CPU).
2. O **Orchestrator** cria um ciclo para cada hotspot e coordena as etapas.
3. O **Generator** aplica uma heurística (timeout, pool de conexões ou cache) em um branch do repositório.
4. O **Sandbox Runner** mede as métricas da versão original e do patch.
5. O **Evaluator** calcula o score. Regressões são sempre rejeitadas.
6. Patches aprovados são promovidos para `main`. É possível fazer rollback.

Cada ciclo é registrado no Postgres. Diffs e relatórios ficam no MinIO.

## Serviços

| Serviço | Porta |
|---------|-------|
| app (Spring Boot) | 8080 |
| evaluator | 5001 |
| generator | 5002 |
| orchestrator | 5003 |
| detector | 5004 |
| sandbox-runner | 9091 |
| Prometheus | 9090 |
| Grafana | 3000 |
| Jaeger | 16686 |
| MinIO (console) | 9001 |

## Executar

Requisitos: Docker com Compose v2.

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Para parar: `docker compose down`.

## Orchestrator API (porta 5003)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/hotspot` | Inicia ciclos a partir de hotspots |
| GET | `/cycles`, `/cycles/{id}` | Consulta ciclos |
| POST | `/cycles/{id}/approve` | Promove o patch para main |
| POST | `/cycles/{id}/reject` | Rejeita o ciclo |
| POST | `/cycles/{id}/rollback` | Reverte o commit promovido |

Com `AUTO_PROMOTE=false`, patches aprovados esperam `/approve`.

## Testes

```bash
pip install -r requirements-dev.txt
pytest tests/unit
python tests/integration/smoke_test.py   # com a stack no ar
```

## Documentação

- [DEVELOPMENT.md](DEVELOPMENT.md): ambiente de desenvolvimento
- [docs/arquitetura.md](docs/arquitetura.md): arquitetura
- [docs/design_decisions.md](docs/design_decisions.md): decisões de projeto
