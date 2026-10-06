# Guia de Desenvolvimento — Código Vivo

## Setup do Ambiente de Desenvolvimento

### 1. Requisitos do Sistema

- **OS**: Linux, macOS ou Windows (WSL2)
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.10+
- **Java**: JDK 17+
- **Git**: 2.25+
- **RAM**: 8GB mínimo, 16GB recomendado
- **Disco**: 20GB livre

### 2. Instalação Inicial

```bash
# Clone o repositório
git clone https://github.com/leoolivramos/darwin.git
cd darwin

# Setup Python venv
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate  # Windows

# Instale dependências de desenvolvimento
pip install -r requirements-dev.txt

# Setup Git hooks (opcional)
cd .git/hooks
ln -s ../../scripts/pre-commit pre-commit
chmod +x pre-commit
```

### 3. Variáveis de Ambiente

```bash
# Copie e customize
cp .env.example .env

# Edite para seu ambiente local (opcional)
# vim .env
```

---

## Desenvolvimento Local

### Opção A: Docker Compose (Recomendado)

```bash
# Inicie todos os serviços
docker-compose up -d

# Verifique status
docker-compose ps

# Veja logs
docker-compose logs -f [service_name]

# Pare tudo
docker-compose down

# Limpe volumes (cuidado!)
docker-compose down -v
```

### Opção B: Serviços Individuais

#### Spring Boot App

```bash
cd app

# Build
mvn clean package

# Run local
mvn spring-boot:run

# Com properties customizadas
mvn spring-boot:run -Dspring-boot.run.arguments="--server.port=9090"

# Com debugging
mvn -Dspringboot.run.jvmArguments="-Xdebug -Xrunjdwp:transport=dt_socket,server=y,suspend=y,address=5005" spring-boot:run
```

#### Detector (Python)

```bash
cd detector

# Instale dependências locais
pip install -r requirements.txt

# Run
PROMETHEUS_URL=http://localhost:9090 python detector.py

# Run com logs DEBUG
LOG_LEVEL=DEBUG PROMETHEUS_URL=http://localhost:9090 python detector.py
```

#### Generator (Python)

```bash
cd generator

# Instale dependências
pip install -r requirements.txt

# Run
python generator.py

# Run com arquivo de config
python generator.py --config config.yaml
```

#### Evaluator (Python)

```bash
cd evaluator

# Instale dependências
pip install -r requirements.txt

# Run
python evaluator.py

# Com metricas customizadas
python evaluator.py --baseline tests/data/baseline.json --candidate tests/data/candidate.json
```

#### Orchestrator (Python)

```bash
cd orchestrator

# Instale dependências
pip install -r requirements.txt

# Run
python orchestrator.py

# Com logging
LOGLEVEL=debug python orchestrator.py
```

---

## Testes

### Testes Unitários

```bash
# Rodar todos
pytest tests/unit -v

# Rodar arquivo específico
pytest tests/unit/test_detector.py -v

# Rodar teste específico
pytest tests/unit/test_detector.py::TestDetectorHealthCheck::test_health_check_initial_state -v

# Com cobertura
pytest tests/unit --cov=src --cov-report=html
```

### Testes de Integração

```bash
# Requer Docker e docker-compose rodando
pytest tests/integration -v

# Específico
pytest tests/integration/test_detector_prometheus.py -v
```

### Testes de Carga

```bash
cd tests/load

# Execute load test
./run-load-test.sh

# Ou com Apache Bench
ab -n 10000 -c 100 http://localhost:8080/api/users

# Ou com wrk
wrk -t12 -c400 -d30s http://localhost:8080/api/users
```

### Coverage Report

```bash
# Gera relatório HTML
pytest tests/ --cov=src --cov-report=html

# Abra no navegador
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Code Quality

### Linting

```bash
# Flake8
flake8 src/ tests/ --max-line-length=120 --exclude=__pycache__,venv

# isort (import sorting)
isort src/ tests/

# Check only
isort --check-only src/ tests/
```

### Code Formatting

```bash
# Black
black src/ tests/

# Check only
black --check src/ tests/
```

### Type Checking

```bash
# MyPy
mypy src/ --ignore-missing-imports

# Strict mode
mypy src/ --strict
```

### Security

```bash
# Bandit
bandit -r src/ -ll  # Only medium+ severity

# Safety (vulnerabilidades de dependências)
safety check
```

### Auto-fix

```bash
# Execute tudo
make lint-fix

