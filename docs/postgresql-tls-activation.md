# 🔄 PostgreSQL TLS Activation

![Change Type](https://img.shields.io/badge/change-rolling_restart_required-orange)

This capability prepares PostgreSQL TLS settings in Patroni DCS without
automatically restarting all database members. Patroni REST and etcd have
separate switches and certificate publication in `postgresql_tls_files`.

## Enable gate

```yaml
postgresql_tls_activation_enabled: false
```

Set to `true` only after certificates are correctly deployed and validated on every node.

## What the playbook does

When enabled, `playbooks/activate-postgresql-tls.yml`:

1. verifies certificate and key files on every node;
2. checks remaining certificate validity;
3. verifies certificate/key match;
4. compares desired TLS parameters with current Patroni DCS;
5. applies only the changed PostgreSQL TLS parameter subset;
6. displays topology/pending-restart information;
7. runs normal HA validation.

Desired PostgreSQL parameters include:

```text
ssl=on
ssl_cert_file=<managed server certificate>
ssl_key_file=<managed private key>
ssl_min_protocol_version=TLSv1.2
```

If `patroni_rest_tls_enabled` is true, the same playbook talks to Patroni over
HTTPS and verifies `patroni_rest_tls_ca_file`. If `etcd_tls_enabled` is true,
the local Patroni configuration and every `etcdctl` validation use the etcd CA
and client certificate.

It intentionally does **not**:

- restart Patroni/PostgreSQL automatically;
- convert HBA rules to `hostssl`;
- switch internal connections directly to `verify-full`.

## Rolling restart sequence

After the DCS change:

```text
1. validate cluster
2. restart one replica
3. confirm streaming/lag
4. restart the other standby as appropriate
5. planned switchover
6. restart former Primary
7. confirm rejoin
8. validate SQL/TLS through VIP
```

## Validate TLS

From SQL:

```sql
SHOW ssl;
SHOW ssl_min_protocol_version;
```

For a client connection:

```sql
SELECT ssl, version, cipher
FROM pg_stat_ssl
WHERE pid = pg_backend_pid();
```

## Internal TLS

Only move Patroni PostgreSQL connection `sslmode` toward `verify-full` after every certificate contains the identity used in the node-to-node connection and the trusted CA bundle is deployed.

## Enforce TLS-only HBA

`postgresql_tls_require_ssl` is reserved for the later HBA enforcement stage. Enforce `hostssl` only after encrypted application and replication traffic has been proven.

## Updated implementation

The [production patch guide](production-fixes.md) supersedes older placeholder/activation notes above and explains the newly implemented workflows and outstanding environment validation.
