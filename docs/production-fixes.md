# Production reliability patch — 2026-09-05

## Applying the patch

Run from the Git repository root corresponding to the uploaded ZIP:

```bash
git status --short
git apply --check postgresql-ha-production-fixes.patch
git apply postgresql-ha-production-fixes.patch
git diff --check
git diff --stat
```

`git apply` edits repository files only. It does not execute Ansible, connect to
servers, initialize disks, restart databases, enforce a firewall, or enable backup.
If the context check fails, stop and reconcile the local edits; do not use
`--reject` or a forced replacement on a production repository.

To reverse only these source changes, while their context is still intact:

```bash
git apply --reverse --check postgresql-ha-production-fixes.patch
git apply --reverse postgresql-ha-production-fixes.patch
```

Reversing a source patch does not reverse previously applied server configuration.
Do not run `site.yml` with example inventory values against an existing cluster.

## Fixed defects

| Finding | Change |
|---|---|
| Obsolete CIDR preflight assertion | Empty legacy list accepted; required HBA input is validated separately. |
| Concurrent load-balancer restart | Serial batches, graceful HAProxy reload, local service and VIP checks before advancing. |
| False successful Patroni reload | Local systemd reload with error propagation; no unconditional success after failure. |
| Unescaped YAML passwords | JSON-quoted string scalars and YAML validation before atomic template replacement. |
| Bootstrap-only PostgreSQL parameters | One managed mapping used for bootstrap and verified REST/DCS subset convergence. |
| Ineffective readonly downgrade | Revoke direct writes and future default writes; reject remaining inherited/owner/PUBLIC write rights. |
| TLS continues after another node fails | Whole-cluster prerequisite checks and global error propagation before DCS mutation. |
| TLS switches are informational only | Explicit internal TLS rollout and proven-TLS-gated hostssl HBA enforcement. |
| Monitoring switches ignored | Flags gate installation/configuration; configured ports respected. |
| Local etcd maintenance stops Patroni | Soft `Wants` dependency replaces `Requires`; remote healthy etcd members remain usable. |
| Unsafe storage re-run checks | Verify configured disk really belongs to the existing VG; create LV only when absent; follow by-id symlinks. |
| Network enforcement missing | Dedicated nftables table, reviewed sources, new SSH connection test and timed rollback. |
| Backup integration missing | Optional encrypted pgBackRest, off-host mount guard, full/diff timers, retention and backup freshness checks. |
| SELECT-only write-path validation | Separate committed marker test via VIP with replica reads and isolated schema cleanup. |

The HA topology and synchronous/strict choices remain the existing inventory
choices. `synchronous_mode_strict: false` is not automatically changed to true.

## Validation supplied and its limits

The authoring environment ran 24 local tests covering YAML duplicate keys and
parsing, Python parsing, shell syntax, reload error propagation, DCS HTTP payloads
and subset comparisons, firewall input validation and rollback, and backup mount
guards. It did not have Ansible/Jinja2/PostgreSQL/nftables/HAProxy executables.
Network installation of those dependencies was unavailable. Three additional
tests therefore skipped locally. No live HA cluster was deployed or certified.

The CI workflow installs Ansible and collections, renders all templates, runs a
PostgreSQL 16 privilege regression against a disposable database, and syntax-checks
all playbooks. CI has been added, not run on your remote repository by this patch.
Before production rollout, run it (or equivalent local checks):

```bash
ansible-galaxy collection install -r requirements.yml
python3 -m unittest discover -s tests -v
ansible-playbook site.yml playbooks/*.yml --syntax-check --ask-vault-pass
```

Tests print an explicit skip if Jinja2 or the disposable PostgreSQL DSN is absent.
Never point `POSTGRES_TEST_DSN` at a business database; it is for an isolated test
instance. Runtime prerequisites are Ubuntu 24.04/Python 3.12 and PostgreSQL 16.

The existing read-only audit remains separate from writes:

```bash
bash scripts/final-readiness-check.sh . --ask-vault-pass -K
```

This does not exercise failover, commits or restore. The explicit write test is:

```bash
ansible-playbook playbooks/validate-write-path.yml --ask-vault-pass -K
```

