# Milestone 3.1 — etcd lab bootstrap

Status: **proposed for first on-host integration**, not yet verified on lab VMs.

This increments the existing `etcd` role rather than replacing the deployment
architecture. `etcd_nodes` is the authoritative group for new inventories;
legacy `postgresql_cluster` remains a fallback for older entry points.
Package installation currently supports Debian-family hosts using APT only.

## Trust boundary

The lab workflow is **plaintext HTTP**, intended only for a trusted, isolated,
disposable three-node environment. It binds etcd client port 2379 on each node
and peer port 2380 on each node. This is not a production TLS deployment. The
operator owns network/firewall reachability and must not expose either port
outside trusted cluster/management networks.

It uses a deterministic initial-cluster token derived from the ordered etcd
management addresses; it is not a credential. Do not change member IPs or
membership after the cluster has initialized using this workflow. No automatic
etcd add/remove, migration, data-dir reset, or DR is implemented.

## Prerequisites

- A **private inventory outside this repository** defining `postgresql_nodes`,
  `etcd_nodes` (exactly three members), `load_balancer_nodes`, and real
  `ansible_host` addresses; inventory preflight must pass.
- Three disposable Debian-family hosts with working SSH, sudo, apt repositories,
  and network connectivity between etcd peer/client ports 2380/2379.
- Verify that these hosts do not already contain an unrelated etcd cluster.
  This workflow does not wipe, reinitialize, or reconcile foreign membership.

## One-command bootstrap (initial lab only)

```bash
ansible-playbook -i "$INV" -u YOUR_SSH_USER -K \
  -e etcd_lab_plaintext_approved=true \
  playbooks/etcd-bootstrap-lab.yml
```

This imports inventory preflight, installs/configures/starts etcd across the
three `etcd_nodes`, and then calls the read-only `roles/etcd/tasks/verify.yml`
from the first etcd member. Verification requires the **exact** declared
member names and peer URLs, a response from every endpoint, a distinct member
ID per endpoint, and an agreed elected leader. The run must end with
`failed=0` on all three nodes. A second run should not restart etcd unless
its configuration actually changes; verify task results must report no changes.

In the first run, the existing role may wait while quorum forms. Never use
`--limit pg01` to bootstrap a fresh three-member quorum. The one-command
playbook intentionally does **not** configure PostgreSQL/Patroni, HAProxy,
Keepalived, storage, or VIPs.

## Validation

```bash
./scripts/validate-local.sh
```

The local pipeline exercises Python regression tests and syntax checks but
cannot establish live etcd quorum. Keep the lab-run result distinct from CI.
For production, prepare the separately reviewed certificate/TLS procedure.
