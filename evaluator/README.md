# ⚖️ Darwin – Evaluator

O Evaluator é o módulo responsável por comparar o desempenho entre uma versão baseline e uma versão candidata. Ele analisa métricas como latência, erro e uso de CPU, calcula um score ponderado e decide se a alteração deve ser:
- `approve_auto` — melhoria significativa e sem erros
- `review_manual` — resultado neutro; requer validação humana
- `reject` — regressão detectada

---

## ⚙️ Estrutura do projeto

```
evaluator/
├── evaluator.py            # Serviço FastAPI
├── metrics/
│   ├── baseline.json       # Métricas de referência
│   ├── candidate.json      # Métricas do candidato
│   └── scoring.py          # Comparação e pontuação
├── utils/
│   ├── report_builder.py   # Geração de relatório auditável
│   └── logger.py           # Logs coloridos e padronizados
└── README.md
```

---

## 🧮 Fórmula de avaliação

score = (Δlatência * 0.5) + (Δerro * 0.3) + (ΔCPU * 0.2)

Tabela de decisão:
| Score      | Decisão        | Descrição         |
|------------|----------------|-------------------|
| > 10       | ✅ approve_auto | Melhoria clara    |
| 0 – 10     | 🟡 review_manual| Resultado neutro  |
| < 0        | ❌ reject      | Piora de desempenho |

Observações:
- Δ (delta) é a redução percentual da métrica do baseline para o candidate:
    Δ = (baseline - candidate) / baseline * 100
- Pesos: latência 50%, erro 30%, CPU 20%.

### Exemplo de entrada

baseline.json
```json
{
    "latency_p95": 200,
    "error_rate": 0.02,
    "cpu_usage": 0.75
}
```

candidate.json
```json
{
    "latency_p95": 180,
    "error_rate": 0.01,
    "cpu_usage": 0.70
}
```

Cálculo dos deltas:
- delta_latency(%) = (200 - 180) / 200 * 100 = 10.00
- delta_error(%)   = (0.02 - 0.01) / 0.02 * 100 = 50.00
- delta_cpu(%)     = (0.75 - 0.70) / 0.75 * 100 ≈ 6.67

Score:
- score = 10.00*0.5 + 50.00*0.3 + 6.67*0.2 ≈ 21.33 → decisão: `approve_auto`

Resposta de exemplo
```json
{
    "summary": {
        "decision": "approve_auto",
        "score": 21.33
    },
    "details": {
        "delta_latency(%)": 10.00,
        "delta_error(%)": 50.00,
        "delta_cpu(%)": 6.67
    }
}
```

---

## 🚀 Execução (local / Docker)

Build e run com Docker:
```bash
docker build -t darwin-evaluator .
docker run -p 5001:5001 darwin-evaluator
```

Chamada de avaliação:
```bash
curl -X POST http://localhost:5001/evaluate \
         -F "baseline=@metrics/baseline.json" \
         -F "candidate=@metrics/candidate.json"
```

---

## 🧭 Integração

- Recebe chamadas do Orchestrator via POST /evaluate.
- Retorna decisão e score para guiar o Canary Deployer.
- Gera logs e relatórios em JSON auditável.

---

## 🔮 Futuras expansões

- Integração com Prometheus para baselines dinâmicos.
- Regressão temporal e thresholds adaptativos por aprendizado.
- Análise multivariada de custo e performance.

<!-- Fim -->