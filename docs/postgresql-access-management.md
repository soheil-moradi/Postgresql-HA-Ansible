# 👥 PostgreSQL Access Management

![Least Privilege](https://img.shields.io/badge/model-least_privilege-success)

The `postgresql_access` role provides optional declarative management for application databases, roles, memberships and common privilege profiles.

## Safety defaults

```yaml
postgresql_access_management_enabled: false
postgresql_managed_roles: []
postgresql_managed_databases: []
postgresql_managed_memberships: []
postgresql_managed_access_profiles: []
```

With these defaults, the playbook changes nothing.

The automation intentionally does **not** drop databases or roles.

## Recommended role model

```text
<service>_owner   NOLOGIN   owns database/schema objects
<service>_rw      NOLOGIN   carries application runtime privileges
<service>_ro      NOLOGIN   optional read-only privileges
<service>_login   LOGIN     authenticates; member of runtime role
```

This separates object ownership, authorization and credentials.

## Passwords

LOGIN role passwords belong in Ansible Vault. Do not commit them in example/group variable files.

## Privilege profiles

The role supports common patterns such as:

```text
readonly
readwrite
```

Review generated grants for the application's actual schema/object model.

## Default privileges warning

`ALTER DEFAULT PRIVILEGES` affects **future objects created by a specific owner/creator role**. It does not retroactively change arbitrary objects and it is not global across all creators.

Design ownership before relying on default privileges.

## Example

Start from:

```text
examples/postgresql-access.yml.example
```

Copy only the objects required by the environment into encrypted/normal variables as appropriate.

## Apply

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/manage-postgresql-access.yml --ask-vault-pass -K
```

The playbook discovers the current Patroni Leader and applies database changes there.

## Validation

After provisioning:

- verify LOGIN roles can connect only as intended;
- verify NOLOGIN roles cannot authenticate;
- verify role memberships;
- verify read/write behavior against required schemas;
- run `validate.yml` to confirm HA remains healthy.
