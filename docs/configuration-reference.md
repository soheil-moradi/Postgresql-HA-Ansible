# ⚙️ Configuration Reference

![Config](https://img.shields.io/badge/config-declarative-blue)

Primary environment variables live in:

```text
inventory/production/group_vars/all/main.yml
```

Secrets live in the encrypted:

```text
inventory/production/group_vars/all/vault.yml
```

## 1. Connection

| Variable | Purpose |
|---|---|
| `ansible_user` | SSH user |
| `ansible_port` | SSH port |
| `ansible_become` | Enable sudo |
| `ansible_become_password` | Vault-backed sudo password |

## 2. Cluster identity

| Variable | Purpose |
|---|---|
| `postgres_cluster_name` | Patroni cluster scope/name |
| `postgres_cluster_vip` | Stable application VIP |
| `postgres_cluster_dns_name` | Service DNS name |
| `postgres_cluster_vip_prefix` | VIP prefix length |

## 3. Infrastructure services

| Variable | Purpose |
|---|---|
| `dns_servers` | Resolver addresses |
| `ntp_servers` | Time sources |
| `repository_probe_urls` | Preflight repository reachability |
| `apt_manage_internal_sources` | Whether Ansible manages APT source definitions |
| `apt_internal_repository_url` | Internal repository base URL |

## 4. Storage

| Variable | Purpose |
|---|---|
| `postgres_data_disk_allow_initialize` | Explicit permission to initialize an empty data disk |
| `postgres_vg_name` | LVM volume group |
| `postgres_lv_name` | LVM logical volume |
| `postgres_mount_point` | PostgreSQL storage mount |
| `postgres_filesystem` | `xfs` or supported filesystem |
| `postgres_mount_options` | Mount options |
| `preflight_min_data_disk_gb` | Minimum accepted disk capacity |

> ⚠️ Changing `postgres_filesystem` does not convert an existing filesystem.

## 5. PostgreSQL sizing

| Variable | Purpose |
|---|---|
| `postgresql_version` | PostgreSQL major version |
| `postgresql_port` | PostgreSQL listener port |
| `postgresql_max_connections` | Connection limit |
| `postgresql_shared_buffers` | Shared buffer cache |
| `postgresql_effective_cache_size` | Planner cache estimate |
| `postgresql_maintenance_work_mem` | Maintenance memory |
| `postgresql_work_mem` | Per-operation work memory |
| `postgresql_wal_keep_size` | Retained WAL for replicas |
| `postgresql_max_wal_size` | Maximum WAL checkpoint target |
| `postgresql_min_wal_size` | Minimum WAL retention |
| `postgresql_log_min_duration_statement_ms` | Slow statement logging threshold |

Sizing values are examples, not universal production recommendations. Tune from actual workload and memory constraints.

## 6. Patroni

| Variable | Purpose |
|---|---|
| `patroni_rest_port` | Patroni REST/metrics port |
| `patroni_namespace` | DCS namespace |
| `patroni_ttl` | Leader lock TTL |
| `patroni_loop_wait` | Control loop period |
| `patroni_retry_timeout` | DCS retry timeout |
| `patroni_maximum_lag_on_failover` | Failover candidate lag limit |
| `patroni_synchronous_mode` | Enable synchronous mode |
| `patroni_synchronous_mode_strict` | Strict synchronous behavior |
| `patroni_synchronous_node_count` | Number of synchronous standbys |

## 7. etcd

| Variable | Purpose |
|---|---|
| `etcd_client_port` | Client/API/metrics port |
| `etcd_peer_port` | Member peer port |
| `etcd_cluster_token` | Initial-cluster token |
| `etcd_data_dir` | etcd storage path |

## 8. HAProxy / Keepalived

| Variable | Purpose |
|---|---|
| `haproxy_postgresql_port` | VIP PostgreSQL port |
| `haproxy_stats_bind` | Local stats bind address |
| `haproxy_stats_port` | Local stats port |
| `keepalived_virtual_router_id` | VRRP ID |
| `keepalived_advert_interval` | VRRP advertisement interval |
| `keepalived_nopreempt` | Avoid unnecessary VIP preemption |

## 9. PostgreSQL HBA

```yaml
postgresql_hba_additional_rules: []
```

Use only for reviewed direct-access exceptions. Mandatory inter-node/replication/rewind rules are generated automatically.

## 10. Network hardening

```yaml
postgresql_network_hardening_enforce: false
postgresql_admin_cidrs: []
postgresql_application_cidrs: []
postgresql_monitoring_cidrs: []
postgresql_network_extra_cidrs: []
```

Keep enforcement off until the real management, application and monitoring source networks have been observed and reviewed.

## 11. Database access management

```yaml
postgresql_access_management_enabled: false
postgresql_managed_roles: []
postgresql_managed_databases: []
postgresql_managed_memberships: []
postgresql_managed_access_profiles: []
```

See `examples/postgresql-access.yml.example`.

## 12. TLS

```yaml
postgresql_tls_management_enabled: false
postgresql_tls_require_ssl: false
postgresql_tls_min_protocol_version: "TLSv1.2"
postgresql_tls_certificate_deployment_enabled: false
postgresql_tls_activation_enabled: false
postgresql_tls_internal_sslmode: "prefer"
postgresql_tls_expected_identities: {}
```

Certificate source paths are empty by default.

## 13. OS hardening

```yaml
os_hardening_enabled: false
os_hardening_manage_sshd: false
os_hardening_apparmor_enforce_enabled: false
os_hardening_apparmor_profiles: []
```

## 14. Monitoring

```yaml
postgresql_ha_monitoring_enabled: true
postgresql_exporter_enabled: true
postgresql_exporter_port: 9187
haproxy_prometheus_enabled: true
haproxy_prometheus_port: 8404
```

Other exporter variables:

```yaml
postgresql_exporter_package: "prometheus-postgres-exporter"
postgresql_exporter_service: "prometheus-postgres-exporter"
postgresql_exporter_os_user: "postgres_exporter"
postgresql_exporter_db_role: "postgres_exporter"
postgresql_exporter_database: "postgres"
```

## 15. Backup/WAL archive

```yaml
postgresql_backup_management_enabled: false
postgresql_backup_archive_command: ""
postgresql_backup_archive_timeout: "60s"
postgresql_backup_destination: ""
```

Do not enable until the archive destination is durable and the command is tested.

## 16. Logging

```yaml
postgresql_central_logging_enabled: false
postgresql_central_logging_destination: ""
```

PostgreSQL local file logging is already configured independently of central shipping.

## 17. Patch management

```yaml
postgresql_patch_automation_enabled: false
```

Normal maintenance is intentionally run through the rolling procedure rather than unattended cluster-wide upgrades.

## 18. Preflight thresholds

| Variable | Purpose |
|---|---|
| `preflight_min_memory_mb` | Minimum memory |
| `preflight_min_vcpus` | Minimum vCPUs |
| `preflight_min_data_disk_gb` | Minimum data disk size |
| `preflight_max_clock_offset_seconds` | Maximum tolerated time offset |
| `preflight_require_vip_unresponsive` | VIP collision safety check |
| `preflight_allow_existing_managed_vip` | Permit idempotent rerun when Keepalived already owns the configured VIP |

## 19. Inventory host variables

Each PostgreSQL node normally defines:

```yaml
ansible_host: <node-ip>
node_fqdn: <node-fqdn>
postgres_data_device: <stable-device-path>
keepalived_priority: <unique-priority>
```

Do not embed private keys, passwords or certificate private material in inventory files.
