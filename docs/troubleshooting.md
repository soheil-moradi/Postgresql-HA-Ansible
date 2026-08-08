# 🧯 Troubleshooting

![Troubleshooting](https://img.shields.io/badge/runbook-symptom--driven-orange)

Start with observation. Avoid destructive recovery until the failure mode is understood.

## 1. Quick triage

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
sudo systemctl --no-pager --full status patroni etcd haproxy keepalived prometheus-postgres-exporter
ip -br addr
sudo ss -lntp
```

Then run:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
```

## 2. No Patroni Leader

Check topology and Patroni logs:

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
sudo journalctl -u patroni --since '-30 min'
```

Check etcd quorum:

```bash
ETCDCTL_API=3 etcdctl --endpoints=<all-etcd-endpoints> endpoint health
```

Common causes:

- DCS quorum loss;
- network partition;
- all candidates exceed lag constraints;
- PostgreSQL startup failure;
- disk/filesystem problem.

Do not manually promote PostgreSQL outside Patroni unless executing a separately approved disaster procedure.

## 3. Replica not streaming

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
sudo journalctl -u patroni --since '-30 min'
```

On the Primary:

```sql
SELECT application_name, client_addr, state, sync_state,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication;
```

Check authentication errors and `pg_hba` rules before considering reinit.

## 4. `no pg_hba.conf entry`

Inspect parsed HBA rules:

```bash
sudo -u postgres psql -x -c "
SELECT * FROM pg_hba_file_rules
WHERE error IS NOT NULL;
"
```

Show the active file:

```bash
sudo -u postgres psql -Atc 'SHOW hba_file'
```

Persistent desired rules are managed through Patroni DCS by the hardening playbook.

## 5. VIP missing

```bash
sudo systemctl status keepalived
sudo journalctl -u keepalived --since '-30 min'
ip -br addr
```

Also verify local HAProxy health because Keepalived tracks the HAProxy service.

## 6. VIP exists but PostgreSQL is unreachable

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
curl -s http://127.0.0.1:7000/stats | head
sudo patronictl -c /etc/patroni/patroni.yml list
```

Test the node's Patroni Primary endpoint:

```bash
curl -i http://<node>:8008/primary
```

Only the current Primary should return the expected successful Primary health response.

## 7. etcd quorum issue

Metrics:

```bash
curl -s http://<node>:2379/metrics | grep -E '^etcd_server_(has_leader|is_leader)'
```

Health:

```bash
ETCDCTL_API=3 etcdctl --endpoints=<all-etcd-endpoints> endpoint health
```

With three members, do not intentionally stop a second member while one is unavailable.

## 8. postgres_exporter `pg_up 0`

```bash
sudo systemctl status prometheus-postgres-exporter
sudo journalctl -u prometheus-postgres-exporter --since '-30 min'
curl -s http://<node>:9187/metrics | grep '^pg_up'
```

Verify local peer authentication:

```bash
sudo runuser -u postgres_exporter -- \
  psql -X -qAt -h /var/run/postgresql -U postgres_exporter -d postgres \
  -c 'SELECT current_user, pg_is_in_recovery();'
```

The exporter DB role should be a non-superuser member of `pg_monitor` and have no password.

## 9. HAProxy metrics missing

```bash
haproxy -vv | grep -iE 'PROMEX|Prometheus'
sudo ss -lntp | grep ':8404'
curl -s http://<node>:8404/metrics | grep '^haproxy_' | head
```

If access is denied, review `postgresql_monitoring_cidrs` and network policy.

## 10. Patroni metrics missing

```bash
curl -s http://<node>:8008/metrics | head
```

Useful role metrics include:

```text
patroni_primary
patroni_master
patroni_replica
patroni_sync_standby
patroni_postgres_streaming
```

Metric names can vary by Patroni version; always inspect the live endpoint before writing alert expressions.

## 11. PostgreSQL TLS fails after activation

Check:

```sql
SHOW ssl;
SHOW ssl_cert_file;
SHOW ssl_key_file;
SHOW ssl_min_protocol_version;
```

Inspect certificate:

```bash
openssl x509 -in /etc/postgresql/tls/server.crt -noout -subject -issuer -dates -ext subjectAltName
```

Verify key/certificate match before restarting another cluster member.

## 12. WAL archive failure

```sql
SELECT archived_count, failed_count,
       last_archived_wal, last_archived_time,
       last_failed_wal, last_failed_time
FROM pg_stat_archiver;
```

The archive command must return non-zero when durable archival fails so PostgreSQL retries.

## 13. Disk pressure

Host filesystem capacity is expected to be monitored by the infrastructure monitoring platform. On the node:

```bash
df -hT /var/lib/postgresql
lvs
pvs
```

Use [Disk Expansion](disk-expansion.md) for online XFS growth.

## 14. Pending restart

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
```

Use a rolling restart/switchover sequence. Never restart all three PostgreSQL members at once.

## 15. Ansible drift or unexpected `changed`

Run the same playbook twice and inspect only changed tasks. Confirm no operator or external process rewrites the same file/configuration.

For the full repository audit:

```bash
./scripts/final-readiness-check.sh .
```
