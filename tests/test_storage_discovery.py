"""Behavior tests for unattended whole-disk selection (no block I/O)."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'roles/storage/filter_plugins/postgresql_storage_discovery.py'
module_spec = importlib.util.spec_from_file_location('postgresql_storage_discovery', PLUGIN)
discovery = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(discovery)


def node(path, kind, filesystem=None, mounts=None, children=None):
    result = {
        'path': path,
        'type': kind,
        'fstype': filesystem,
        'mountpoints': mounts if mounts is not None else [None],
    }
    if children is not None:
        result['children'] = children
    return result


def fresh_host():
    return {'blockdevices': [
        node('/dev/sda', 'disk', children=[
            node('/dev/sda1', 'part', 'LVM2_member', children=[
                node('/dev/mapper/vg0-root', 'lvm', 'ext4', ['/']),
                node('/dev/mapper/vg0-var', 'lvm', 'xfs', ['/var']),
            ]),
        ]),
        node('/dev/sdb', 'disk'),
    ]}


class StorageAutoDiscovery(unittest.TestCase):
    def test_selects_raw_data_disk_without_hardcoding_sdb(self):
        source = fresh_host()
        self.assertEqual(discovery.select_auto_disk(source), '/dev/sdb')
        source['blockdevices'][1]['path'] = '/dev/vdb'
        self.assertEqual(discovery.select_auto_disk(source), '/dev/vdb')

    def test_detects_existing_lvm_disk_on_rerun(self):
        source = fresh_host()
        source['blockdevices'][1] = node('/dev/sdb', 'disk', 'LVM2_member',
                                         children=[node('/dev/dm-3', 'lvm', 'xfs',
                                                        ['/var/lib/postgresql'])])
        self.assertEqual(discovery.select_auto_disk(source), '/dev/sdb')

    def test_rejects_two_non_root_disks(self):
        source = fresh_host()
        source['blockdevices'].append(node('/dev/sdc', 'disk'))
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'exactly one'):
            discovery.select_auto_disk(source)

    def test_rejects_unidentifiable_root(self):
        source = fresh_host()
        source['blockdevices'][0]['children'][0]['children'][0]['mountpoints'] = [None]
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'root filesystem'):
            discovery.select_auto_disk(source)

    def test_rejects_partitions_or_foreign_filesystems(self):
        source = fresh_host()
        source['blockdevices'][1]['children'] = [node('/dev/sdb1', 'part')]
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'partitions'):
            discovery.select_auto_disk(source)
        source = fresh_host()
        source['blockdevices'][1]['fstype'] = 'ext4'
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'unrelated filesystem'):
            discovery.select_auto_disk(source)

    def test_rejects_foreign_mount_or_unknown_lvm_graph(self):
        source = fresh_host()
        source['blockdevices'][1]['mountpoints'] = ['/mnt/foreign']
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'mounted'):
            discovery.select_auto_disk(source)
        source = fresh_host()
        source['blockdevices'][1]['fstype'] = 'LVM2_member'
        source['blockdevices'][1]['children'] = [node('/dev/sdb1', 'part')]
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'unexpected'):
            discovery.select_auto_disk(source)

    def test_rejects_duplicate_or_malformed_metadata(self):
        source = fresh_host()
        source['blockdevices'].append(copy.deepcopy(source['blockdevices'][1]))
        with self.assertRaisesRegex(discovery.StorageDiscoveryError, 'more than once'):
            discovery.select_auto_disk(source)
        with self.assertRaises(discovery.StorageDiscoveryError):
            discovery.select_auto_disk({'blockdevices': 'oops'})


if __name__ == '__main__':
    unittest.main()
