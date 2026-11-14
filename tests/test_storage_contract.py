"""Structural regression tests for the non-destructive Storage Contract v1.

These tests do not substitute for loopback-device integration tests.
"""
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / 'roles/storage/tasks/main.yml'
GUARD = ROOT / 'roles/storage/tasks/validate.yml'


class StorageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role = yaml.safe_load(ROLE.read_text(encoding='utf-8'))
        cls.guard = yaml.safe_load(GUARD.read_text(encoding='utf-8'))
        cls.role_text = ROLE.read_text(encoding='utf-8')
        cls.guard_text = GUARD.read_text(encoding='utf-8')

    def test_validation_is_before_mutation(self):
        self.assertEqual(self.role[0]['ansible.builtin.import_tasks'], 'validate.yml')
        for task in self.guard:
            self.assertFalse(set(task).intersection({
                'ansible.builtin.shell', 'ansible.builtin.file', 'ansible.posix.mount',
                'community.general.lvg', 'community.general.lvol',
                'community.general.filesystem',
            }), task.get('name'))
            if 'ansible.builtin.command' in task:
                self.assertEqual(task.get('changed_when'), False, task['name'])

    def test_lvm_creation_is_gated_and_pvs_cannot_be_removed(self):
        vg = next(x for x in self.role if 'community.general.lvg' in x)
        lv = next(x for x in self.role if 'community.general.lvol' in x)
        self.assertFalse(vg['community.general.lvg']['remove_extra_pvs'])
        self.assertFalse(lv['community.general.lvol']['shrink'])
        self.assertIn('not storage_disk_is_managed', vg['when'])
        self.assertIn('not storage_disk_is_managed', lv['when'])
        self.assertIn('postgres_data_disk_allow_initialize', self.guard_text)

    def test_existing_filesystem_is_never_recreated(self):
        fs = next(x for x in self.role if 'community.general.filesystem' in x)
        self.assertFalse(fs['community.general.filesystem']['force'])
        self.assertIn('not storage_disk_is_managed', fs['when'])
        self.assertIn('storage_managed_fstype.stdout | trim == postgres_filesystem', self.guard_text)

    def test_disk_mountpoint_and_lvm_identity_are_validated(self):
        inspect = next(x for x in self.guard if x['name'].startswith('Inspect the target device'))
        self.assertIn('--tree', inspect['ansible.builtin.command']['argv'])
        for rule in (
            "storage_device_tree.type == 'disk'",
            "storage_disk_children | length == 0",
            'storage_disk_signatures.stdout | trim | length == 0',
            'storage_existing_disk_vg.stdout | trim == postgres_vg_name',
            'storage_existing_pv_count.stdout | trim | int == 1',
            'storage_disk_children[0].kname',
            'storage_disk_children[0].mountpoints',
            'storage_unmounted_destination_entries.matched',
            'storage_existing_mount_realpath.stdout',
            'storage_fstab_source',
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, self.guard_text)
        self.assertIn('storage_final_mount_source.stdout', self.role_text)

    def test_local_validation_script_is_safe_to_execute_as_child(self):
        p = ROOT / 'scripts/validate-local.sh'
        self.assertEqual(subprocess.run(['bash', '-n', str(p)],
                                        capture_output=True).returncode, 0)
        contents = p.read_text(encoding='utf-8')
        self.assertIn('python -m unittest discover -s tests -v', contents)
        self.assertIn('ansible-playbook site.yml playbooks/*.yml --syntax-check', contents)
        self.assertNotIn('|| exit 1', contents)


if __name__ == '__main__':
    unittest.main()
