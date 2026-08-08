# 🧱 Node Rebuild & Replica Rejoin

![Safety](https://img.shields.io/badge/rebuild-one_node_at_a_time-red)

This runbook is for replacing or rebuilding **one** database member while the remaining cluster is healthy.

## 1. Never start with destructive cleanup

Do not wipe a PostgreSQL data directory simply because a replica is unhealthy. First determine whether Patroni can rewind or rejoin it automatically.

Check:

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
sudo journalctl -u patroni --since '-30 min'
```

## 2. Preconditions for a rebuild

Before any deliberate reinitialize/reprovision action:

- one healthy Patroni Leader exists;
- at least one other standby is streaming;
- etcd quorum is healthy;
- backup status is understood;
- the target node identity is confirmed;
- no second node is under maintenance.

## 3. Infrastructure replacement

If the VM itself must be replaced:

1. preserve the same intended inventory identity or update inventory deliberately;
2. provision supported Ubuntu and the expected data disk;
3. verify DNS/NTP/repository access;
4. run preflight against the replacement node;
5. deploy the required roles;
6. allow Patroni to clone/rejoin from the healthy cluster;
7. wait for `streaming` and acceptable lag;
8. run full HA validation.

## 4. Patroni reinitialize

Use `patronictl reinit` only when normal rewind/rejoin is not viable and you intentionally accept recloning the replica.

Before running it, verify the target member name twice:

```bash
sudo patronictl -c /etc/patroni/patroni.yml list
```

Then use Patroni's reinitialize workflow for that one member according to the installed Patroni version and operational approval.

> ⚠️ Never reinitialize the current Leader.

## 5. After rejoin

Require:

```text
member state = streaming
lag near zero
synchronous standby available
VIP write path healthy
```

Run:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
```

## 6. etcd member recovery

etcd replacement has different membership semantics from PostgreSQL replica rebuild. Do not copy the PostgreSQL reinit procedure to etcd. Preserve quorum and follow the installed etcd version's member replacement procedure.
