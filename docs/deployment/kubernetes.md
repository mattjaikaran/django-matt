# Kubernetes Deployment

Deploy django-matt applications to Kubernetes for scalable, self-healing container orchestration.

## Overview

Kubernetes (K8s) provides enterprise-grade container orchestration:

- **Auto-Scaling** - Horizontal and vertical pod autoscaling
- **Self-Healing** - Automatic restart and replacement of failed pods
- **Rolling Updates** - Zero-downtime deployments
- **Service Discovery** - Built-in DNS and load balancing
- **Secret Management** - Secure secrets storage

## Prerequisites

1. **Kubernetes Cluster** - Local (minikube, kind) or cloud (GKE, EKS, AKS)
2. **kubectl** - Kubernetes CLI
3. **Docker** - For building images
4. **Helm** (optional) - Kubernetes package manager

### Install kubectl

=== "macOS"
    ```bash
    brew install kubectl
    ```

=== "Linux"
    ```bash
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    ```

=== "Windows"
    ```powershell
    choco install kubernetes-cli
    ```

### Verify Installation

```bash
kubectl version --client
kubectl cluster-info
```

## Quick Start

### Local Development with Minikube

```bash
# Start minikube
minikube start

# Enable ingress
minikube addons enable ingress

# Point Docker to minikube
eval $(minikube docker-env)
```

## Kubernetes Manifests

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: myapp
  labels:
    app: myapp
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
  namespace: myapp
data:
  DJANGO_SETTINGS_MODULE: "config.settings"
  DJANGO_ENV: "production"
  DEBUG: "false"
  ALLOWED_HOSTS: ".myapp.example.com"
  STATIC_URL: "/static/"
  STATIC_ROOT: "staticfiles"
```

### Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secrets
  namespace: myapp
type: Opaque
stringData:
  SECRET_KEY: "your-secret-key-here"
  DATABASE_URL: "postgres://user:password@postgres:5432/myapp"
  REDIS_URL: "redis://redis:6379/0"
```

!!! warning "Secrets Management"
    In production, use a secrets management solution like:
    - External Secrets Operator
    - Sealed Secrets
    - HashiCorp Vault
    - AWS Secrets Manager

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-web
  namespace: myapp
  labels:
    app: myapp
    component: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      component: web
  template:
    metadata:
      labels:
        app: myapp
        component: web
    spec:
      containers:
        - name: web
          image: myregistry/myapp:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
              protocol: TCP
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /live/
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready/
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
      initContainers:
        - name: migrate
          image: myregistry/myapp:latest
          command: ["python", "manage.py", "migrate", "--noinput"]
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secrets
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp-web
  namespace: myapp
  labels:
    app: myapp
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
      name: http
  selector:
    app: myapp
    component: web
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: myapp
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  tls:
    - hosts:
        - myapp.example.com
      secretName: myapp-tls
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp-web
                port:
                  number: 80
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-web-hpa
  namespace: myapp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp-web
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### PostgreSQL StatefulSet

```yaml
# k8s/postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: myapp
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              value: myapp
            - name: POSTGRES_USER
              value: django
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: myapp-secrets
                  key: POSTGRES_PASSWORD
          volumeMounts:
            - name: postgres-data
              mountPath: /var/lib/postgresql/data
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
  volumeClaimTemplates:
    - metadata:
        name: postgres-data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: myapp
spec:
  ports:
    - port: 5432
  selector:
    app: postgres
  clusterIP: None
```

### Redis Deployment

```yaml
# k8s/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
            limits:
              memory: "128Mi"
              cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: myapp
spec:
  ports:
    - port: 6379
  selector:
    app: redis
```

### Celery Worker Deployment

```yaml
# k8s/celery-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
  namespace: myapp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: myapp
      component: celery-worker
  template:
    metadata:
      labels:
        app: myapp
        component: celery-worker
    spec:
      containers:
        - name: celery
          image: myregistry/myapp:latest
          command: ["celery", "-A", "config", "worker", "-l", "info"]
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

### Celery Beat Deployment

```yaml
# k8s/celery-beat.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-beat
  namespace: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
      component: celery-beat
  template:
    metadata:
      labels:
        app: myapp
        component: celery-beat
    spec:
      containers:
        - name: celery-beat
          image: myregistry/myapp:latest
          command: ["celery", "-A", "config", "beat", "-l", "info"]
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secrets
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "200m"
```

## Deployment Steps

### 1. Build and Push Docker Image

```bash
# Build image
docker build -t myregistry/myapp:latest .

