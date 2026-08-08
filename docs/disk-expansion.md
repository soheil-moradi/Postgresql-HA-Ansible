# 💽 PostgreSQL Data Disk Expansion

![Filesystem](https://img.shields.io/badge/filesystem-XFS-blue)
![Online Grow](https://img.shields.io/badge/online_grow-supported-success)

Reference layout:

```text
virtual/block disk
  -> LVM PV
  -> vg_postgresql
  -> lv_postgresql
  -> XFS
  -> /var/lib/postgresql
```

XFS can grow online but cannot shrink.

## Procedure

First expand the underlying virtual/block disk in the infrastructure platform.

Identify the device:

```bash
lsblk
pvs
vgs
lvs
findmnt /var/lib/postgresql
```

If needed, rescan the device (example for `/dev/sdb`):

```bash
echo 1 | sudo tee /sys/class/block/sdb/device/rescan
lsblk
```

Resize the PV:

```bash
sudo pvresize /dev/sdb
```

Extend the LV, for example with all currently free extents:

```bash
sudo lvextend -l +100%FREE /dev/vg_postgresql/lv_postgresql
```

Grow XFS:

```bash
sudo xfs_growfs /var/lib/postgresql
```

Validate:

```bash
pvs
vgs
lvs
df -hT /var/lib/postgresql
xfs_info /var/lib/postgresql
```

> ⚠️ Do not reformat the filesystem. Do not attempt to shrink XFS.

For infrastructure changes that affect more than capacity metadata, prefer one node at a time and validate Patroni membership after each node.
