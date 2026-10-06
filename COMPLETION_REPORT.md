# Status de Implementação — Código Vivo

## Ciclo implementado

```
Detector -> Orchestrator -> Generator (patch real em branch)
         -> Sandbox Runner (baseline vs candidato, métricas reais)
         -> Evaluator (score; regressões sempre rejeitadas)
         -> promote em main (auto ou aprovação humana) -> rollback
```

Todo ciclo é auditado no Postgres; diffs e relatórios ficam no MinIO.

## Endpoints do Orchestrator (porta 5003)

| Método | Rota | Função |
|--------|------|--------|
| POST | `/hotspot` | Inicia ciclos a partir de hotspots |
| GET | `/cycles`, `/cycles/{id}` | Consulta ciclos |
| POST | `/cycles/{id}/approve` | Promove o patch para main |
| POST | `/cycles/{id}/reject` | Rejeita o ciclo |
| POST | `/cycles/{id}/rollback` | Reverte o commit promovido |

`AUTO_PROMOTE=false` exige aprovação humana via `/approve`.

## Verificação

- Testes unitários: `pytest tests/unit` (41 passando).
- Smoke test de integração: `tests/integration/smoke_test.py` (executado no CI com `docker compose up --wait`).

## Limitações conhecidas

- Heurísticas limitadas a timeout, pool de conexões e cache em código Java.
- Credenciais do `.env` já commitadas no histórico devem ser rotacionadas.
- Fluxo completo com Docker não foi validado nesta máquina; depende do CI.
