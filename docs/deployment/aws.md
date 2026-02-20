# AWS Deployment

Deploy django-matt applications to AWS using App Runner or ECS Fargate with RDS PostgreSQL and ElastiCache Redis.

## Overview

AWS provides enterprise-grade infrastructure for django-matt applications:

- **AWS App Runner** - Fully managed container service (simpler)
- **ECS Fargate** - Serverless container orchestration (more control)
- **RDS PostgreSQL** - Managed relational database
- **ElastiCache** - Managed Redis caching
- **Secrets Manager** - Secure secrets storage
- **CloudWatch** - Logging and monitoring

## Prerequisites

1. **AWS Account** - Sign up at [aws.amazon.com](https://aws.amazon.com)
2. **AWS CLI** - Install and configure credentials
3. **Docker** - For building container images

### Install AWS CLI

=== "macOS"
    ```bash
    brew install awscli
    ```

=== "Linux"
    ```bash
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    ```

=== "Windows"
    ```powershell
    msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
    ```

### Configure Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region (e.g., us-east-1)
# Enter output format (json)

# Verify configuration
aws sts get-caller-identity
```

## Quick Start

### Using django-matt Deploy Module

```python
from django_matt.deploy import DeploymentConfig, AWSProvider

# Configure deployment
config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    python_version="3.13",
    port=8000,
    workers=4,
    create_database=True,
    health_check_path="/health/",
)

# Initialize provider (mode: "apprunner" or "ecs")
provider = AWSProvider(config, mode="apprunner")

# Validate configuration
errors = provider.validate()
if errors:
    print("Validation errors:", errors)

# Generate configuration files
files = provider.generate_config()
for filename, content in files.items():
    with open(filename, "w") as f:
        f.write(content)
    print(f"Generated: {filename}")

# Deploy
import asyncio
result = asyncio.run(provider.deploy())
print(f"Status: {result.status}")
print(f"URL: {result.url}")
```

## Deployment Options

### Option 1: AWS App Runner (Recommended for Simplicity)

App Runner is the easiest way to deploy containers on AWS.

### Option 2: ECS Fargate (Recommended for Control)

ECS Fargate provides more control over networking, scaling, and costs.

## App Runner Deployment

### Generated Configuration

#### apprunner.yaml

```yaml
version: 1.0
runtime: python313
build:
  commands:
    pre-build:
      - uv pip install -r requirements.txt
    build:
      - python manage.py collectstatic --noinput
run:
  runtime-version: "3.13"
  command: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4
  network:
    port: 8000
    env: PORT
  env:
    - name: DJANGO_SETTINGS_MODULE
      value: config.settings
    - name: DJANGO_ENV
      value: production
    - name: DEBUG
      value: "false"
    - name: STATIC_URL
      value: /static/
    - name: STATIC_ROOT
      value: staticfiles
```

### Step-by-Step App Runner Deployment

#### 1. Create ECR Repository

```bash
# Create ECR repository
aws ecr create-repository --repository-name myapp

# Get login command
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

#### 2. Build and Push Docker Image

```bash
# Build image
docker build -t myapp .

# Tag for ECR
docker tag myapp:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/myapp:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/myapp:latest
```

#### 3. Create RDS Database

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
    --db-subnet-group-name myapp-db-subnet \
    --db-subnet-group-description "Subnet group for myapp" \
    --subnet-ids subnet-xxx subnet-yyy

# Create RDS instance
aws rds create-db-instance \
    --db-instance-identifier myapp-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username django \
    --master-user-password <password> \
    --allocated-storage 20 \
    --db-subnet-group-name myapp-db-subnet \
    --vpc-security-group-ids sg-xxx \
    --publicly-accessible
```

#### 4. Store Secrets

```bash
# Create secret for database URL
aws secretsmanager create-secret \
    --name myapp/database-url \
    --secret-string "postgres://django:<password>@<rds-endpoint>:5432/myapp"

# Create secret for Django secret key
aws secretsmanager create-secret \
    --name myapp/secret-key \
    --secret-string "your-very-long-secret-key"
