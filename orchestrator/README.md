# 🧠 Darwin – Orchestrator

O **Orchestrator** é o cérebro do ecossistema **Darwin**, coordenando o ciclo completo de autoevolução do sistema.  
Ele atua como um **controlador de fluxo inteligente**, recebendo sinais do `detector/` e acionando dinamicamente os módulos `generator/` e `evaluator/`.

---

## ⚙️ Função

1. Receber *hotspots* do Detector.  
2. Solicitar ao **Generator** a criação de um *candidate branch*.  
3. Enviar o candidato ao **Evaluator** para testes e métricas.  
4. Tomar decisão automatizada: **aprovar**, **rejeitar** ou **aguardar revisão humana**.  
5. Registrar o resultado em um log imutável.

---

## 🧩 Estrutura

```
orchestrator/
├── orchestrator.py           # API e orquestração principal
├── utils/
│   ├── api_client.py         # Comunicação com serviços externos
│   ├── job_scheduler.py      # Registro e controle de jobs
│   └── logger.py             # Sistema de logs colorido e centralizado
├── Dockerfile                # Build do microserviço
├── requirements.txt          # Dependências Python
├── jobs_log/                 # Logs de execução (JSON)
└── README.md
```

---

## 📡 Endpoints

| Método | Rota        | Descrição                                           |
|--------|-------------|-----------------------------------------------------|
| GET    | /health     | Verifica status e horário atual.                    |
| POST   | /hotspot    | Recebe hotspots do Detector e inicia o ciclo.       |

---

## 🔗 Comunicação

O Orchestrator comunica-se com outros serviços via HTTP JSON:

- **Generator** → http://generator:5002/generate  
- **Evaluator** → http://evaluator:5001/evaluate

---

## 🧾 Log de Jobs

Cada execução do ciclo gera um arquivo JSON em `jobs_log/` com a estrutura:

```json
{
    "timestamp": "20251010_183022",
    "candidate": {
        "branch": "candidate_123",
        "...": "..."
    },
    "evaluation": {
        "score": 0.94,
        "decision": "approve_auto"
    },
    "decision": "approve_auto"
}
```

---

## 🚀 Execução

Local:
```bash
uvicorn orchestrator:app --reload --port 5003
```

Docker:
```bash
docker build -t darwin-orchestrator .
docker run -p 5003:5003 darwin-orchestrator
```

---

## 🧩 Futuras Expansões

| Funcionalidade               | Descrição                                                       |
|-----------------------------|-----------------------------------------------------------------|
| Retry automático            | Repetir tasks em falha de rede ou build.                        |
| Audit Trail externo         | Enviar logs para Loki / Elasticsearch.                          |
| Dashboard de Jobs           | UI em Grafana ou React para acompanhar decisões.                |
| Integração com Canary Deployer | Envio automático para rollout após aprovação.                 |

---

O Orchestrator representa a consciência operacional do “Darwin”: ele conecta dados, decisões e ações — permitindo que o código aprenda e se ajuste continuamente.