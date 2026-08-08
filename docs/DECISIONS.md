# 🧭 Architecture Decisions

This file records current design choices, not future intentions.

| Decision | Current choice |
|---|---|
| Cluster size | Three PostgreSQL/Patroni nodes |
| Failure domains | One database VM per independent failure domain where possible |
| OS | Ubuntu Server 24.04 LTS |
| PostgreSQL | Version 16 from approved APT repositories |
| HA manager | Patroni |
| DCS | Three-member etcd |
| Replication | Streaming replication with one synchronous standby |
| Application endpoint | Single Keepalived VIP on PostgreSQL port 5432 |
| Load balancer | HAProxy TCP mode, Primary-only backend health via Patroni |
| Read balancing | Not enabled; normal path is writable Primary |
| PostgreSQL storage | Local LVM + XFS at `/var/lib/postgresql` |
| Shared storage | Not required |
| Authentication | SCRAM for TCP, peer for local Unix-socket administration |
| `pg_hba` control | Patroni dynamic configuration for existing clusters |
| HAProxy metrics | Built-in PROMEX on port 8404 |
| PostgreSQL metrics | `prometheus-postgres-exporter` on port 9187, `pg_monitor`, peer auth |
| Host monitoring | External to this repository |
| TLS | Staged capability; environment-specific activation |
| Firewall enforcement | Disabled until real CIDRs are reviewed |
| Backup | Native WAL/PITR framework present; repository/destination is environment-specific |
| Package updates | Rolling maintenance runbook; unattended cluster upgrade disabled |

## Safety decisions

- Do not destroy/reinitialize a database node as a first troubleshooting step.
- Do not guess application, Kubernetes, admin or monitoring CIDRs.
- Do not enable TLS-only HBA before TLS is proven across application and replication paths.
- Do not store database passwords or private certificate keys in plaintext Git content.
- Do not automate simultaneous restart/upgrade of all HA nodes.
