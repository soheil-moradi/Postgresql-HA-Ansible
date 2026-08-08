# 📊 PostgreSQL HA Monitoring

![Prometheus](https://img.shields.io/badge/Prometheus-compatible-orange?logo=prometheus)
![Host Metrics](https://img.shields.io/badge/host_metrics-out_of_scope-lightgrey)

## Scope

This repository monitors the **database and HA stack only**.

Host-level monitoring is intentionally excluded. CPU, RAM, filesystem, disk I/O, load and NIC metrics should remain in the infrastructure monitoring system.

## Endpoints

Per database node:

| Component | Endpoint | Notes |
|---|---|---|
| Patroni | `http://<node>:8008/metrics` | Built into Patroni |
| etcd | `http://<node>:2379/metrics` | Built into etcd |
| HAProxy | `http://<node>:8404/metrics` | Built-in PROMEX service |
| PostgreSQL | `http://<node>:9187/metrics` | `prometheus-postgres-exporter` |
| HAProxy local stats | `http://127.0.0.1:7000/stats` | Local-only UI |

## postgres_exporter security model

```text
systemd service
  -> OS user postgres_exporter
  -> local Unix socket /var/run/postgresql
  -> peer authentication
  -> DB role postgres_exporter
  -> member of pg_monitor
```

The DB role is deliberately:

```text
LOGIN
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOREPLICATION
NOBYPASSRLS
CONNECTION LIMIT 5
PASSWORD NULL
```

This avoids a reusable database password for the local exporter.

## Additional collectors

The exporter configuration enables collectors for areas such as:

```text
database wraparound
long-running transactions
postmaster
stat_activity autovacuum
WAL receiver
```

Default collectors provide additional database, lock, replication, table and WAL metrics.

`pg_stat_statements` is not enabled automatically because that is a separate PostgreSQL extension/configuration decision.

## Prometheus examples

Use:

```text
monitoring/prometheus-scrape.example.yml
monitoring/postgresql-ha-alerts.example.yml
```

Replace placeholders and validate live metric names before copying alert rules into production.

## Important Patroni metrics

Common live metrics include:

```text
patroni_postgres_running
patroni_primary
patroni_master
patroni_replica
patroni_sync_standby
patroni_postgres_streaming
patroni_dcs_last_seen
patroni_pending_restart
```

Metric availability/naming can vary by Patroni release; inspect `/metrics` on the installed version.

## Important etcd metrics

Examples:

```text
etcd_server_has_leader
etcd_server_is_leader
```

Use broader official etcd metric families for latency, proposals, backend and peer health as required.

## HAProxy

HAProxy is compiled with built-in PROMEX support; no separate HAProxy exporter is required.

Backend metrics should expose the `patroni_primary_nodes` backend and server health.

## Network access

When `postgresql_monitoring_cidrs` is populated, the HAProxy metrics frontend can restrict source addresses. The final host firewall should also restrict monitoring ports to approved monitoring sources.

Do not expose monitoring endpoints to untrusted networks.

## Validation

Enable/configure both added endpoints:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/enable-postgresql-monitoring-endpoints.yml \
  --ask-vault-pass -K
```

Read-only audit:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-ha-monitoring.yml \
  --ask-vault-pass -K
```

Quick tests:

```bash
curl -s http://<node>:9187/metrics | grep '^pg_up'
curl -s http://<node>:8008/metrics | grep '^patroni_primary'
curl -s http://<node>:2379/metrics | grep '^etcd_server_has_leader'
curl -s http://<node>:8404/metrics | grep '^haproxy_backend_' | head
```

Expected PostgreSQL exporter signal:

```text
pg_up 1
```

## Alert baseline

Recommended high-value alerts:

```text
Prometheus target down
no Patroni Primary / not exactly one Primary
PostgreSQL not running
replica not streaming
DCS stale / etcd leader unavailable
PostgreSQL exporter pg_up=0
HAProxy backend/server unhealthy
connection saturation
long transaction
transaction-ID wraparound risk
replication/WAL lag
backup/WAL archive stale or failed
```

Filesystem capacity alerts remain with host monitoring.
