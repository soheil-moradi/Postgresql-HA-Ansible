# 🧾 Logging

![Logging](https://img.shields.io/badge/PostgreSQL-file_logging-enabled-success)

## PostgreSQL baseline

Patroni-managed PostgreSQL parameters enable file logging with rotation and useful operational signals such as:

```text
logging collector
slow statement threshold
lock waits
checkpoints
autovacuum duration
temporary-file threshold
```

Default log directory:

```text
/var/log/postgresql
```

## Audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-logging.yml --ask-vault-pass -K
```

## Central logging

Central shipping is intentionally environment-specific:

```yaml
postgresql_central_logging_enabled: false
postgresql_central_logging_destination: ""
```

Do not install an arbitrary logging agent from this database role. Integrate with the approved platform logging agent and destination.

## Recommended sources

Consider centralizing, according to retention/security policy:

```text
PostgreSQL logs
Patroni journal
etcd journal
HAProxy journal
Keepalived journal
postgres_exporter journal
Ansible deployment/audit output
```

Preserve enough local log history to troubleshoot database incidents when the central logging service itself is unavailable.
