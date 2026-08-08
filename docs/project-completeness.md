# 🧾 Project Completeness Checklist

![Core](https://img.shields.io/badge/core_HA-complete-success)
![Docs](https://img.shields.io/badge/documentation-complete-success)
![Environment Gates](https://img.shields.io/badge/environment_gates-explicit-orange)

This checklist distinguishes **implemented repository capabilities** from **environment-specific activation work**.

## Core platform

- [x] Ubuntu 24.04 baseline
- [x] PostgreSQL 16
- [x] Patroni three-node HA
- [x] three-member etcd quorum
- [x] synchronous replication
- [x] HAProxy Primary-only routing
- [x] Keepalived VIP
- [x] LVM + XFS data storage
- [x] preflight safety checks
- [x] cluster-wide validation
- [x] idempotency safeguards for repeated runs

## Security

- [x] SCRAM TCP authentication baseline
- [x] local peer authentication
- [x] `trust` rule removal/validation
- [x] Patroni DCS-managed HBA workflow
- [x] declarative DB/user/role capability
- [x] network audit and CIDR model
- [x] TLS audit capability
- [x] TLS certificate deployment capability
- [x] TLS activation preparation capability
- [x] OS/SSH/AppArmor hardening framework
- [x] secrets/Vault guidance
- [ ] real firewall enforcement — environment-specific
- [ ] real PKI/TLS rollout — environment-specific
- [ ] Patroni REST / etcd TLS — separate environment-specific hardening

## Monitoring

- [x] Patroni Prometheus endpoint
- [x] etcd Prometheus endpoint
- [x] HAProxy built-in PROMEX endpoint
- [x] postgres_exporter endpoint
- [x] least-privilege exporter DB role (`pg_monitor`)
- [x] example Prometheus scrape configuration
- [x] example alert rules
- [x] monitoring audit playbook
- [x] host metrics explicitly kept outside project scope
- [ ] central Prometheus target integration — environment-specific
- [ ] alert routing/dashboard integration — environment-specific

## Recovery / operations

- [x] backup/WAL readiness audit
- [x] staged WAL archive configuration capability
- [x] restore/PITR runbook
- [x] PostgreSQL logging audit
- [x] patch-readiness audit
- [x] rolling maintenance runbook
- [x] XFS/LVM disk expansion runbook
- [x] node rebuild/rejoin runbook
- [x] failover/switchover runbook and reference test evidence
- [ ] durable backup repository — environment-specific
- [ ] recurring restore/PITR test — environment-specific
- [ ] central logging destination — environment-specific

## Documentation

- [x] root README
- [x] documentation index
- [x] architecture
- [x] ports/endpoints
- [x] deployment
- [x] preflight
- [x] validation/idempotency
- [x] operations
- [x] failover/switchover
- [x] security hardening
- [x] network hardening
- [x] access management
- [x] TLS design and activation
- [x] secrets management
- [x] monitoring
- [x] backup/restore/PITR
- [x] logging
- [x] patch management
- [x] disk expansion
- [x] node rebuild
- [x] troubleshooting
- [x] production readiness
- [x] architecture decisions
- [x] remaining environment integrations
- [x] changelog

## Final acceptance

Before treating a deployment as production-ready, complete the environment-specific unchecked items that match the deployment's security, backup, observability and recovery requirements.
