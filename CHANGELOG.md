# Changelog

## Initial documented release — 2026-08

### Core HA

- PostgreSQL 16 three-node Patroni cluster automation
- three-member etcd DCS
- HAProxy Primary-only routing
- Keepalived VIP
- synchronous replication
- LVM + XFS data storage
- deployment and HA validation

### Hardening

- SCRAM/peer authentication baseline
- Patroni DCS-managed `pg_hba`
- network-hardening audit/foundation
- declarative PostgreSQL access-management capability
- PostgreSQL TLS audit, certificate-deployment and activation capabilities
- optional OS/SSH/AppArmor hardening framework

### Observability

- Patroni Prometheus metrics
- etcd Prometheus metrics
- HAProxy built-in PROMEX endpoint
- PostgreSQL `prometheus-postgres-exporter` using local peer auth and `pg_monitor`
- example Prometheus scrape configuration and alert rules

### Operations

- backup/WAL/PITR readiness framework
- PostgreSQL logging audit
- rolling patch-management runbook
- LVM/XFS disk-expansion runbook
- node rebuild/rejoin runbook
- failover/switchover test documentation
- final production-readiness/self-check workflow

## 2026-09-05 — Production reliability fixes

- Fix preflight, YAML secret encoding, Patroni reload errors and existing-cluster DCS convergence.
- Serialize load-balancer changes and use graceful HAProxy reload.
- Enforce readonly downgrades and reject inherited write rights.
- Gate TLS on all-node prerequisites; implement internal TLS and hostssl workflows.
- Add opt-in managed-port nftables enforcement with timed rollback.
- Add opt-in encrypted pgBackRest on a verified shared off-host NFS repository.
- Add committed VIP/replica probes, regression tests and PostgreSQL 16 CI tests.
- Document unexecuted live HA, firewall, backup and restore acceptance tests.
