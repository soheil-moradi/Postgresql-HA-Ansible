# Inventory Contract v1 (initial deployment)

**Status:** Implementation draft; requires review before a real deployment.

This contract separates **host placement** from service configuration. VMs and
bare-metal servers are equivalent from Ansible's point of view. No Terraform,
hypervisor, or cloud-specific fields are required.

## Role groups

| Inventory group | Installed services | Required in v1 |
| --- | --- | --- |
| `postgresql_nodes` | PostgreSQL and Patroni | Yes (>= 3 for target HA profile) |
| `etcd_nodes` | etcd | Yes (odd count >= 3) |
| `load_balancer_nodes` | HAProxy and Keepalived | Yes (>= 1; 2+ recommended) |
| `backup_nodes` | Future optional backup placement | No |
| `monitoring_nodes` | Future optional monitoring placement | No |

Multiple group memberships are allowed, including all three core roles on
one machine, as in [`topology-3-vm.yml`](../inventory/examples/topology-3-vm.yml).
The Monitoring **server** is explicitly out of scope; metrics must be made
available for the existing external monitoring stack in a later milestone.

The inventory controls initial role placement, **not** membership changes to
an existing etcd/Patroni cluster. Changing host placement in a deployed
cluster must not automatically remove, reinitialize, or migrate any member.

## Variables

- `ansible_host`: required per host. Inventory hosts must have distinct IPs.
- `node_fqdn`: required for every PostgreSQL host in the current codebase.
- `postgres_data_device`: required for every PostgreSQL host. Prefer a stable
  `/dev/disk/by-id/` reference; actual physical device safety is validated on
  the target host before initializing LVM + XFS.
- `keepalived_priority`: required for every load balancer host (1..254).
- `postgres_cluster_vip`: **Read/Write** VIP. This preserves the variable name
  used by the legacy HAProxy/Keepalived roles.
- `postgres_read_vip`: **Read-only** VIP (new variable; routing to healthy
  standbys is NOT implemented yet).
- `postgres_cluster_dns_name` and `postgres_read_dns_name`: independent DNS
  names for the two VIPs. Both may use TCP/5432 on their respective VIPs.
- `postgresql_dr_enabled`: false for v1; DR workflows are not implemented.
- `patroni_synchronous_mode`: false for the initial asynchronous lab profile;
  production durability policy remains a separate decision.

No machine count, package source, operating system family, or hardware creator
is encoded in the role group names. OS-specific installation is a later
refactor; the legacy deploy playbook currently assumes Ubuntu.

## Controller-only validation

Run this before even considering an on-host deployment:

```bash
ansible-playbook \
  -i inventory/examples/topology-3-vm.yml \
  playbooks/inventory-preflight.yml
```

This reads inventory only: no SSH, no `sudo`, no fact gathering, no disk changes.
It checks the role groups, etcd quorum member count, distinct host IPs,
required host properties, and two distinct Read/Write endpoint definitions.
It does **not** probe the network, disk contents, actual etcd quorum health,
existing cluster membership, VIP ownership, or PostgreSQL readiness.

For a real deployment, create a **private** inventory with real addresses and
disk identifiers outside this public repository. The documentation addresses
in the example intentionally do not route to real servers.

## Explicit non-goals for this increment

1. The legacy `site.yml` and `playbooks/deploy.yml` are **not** yet role-driven;
   do not use this example inventory with the old deployment entry points.
2. This increment does **not** configure HAProxy Read routing, Keepalived's
   second VIP, or PostgreSQL storage. Those require separate reviewed changes.
3. It does **not** implement dynamic scale-out/in or data migration.
4. GitHub Actions validates public code only, never accesses company servers.
