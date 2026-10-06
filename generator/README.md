# Darwin – Generator

O **Generator** é o módulo responsável por **propor e aplicar mudanças no código‑fonte**, baseando‑se em heurísticas determinísticas ou em modelos de IA. É o **núcleo evolutivo** do sistema — onde o código “muta” para se adaptar a problemas reais detectados em produção.

---

## Função

1. Recebe *hotspots* do **Orchestrator**.  
2. Identifica o arquivo mais relevante (via análise AST).  
3. Aplica uma ou mais **regras heurísticas**.  
4. Gera um *patch* e cria um *branch candidato*.  
5. Retorna a branch para o ciclo de avaliação.

---

## Estrutura

```
generator/
├── generator.py            # Serviço principal
├── heuristics/             # Regras determinísticas
│   ├── timeout_rule.py     # Ajuste de timeouts
│   ├── pool_size_rule.py   # Ajuste de pool de conexões
│   └── caching_rule.py     # Injeção de cache
├── models/                 # (opcional) Modelos IA
│   └── tinyllama_adapter.py
├── utils/
│   ├── git_helper.py       # Automação de Git
│   ├── ast_parser.py       # Busca e análise de código
│   └── patch_writer.py     # Escrita e versionamento de patches
└── README.md
```

---

## Comunicação

- Recebe de: `orchestrator` (`POST /generate`)  
- Envia para: `evaluator` (`POST /evaluate`) *(indireto, via orchestrator)*

---

## Modos de Operação

| Modo | Descrição |
|------|-----------|
| **Heurístico (padrão)** | Usa regras AST simples para aplicar mudanças determinísticas. |
| **IA (TinyLlama)**      | Gera sugestões textuais de patch com base em contexto de erro. |

---

## Exemplo de Execução

Entrada (hotspot):
```json
{
    "hotspots": [
        { "endpoint": "/api/users", "type": "latency", "p95": 2.4 }
    ]
}
```

Saída (branch gerado):
```json
{
    "branch": "candidate_patch_20251010_145920",
    "file": "src/main/java/UserController.java",
    "rule": "timeout"
}
```

---

## Futuras Expansões

- Análise AST mais precisa (ex.: JavaParser via subprocesso).  
- Fine‑tuning de LLMs usando commits históricos.  
- Feedback loop com métricas do Evaluator para aprendizado adaptativo.

---