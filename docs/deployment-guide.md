# 🚀 Deployment Guide

![Workflow](https://img.shields.io/badge/workflow-preflight_%E2%86%92_deploy_%E2%86%92_validate-blue)

This guide describes a clean three-node deployment and the safe post-deployment capabilities.

## 0. Clone and enter the repository

```bash
git clone <repository-url> postgresql-ha-ansible
cd postgresql-ha-ansible
```

Before running any deployment playbook, review the inventory, group variables, Vault example, target data disk and optional feature flags. The repository defaults are intentionally conservative.

## 1. Prerequisites

### Control host

- Ansible Core compatible with the repository;
- SSH access to all database nodes;
- sudo privileges on the managed nodes;
- required collections installed from `requirements.yml`.

### Database nodes

Reference platform:

```text
Ubuntu Server 24.04 LTS
PostgreSQL 16 packages available from an approved APT repository
one dedicated PostgreSQL data disk
stable DNS and NTP
three independent failure domains where possible
```

For isolated environments, all required packages must exist in the internal repository before deployment.

## 2. Configure inventory

Edit:

```text
inventory/production/hosts.yml
```

Example only:

```yaml
all:
  children:
    postgresql_cluster:
      hosts:
        pg-node-01:
          ansible_host: 10.10.20.11
          node_fqdn: pg-node-01.example.local
          postgres_data_device: /dev/sdb
          keepalived_priority: 150
```

Use unique IPs, FQDNs and Keepalived priorities.

## 3. Configure group variables

Edit:

```text
inventory/production/group_vars/all/main.yml
```

Review:

- cluster name, VIP and DNS name;
- DNS and NTP;
- APT repository probes;
- data disk and XFS/LVM settings;
- PostgreSQL resource sizing;
- Patroni timing and synchronous mode;
- optional hardening flags;
- monitoring CIDRs.

See [Configuration Reference](configuration-reference.md).

## 4. Create Vault secrets

```bash
cp inventory/production/group_vars/all/vault.yml.example \
   inventory/production/group_vars/all/vault.yml

ansible-vault encrypt inventory/production/group_vars/all/vault.yml
```

Fill only the required secret values. Never commit plaintext secrets.

## 5. Verify connectivity

```bash
ansible \
  -i inventory/production/hosts.yml \
  postgresql_cluster \
  -m ping \
  --ask-vault-pass -K
```

## 6. Run preflight

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  playbooks/preflight.yml \
  --ask-vault-pass -K
```

Preflight is deliberately non-destructive. It checks:

- Ubuntu release;
- CPU and memory thresholds;
- DNS/FQDN resolution;
- inter-node reachability;
- NTP/clock health;
- package repository reachability and candidates;
- VIP safety;
- data disk existence, size and signatures;
- required Vault values.

Resolve all failures before continuing.

## 7. Deploy

Before the first destructive storage initialization, verify the exact target device from preflight and explicitly set:

```yaml
postgres_data_disk_allow_initialize: true
```

Keep the repository default `false` unless initialization is intentionally required.

Optional dry-run:

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  site.yml \
  --check --diff \
  --ask-vault-pass -K
```

Then deploy:

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  site.yml \
  --ask-vault-pass -K
```

The storage role initializes the configured data disk only when explicitly allowed and only after safety checks pass.

## 8. Harden PostgreSQL authentication

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  playbooks/harden-pg-hba.yml \
  --ask-vault-pass -K
```

This moves the persistent desired HBA rules into Patroni dynamic configuration and validates that no `trust` rules remain.

## 9. Enable monitoring endpoints

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  playbooks/enable-postgresql-monitoring-endpoints.yml \
  --ask-vault-pass -K
```

The playbook:

1. verifies `prometheus-postgres-exporter` exists in configured APT repositories;
2. verifies HAProxy was built with PROMEX support;
3. creates a least-privilege PostgreSQL monitoring role;
4. installs and configures postgres_exporter;
5. enables HAProxy `/metrics`;
6. validates both endpoints;
7. runs the normal HA validation.

## 10. Optional capabilities

### Access management

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/manage-postgresql-access.yml --ask-vault-pass -K
```

Disabled until `postgresql_access_management_enabled: true` and objects are defined.

### TLS audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-tls.yml --ask-vault-pass -K
```

### TLS certificate deployment

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/deploy-postgresql-tls-certificates.yml --ask-vault-pass -K
```

Disabled until certificate sources and identities are reviewed.

### TLS activation preparation

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/activate-postgresql-tls.yml --ask-vault-pass -K
```

Disabled by default and intentionally does not perform rolling restarts automatically.

### Network audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-network-hardening.yml --ask-vault-pass -K
```

Firewall enforcement remains off until management/application/monitoring CIDRs are reviewed.

### WAL archive preparation

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/prepare-wal-archiving.yml --ask-vault-pass -K
```

Disabled until a real backup destination and durable archive command exist.

## 11. Validate

```bash
ansible-playbook \
  -i inventory/production/hosts.yml \
  playbooks/validate.yml \
  --ask-vault-pass -K
```

Expected cluster properties:

```text
1 running Leader
2 streaming standby members
>=1 synchronous standby
exactly 1 VIP owner
VIP:5432 reachable
VIP SQL connection reaches writable Primary
etcd healthy
HAProxy configuration valid
required local services active
```

## 12. Run final readiness audit

```bash
./scripts/final-readiness-check.sh .
```

This checks duplicate YAML keys, syntax-checks all playbooks, executes safe audits and performs final HA validation.

## 13. Idempotency

Re-run important playbooks after deployment. A stable configuration should converge to `changed=0` unless an intended external drift or package/configuration change exists.
