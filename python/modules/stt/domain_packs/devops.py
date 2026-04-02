# -*- coding: utf-8 -*-
"""DevOps / Infrastructure vocabulary pack."""

VOCAB = [
    # Containers & orchestration
    "Docker", "Podman", "containerd", "OCI",
    "Kubernetes", "K8s", "K3s", "Minikube", "Kind",
    "Helm", "Kustomize", "ArgoCD", "FluxCD",
    "Istio", "Linkerd", "Envoy",
    # Cloud providers
    "AWS", "GCP", "Azure", "DigitalOcean", "Hetzner", "Fly.io",
    "EC2", "ECS", "EKS", "Lambda", "S3", "RDS", "CloudFront",
    "GKE", "Cloud Run", "BigQuery",
    "AKS", "App Service", "Blob",
    # IaC
    "Terraform", "Pulumi", "Ansible", "Chef", "Puppet",
    "CloudFormation", "CDK",
    "Vault", "Consul",
    # CI/CD
    "GitHub Actions", "GitLab CI", "Jenkins", "CircleCI", "TeamCity",
    "Tekton", "Argo Workflows", "Drone",
    "CI/CD", "pipeline", "artifact", "registry",
    # Monitoring & observability
    "Prometheus", "Grafana", "Loki", "Tempo", "Mimir",
    "Datadog", "New Relic", "Dynatrace", "Sentry",
    "OpenTelemetry", "Jaeger", "Zipkin",
    "ELK", "Elasticsearch", "Logstash", "Kibana", "Fluentd",
    # Networking
    "nginx", "Traefik", "HAProxy", "Caddy",
    "VPN", "VPC", "subnet", "ingress", "egress",
    "DNS", "CDN", "load balancer", "reverse proxy",
    "Cloudflare", "Fastly",
    # Message queues
    "Kafka", "RabbitMQ", "SQS", "Pub/Sub", "NATS",
    # Version control
    "Git", "GitHub", "GitLab", "Bitbucket",
    "branch", "merge", "rebase", "tag", "release",
    # Security / secrets
    "SAST", "DAST", "SBOM", "CVE", "Trivy", "Snyk",
    "SSO", "SAML", "LDAP",
    # Concepts
    "SRE", "SLA", "SLO", "SLI", "MTTR", "MTBF",
    "blue-green", "canary", "rolling update", "rollback",
    "autoscaling", "HPA", "VPA", "pod", "node", "namespace",
    "ConfigMap", "Secret", "PVC", "StatefulSet", "DaemonSet",
    # Russian ASR variants
    "докер", "кубернетес", "хелм", "террафом", "дженкинс",
    "гитхаб", "гитлаб", "нжинкс", "кафка",
]
