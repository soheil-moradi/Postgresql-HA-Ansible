# 📚 Documentation Index

> See [Project Completeness](project-completeness.md) for the implemented-capability checklist and environment-specific gates.

![Docs](https://img.shields.io/badge/docs-maintained-success)
![Safety](https://img.shields.io/badge/approach-safety--first-blue)

Use this page as the entry point for operators, platform engineers and DBAs.

## 🚀 Build and deploy

| Document | Purpose |
|---|---|
| [Architecture](architecture.md) | Components, data path, control plane, storage and port matrix |
| [Ports & Endpoints](ports-and-endpoints.md) | Quick network and monitoring port reference |
| [Deployment Guide](deployment-guide.md) | End-to-end installation workflow |
| [Preflight Checks](preflight.md) | Non-destructive deployment safety gate |
| [Validation & Idempotency](validation.md) | HA assertions, readiness checks and convergence target |
| [Configuration Reference](configuration-reference.md) | Important variables and feature flags |
| [Secrets Management](secrets-management.md) | Vault, credentials, certificates and rotation principles |

## 🛠️ Operate

| Document | Purpose |
|---|---|
| [Operations Guide](operations-guide.md) | Daily health checks, status, maintenance and safe restart rules |
| [Failover & Switchover](failover-and-switchover.md) | Planned and automatic role changes, validation and test evidence |
| [Monitoring](monitoring.md) | Prometheus endpoints, exporter security and alerting |
| [Logging](logging.md) | PostgreSQL log baseline and central-shipping integration |
| [Patch Management](patch-management.md) | HA-safe rolling patch workflow |
| [Disk Expansion](disk-expansion.md) | Online LVM/XFS growth procedure |
| [Node Rebuild](node-rebuild.md) | Safe replacement/rejoin procedure for one failed replica node |
| [Troubleshooting](troubleshooting.md) | Symptom-driven diagnostic commands |

## 🔒 Secure

| Document | Purpose |
|---|---|
| [Security Hardening](security-hardening.md) | Overall security model and hardening status |
| [Network Hardening](network-hardening.md) | CIDR model and safe firewall-enforcement workflow |
| [PostgreSQL Access Management](postgresql-access-management.md) | Databases, roles, memberships and privilege profiles |
| [PostgreSQL TLS](postgresql-tls.md) | TLS design, audit and certificate requirements |
| [PostgreSQL TLS Activation](postgresql-tls-activation.md) | Controlled TLS activation and rolling restart sequence |

## 💾 Protect and recover

| Document | Purpose |
|---|---|
| [Backup & Restore](backup-and-restore.md) | Base backup, WAL archive, PITR and restore validation |
| [Production Readiness](production-readiness.md) | Safe final audit and remaining environment-specific gates |

## 🧭 Project history and decisions

- [Architecture Decisions](DECISIONS.md)
- [Remaining Environment Integrations](NEXT_PHASES.md)

> ✅ Feature-specific documentation is intentionally linked from the top-level README and from this index so a new engineer does not need prior project history to operate the cluster safely.
