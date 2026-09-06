# 🧩 Remaining Environment Integrations

The repository capabilities are implemented, but several production integrations intentionally require environment-specific values and approvals.

## 🔒 Network enforcement

- populate reviewed admin/application/monitoring CIDRs;
- verify routing and SNAT behavior;
- retain console access during first enforcement;
- apply one node at a time and validate SSH after every step.

## 🔐 TLS rollout

- obtain CA-signed certificates for all database nodes;
- verify node and shared service identities/SANs;
- deploy certificate files;
- enable PostgreSQL TLS in Patroni DCS;
- roll restarts safely;
- move internal PostgreSQL connections toward `verify-full` when naming is correct;
- only then consider `hostssl` enforcement;
- harden Patroni REST and etcd TLS as separate control-plane changes.

## 💾 Backup and recovery

- select the durable off-host backup/WAL repository;
- configure archive command/tooling;
- enable WAL archiving;
- establish base-backup schedule and retention;
- perform isolated restore/PITR tests;
- alert on backup/WAL freshness and restore-test age.

## 🧾 Central logging

- select the approved logging agent and destination;
- ship PostgreSQL/Patroni/etcd/HAProxy/Keepalived operational logs as required;
- preserve local logs during remote logging outages.

## 📈 Monitoring integration

The database/HA endpoints already exist. Remaining work is on the central monitoring side:

- add scrape targets;
- adapt alert rules to the installed metric names;
- route alerts to the existing alerting platform;
- add dashboards as required.

Host metrics remain managed by the existing infrastructure monitoring stack.

## 🧪 Recurring resilience tests

Periodically re-test:

- planned switchover;
- Primary VM loss;
- one etcd member loss;
- replica rebuild/rejoin;
- backup restore/PITR;
- disk expansion in a safe environment.

## Updated implementation

The [production patch guide](production-fixes.md) supersedes older placeholder/activation notes above and explains the newly implemented workflows and outstanding environment validation.
