# 🛡️ Security Hardening

![Auth](https://img.shields.io/badge/PostgreSQL-SCRAM-success)
![HBA](https://img.shields.io/badge/pg__hba-Patroni_managed-blue)
![Secrets](https://img.shields.io/badge/secrets-Vault-red)

## Security status

| Control | Status |
|---|---|
| PostgreSQL TCP password encryption | ✅ SCRAM-SHA-256 |
| Local PostgreSQL admin auth | ✅ Unix-socket `peer` |
| `trust` rules | ✅ Removed |
| Existing-cluster HBA source of truth | ✅ Patroni DCS `postgresql.pg_hba` |
| Broad default client subnet rule | ✅ Removed |
| Application DB role framework | ✅ Available, disabled until defined |
| postgres_exporter privilege | ✅ `pg_monitor`, non-superuser, no DB password |
| Network audit | ✅ Available |
| Firewall enforcement | 🧩 Disabled until CIDRs are reviewed |
| PostgreSQL TLS audit/files/activation | ✅ Capability available |
| TLS-only HBA / `verify-full` | 🧩 Environment-specific rollout |
| SSH/AppArmor framework | ✅ Capability available, enforcement disabled |
| etcd/Patroni REST TLS | 🧩 Separate future control-plane hardening |

## 1. PostgreSQL authentication ownership

Persistent HBA rules for an initialized Patroni cluster belong in Patroni dynamic configuration:

```text
postgresql.pg_hba
```

`bootstrap.pg_hba` applies to initial cluster creation and is not the control plane for changing an already initialized cluster.

The Patroni bootstrap template also sets:

```text
auth-local: peer
auth-host: scram-sha-256
```

to avoid insecure `initdb` authentication defaults on new clusters.

## 2. Mandatory HBA shape

The hardening playbook generates:

```text
local all all peer
host all all 127.0.0.1/32 scram-sha-256
host replication <replication-user> <db-node>/32 scram-sha-256
host all <rewind-user> <db-node>/32 scram-sha-256
host all all <db-node>/32 scram-sha-256
```

plus explicitly reviewed `postgresql_hba_additional_rules`.

Avoid broad rules such as:

```text
host all all 0.0.0.0/0 scram-sha-256
```

## 3. Apply HBA hardening

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/harden-pg-hba.yml --ask-vault-pass -K
```

The playbook compares desired DCS configuration, applies only when different, waits for convergence and validates there are no `trust`/parse errors.

## 4. Validate HBA

```bash
sudo -u postgres psql -x -c "
SELECT * FROM pg_hba_file_rules
WHERE error IS NOT NULL OR auth_method = 'trust';
"
```

Expected:

```text
(0 rows)
```

## 5. Network hardening

Do not infer source networks from design diagrams. Observe actual SSH/Ansible, application and monitoring sources first.

Variables:

```yaml
postgresql_network_hardening_enforce: false
postgresql_admin_cidrs: []
postgresql_application_cidrs: []
postgresql_monitoring_cidrs: []
postgresql_network_extra_cidrs: []
```

Run the read-only audit before any enforcement:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-network-hardening.yml --ask-vault-pass -K
```

See [Network Hardening](network-hardening.md).

## 6. Kubernetes/application networking

When applications use the VIP through HAProxy, PostgreSQL normally sees the HAProxy/database-node backend source, not necessarily the original Pod address.

Therefore:

- use database roles/privileges for application identity;
- apply application source restrictions at firewall/HAProxy after verifying real CNI/SNAT behavior;
- never invent Pod CIDRs in reusable defaults.

## 7. TLS

Safe order:

```text
audit
-> obtain correct certificates
-> deploy cert/key/CA files
-> validate SAN/expiry/key match
-> enable PostgreSQL TLS in Patroni DCS
-> rolling restart
-> validate encrypted application and replication sessions
-> move internal clients toward verify-full
-> only then enforce hostssl
```

PostgreSQL, Patroni REST and etcd are separate TLS surfaces.

See [PostgreSQL TLS](postgresql-tls.md) and [TLS Activation](postgresql-tls-activation.md).

## 8. Access management

Recommended ownership model:

```text
<service>_owner  NOLOGIN  owns objects
<service>_rw     NOLOGIN  carries runtime privileges
<service>_login  LOGIN    authenticates and inherits runtime role
```

The role intentionally does not automate destructive DROP operations.

See [PostgreSQL Access Management](postgresql-access-management.md).

## 9. Monitoring identity

postgres_exporter runs with:

```text
OS user: postgres_exporter
DB role: postgres_exporter
DB password: none
DB membership: pg_monitor
transport: local Unix socket
authentication: peer
```

This avoids using the PostgreSQL superuser for metrics.

## 10. SSH/AppArmor

The OS hardening capability is disabled by default to avoid operator lockout or untested AppArmor enforcement.

Run audit first:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-os-hardening.yml --ask-vault-pass -K
```

If enforcing SSH changes, retain console/out-of-band access and apply one node at a time.

## 11. Secrets

See [Secrets Management](secrets-management.md). Real passwords/private keys must never be committed in plaintext.

## 12. Final validation

After security changes:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
```
