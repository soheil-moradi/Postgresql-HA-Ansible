# ✅ Validation & Idempotency

![Validation](https://img.shields.io/badge/validation-HA_path-success)

## Cluster validation

Run:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
```

The validation playbook checks the operational path, not only process state.

Expected assertions include:

- etcd endpoint health;
- HAProxy configuration validity;
- etcd, Patroni, HAProxy and Keepalived active on all nodes;
- Patroni REST health;
- exactly one running Patroni Leader;
- the remaining members streaming;
- at least one synchronous standby;
- VIP owned by exactly one node;
- PostgreSQL reachable through VIP/HAProxy;
- SQL through VIP reaches a writable Primary.

## Monitoring validation

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-ha-monitoring.yml --ask-vault-pass -K
```

The reference deployment exposes:

```text
Patroni            :8008/metrics
etcd               :2379/metrics
HAProxy            :8404/metrics
postgres_exporter  :9187/metrics
```

## Full safe readiness check

```bash
./scripts/final-readiness-check.sh .
```

This runs:

1. duplicate YAML-key detection;
2. syntax check for all playbooks;
3. safe OS/network/TLS/monitoring/backup/logging/patch audits;
4. final HA validation.

## Idempotency target

After intended state has converged, rerunning a configuration playbook should normally produce:

```text
failed=0
unreachable=0
changed=0
```

A non-zero `changed` count is not automatically an error, but it should have an explainable cause such as:

- a deliberate configuration change;
- package installation/upgrade;
- external configuration drift;
- a generated file being rewritten by another system.

Investigate repeated changes before calling a role idempotent.
