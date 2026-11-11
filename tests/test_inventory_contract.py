"""Inventory Contract v1 tests, including optional ansible-controller execution.

Pure Python checks run offline without Ansible; integration checks run when
ansible-playbook is installed (e.g. GitHub Actions).
"""
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'inventory/examples/topology-3-vm.yml'
PLAYBOOK = ROOT / 'playbooks/inventory-preflight.yml'


class InventoryContract(unittest.TestCase):
    def setUp(self):
        self.inventory = yaml.safe_load(EXAMPLE.read_text(encoding='utf-8'))

    def test_three_host_colocated_topology(self):
        groups = self.inventory['all']['children']
        expected = {'pg01', 'pg02', 'pg03'}
        self.assertEqual(set(groups['postgresql_nodes']['hosts']), expected)
        self.assertEqual(set(groups['etcd_nodes']['hosts']), expected)
        self.assertEqual(set(groups['load_balancer_nodes']['hosts']), expected)
        self.assertEqual(len(groups['etcd_nodes']['hosts']) % 2, 1)

    def test_two_independent_documentation_only_vips(self):
        config = self.inventory['all']['vars']
        self.assertEqual(config['postgres_cluster_vip'], '192.0.2.100')
        self.assertEqual(config['postgres_read_vip'], '192.0.2.101')
        self.assertNotEqual(config['postgres_cluster_dns_name'], config['postgres_read_dns_name'])
        self.assertFalse(config['postgresql_dr_enabled'])
        self.assertFalse(config['patroni_synchronous_mode'])

    def test_no_real_host_addresses_or_unstable_data_devices(self):
        groups = self.inventory['all']['children']
        hostvars = groups['postgresql_nodes']['hosts']
        self.assertEqual(len({v['ansible_host'] for v in hostvars.values()}), 3)
        for value in hostvars.values():
            self.assertTrue(value['ansible_host'].startswith('192.0.2.'))
            self.assertTrue(value['postgres_data_device'].startswith('/dev/disk/by-id/'))

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'ansible-playbook not installed')
    def test_controller_preflight_valid_example(self):
        self._run_preflight(self.inventory, expected_success=True)

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'ansible-playbook not installed')
    def test_controller_preflight_rejects_unsafe_variants(self):
        cases = {}
        cases['two_pg_hosts'] = lambda data: data['all']['children']['postgresql_nodes']['hosts'].pop('pg03')
        cases['even_etcd'] = lambda data: data['all']['children']['etcd_nodes']['hosts'].pop('pg03')
        cases['duplicate_ip'] = lambda data: data['all']['children']['postgresql_nodes']['hosts']['pg03'].update(
            ansible_host='192.0.2.11')
        cases['shared_vip'] = lambda data: data['all']['vars'].update(postgres_read_vip='192.0.2.100')
        cases['missing_disk'] = lambda data: data['all']['children']['postgresql_nodes']['hosts']['pg03'].pop(
            'postgres_data_device')
        cases['dr_enabled'] = lambda data: data['all']['vars'].update(postgresql_dr_enabled=True)
        cases['duplicate_priority'] = lambda data: data['all']['children']['load_balancer_nodes']['hosts']['pg03'].update(
            keepalived_priority=150)
        for name, mutate in cases.items():
            with self.subTest(case=name):
                variant = copy.deepcopy(self.inventory)
                mutate(variant)
                self._run_preflight(variant, expected_success=False)

    def _run_preflight(self, inventory, expected_success):
        with tempfile.TemporaryDirectory(prefix='pg-inventory-test-') as tmp:
            fixture = Path(tmp) / 'hosts.yml'
            fixture.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding='utf-8')
            result = subprocess.run(
                ['ansible-playbook', '-i', str(fixture), str(PLAYBOOK)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            if expected_success:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            else:
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