# Push to registry
docker push myregistry/myapp:latest
```

### 2. Apply Kubernetes Manifests

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create config and secrets
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# Deploy database and cache
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# Wait for database
kubectl wait --for=condition=ready pod -l app=postgres -n myapp --timeout=120s

# Deploy application
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Deploy workers (if using Celery)
kubectl apply -f k8s/celery-worker.yaml
kubectl apply -f k8s/celery-beat.yaml

# Set up autoscaling
kubectl apply -f k8s/hpa.yaml
```

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -n myapp

# Check services
kubectl get svc -n myapp

# Check ingress
kubectl get ingress -n myapp

# View logs
kubectl logs -f deployment/myapp-web -n myapp
```

## Operations

### Scaling

```bash
# Manual scaling
kubectl scale deployment myapp-web --replicas=5 -n myapp

# Check HPA status
kubectl get hpa -n myapp
```

### Rolling Updates

```bash
# Update image
kubectl set image deployment/myapp-web web=myregistry/myapp:v2 -n myapp

# Check rollout status
kubectl rollout status deployment/myapp-web -n myapp

# View rollout history
kubectl rollout history deployment/myapp-web -n myapp
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/myapp-web -n myapp

# Rollback to specific revision
kubectl rollout undo deployment/myapp-web --to-revision=2 -n myapp
```

### Run Management Commands

```bash
# Run migrations
kubectl exec -it deployment/myapp-web -n myapp -- python manage.py migrate

# Create superuser
kubectl exec -it deployment/myapp-web -n myapp -- python manage.py createsuperuser

# Django shell
kubectl exec -it deployment/myapp-web -n myapp -- python manage.py shell
```

### View Logs

```bash
# Pod logs
kubectl logs -f deployment/myapp-web -n myapp

# All pods logs
kubectl logs -f -l app=myapp -n myapp

# Previous container logs (after crash)
kubectl logs deployment/myapp-web -n myapp --previous
```

### Database Operations

```bash
# Access PostgreSQL
kubectl exec -it statefulset/postgres -n myapp -- psql -U django -d myapp

# Backup database
kubectl exec -it statefulset/postgres -n myapp -- pg_dump -U django myapp > backup.sql
```

## Helm Chart (Optional)

Create a Helm chart for easier management:

### Chart Structure

```
myapp-chart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── hpa.yaml
```

### values.yaml

```yaml
replicaCount: 3

image:
  repository: myregistry/myapp
  tag: latest
  pullPolicy: Always

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  host: myapp.example.com
  tls: true

resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

django:
  settingsModule: config.settings
  env: production
  debug: false

postgresql:
  enabled: true
  auth:
    database: myapp
    username: django

redis:
  enabled: true
```

### Install with Helm

```bash
# Install
helm install myapp ./myapp-chart -n myapp

# Upgrade
helm upgrade myapp ./myapp-chart -n myapp

# Rollback
helm rollback myapp 1 -n myapp
```

## Health Check Endpoints

Ensure your Django app has health check endpoints:

```python
# urls.py
from django_matt.deploy import get_health_urls

urlpatterns = [
    ...
    *get_health_urls(),  # Adds /health/, /ready/, /live/
]
```

The endpoints:

- `/live/` - Liveness probe (is the app running?)
- `/ready/` - Readiness probe (is the app ready for traffic?)
- `/health/` - Full health check (database, cache, etc.)

## Monitoring

### Prometheus & Grafana

```yaml
# Install via Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

### Django Prometheus Metrics

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_prometheus',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    ...
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# urls.py
urlpatterns = [
    ...
    path('metrics/', include('django_prometheus.urls')),
]
```

## Troubleshooting

### Pod Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n myapp

# Check events
kubectl get events -n myapp --sort-by='.lastTimestamp'
```

### Crashloopbackoff

```bash
# Check logs
kubectl logs <pod-name> -n myapp --previous

# Debug container
kubectl exec -it <pod-name> -n myapp -- /bin/sh
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
kubectl get pods -l app=postgres -n myapp

# Test connection from app pod
kubectl exec -it deployment/myapp-web -n myapp -- python manage.py dbshell
```

### Ingress Not Working

```bash
# Check ingress status
kubectl describe ingress myapp-ingress -n myapp

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

## Best Practices

1. **Use Resource Limits** - Prevent runaway containers
2. **Set Up Probes** - Enable self-healing
3. **Use PodDisruptionBudgets** - Ensure availability during updates
4. **Implement Network Policies** - Secure pod communication
5. **Use Secrets Management** - Don't store secrets in manifests
6. **Enable Logging** - Centralize logs with EFK/Loki
7. **Monitor Everything** - Use Prometheus/Grafana

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
