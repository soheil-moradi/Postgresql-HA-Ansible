# 🔐 Secrets Management

![Vault](https://img.shields.io/badge/secrets-Ansible_Vault-red)

## 1. Principles

- No plaintext database/Patroni passwords in Git.
- No private SSH keys in the repository.
- No unencrypted TLS private keys in Git.
- Prefer one authoritative secret source per credential.
- Rotate credentials through automation, not ad-hoc node edits.

## 2. Vault file

Create from the example:

```bash
cp inventory/production/group_vars/all/vault.yml.example \
   inventory/production/group_vars/all/vault.yml
```

Encrypt immediately:

```bash
ansible-vault encrypt inventory/production/group_vars/all/vault.yml
```

The local `vault.yml` is ignored by Git, but Git ignore is **not** a security boundary; encryption is still mandatory.

## 3. Typical protected values

The repository uses Vault-backed secrets for identities such as:

```text
PostgreSQL superuser
Patroni replication user
pg_rewind user
Patroni REST authentication
Ansible become password when required
managed application LOGIN roles
```

Use the exact variable names from `vault.yml.example` and role examples.

## 4. Application database passwords

For managed application login roles, store the password only in Vault and reference it from the declarative role definition. Use a version/rotation marker where documented so a deliberate rotation is visible to automation.

## 5. postgres_exporter

The monitoring exporter intentionally requires **no database password**:

```text
OS user postgres_exporter
-> Unix socket
-> peer authentication
-> DB role postgres_exporter
-> pg_monitor
```

The database role is configured with no password and is not a superuser.

## 6. TLS material

Treat `server.key` as a secret. Certificate deployment variables point to operator-controlled source paths; the repository should not contain real private keys.

Use the environment's approved PKI/secret delivery mechanism.

## 7. Rotation procedure

For a credential used by cluster internals:

1. identify every consumer;
2. stage the new secret in Vault;
3. update configuration through Ansible/Patroni;
4. validate replication/HA/API access;
5. retire the old secret;
6. run `validate.yml`.

Do not rotate replication or rewind credentials manually on one node only.

## 8. Local operator hygiene

Recommended exclusions:

```text
inventory/**/vault.yml
.vault_pass
*.pem
*.key
```

Protect the Ansible workstation and its shell history as part of the credential boundary.
