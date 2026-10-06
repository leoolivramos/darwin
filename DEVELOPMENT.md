# Desenvolvimento

## Requisitos

- Docker com Compose v2
- Python 3.10+
- JDK 21+ e Maven (para o app)
- Git 2.25+

## Setup

```bash
git clone https://github.com/leoolivramos/darwin.git
cd darwin

python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
```

## Stack completa

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f orchestrator
docker compose down        # -v remove também os volumes
```

## Serviços individuais

Cada serviço Python tem seu `requirements.txt`.

```bash
cd detector            # ou generator, evaluator, orchestrator, sandbox-runner
pip install -r requirements.txt
python detector.py     # detector.py, generator.py, evaluator.py, orchestrator.py, sandbox_runner.py
```

O orchestrator precisa de Redis e Postgres, e o worker é iniciado com:

```bash
cd orchestrator
celery -A worker worker --loglevel=info
```

App Spring Boot:

```bash
cd app
mvn spring-boot:run
```

## Testes

```bash
pytest tests/unit -v
pytest tests/unit --cov
```

Teste de integração (requer a stack no ar):

```bash
python tests/integration/smoke_test.py
```

O CI (`.github/workflows/ci.yml`) roda build, testes unitários e o teste de integração a cada push e pull request.

## Convenções

- Commits no padrão Conventional Commits (`feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, `chore`).
- Um commit por mudança lógica.
- Não commitar `.env` nem credenciais.
