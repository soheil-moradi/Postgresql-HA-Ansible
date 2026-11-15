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

## Auto discovery (Lab extension, Milestone 2.1)

`postgres_storage_discovery_mode` defaults to `explicit`. In this mode, each
host must supply a stable `postgres_data_device` (the production contract).
`auto` is **opt-in, for disposable lab VMs only**, and overrides even a legacy
`postgres_data_device` value in the private inventory. It does not overwrite
that inventory file. Do not enable automatic selection in production.

In `auto` mode the role reads the **entire** `lsblk` tree, identifies disk(s)
backing `/` from their descendants, then requires **exactly one other whole
disk**. A system whose root disk cannot be identified, or a system with
multiple independent data disks, **fails closed**. The candidate must be raw
or an already recognized LVM whole disk. The original storage guard then
checks `wipefs`, the exact PV/VG/LV identity, filesystem, foreign mounts,
`fstab`, and nonempty unmounted destinations. Disk ordering (`sdb`, `vdb`)
is not an input to selection.

The selected kernel disk is resolved to `/dev/disk/by-id/` (preferred) or
`/dev/disk/by-path/`. If neither exists, discovery fails instead of trusting
an unstable `/dev/sdX` name. A `by-path` identifier may change if Terraform
moves the disk to another virtual controller/slot. Configure an explicit
serial/WWN in provisioning if a stronger persistent identity is required.

`playbooks/storage-integration.yml` is a standalone **Storage-only** playbook,
not a cluster deployment. It is read-only by default. Sample commands (from
the repository root, with private inventory outside the public repository):

```bash
INV=/path/to/private/lab.yml
ansible-playbook -i "$INV" -u <ssh-user> -K \
  -e postgres_storage_discovery_mode=auto \
  playbooks/storage-integration.yml
# Only after confirming independent disposable data disks and reviewing the
# read-only result, allow initial LVM/XFS provisioning on these lab VMs:
ansible-playbook -i "$INV" -u <ssh-user> -K \
  -e postgres_storage_discovery_mode=auto \
  -e postgres_storage_initialize=true \
  playbooks/storage-integration.yml
```

The initialize switch provides **per-run explicit permission** to the role;
without it, the playbook includes only the read-only `validate` task list,
and never invokes the Storage role's mutating `main` task list. The playbook uses `serial: 1` and `any_errors_fatal: true`.
It does not install PostgreSQL/Patroni or extend disks. Real on-host storage
execution and idempotency must still be confirmed before production rollout.

## Post-reboot persistence verification (Milestone 2.1)

This **disruptive, opt-in** test is for already-initialized, disposable lab VMs.
It never initializes a PV/VG/LV or repairs a mount. The test runs on one host
at a time (`serial: 1`), checks that the expected XFS/ext4 LV is mounted,
creates one unique root-owned probe on that filesystem, flushes writes,
reboots the VM, verifies the *same LV* was remounted, and checks the probe's
exact contents. It then attempts to remove only its own probe, but only while the original
managed LV remains mounted.

Run locally against your **private** lab inventory only after approving a
reboot of *every selected node*. Since it reboots hosts, do not run this on
production or once real PostgreSQL workloads have been started:

```bash
ansible-playbook -i "$INV" -u <ssh-user> -K \
  -e postgres_storage_discovery_mode=auto \
  -e postgres_storage_persistence_test_approved=true \
  playbooks/storage-persistence-lab.yml
```

The playbook fails closed without the separate reboot approval, without `auto`
lab mode, or if `postgres_storage_initialize` is enabled. A failed reboot or
unreachable host may prevent automatic probe cleanup; investigate the
`.ansible-storage-persistence-*.probe` test file after recovery. The playbook
never deletes an unspecified existing file. The test does not prove behavior
under power loss, storage-controller failure, or hardware failover.

Static validation and the `findmnt` argument regression run together via
`./scripts/validate-local.sh`. Local and CI syntax checks use only the public
example inventory plus a syntax-only alias for legacy `postgresql_cluster`
playbooks; neither check contacts any actual node. Actual reboot tests are
intentionally excluded from CI and require explicit operator invocation.
