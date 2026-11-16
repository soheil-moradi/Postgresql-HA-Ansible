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
        self.assertIn('postgres_data_disk_allow_initialize', self.role_text)

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

    def test_discovery_is_read_only_and_before_existing_guard(self):
        discovery = yaml.safe_load((ROOT / 'roles/storage/tasks/discover.yml').read_text(encoding='utf-8'))
        self.assertEqual(self.guard[0]['ansible.builtin.import_tasks'], 'discover.yml')
        self.assertIn('storage_selected_device', self.guard_text)
        self.assertNotIn('postgres_data_disk_allow_initialize', self.guard_text)
        self.assertIn('postgres_data_disk_allow_initialize', self.role_text)
        self.assertIn('postgres_storage_discovery_mode', str(discovery))
        for task in discovery:
            self.assertFalse(set(task).intersection({
                'ansible.builtin.file', 'ansible.posix.mount', 'community.general.lvg',
                'community.general.lvol', 'community.general.filesystem',
            }), task.get('name'))
            if 'ansible.builtin.command' in task or 'ansible.builtin.shell' in task:
                self.assertFalse(task.get('changed_when'), task['name'])

    def test_integration_playbook_requires_explicit_initialization_flag(self):
        integration = yaml.safe_load((ROOT / 'playbooks/storage-integration.yml').read_text(encoding='utf-8'))
        self.assertEqual(integration[0]['ansible.builtin.import_playbook'], 'inventory-preflight.yml')
        self.assertEqual(integration[1]['hosts'], 'postgresql_nodes')
        self.assertEqual(integration[1]['serial'], 1)
        tasks = integration[1]['tasks']
        self.assertIn('not (postgres_storage_initialize', tasks[0]['when'])
        self.assertIn('postgres_storage_initialize', tasks[1]['when'])
        self.assertEqual(tasks[0]['ansible.builtin.include_role']['tasks_from'], 'validate')
        self.assertTrue(tasks[1]['vars']['postgres_data_disk_allow_initialize'])

    def test_final_findmnt_command_keeps_output_columns_as_one_argument(self):
        task = next(
            task for task in self.role
            if task.get('name') == 'Verify the mountpoint after storage reconciliation'
        )
        argv = task['ansible.builtin.command']['argv']
        self.assertEqual(argv[-2:], ['--output', 'SOURCE,FSTYPE'])
        self.assertEqual(argv.count('SOURCE,FSTYPE'), 1)
        self.assertNotIn('SOURCE', argv)
        self.assertNotIn('FSTYPE', argv)

    def test_persistence_playbook_is_opt_in_serial_and_never_formats(self):
        path = ROOT / 'playbooks/storage-persistence-lab.yml'
        source = path.read_text(encoding='utf-8')
        plays = yaml.safe_load(source)
        self.assertEqual(plays[0]['ansible.builtin.import_playbook'], 'inventory-preflight.yml')
        play = plays[1]
        self.assertEqual(play['hosts'], 'postgresql_nodes')
        self.assertEqual(play['serial'], 1)
        self.assertTrue(play['any_errors_fatal'])
        approval = play['pre_tasks'][0]['ansible.builtin.assert']['that']
        self.assertTrue(any('postgres_storage_persistence_test_approved' in a for a in approval))
        self.assertTrue(any('postgres_storage_discovery_mode' in a for a in approval))
        self.assertTrue(any('postgres_storage_initialize' in a for a in approval))
        tasks = play['tasks'][0]
        self.assertIn('always', tasks)
        actions = [next(iter(task.keys() - {'name', 'register', 'changed_when'}), '')
                   for task in tasks['block']]
        self.assertIn('ansible.builtin.tempfile', actions)
        self.assertIn('ansible.builtin.reboot', actions)
        self.assertIn('ansible.builtin.slurp', actions)
        self.assertEqual(actions.count('ansible.builtin.include_tasks'), 2)
        self.assertIn('ansible.builtin.file', str(tasks['always']))
        self.assertIn('storage_persistence_cleanup_source.stdout', str(tasks['always']))
        self.assertIn('storage_expected_lv_realpath.stdout', str(tasks['always']))
        for forbidden in ('community.general.lvg', 'community.general.lvol',
                          'community.general.filesystem', 'ansible.posix.mount'):
            self.assertNotIn(forbidden, source)
        verify = yaml.safe_load((ROOT / 'playbooks/tasks/storage-persistence-verify.yml').read_text(encoding='utf-8'))
        self.assertEqual(verify[0]['ansible.builtin.include_role']['tasks_from'], 'validate')
        self.assertEqual(verify[2]['ansible.builtin.command']['argv'][-2:],
                         ['--output', 'SOURCE,FSTYPE'])

    def test_local_validation_script_is_safe_to_execute_as_child(self):
        p = ROOT / 'scripts/validate-local.sh'
        self.assertEqual(subprocess.run(['bash', '-n', str(p)],
                                        capture_output=True).returncode, 0)
        contents = p.read_text(encoding='utf-8')
        self.assertIn('python -m unittest discover -s tests -v', contents)
        self.assertIn('-i inventory/examples/topology-3-vm.yml', contents)
        self.assertIn('-i inventory/examples/syntax-legacy-alias.ini', contents)
        self.assertIn('site.yml playbooks/*.yml --syntax-check', contents)
        self.assertIn('[postgresql_cluster:children]',
                      (ROOT / 'inventory/examples/syntax-legacy-alias.ini').read_text())
        workflow = (ROOT / '.github/workflows/ansible-ci.yml').read_text(encoding='utf-8')
        self.assertIn('inventory/examples/syntax-legacy-alias.ini', workflow)
        self.assertNotIn('|| exit 1', contents)


if __name__ == '__main__':
    unittest.main()
