# 🚀 Quick Start — Darwin

## Pré-requisitos

- Docker Desktop 20.10+ ou Docker Engine + Docker Compose
- Git
- Python 3.10+ (para desenvolvimento local)
- Java 17+ (para desenvolvimento do app)

## 1. Setup Inicial

### Clone o repositório

```bash
git clone <repo-url> darwin
cd darwin
```

### Copie o arquivo de ambiente

```bash
cp .env.example .env
```

### Configure credenciais (opcional para produção)

```bash
# GitLab token
echo "seu_token_aqui" > secrets/gitlab_token.txt

# SSH key para repositório
cp ~/.ssh/id_rsa secrets/id_rsa
chmod 600 secrets/id_rsa
```

## 2. Inicie os Serviços

### Com Docker Compose

```bash
# Build e start tudo
docker-compose up -d --build

# Acompanhe os logs
docker-compose logs -f

# Parar tudo
docker-compose down
```

### Com Kubernetes (Minikube/Kind)

```bash
# Inicie o cluster local
minikube start --cpus=4 --memory=8192

# Aplique o manifesto all-in-one
kubectl apply -f infra/k8s/all-in-one.yaml

# Monitorar
kubectl get pods -n darwin
kubectl logs -n darwin -f deployment/detector

# Acesse pelo port-forward
kubectl port-forward -n darwin svc/darwin-app 8080:80
```

## 3. Acesse os Serviços


| Serviço         | URL                        | Credenciais           |
| ---------------- | -------------------------- | --------------------- |
| App              | http://localhost:8080      | -                     |
| Prometheus       | http://localhost:9090      | -                     |
| Grafana          | http://localhost:3000      | admin/admin           |
| Jaeger           | http://localhost:16686     | -                     |
| Silo Console    | http://localhost:9001      | minioadmin/minioadmin |
| Detector API     | http://localhost:5004/docs | -                     |
| Evaluator API    | http://localhost:5001/docs | -                     |
| Orchestrator API | http://localhost:5003/docs | -                     |
| Generator API    | http://localhost:5002/docs | -                     |

## 4. Teste a API

### Health checks

```bash
curl http://localhost:8080/actuator/health
curl http://localhost:5004/health
curl http://localhost:5001/health
curl http://localhost:5003/health
curl http://localhost:5002/health
```

### Visualize hotspots detectados

```bash
curl http://localhost:5004/hotspots | jq .
```

### Envie um hotspot para teste

```bash
curl -X POST http://localhost:5003/hotspots \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "/api/users",
    "metric": "latency_p99",
    "value": 1250,
    "threshold": 500
  }' | jq .
```

## 5. Geração de Carga (Load Testing)

```bash
# Instale o Apache Bench
apt-get install apache2-utils  # Ubuntu/Debian
brew install httpd             # macOS

# Gere carga na aplicação
ab -n 10000 -c 100 http://localhost:8080/api/users

# Observe no Grafana
# http://localhost:3000 → Dashboards → Darwin
```

## 6. Monitorar Ciclo de Evolução

### 1. Verifique detecção

```bash
docker-compose logs detector | grep "hotspot"
```

### 2. Verifique geração

```bash
docker-compose logs generator | grep "patch"
```

### 3. Verifique avaliação

```bash
docker-compose logs evaluator | grep "score"
```

### 4. Verifique decisão

```bash
docker-compose logs orchestrator | grep "decision"
```

### 5. Acesse logs em Loki

```
http://localhost:3000 → Explore → Selecione "Loki"
```

## 7. Desenvolvimento Local

### Executar app Spring Boot localmente

```bash
cd app
mvn spring-boot:run \
  -Dspring-boot.run.arguments="--management.endpoints.web.exposure.include=prometheus,health"
```

### Executar detector localmente

```bash
cd detector
pip install -r requirements.txt
PROMETHEUS_URL=http://localhost:9090 python detector.py
```

### Executar generator localmente

```bash
cd generator
pip install -r requirements.txt
REPO_PATH=./repo python generator.py
```

## 8. Testes

```bash
# Testes unitários
pytest tests/unit -v

# Testes de integração
pytest tests/integration -v

# Testes de carga
cd tests/load
./run-load-test.sh
```

## 9. Troubleshooting

### Containers não iniciam

```bash
# Verifique logs
docker-compose logs

# Limpe e recrie
docker-compose down -v
docker-compose up -d --build
```

### Prometheus não conecta

```bash
# Verifique conectividade
docker exec darwin-prometheus \
  wget -O- http://darwin-app:8080/actuator/prometheus | head -20
```

### Generator não encontra repo

```bash
# Crie diretório
mkdir -p repo/patches repo/artifacts

# Configure git
cd repo
git init
git config user.email "bot@darwin.ai"
git config user.name "Darwin Bot"
```

### Permissão negada em secrets

```bash
chmod 600 secrets/id_rsa
chmod 600 secrets/gitlab_token.txt
```

## 10. Próximos Passos

1. **Integre seu código**: Copie seu Java app para `runtime-app/`
2. **Customize heurísticas**: Edit `generator/heuristics/*.py`
3. **Configure thresholds**: Ajuste `.env` com seus valores
4. **Implante em produção**: Use `infra/k8s/` para Kubernetes
5. **Monitore**: Configure alertas em Grafana

## Documentação Completa

- [Arquitetura](docs/arquitetura.md)
- [Design Decisions](docs/design_decisions.md)
- [Fluxo de Dados](docs/fluxo_dados.md)
- [README Detector](detector/README.md)
- [README Generator](generator/README.md)
- [README Evaluator](evaluator/README.md)
- [README Orchestrator](orchestrator/README.md)

## Suporte

Abra uma issue no repositório com:

- Descrição do problema
- Logs relevantes
- Versão do Docker
- Sistema operacional

---

**Última atualização**: Janeiro 2026
