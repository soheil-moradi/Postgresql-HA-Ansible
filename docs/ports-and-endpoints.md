# 🔌 Ports & Endpoints

![Network](https://img.shields.io/badge/network-explicit_ports-blue)

This quick reference separates the application data path, HA control plane and monitoring endpoints.

## Application / PostgreSQL

| Endpoint | Default | Exposure |
|---|---:|---|
| PostgreSQL service VIP | `5432/tcp` | Approved application networks |
| Direct PostgreSQL node listener | `5432/tcp` | Cluster nodes and explicitly reviewed direct clients only |

Normal applications should use the service DNS/VIP rather than a fixed node address.

## HA control plane

| Component | Default | Exposure |
|---|---:|---|
| Patroni REST | `8008/tcp` | Cluster nodes; approved monitoring if required |
| etcd client | `2379/tcp` | Cluster nodes; approved monitoring if required |
| etcd peer | `2380/tcp` | Cluster nodes only |
| Keepalived VRRP | IP protocol `112` | Cluster nodes only |

## Monitoring

| Component | Default | Path |
|---|---:|---|
| Patroni | `8008/tcp` | `/metrics` |
| etcd | `2379/tcp` | `/metrics` |
| HAProxy PROMEX | `8404/tcp` | `/metrics` |
| postgres_exporter | `9187/tcp` | `/metrics` |
| HAProxy local stats | `127.0.0.1:7000` | `/stats` |

The HAProxy local stats endpoint is intentionally not a remote monitoring interface.

## Management

| Component | Default | Exposure |
|---|---:|---|
| SSH | `22/tcp` | Reviewed admin/Ansible sources |

## Firewall guidance

Do not copy example CIDRs directly. Populate these only after observing real traffic sources:

```yaml
postgresql_admin_cidrs: []
postgresql_application_cidrs: []
postgresql_monitoring_cidrs: []
postgresql_network_extra_cidrs: []
```

See [Network Hardening](network-hardening.md) for the enforcement workflow.
