# 💾 PostgreSQL Native Backup, WAL Archive & PITR

![Recovery](https://img.shields.io/badge/recovery-base_backup_%2B_WAL-blue)
![Restore Test](https://img.shields.io/badge/restore_test-required-red)

## Goal

A production recovery design should provide:

```text
base backup
  +
continuous WAL archive
  -> retention
  -> restore
  -> point-in-time recovery
  -> validation
```

VM-level backup can be useful as an additional layer, but it does not replace PostgreSQL-native, application-consistent recovery and tested PITR.

## Current repository capability

```yaml
postgresql_backup_management_enabled: false
postgresql_backup_archive_command: ""
postgresql_backup_archive_timeout: "60s"
postgresql_backup_destination: ""
```

The repository intentionally does not invent a backup destination.

## WAL archive command requirements

`archive_command` must:

- return `0` only after the WAL file is durably archived;
- return non-zero on failure so PostgreSQL retries;
- avoid silently replacing a different WAL file with the same name;
- protect archived WAL with the same sensitivity as database data.

## Audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-backup-readiness.yml --ask-vault-pass -K
```

The audit reads archive settings/status and verifies `pg_basebackup` availability.

## Staged WAL configuration

After selecting a real repository/tool:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/prepare-wal-archiving.yml --ask-vault-pass -K
```

The capability can place archive settings into Patroni DCS. It intentionally does not perform a rolling PostgreSQL restart for server-start parameters.

## Validate archiving

After real activation:

```sql
SELECT pg_switch_wal();

SELECT archived_count,
       failed_count,
       last_archived_wal,
       last_archived_time,
       last_failed_wal,
       last_failed_time
FROM pg_stat_archiver;
```

Also verify the WAL object is actually present and readable in the backup repository.

## Base backup

The environment must decide:

- backup tool/workflow;
- source node policy;
- off-host repository location;
- encryption;
- schedule;
- retention;
- throughput limits;
- repository credentials;
- immutability/offline protection as required.

## Restore/PITR test

A backup is not considered reliable until restore is tested.

Recommended procedure:

1. provision an isolated recovery host;
2. restore a base backup;
3. configure `restore_command` for the archive;
4. configure a recovery target when testing PITR;
5. start the recovered PostgreSQL outside the production Patroni cluster;
6. verify database consistency and expected application data;
7. record restore duration and recovery-point results.

> ⚠️ Never test PITR by overwriting the production cluster's data directory.

## Monitoring

Alert on:

```text
WAL archive failures
last successful WAL archive too old
base backup failed
last successful base backup too old
restore/PITR test too old or never completed
```