It creates and commits a uniquely named marker schema, reads it on both replicas,
and removes only the schema with the matching ownership marker. It generates WAL.
If cleanup cannot reconnect after a failure, it reports the schema name; investigate
and remove that specific test schema once the primary is healthy.

## Existing-cluster PostgreSQL configuration

`site.yml` now also runs `apply-postgresql-config.yml`. For a targeted change:

```bash
ansible-playbook playbooks/apply-postgresql-config.yml --ask-vault-pass -K
```

Review `patroni_dynamic_configuration` first: it is the authoritative subset owned
by this repository. Unrelated DCS keys such as HBA, TLS, custom archive commands
and externally added parameters are retained. A successful API patch means DCS
converged; settings requiring a PostgreSQL restart may remain pending.

For a restart-required change, verify one leader, two streaming replicas and etcd
quorum first. Use the installed `patronictl restart` to restart one replica; wait
for health and streaming recovery before the other. Perform a planned switchover
to an updated replica, validate, then restart the former primary if required.
For decreases to shared-memory sizing parameters PostgreSQL requires primary-first
ordering; follow PostgreSQL's parameter-specific rules instead of blindly applying
a generic replica-first sequence. Do not automate a cluster-wide restart.

## TLS rollout

1. Provide node-specific CA-signed server certificates and keys. Because Patroni
   advertises IP addresses, `verify-full` requires the matching IP SANs. Include the
   VIP/service DNS identity in every server certificate when clients verify the
   shared endpoint. Supply intermediates in the certificate bundle if needed.
2. Set `postgresql_tls_certificate_deployment_enabled: true` and provide sources;
   run `deploy-postgresql-tls-certificates.yml`. Candidates are validated before
   they replace live files. Encrypted server private keys requiring a prompt are
   unsupported by this unattended workflow.
3. Set `postgresql_tls_activation_enabled: true`; run
   `activate-postgresql-tls.yml` across ALL nodes. `ssl` is reloadable: activation
   can take effect immediately when Patroni updates PostgreSQL. The play verifies
   CA-trusted encrypted sessions; it does not automatically restart PostgreSQL.
4. Choose `postgresql_tls_internal_sslmode: verify-full` after SANs are ready; run
   `apply-postgresql-internal-tls.yml`. It proves the selected policy against every
   endpoint before updating local Patroni configurations one at a time. Reloading
   does not forcibly replace an already-open replication session; verify new
   sessions during the next controlled reconnect/maintenance test.
5. After applications support TLS, set `postgresql_tls_require_ssl: true`; run
   `harden-pg-hba.yml`. Unix peer administration is retained. TCP `host` entries,
   including reviewed extra rules, become `hostssl`; contradictory `hostnossl`
   exceptions and trust entries are rejected.

Patroni REST and etcd still use HTTP in this patch; PostgreSQL TLS does not encrypt
the control plane. Use the reviewed isolated management network/firewall described
below. If policy requires control-plane mutual TLS, plan that as a separate PKI
migration. This patch does not invent CA files or rotate etcd identities.

## Network enforcement

Define real `postgresql_admin_cidrs`, `postgresql_application_cidrs` and
`postgresql_monitoring_cidrs`. The observed SSH source must be covered by admin
CIDRs. Extra unrestricted CIDRs and `/0` are rejected. This implementation targets
the repository's IPv4 topology and drops IPv6 access to managed ports.

```bash
ansible-playbook playbooks/audit-network-hardening.yml --ask-vault-pass -K
# Set postgresql_network_hardening_enforce: true after reviewing source networks.
ansible-playbook playbooks/apply-network-hardening.yml --ask-vault-pass -K
```

Only the `inet pg_ha_guard` table is owned. Other firewall rules are neither flushed
nor adopted, and an unrelated pre-existing table with that name is rejected.
Each node receives a 120-second rollback timer independent of the SSH session.
The play opens a fresh SSH connection, verifies etcd and the VIP, then commits.
On failure, stop and allow rollback; do not proceed to a second node. Keep console
access for infrastructure tests. Turning the flag false stops management; it does
not remove an already installed firewall policy.

