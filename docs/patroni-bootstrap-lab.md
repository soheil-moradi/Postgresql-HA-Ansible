# PostgreSQL 16 + Patroni: controlled lab bootstrap

Status: **storage and Patroni read-only preflight verified on all three lab
nodes; the new Patroni bootstrap is proposed but NOT yet deployed**. PostgreSQL
replication has not been tested.

This playbook is for a **disposable, trusted, colocated 3-node lab only**. It
reuses `roles/patroni`, never formats a disk or changes etcd membership, and
requires explicit approval and four separately encrypted secrets. Transport
is currently plaintext HTTP for etcd and Patroni; PostgreSQL TCP uses SCRAM.
Production certificate deployment, DR, synchronous durability, automatic
membership changes, backup and RW/RO VIPs are separate milestones.

## Private secret source

Keep the encrypted file OUTSIDE the public repository and inventory examples.
Create using `EDITOR=vim ansible-vault create "$HOME/w/postgres/patroni-lab-vault.yml"`.
Inside the editor, define four distinct random passwords (20+ characters):

```yaml
vault_postgres_superuser_password: REPLACE_WITH_RANDOM_SECRET
vault_postgres_replication_password: REPLACE_WITH_RANDOM_SECRET
vault_postgres_rewind_password: REPLACE_WITH_RANDOM_SECRET
vault_patroni_rest_password: REPLACE_WITH_RANDOM_SECRET
```

Use a private inventory for all real addresses. The role's low-priority
nonsecret defaults supply a small **asynchronous** lab configuration unless
explicitly overridden. Do not use production group_vars as lab shortcuts.

## Validate, then bootstrap

```bash
./scripts/validate-local.sh
ansible-playbook -i "$INV" -u YOUR_SSH_USER -K \
  --ask-vault-pass \
  -e "@$HOME/w/postgres/patroni-lab-vault.yml" \
  -e postgres_storage_discovery_mode=auto \
  -e patroni_lab_bootstrap_approved=true \
  playbooks/patroni-bootstrap-lab.yml
```

The workflow imports the read-only PostgreSQL storage + etcd preflight, rejects
an unapproved run before mutations, rejects foreign data directories, previous
unmanaged configurations, listeners and distro PostgreSQL clusters, then checks
that the DCS namespace and known local data state agree. A matching local
ownership marker allows safe rerun or recovery after partial installation.
Never delete/rename `PG_VERSION`, the marker or etcd keys to bypass these gates.

Installation is separate from startup: all three nodes receive the existing
Patroni role, the first node starts before the two replicas, and the final
checks require exactly one leader, two streaming replicas and two streaming
connections in `pg_stat_replication`. A second run should have `changed=0`.
Stop after a failure; inspect the first failed task before attempting a rerun.
