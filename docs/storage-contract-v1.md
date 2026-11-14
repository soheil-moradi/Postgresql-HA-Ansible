# Storage Contract v1 (Initial Deployment)

Status: **proposed implementation — not production validated**.

## Scope

This contract defines storage placement for PostgreSQL hosts in a generic
three-node, inventory-driven initial deployment. It is independent of whether
hosts were provisioned by Terraform, another tool, or manually; and whether
those hosts are virtual machines or bare metal.

Each PostgreSQL host has an OS disk **outside this role's scope** and a dedicated
whole data disk, identified with `postgres_data_device`. The role uses one
LVM physical volume directly on that disk, a volume group, a logical volume,
and an XFS filesystem. No partition table is required. For v1, only
`/var/lib/postgresql` and `/pgdata` are accepted mountpoints. Existing ext4 data
volumes remain supported only when `postgres_filesystem: ext4` is explicitly
retained; conversion to XFS is never automatic.

Representative variables (documentation-only placeholder):

```yaml
postgres_data_device: /dev/disk/by-id/<stable-disk-identifier>
postgres_data_disk_allow_initialize: false
postgres_vg_name: vg_postgresql
postgres_lv_name: lv_postgresql
postgres_filesystem: xfs
postgres_mount_point: /var/lib/postgresql
postgres_mount_options: defaults,noatime
```

The current deployment's Patroni data directory is derived from
`postgres_mount_point`; keep `/var/lib/postgresql` for backwards compatibility.
A stable `/dev/disk/by-id/` identifier is recommended. Inventory validation
checks only the declared value; the on-host storage guard verifies device
identity and the actual block graph.

## Behavior

- **New, empty disk**: only initialize when `postgres_data_disk_allow_initialize`
  is explicitly `true`, after verifying a whole disk with no signatures,
  partitions, dependent devices or mounts. Run LVM PV/VG, LV, filesystem,
  and mount steps in that order.
- **Existing managed disk**: verify the declared PV belongs to the exact VG,
  the VG uses exactly one PV and contains exactly the expected LV on the target disk, and the filesystem
  matches the declared type. Do not run filesystem creation or LVM creation.
  A repeat deployment must not reinitialize this disk.
- **Unknown or partial LVM state**: stop. A partially completed initialization
  needs an operator review; no automatic destructive repair is attempted.
- **Mountpoint**: reject symlinks, foreign mounts, conflicting fstab sources,
  and nonempty unmounted directories. These checks prevent masking OS data.
- **Expansion**: intentionally excluded from this change. The existing
  `playbooks/extend_storage.yml` remains legacy and must not be used as the
  v1 XFS or bare-metal expansion procedure. Expanding PV/LV/XFS must have a
  separately reviewed workflow and explicit approval.

## Trust boundaries and limitations

This role assumes a fresh, explicitly designated data device whose identity
was independently confirmed by the operator. Software checks are not a
replacement for verifying the underlying storage/LUN assignment. `wipefs
--no-act` reads detectable signatures; it does not prove a disk has never held
valuable data. The role does **not** format an existing recognized LV and does
not remove PVs from a VG (`remove_extra_pvs: false`).

The storage role runs only when explicitly invoked by the deployment workflow;
the older deployment and system-wide preflight still use the legacy
`postgresql_cluster` group. Inventory-driven placement refactoring is a
separate milestone. No cluster host membership change or live migration is
performed by this change.

## Validation gate

Before commit, run `./scripts/validate-local.sh` in the project's Python venv.
It checks the three-node inventory, Python regressions, and Ansible syntax for
all entry points. PostgreSQL integration tests require an isolated disposable
PostgreSQL 16 instance and `POSTGRES_TEST_DSN`; skip status is not proof of
integration success. Additional tests on **disposable loopback disks** must
precede any real storage initialization. Never test destructive steps on a
corporate data device.