The policy applies to managed service ports; it is not a universal default-deny
host firewall. Existing firewall drops still take precedence. A dedicated boot
unit restores this table; test reboot persistence alongside your existing firewall
manager. No generic nftables service or unrelated ruleset is enabled/replaced.

etcd exposes metrics and its unauthenticated API on the same port. By default only
DB-node sources can access that port. `postgresql_etcd_metrics_network_access: true`
explicitly extends that trust to reviewed monitoring CIDRs; use it only if that
trust is acceptable. For strictly separated metrics, use a dedicated proxy or
control-plane mTLS integration. Patroni/HAProxy/postgres_exporter probes are allowed
from DB nodes and reviewed monitoring sources.

## Backup setup and retention

This implementation chooses one concrete supported model: the same durable,
read/write **hard-mounted off-host NFS export on all three nodes**, with pgBackRest
repository encryption. Provision the mount and writable repository directory
outside PGDATA; this playbook does not mount or provision a NAS.

Set:

```yaml
postgresql_backup_management_enabled: true
postgresql_backup_repository_mount: /mnt/pg-backups
postgresql_backup_repository_source: nas.example.local:/postgres-backups
postgresql_backup_destination: /mnt/pg-backups/pg-internal
postgresql_backup_retention_full: 2
postgresql_backup_retention_diff: 7
postgresql_backup_schedule_enabled: false
```

Use your actual NFS source, path and retention. In encrypted Vault provide
`vault_pgbackrest_repository_password`, a 32+ character base64-style random secret.
Keep an independently recoverable copy of that secret. Do not change it on an
existing encrypted repository without a deliberate migration.

```bash
ansible-playbook playbooks/configure-backups.yml --ask-vault-pass -K
```

If `archive_mode` is pending restart, complete the controlled rolling restart.
Then, on the current primary, create the first verified full backup:

```bash
sudo -u postgres /usr/local/sbin/pg-ha-backup full
```

Enable `postgresql_backup_schedule_enabled: true` and rerun `configure-backups.yml`.
The default schedules are Sunday full and Monday–Saturday differential at 02:00 UTC.
Timers exist on all nodes, but only the current primary runs a backup. After
failover the next scheduled run happens on the new primary. Review the backup-age
objective and run a manual backup if a failover interrupted the scheduled one.

Every archive/backup checks the mounted source and rejects missing mounts, local
fallback, read-only/soft NFS mounts, and repository path escapes. These checks do
not replace storage-level durability/availability and mount health monitoring.
pgBackRest performs retention; there is no ad hoc deletion of WAL files.

```bash
ansible-playbook playbooks/verify-backups.yml --ask-vault-pass -K
```

This exercises WAL archiving and requires a completed backup within the configured
age. `prepare-wal-archiving.yml` remains for externally managed archive tools; do
not run it with a conflicting command after configuring managed pgBackRest.

## Isolated restore/PITR acceptance

A successful backup is not a completed restore test. On a separate recovery VM
outside the production inventory, install PostgreSQL 16 and the same pgBackRest
version, provide read access to the repository and its encryption secret, and use
a separate recovery configuration with an EMPTY data directory outside production.

Use `pgbackrest --config=<recovery-config> --stanza=<cluster> --pg1-path=<empty-test-dir>
restore` for latest recovery. For PITR add `--type=time --target='<timestamp with
explicit time zone>' --target-action=promote`. Do not use `--delta` against a live
or nonempty production directory. Start only this isolated PostgreSQL instance on
a separate local port, inspect recovery logs, and verify expected application data
at the chosen point. Record backup label, recovery target, achieved recovery point,
startup consistency checks and elapsed recovery time. Keep this test out of the
production Patroni/etcd namespace.

## References

- [Patroni dynamic configuration](https://patroni.readthedocs.io/en/latest/faq.html)
- [Ansible fatal error handling](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_error_handling.html)
- [PostgreSQL 16 TLS](https://www.postgresql.org/docs/16/ssl-tcp.html)
- [pgBackRest configuration](https://pgbackrest.org/configuration.html)
- [pgBackRest recovery guide](https://pgbackrest.org/user-guide.html)
