# 🧪 Preflight Checks

![Preflight](https://img.shields.io/badge/preflight-non--destructive-success)

`playbooks/preflight.yml` is the safety gate before deployment.

## What it checks

The preflight role validates, as applicable:

- supported Ubuntu release;
- minimum CPU and memory;
- node FQDN resolution;
- inter-node reachability;
- repository reachability and APT package candidates;
- DNS/NTP readiness and clock offset;
- PostgreSQL data device existence and minimum size;
- disk partition/filesystem/signature safety;
- VIP collision or an already-managed VIP during idempotent reruns;
- required secret variables.

## What it does not do

Preflight does not initialize the PostgreSQL disk, create LVM, format a filesystem or deploy the HA stack.

## Run

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/preflight.yml --ask-vault-pass -K
```

## VIP behavior

On a fresh deployment, the configured VIP should normally be unused.

For safe idempotent reruns, the project can accept an existing VIP only when it is recognized as the VIP already managed by the deployed Keepalived configuration:

```yaml
preflight_allow_existing_managed_vip: true
```

This avoids treating the project's own healthy VIP as a deployment collision.

## Data disk safety

Disk initialization requires explicit permission:

```yaml
postgres_data_disk_allow_initialize: true
```

The storage workflow still refuses unsafe implicit filesystem conversion or unexpected signatures.

Use a stable `/dev/disk/by-id/...` device path when practical.
