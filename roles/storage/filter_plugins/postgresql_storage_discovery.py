"""Conservative block-device selection for explicitly opted-in disposable labs.

No disk is modified. The storage role validates signatures, identity, and LVM
ownership after this filter identifies the only non-root whole disk.
"""

from __future__ import annotations


class StorageDiscoveryError(ValueError):
    """Raised when unattended storage selection would be ambiguous or unsafe."""


def _mountpoints(node):
    values = node.get("mountpoints")
    if values is None:
        values = [node.get("mountpoint")]
    elif isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        raise StorageDiscoveryError("Unexpected lsblk mountpoints structure")
    return {value for value in values if isinstance(value, str) and value}


def _contains_root(node):
    if not isinstance(node, dict):
        raise StorageDiscoveryError("Unexpected lsblk device structure")
    children = node.get("children") or []
    if not isinstance(children, list):
        raise StorageDiscoveryError("Unexpected lsblk children structure")
    return "/" in _mountpoints(node) or any(_contains_root(child) for child in children)


def select_auto_disk(lsblk):
    """Return the only physical disk not backing '/'; otherwise fail closed.

    Every other type, or a topology without an identifiable root disk, is
    rejected. Foreign filesystems/signatures on the selected disk are rejected
    by the role's existing read-only storage validation, NOT filtered away.
    This avoids silently choosing a blank disk beside a foreign data disk.
    """
    if not isinstance(lsblk, dict) or not isinstance(lsblk.get("blockdevices"), list):
        raise StorageDiscoveryError("Missing lsblk JSON blockdevices list")

    disks = []
    seen = set()
    for node in lsblk["blockdevices"]:
        if not isinstance(node, dict):
            raise StorageDiscoveryError("Unexpected lsblk device structure")
        if node.get("type") != "disk":
            continue
        path = node.get("path")
        if not isinstance(path, str) or not path.startswith("/dev/") or "\n" in path:
            raise StorageDiscoveryError("Disk has no safe absolute /dev path")
        if path in seen:
            raise StorageDiscoveryError("lsblk lists a physical disk more than once")
        seen.add(path)
        disks.append(node)

    if not disks:
        raise StorageDiscoveryError("No physical disks found by lsblk")

    root_disks = [disk for disk in disks if _contains_root(disk)]
    if not root_disks:
        raise StorageDiscoveryError(
            "Cannot identify the root filesystem's physical disk; refusing automatic selection"
        )

    others = [disk for disk in disks if disk not in root_disks]
    if len(others) != 1:
        raise StorageDiscoveryError(
            f"Expected exactly one independent non-OS disk; found {len(others)}. "
            "Use explicit disk identity instead of guessing."
        )

    candidate = others[0]
    if _mountpoints(candidate):
        raise StorageDiscoveryError("The independent disk is already mounted")

    children = candidate.get("children") or []
    if not isinstance(children, list):
        raise StorageDiscoveryError("Unexpected lsblk children structure")
    fstype = candidate.get("fstype")
    if fstype in (None, ""):
        if children:
            raise StorageDiscoveryError("Non-OS disk contains partitions or unknown dependencies")
    elif fstype == "LVM2_member":
        if len(children) != 1 or children[0].get("type") != "lvm":
            raise StorageDiscoveryError("LVM disk has unexpected dependent devices")
        # VG/LV ownership, contents and mountpoint are verified by validate.yml.
    else:
        raise StorageDiscoveryError("Non-OS disk has an unrelated filesystem or signature")

    # This path is a *candidate*, not permission to initialize. validate.yml
    # re-checks the exact block topology and wipefs signatures read-only.
    return candidate["path"]


class FilterModule:
    def filters(self):
        return {"postgres_storage_select_auto_disk": select_auto_disk}
