# Deployment Guide

This guide covers deploying the Unified MCP Tool Graph in various environments.

## Prerequisites

- Docker and Docker Compose (for containerized deployment)
- Python 3.12+ (for direct deployment)
- Neo4j 5.x+ (optional, for dynamic tool retrieval)
- PostgreSQL 16+ (optional, for SaaS features)
- Redis 7+ (optional, for caching and rate limiting)

## Quick Start with Docker

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/unified-mcp-tool-graph.git
cd unified-mcp-tool-graph
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your configuration
```

### 3. Start Services

```bash
docker-compose up -d
```

This will start:
- Gateway service (port 8000)
- Neo4j (ports 7474, 7687)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Prometheus (port 9091)
- Grafana (port 3000)

### 4. Verify Deployment

```bash
curl http://localhost:8000/health
```

## Production Deployment

### Docker Compose (Recommended for Small-Medium Scale)

1. **Configure Production Environment**

```bash
# Production .env
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
ENABLE_HTTPS=true
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
ENABLE_MULTI_TENANCY=true
ENABLE_RATE_LIMITING=true
```

2. **Use Production Docker Compose**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. **Set Up Reverse Proxy (Nginx)**

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Kubernetes Deployment

1. **Create Namespace**

```bash
kubectl create namespace mcp-gateway
```

2. **Create Secrets**

```bash
kubectl create secret generic mcp-secrets \
  --from-literal=neo4j-password=your-password \
  --from-literal=jwt-secret=your-secret \
  --namespace=mcp-gateway
```

3. **Deploy Services**

```bash
kubectl apply -f k8s/ -n mcp-gateway
```

4. **Expose Service**

```bash
kubectl expose deployment gateway \
  --type=LoadBalancer \
  --port=80 \
  --target-port=8000 \
  --namespace=mcp-gateway
```

## Environment-Specific Configurations

### Development

```bash
# .env.development
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_REQUEST_LOGGING=true
MOCK_MCP_SERVERS=false
```

### Staging

```bash
# .env.staging
DEBUG=false
LOG_LEVEL=INFO
ENABLE_MULTI_TENANCY=true
ENABLE_RATE_LIMITING=true
```

### Production

```bash
# .env.production
DEBUG=false
LOG_LEVEL=WARNING
ENABLE_MULTI_TENANCY=true
ENABLE_RATE_LIMITING=true
ENABLE_HTTPS=true
ENABLE_METRICS=true
```

## Database Setup

### Neo4j

1. **Start Neo4j**

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5.15-community
```

2. **Run Ingestion Pipeline**

```bash
uv run python Ingestion_pipeline/Ingestion_Neo4j.py
```

### PostgreSQL

1. **Initialize Database**

```bash
psql -U postgres -d mcp_gateway -f scripts/init_db.sql
```

2. **Run Migrations**

```bash
uv run python scripts/migrate.py
```

## Monitoring Setup

### Prometheus

Prometheus is included in `docker-compose.yml`. Access at `http://localhost:9091`

### Grafana

1. Access Grafana at `http://localhost:3000`
2. Default credentials: `admin/admin`
3. Import dashboards from `config/grafana/dashboards/`

### Health Checks

```bash
# Gateway health
curl http://localhost:8000/health

# Metrics
curl http://localhost:9090/metrics
```

## Scaling

### Horizontal Scaling

1. **Gateway Instances**

```bash
# Scale gateway to 3 instances
docker-compose up -d --scale gateway=3
```

2. **Load Balancer**

Configure a load balancer (Nginx, HAProxy, or cloud LB) to distribute traffic.

### Vertical Scaling

Adjust resource limits in `docker-compose.yml`:

```yaml
services:
  gateway:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## Backup and Recovery

### Neo4j Backup

```bash
# Create backup
docker exec neo4j neo4j-admin backup --backup-dir=/backups --name=backup-$(date +%Y%m%d)

# Restore backup
docker exec neo4j neo4j-admin restore --from=/backups/backup-20240115
```

### PostgreSQL Backup

```bash
# Create backup
docker exec postgres pg_dump -U postgres mcp_gateway > backup.sql

# Restore backup
docker exec -i postgres psql -U postgres mcp_gateway < backup.sql
```

## Troubleshooting

### Gateway Won't Start

1. Check logs: `docker-compose logs gateway`
2. Verify ports aren't in use: `netstat -tulpn | grep 8000`
3. Check environment variables: `docker-compose config`

### Neo4j Connection Issues

1. Verify Neo4j is running: `docker ps | grep neo4j`
2. Test connection: `cypher-shell -u neo4j -p password`
3. Check firewall rules

### High Memory Usage

1. Reduce `MAX_CONCURRENT_SERVERS`
2. Lower `SERVER_KEEP_ALIVE` timeout
3. Enable tool caching to reduce queries

## Performance Tuning

### Database Connections

```python
# In your .env
NEO4J_MAX_CONNECTIONS=50
POSTGRES_MAX_CONNECTIONS=20
REDIS_MAX_CONNECTIONS=100
```

### Caching

```python
ENABLE_TOOL_CACHE=true
TOOL_CACHE_TTL=3600  # 1 hour
```

### Server Pooling

```python
MAX_CONCURRENT_SERVERS=50
SERVER_KEEP_ALIVE=600  # 10 minutes
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable HTTPS
- [ ] Configure CORS
- [ ] Set up rate limiting
- [ ] Enable authentication
- [ ] Configure firewall
- [ ] Set up monitoring
- [ ] Enable database encryption
- [ ] Regular backups
- [ ] Security updates

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Review documentation: `docs/`
3. Open an issue on GitHub
4. Check health endpoint: `/health`