```

#### 5. Create App Runner Service

```bash
# Create App Runner service
aws apprunner create-service \
    --service-name myapp \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/myapp:latest",
            "ImageConfiguration": {
                "Port": "8000",
                "RuntimeEnvironmentVariables": {
                    "DJANGO_SETTINGS_MODULE": "config.settings",
                    "DJANGO_ENV": "production"
                }
            },
            "ImageRepositoryType": "ECR"
        },
        "AutoDeploymentsEnabled": true
    }' \
    --instance-configuration '{
        "Cpu": "1024",
        "Memory": "2048"
    }' \
    --health-check-configuration '{
        "Protocol": "HTTP",
        "Path": "/health/",
        "Interval": 10,
        "Timeout": 5,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5
    }'
```

## ECS Fargate Deployment

### Generated Configuration

#### ecs-task-definition.json

```json
{
  "family": "myapp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/myapp-execution-role",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/myapp-task-role",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/myapp:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DJANGO_SETTINGS_MODULE",
          "value": "config.settings"
        },
        {
          "name": "DJANGO_ENV",
          "value": "production"
        },
        {
          "name": "DEBUG",
          "value": "false"
        },
        {
          "name": "PORT",
          "value": "8000"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:myapp/database-url"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:myapp/secret-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/myapp",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health/ || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

### Step-by-Step ECS Deployment

#### 1. Create VPC and Networking (if not exists)

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Create subnets, internet gateway, route tables...
# (Or use existing VPC)
```

#### 2. Create IAM Roles

```bash
# Create execution role (for ECS agent)
aws iam create-role \
    --role-name myapp-execution-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

# Attach policies
aws iam attach-role-policy \
    --role-name myapp-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Secrets Manager access
aws iam put-role-policy \
    --role-name myapp-execution-role \
    --policy-name SecretsManagerAccess \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": "arn:aws:secretsmanager:*:*:secret:myapp/*"
        }]
    }'
```

#### 3. Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name myapp-cluster
```

#### 4. Create CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name /ecs/myapp
```

#### 5. Register Task Definition

```bash
aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition.json
```

#### 6. Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name myapp-alb \
    --subnets subnet-xxx subnet-yyy \
    --security-groups sg-xxx \
    --type application

# Create target group
aws elbv2 create-target-group \
    --name myapp-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id vpc-xxx \
    --target-type ip \
    --health-check-path /health/

# Create listener
aws elbv2 create-listener \
    --load-balancer-arn <alb-arn> \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=<acm-cert-arn> \
    --default-actions Type=forward,TargetGroupArn=<tg-arn>
```

#### 7. Create ECS Service

```bash
aws ecs create-service \
    --cluster myapp-cluster \
    --service-name myapp \
    --task-definition myapp \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration '{
        "awsvpcConfiguration": {
            "subnets": ["subnet-xxx", "subnet-yyy"],
            "securityGroups": ["sg-xxx"],
            "assignPublicIp": "ENABLED"
        }
    }' \
    --load-balancers '[{
        "targetGroupArn": "<tg-arn>",
        "containerName": "web",
        "containerPort": 8000
    }]'
```

## buildspec.yml (CodeBuild)

For CI/CD with AWS CodePipeline:

```yaml
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - REPOSITORY_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/myapp
      - COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=${COMMIT_HASH:=latest}

  build:
    commands:
      - echo Build started on `date`
      - echo Building the Docker image...
      - docker build -t $REPOSITORY_URI:latest .
      - docker tag $REPOSITORY_URI:latest $REPOSITORY_URI:$IMAGE_TAG

  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing the Docker images...
      - docker push $REPOSITORY_URI:latest
      - docker push $REPOSITORY_URI:$IMAGE_TAG
      - echo Writing image definitions file...
      - printf '[{"name":"web","imageUri":"%s"}]' $REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
```

## Operations

### Scaling

#### App Runner

```bash
# Update auto-scaling configuration
aws apprunner update-service \
    --service-arn <service-arn> \
    --auto-scaling-configuration-arn <auto-scaling-arn>
```

#### ECS Fargate

```bash
# Update desired count
aws ecs update-service \
    --cluster myapp-cluster \
    --service myapp \
    --desired-count 5

# Configure auto-scaling
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/myapp-cluster/myapp \
    --min-capacity 1 \
    --max-capacity 10

# Add scaling policy
aws application-autoscaling put-scaling-policy \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/myapp-cluster/myapp \
    --policy-name cpu-scaling \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
        },
        "ScaleOutCooldown": 60,
        "ScaleInCooldown": 60
    }'
```

### View Logs

```bash
# View CloudWatch logs
aws logs tail /ecs/myapp --follow

# Or filter by time
aws logs tail /ecs/myapp --since 1h
```

### Run Migrations

```bash
# Run a one-off task
aws ecs run-task \
    --cluster myapp-cluster \
    --task-definition myapp \
    --launch-type FARGATE \
    --network-configuration '{
        "awsvpcConfiguration": {
            "subnets": ["subnet-xxx"],
            "assignPublicIp": "ENABLED"
        }
    }' \
    --overrides '{
        "containerOverrides": [{
            "name": "web",
            "command": ["python", "manage.py", "migrate"]
        }]
    }'
```

### Rollback

```bash
# ECS rollback via circuit breaker
aws ecs update-service \
    --cluster myapp-cluster \
    --service myapp \
    --deployment-configuration '{
        "deploymentCircuitBreaker": {
            "enable": true,
            "rollback": true
        }
    }'

# Or deploy previous task definition
aws ecs update-service \
    --cluster myapp-cluster \
    --service myapp \
    --task-definition myapp:previous-version
```

## Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `SECRET_KEY` | Django secret key | Secrets Manager |
| `DATABASE_URL` | PostgreSQL connection | Secrets Manager |
| `REDIS_URL` | ElastiCache endpoint | Environment |
| `ALLOWED_HOSTS` | Allowed hosts | Environment |
| `DJANGO_SETTINGS_MODULE` | Settings module | Environment |

## Cost Optimization

### App Runner

- Pay per vCPU-hour and GB-hour when running
- Automatic scale to zero capability
- Start from ~$5/month

### ECS Fargate

- Pay per vCPU and memory per second
- No scale to zero (minimum 1 task)
- More control over resources
- Start from ~$10/month

### Tips

1. **Use Spot Instances** - For non-production workloads
2. **Right-size containers** - Don't over-provision
3. **Use Reserved Instances** - For RDS in production
4. **Enable auto-scaling** - Scale down during low traffic
5. **Use NAT Gateway efficiently** - Centralize for multiple services

## Troubleshooting

### Container Won't Start

```bash
# Check CloudWatch logs
aws logs tail /ecs/myapp --since 1h

# Check task stopped reason
aws ecs describe-tasks \
    --cluster myapp-cluster \
    --tasks <task-arn>
```

### Database Connection Issues

```bash
# Verify security group allows traffic
aws ec2 describe-security-groups --group-ids sg-xxx

# Check RDS endpoint
aws rds describe-db-instances --db-instance-identifier myapp-db

# Verify secret value
aws secretsmanager get-secret-value --secret-id myapp/database-url
```

### Health Check Failures

```bash
# Check target group health
aws elbv2 describe-target-health --target-group-arn <tg-arn>

# Verify health check endpoint
curl http://<alb-dns>/health/
```

## Complete Example

```python
# deploy_aws.py
import asyncio
from django_matt.deploy import DeploymentConfig, AWSProvider

async def deploy():
    config = DeploymentConfig(
        app_name="myapp",
        django_settings_module="config.settings",
        python_version="3.13",
        port=8000,
        workers=4,
        environment="production",
        debug=False,
        allowed_hosts=["myapp.example.com"],
        health_check_path="/health/",
        health_check_interval=30,
        min_instances=2,
        max_instances=10,
        auto_scale=True,
    )

    # Use App Runner for simplicity
    provider = AWSProvider(config, mode="apprunner")
    # Or ECS for more control
    # provider = AWSProvider(config, mode="ecs")

    # Validate
    errors = provider.validate()
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return

    # Generate and deploy
    result = await provider.deploy()

    print(f"Status: {result.status}")
    print(f"URL: {result.url}")

    for log in result.logs:
        print(f"  {log}")

if __name__ == "__main__":
    asyncio.run(deploy())
```

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [AWS Documentation](https://docs.aws.amazon.com/)
