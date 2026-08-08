# 🩹 Patch Management

![Maintenance](https://img.shields.io/badge/maintenance-rolling-blue)
![Auto Upgrade](https://img.shields.io/badge/automatic_cluster_upgrade-disabled-lightgrey)

Automatic cluster-wide package upgrades are deliberately disabled.

## Audit available packages

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-patch-readiness.yml --ask-vault-pass -K
```

The audit shows installed HA package versions and simulates APT upgrades without installing them.

## Rolling maintenance sequence

For changes requiring restart/reboot:

```text
1. validate cluster
2. patch/restart Replica A
3. wait for streaming and acceptable lag
4. patch/restart Replica B / Sync Standby as appropriate
5. planned switchover if the Primary needs maintenance
6. patch/restart former Primary
7. wait for rejoin
8. final validation
```

Never intentionally lose etcd quorum. With three members, keep at least two available.

## PostgreSQL major upgrades

This runbook is **not** a PostgreSQL major-version upgrade procedure. Treat major-version migration as a separate project with explicit compatibility, rollback and data-migration planning.

## Repository promotion

For controlled environments, promote tested package versions through internal repository channels before database maintenance.
