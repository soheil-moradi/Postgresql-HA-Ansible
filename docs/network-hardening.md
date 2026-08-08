# 🌐 Network Hardening

![Firewall](https://img.shields.io/badge/firewall-enforcement_opt--in-lightgrey)

## Objective

Reduce network exposure without guessing management/application/monitoring source networks or locking operators out.

## Safe workflow

```text
read-only audit
-> observe real source addresses
-> populate reviewed CIDRs
-> render/review intended policy
-> retain console access
-> enforce one node at a time
-> verify SSH and HA after each node
```

## Variables

```yaml
postgresql_network_hardening_enforce: false
postgresql_admin_cidrs: []
postgresql_application_cidrs: []
postgresql_monitoring_cidrs: []
postgresql_network_extra_cidrs: []
```

## Audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-network-hardening.yml --ask-vault-pass -K
```

The audit inspects interfaces/routes, SSH source observations, listeners and current firewall state without changing policy.

## Intended access model

Typical intent:

| Traffic | Source | Destination |
|---|---|---|
| SSH | reviewed admin networks | nodes `22/tcp` |
| Application DB | reviewed application networks | VIP `5432/tcp` |
| PostgreSQL internal | DB nodes | node `5432/tcp` |
| Patroni | DB nodes + approved monitoring if required | `8008/tcp` |
| etcd client | DB nodes + approved monitoring if required | `2379/tcp` |
| etcd peer | DB nodes | `2380/tcp` |
| HAProxy metrics | approved monitoring | `8404/tcp` |
| postgres_exporter | approved monitoring | `9187/tcp` |
| VRRP | DB nodes | IP protocol 112 |

Do not expose etcd/Patroni/metrics broadly merely because they use HTTP endpoints.

## Kubernetes note

Do not guess Pod CIDRs. Determine what source address actually reaches the database network after CNI/NAT/load-balancing behavior.

## Safety requirements for first enforcement

- `postgresql_admin_cidrs` must be non-empty and reviewed;
- preserve out-of-band/console access;
- validate syntax before applying;
- process one node at a time;
- run `wait_for_connection` after SSH policy changes;
- run full HA validation afterward;
- do not flush unrelated nftables rulesets blindly.

The current repository provides the audit/model foundation; final enforcement remains an environment-specific change.
