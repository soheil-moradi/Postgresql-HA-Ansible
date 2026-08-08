# 🛠️ Operations Guide

![Operations](https://img.shields.io/badge/operations-HA--safe-success)

## 1. Golden rule

> Persistent cluster configuration must be changed through Ansible and Patroni-aware workflows. Avoid permanent manual edits on individual database nodes.

## 2. Daily health check

### Patroni topology

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
```

Healthy three-node shape:

```text
1 Leader / running
1 Sync Standby / streaming
1 Replica / streaming
lag near zero
```

### etcd health

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://<node-1>:2379,http://<node-2>:2379,http://<node-3>:2379 \
  endpoint health
```

### VIP owner

```bash
ip -br addr | grep '<VIP>'
```

Exactly one node should own the VIP.

### HAProxy

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
curl -s http://127.0.0.1:7000/stats | head
```

### Writable VIP path

From an approved client path:

```bash
psql "host=<VIP-or-service-DNS> port=5432 dbname=postgres user=<approved-user>" \
  -c "SELECT pg_is_in_recovery();"
```

Expected on the application read/write endpoint:

```text
f
```

## 3. Monitoring endpoints

Per database node:

```text
:8008/metrics Patroni
:2379/metrics etcd
:8404/metrics HAProxy
:9187/metrics postgres_exporter
```

Useful spot checks:

```bash
curl -s http://<node>:8008/metrics | grep '^patroni_primary'
curl -s http://<node>:2379/metrics | grep '^etcd_server_has_leader'
curl -s http://<node>:8404/metrics | grep '^haproxy_backend_' | head
curl -s http://<node>:9187/metrics | grep -E '^pg_up|^pg_stat_database_' | head
```

## 4. Safe service restart policy

Do not restart all database nodes together.

For maintenance requiring PostgreSQL/Patroni restart:

```text
1. validate cluster
2. restart one Replica
3. wait until streaming and caught up
4. restart the other standby if required
5. perform planned switchover if the Primary must restart
6. restart the former Primary
7. wait for rejoin
8. validate cluster again
```

Keep etcd quorum at **2/3 or better** at all times.

## 5. Planned switchover

Use Patroni, not manual PostgreSQL promotion:

```bash
sudo patronictl -c /etc/patroni/patroni.yml switchover
```

Before switchover:

- all three members healthy;
- target candidate streaming;
- replication lag acceptable;
- no active maintenance on another member.

After switchover:

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
```

Then verify VIP SQL writes.

## 6. Pending restart

Check:

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
```

A `Pending restart` marker means configuration changed but PostgreSQL still needs a restart to apply server-start parameters. Use the rolling procedure; never restart the whole cluster simultaneously.

## 7. PostgreSQL logs

Default log directory:

```text
/var/log/postgresql
```

Useful commands:

```bash
sudo ls -lhtr /var/log/postgresql | tail
sudo journalctl -u patroni --since '-30 min'
sudo journalctl -u etcd --since '-30 min'
sudo journalctl -u haproxy --since '-30 min'
sudo journalctl -u keepalived --since '-30 min'
sudo journalctl -u prometheus-postgres-exporter --since '-30 min'
```

## 8. Configuration state

Patroni DCS configuration:

```bash
sudo patronictl -c /etc/patroni/patroni.yml show-config
```

Active PostgreSQL settings:

```bash
sudo -u postgres psql -X -c "SHOW config_file;"
sudo -u postgres psql -X -c "SHOW hba_file;"
```

## 9. Database/user provisioning

Use `playbooks/manage-postgresql-access.yml`. Do not manually create long-lived application users unless emergency procedures require it and the change is subsequently reconciled into Ansible.

## 10. Storage expansion

See [Disk Expansion](disk-expansion.md). XFS can grow online but cannot shrink.

## 11. Backup operations

A VM snapshot/backup can complement recovery but does not replace PostgreSQL-native base backup + WAL archive + tested PITR.

See [Backup & Restore](backup-and-restore.md).

## 12. After every meaningful change

Run:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
```

For a broader audit:

```bash
./scripts/final-readiness-check.sh .
```
