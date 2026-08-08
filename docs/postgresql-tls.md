# 🔐 PostgreSQL TLS

![TLS](https://img.shields.io/badge/TLS-staged_capability-blue)
![Minimum](https://img.shields.io/badge/minimum-TLSv1.2-success)

## Scope

This document covers the PostgreSQL data-plane TLS design. Patroni REST and etcd TLS are separate control-plane hardening changes.

## Current safe defaults

```yaml
postgresql_tls_management_enabled: false
postgresql_tls_require_ssl: false
postgresql_tls_min_protocol_version: "TLSv1.2"
postgresql_tls_certificate_deployment_enabled: false
postgresql_tls_activation_enabled: false
postgresql_tls_internal_sslmode: "prefer"
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

See [TLS Activation](postgresql-tls-activation.md).