# Ou manualmente
black src/ tests/
isort src/ tests/
autopep8 --in-place --aggressive --aggressive -r src/
```

---

## Debugging

### VS Code

1. Instale extensão Python
2. Crie `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Detector",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/detector/detector.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Python: Generator",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/generator/generator.py",
      "console": "integratedTerminal"
    }
  ]
}
```

3. Pressione F5 para iniciar debug

### Spring Boot (Java)

```bash
cd app

# Com breakpoints
mvn -Dspringboot.run.jvmArguments="-Xdebug -Xrunjdwp:transport=dt_socket,server=y,suspend=y,address=5005" spring-boot:run

# Conecte debugger na porta 5005
```

### Logs

```bash
# Docker
docker-compose logs -f detector

# Local com tail
tail -f app/logs/*.log

# Grep para erros
docker-compose logs | grep ERROR
```

---

## Build e Distribuição

### Docker Images

```bash
# Build local
docker build -t codigo-vivo/detector:dev detector/
docker build -t codigo-vivo/generator:dev generator/
docker build -t codigo-vivo/app:dev app/

# Push para registry
docker login
docker tag codigo-vivo/detector:dev seu-registry/codigo-vivo/detector:v1.0
docker push seu-registry/codigo-vivo/detector:v1.0
```

### Versionamento

```bash
# Bump version
cd app && mvn versions:set -DnewVersion=1.0.1

# Tag no git
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1
```

---

## Documentação

### Gerar Docs

```bash
# Python (pdoc)
pdoc --html --output-dir docs/api src/

# Java (Javadoc)
cd app && mvn javadoc:javadoc

# API OpenAPI
# Disponível em http://localhost:5004/docs (FastAPI)
# Disponível em http://localhost:8080/v3/api-docs (Spring Boot)
```

### Editar Docs

- Markdown: `docs/*.md`
- Diagramas: `architecture/` (PlantUML)
- Imagens: `docs/images/`

---

## 🔧 Troubleshooting

### Porta em Uso

```bash
# Identifique o processo
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows

# Mate o processo
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

### Dependências Faltando

```bash
# Atualize pip
pip install --upgrade pip

# Reinstale requirements
pip install -r requirements-dev.txt --force-reinstall
```

### Docker Issues

```bash
# Limpe tudo
docker-compose down -v
docker system prune -a

# Recrie
docker-compose up --build
```

### Git Issues

```bash
# Reset local para remoto
git fetch origin
git reset --hard origin/main

# Limpe arquivos untracked
git clean -fd
```

---

## Padrões e Convenções

### Nomes de Variáveis

```python
# Bom
detector_state = {}
hotspot_threshold = 500
PROMETHEUS_URL = "http://prometheus:9090"

# Ruim
d_state = {}
threshold = 500  # ambíguo
prometheus_url = "http://prometheus:9090"  # deveria ser SCREAMING_SNAKE_CASE para constantes
```

### Estrutura de Arquivos

```
src/
├── __init__.py
├── models.py        # Data models
├── services.py      # Business logic
├── routes.py        # API endpoints
├── config.py        # Configuration
├── utils.py         # Utilities
└── exceptions.py    # Custom exceptions

tests/
├── unit/
├── integration/
└── data/
```

### Commits

```bash
# Bom
git commit -m "feat: add hotspot detection for latency"
git commit -m "fix: correct threshold calculation in detector"
git commit -m "docs: update detector README"

# Ruim
git commit -m "fix stuff"
git commit -m "WIP"
git commit -m "aaa"
```

---

## Workflow Típico

```bash
# 1. Crie branch
git checkout -b feature/sua-feature

# 2. Faça mudanças
# ... edit files ...

# 3. Teste localmente
pytest tests/ -v
black --check src/
flake8 src/

# 4. Commit
git add .
git commit -m "feat: your feature"

# 5. Push
git push origin feature/sua-feature

# 6. Abra Pull Request
# ... GitHub/GitLab UI ...

# 7. Aguarde review
# ... feedback ...

# 8. Merge
# ... após aprovação ...

# 9. Delete branch
git push origin --delete feature/sua-feature
```

---

## Dicas de Performance

### Python

```python
# Usa type hints para melhor performance
def process_hotspots(metrics: Dict[str, float]) -> List[str]:
    pass

# Usa generators para grandes datasets
def large_dataset():
    for i in range(1_000_000):
        yield i

# Cache resultados
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_query(endpoint: str) -> Dict:
    pass
```

### Java

```java
@Configuration
public class DataSourceConfig {
    @Bean
    public HikariDataSource dataSource() {
        HikariConfig config = new HikariConfig();
        config.setMaximumPoolSize(20);
        return new HikariDataSource(config);
    }
}

@Cacheable(value = "hotspots")
public List<Hotspot> getHotspots() {
    return repository.findAll();
}
```
