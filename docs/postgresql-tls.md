# 🔐 PostgreSQL TLS

![TLS](https://img.shields.io/badge/TLS-staged_capability-blue)
![Minimum](https://img.shields.io/badge/minimum-TLSv1.2-success)

## Scope

This document covers PostgreSQL data-plane TLS plus the optional Patroni REST and
etcd control-plane TLS switches. Every switch is disabled by default and requires
organization-issued certificates; this project never generates private keys.

## Current safe defaults

```yaml
postgresql_tls_management_enabled: false
postgresql_tls_require_ssl: false
postgresql_tls_min_protocol_version: "TLSv1.2"
postgresql_tls_certificate_deployment_enabled: false
postgresql_tls_activation_enabled: false
postgresql_tls_internal_sslmode: "prefer"
patroni_rest_tls_enabled: false
etcd_tls_enabled: false
```

TLS is not enabled by merely defining file paths.

## HAProxy behavior

HAProxy uses TCP mode, so PostgreSQL TLS can pass through the VIP and terminate end-to-end on the current Primary.

## Certificate layout

Default destinations:

```text
/etc/postgresql/tls/server.crt
/etc/postgresql/tls/server.key
/etc/postgresql/tls/ca.crt
```

Private key permissions are restricted by the certificate-deployment role.

## Certificate identity design

Before using `verify-full`, certificates must match the actual names/addresses clients use.

Potential identities can include:

```text
node FQDN
shared PostgreSQL service DNS name
node IP when internal clients connect by IP
VIP IP if clients verify against the VIP address
```

Do not blindly copy SAN examples; derive them from the actual connection paths.

## Audit

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-tls.yml --ask-vault-pass -K
```

The audit reports current PostgreSQL TLS state, destination files, certificate metadata when present, Patroni internal SSL mode and HAProxy TCP mode.

## Certificate deployment

Configure source paths and expected identities, then explicitly enable:

```yaml
postgresql_tls_certificate_deployment_enabled: true
```

Run:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/deploy-postgresql-tls-certificates.yml --ask-vault-pass -K
```

The role validates PEM files, certificate/key match, expiry threshold and optional SAN identities. It does **not** enable PostgreSQL TLS or restart services.

## Encryption vs verification

Typical libpq modes:

```text
prefer       opportunistic TLS
require      encryption required
verify-ca    encryption + CA validation
verify-full  encryption + CA + hostname/IP verification
```

The long-term hardened target is usually `verify-full`, after correct SANs and trust distribution are proven.

## Why `hostssl` is last

Switching HBA to `hostssl` before TLS works for application, replication and rewind paths can break the HA cluster.

Safe sequence:

```text
certificates
-> ssl=on
-> rolling restart
-> validate TLS application path
-> validate replication/rewind TLS
-> verify-full where appropriate
-> hostssl enforcement
-> switchover/failover test
```

See [TLS Activation](postgresql-tls-activation.md) for PostgreSQL and the control
plane rollout sequence.

## Control-plane TLS

Patroni REST and etcd must be migrated as a coordinated phase because deploy and
validation probes depend on their URL schemes.

1. Issue a CA-signed Patroni REST certificate for each node and configure its
   source, key source, CA source and expected DNS/IP identities.
2. Issue etcd server, peer and client certificates. The server and peer
   certificates must contain every address used by the three-node cluster.
3. Set `patroni_rest_tls_enabled: true` and/or `etcd_tls_enabled: true`, then run
   `playbooks/deploy-postgresql-tls-certificates.yml` on all three nodes.
4. Review the validation output. For an already-running HTTP quorum, use the
   explicit `playbooks/migrate-etcd-tls.yml` maintenance playbook; do not set the
   flag and run a normal rolling deploy. For a new cluster, rerun the normal
   deploy/validation workflow; it
   will use HTTPS/mTLS URLs automatically. Do not use `--limit` for this change.

For Patroni REST, `optional` client verification is the default so HAProxy can
perform an HTTPS health check without holding a client private key. The current
automation deliberately accepts only `none` or `optional`; selecting
`required` would make the built-in HAProxy check fail until a reviewed client-key
delivery and health-check configuration is added.

### هشدار مهاجرت etcd موجود

تغییر مستقیم `etcd_tls_enabled` روی quorum فعال، اعضا را یکی‌یکی از HTTP به
HTTPS می‌برد و می‌تواند quorum را از بین ببرد. role عمداً این حالت را بدون
تأیید صریح متوقف می‌کند. برای یک کلاستر موجود، قبل از اجرای تغییر باید یک
maintenance window، snapshot قابل‌بازگردانی و روش هماهنگ توقف/راه‌اندازی هر سه
عضو و Patroni داشته باشید. پس از اثبات سلامت quorum، مقدار
`etcd_tls_existing_cluster_migration_ack` را فقط برای همان اجرای کنترل‌شده true
کنید و وجود marker زیر را بررسی کنید:

```text
/etc/etcd/tls/.migration-complete
```

در استقرار کاملاً جدید، چون etcd هنوز فعال نشده است، این guard مانع فعال‌سازی
TLS نمی‌شود.
