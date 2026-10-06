apiVersion: v1
kind: Secret
metadata:
  name: darwin-secrets
  namespace: default
type: Opaque
stringData:
  MINIO_ROOT_USER: "CHANGE_ME"
  MINIO_ROOT_PASSWORD: "CHANGE_ME"
  SPRING_PROFILES_ACTIVE: "prod"
  MANAGEMENT_METRICS_EXPORT_PROMETHEUS_ENABLED: "true"
  MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE: "prometheus,health,info"
