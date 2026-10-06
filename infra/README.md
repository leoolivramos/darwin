# infra/ — Infraestrutura e Observabilidade do Darwin

> Infra local (dev / PoC) e artefatos iniciais para migrar para Kubernetes.
> Inclui configurações de Prometheus, Grafana, Jaeger, MinIO e manifests básicos de k8s.

## Índice
- [Visão geral](#visão-geral)
- [Pré-requisitos](#pré-requisitos)
- [Estrutura de arquivos](#estrutura-de-arquivos)
- [Instruções rápidas — subir a infra local](#instruções-rápidas---subir-a-infra-local)
- [Prometheus](#prometheus)
    - [Arquivo principal](#arquivo-principal)
    - [Como adicionar targets](#como-adicionar-targets)
    - [Debug / verificação](#debug--verificação)
- [Grafana](#grafana)
    - [Dashboards](#dashboards)
    - [Importar dashboard JSON](#importar-dashboard-json)
    - [Provisionamento (opcional)](#provisionamento-opcional)
- [Jaeger (Tracing)](#jaeger-tracing)
- [MinIO (Object Storage)](#minio-object-storage)
    - [Arquivos importantes](#arquivos-importantes)
    - [Usando mc (MinIO Client)](#usando-mc-minio-client)
    - [Backup / restore](#backup--restore)
- [Kubernetes (k8s)](#kubernetes-k8s)
    - [Secret e PVC](#secret-e-pvc)
- [Integração com serviços](#integração-com-serviços)
- [Segurança e gestão de segredos](#segurança-e-gestão-de-segredos)
- [Troubleshooting — problemas comuns](#troubleshooting---problemas-comuns)
- [Boas práticas e próximos passos](#boas-práticas-e-próximos-passos)
- [Comandos úteis (recap)](#comandos-úteis-recap)

---

## Visão geral

A pasta `infra/` foi planejada para dois cenários:

1. Desenvolvimento local / PoC: docker compose (arquivo `docker-compose.yml` na raiz) para subir app + Prometheus + Grafana + Jaeger + MinIO.
2. Deploy em cluster (Kubernetes): manifests iniciais em `infra/k8s/` como ponto de partida.

Objetivo: fornecer observabilidade, armazenamento de artefatos, tracing e facilitar coleta de métricas dos microserviços do Darwin.

---

## Pré-requisitos

- Docker & Docker Compose (ou Docker Desktop)
- (Opcional) kubectl com acesso a um cluster Kubernetes
- (Opcional) mc (MinIO Client)
- (Opcional) jq (para manipular JSON em CLI)
- (Opcional) promtool (para validar prometheus.yml)

---

## Estrutura de arquivos (resumo)

```
infra/
├─ prometheus/
│  └─ prometheus.yml           # config principal do Prometheus (scrape targets)
├─ grafana/
│  └─ dashboards/              # dashboards JSON exportados do Grafana
├─ jaeger/
│  └─ config.yaml              # config mínima para Jaeger all-in-one
├─ minio/
│  ├─ Dockerfile               # imagem custom (wrapper p/ init)
│  ├─ init.sh                  # cria buckets (artifacts, telemetry, patches)
│  └─ data/                    # dados persistidos (montar volume)
└─ k8s/
     ├─ app-deploy.yaml
     ├─ prometheus.yaml
     ├─ generator.yaml
     ├─ evaluator.yaml
     └─ orchestrator.yaml
```

> Observação: há um `docker-compose.yml` na raiz do repositório que referencia esses arquivos.

---

## Instruções rápidas — subir a infra local

1. Crie `.env` na raiz com variáveis como `MINIO_ROOT_USER` e `MINIO_ROOT_PASSWORD`.
2. A partir da raiz do projeto:

```bash
docker compose --env-file .env up -d --build
```

URLs úteis (padrão local):
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin por padrão)
- Jaeger UI: http://localhost:16686
- MinIO Console: http://localhost:9001
- MinIO S3 API: http://localhost:9000

---

## Prometheus

### Arquivo principal
`infra/prometheus/prometheus.yml` contém os jobs em `scrape_configs` para:
- spring-app → app:8080 (/actuator/prometheus)
- sandbox-candidates → sandbox-runner:9091
- evaluator → evaluator:5001
- generator → generator:5002
- orchestrator → orchestrator:5003

Ajuste os targets conforme o nome dos serviços no Docker Compose ou k8s Services.

### Como adicionar targets
Edite `infra/prometheus/prometheus.yml` e adicione um job em `scrape_configs`. Exemplo:

```yaml
- job_name: "myservice"
    static_configs:
        - targets: ["myservice:8080"]
```

Reinicie o container Prometheus ou envie reload via API se disponível.

### Debug / verificação
- Verificar targets: http://localhost:9090/targets
- Testar queries: http://localhost:9090/graph
- Logs do container: `docker logs darwin-prometheus`
- Validar YAML: `promtool check config infra/prometheus/prometheus.yml`

---

## Grafana

### Dashboards
Coloque dashboards exportados em `infra/grafana/dashboards/`. Eles podem ser montados como volume e importados automaticamente via provisioning ou importados manualmente.

### Importar dashboard JSON (manual)
1. Abra Grafana: http://localhost:3000
2. Menu → Dashboards → Import → Cole JSON ou selecione o arquivo.
3. Escolha o datasource (Prometheus).

### Provisionamento (opcional)
Automatize com configurações em `provisioning/dashboards` e `provisioning/datasources` e monte essas pastas no container Grafana.

---

## Jaeger (Tracing)

- Arquivo base: `infra/jaeger/config.yaml` (all-in-one).
- UI: http://localhost:16686

Para aparecerem traces, a aplicação e microserviços devem exportar spans via OpenTelemetry ou exporters compatíveis (Jaeger/Zipkin).

Verificação: gere uma requisição à API (ex.: `curl http://localhost:8080/api/test`) e verifique a UI do Jaeger.

---

## MinIO (Object Storage)

### Arquivos importantes
- `infra/minio/Dockerfile` — imagem que inclui `init.sh`.
- `infra/minio/init.sh` — cria buckets (artifacts, telemetry, patches).
- `infra/minio/data/` — diretório usado para persistência (montar volume).

Console: http://localhost:9001 (credenciais do `.env`)
S3 API: http://localhost:9000

### Usando mc (MinIO Client)
Exemplo:

```bash
mc alias set local http://localhost:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}
mc ls local
mc mb local/artifacts
mc cp local/file.txt local/artifacts/
```

Se não tiver `mc` local, rode dentro de um container temporário:

```bash
docker run --rm -it --network darwin-net minio/mc mc alias set local http://darwin-minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} && mc ls local
```

### Backup / restore
- Backup simples: compacte `infra/minio/data` (quando volume local).
- Em produção, prefira replicação S3 ou snapshot do volume.

---

## Kubernetes (k8s)

Pasta `infra/k8s/` contém manifests iniciais:
- `app-deploy.yaml` → Deployment + Service para a aplicação
- `prometheus.yaml` → Deployment + ConfigMap (prometheus.yml)
- `generator.yaml`, `evaluator.yaml`, `orchestrator.yaml` → Deploys + Services

### Secret e PVC
Aplique secrets e recursos:

```bash
kubectl apply -f infra/k8s/darwin-secrets.yaml
kubectl apply -f infra/k8s/prometheus.yaml
kubectl apply -f infra/k8s/app-deploy.yaml
```

Para MinIO em k8s, crie um PVC e monte em `/data`. Exemplo básico de PVC:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
    name: minio-pvc
spec:
    accessModes:
        - ReadWriteOnce
    resources:
        requests:
            storage: 10Gi
```

Ajuste `StorageClass` conforme o provedor (NFS, AWS EBS, GCP PD, etc).

---

## Integração com serviços (generator, evaluator, orchestrator, app)

- Prometheus: configure `infra/prometheus/prometheus.yml` com os nomes dos serviços do Compose ou k8s Services para habilitar scraping.
- Jaeger: habilite exporter/OpenTelemetry nos serviços.
- MinIO: configure variáveis `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (use `.env` em dev; secrets em produção).
- Generator: em compose, monte o código Fonte como volume em `/repo` para permitir edições locais.

---

## Segurança e gestão de segredos

- Não commite segredos. `.gitignore` deve incluir `infra/minio/data`, `secrets/`, `.env`.
- Local: use `.env` montado via `--env-file`.
- Produção: Docker Secrets (Swarm) ou Kubernetes Secrets.
- Rotação de credenciais: adote um secrets manager em produção.

---

## Troubleshooting — problemas comuns

1. Prometheus não sobe / parsing error
     - Use `promtool` para validar `infra/prometheus/prometheus.yml`.
     - Veja logs: `docker logs darwin-prometheus`.

2. Grafana não mostra dados
     - Verifique Prometheus (`curl http://localhost:9090/metrics`).
     - Confira datasource URL (no Compose use `http://prometheus:9090`).

3. MinIO não cria buckets
     - Logs: `docker logs darwin-minio`.
     - Verifique permissão de execução de `init.sh` (chmod +x).
     - Confira credenciais no `.env`.

4. Jaeger sem traces
     - Confirme instrumentação e endpoint correto (`http://jaeger:14268/api/traces` ou OTLP).
     - Verifique sampling.

5. Portas em uso
     - `docker ps` e `sudo lsof -i :PORT`.

---

## Boas práticas e próximos passos

- Versione dashboards e alerts em `infra/`.
- Automatize provisioning do Grafana.
- Em k8s, considere `kube-prometheus-stack` (Helm) para setup robusto.
- Implementar RBAC, network policies e processo de rotação de segredos.
- Backups regulares do MinIO (cronjob / snapshot).

---

## Comandos úteis (recap)

Subir tudo (raiz do repo):

```bash
docker compose --env-file .env up -d --build
```

Ver logs:

```bash
docker-compose logs -f prometheus
docker logs -f darwin-minio
```

Ver targets do Prometheus:

```bash
curl http://localhost:9090/api/v1/targets | jq
```

Listar buckets MinIO com mc:

```bash
mc alias set local http://localhost:9000 admin supersecret
mc ls local
```

---