"""Offline tests for the inventory-driven, lab-only etcd bootstrap."""
import unittest
import shutil
import subprocess
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / 'roles' / 'etcd'
PLAYBOOK = ROOT / 'playbooks' / 'etcd-bootstrap-lab.yml'


class EtcdBootstrapContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defaults = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
        cls.template = (ROLE / 'templates/etcd.j2').read_text()
        cls.playbook = yaml.safe_load(PLAYBOOK.read_text())
        cls.verify = yaml.safe_load((ROLE / 'tasks/verify.yml').read_text())
        cls.role = yaml.safe_load((ROLE / 'tasks/main.yml').read_text())

    def test_separate_etcd_group_not_legacy_postgresql_group(self):
        self.assertIn('etcd_cluster_hosts', self.template)
        self.assertNotIn("groups['postgresql_cluster']", self.template)
        self.assertIn('etcd_nodes', self.defaults['etcd_cluster_hosts'])
        self.assertIn('postgresql_cluster', self.defaults['etcd_cluster_hosts'])

    def test_etcd_cluster_template_renders_each_declared_peer(self):
        env = jinja2.Environment(keep_trailing_newline=True)
        env.filters['bool'] = bool
        hosts = ['etcd01', 'etcd02', 'etcd03']
        addresses = [f'192.0.2.{i}' for i in range(11, 14)]
        hostvars = {name: {'ansible_host': address} for name, address in zip(hosts, addresses)}
        rendered = env.from_string(self.template).render(
            inventory_hostname='etcd01', ansible_host='192.0.2.11',
            etcd_cluster_hosts=hosts, hostvars=hostvars,
            etcd_data_dir='/var/lib/etcd', etcd_client_port=2379,
            etcd_peer_port=2380, etcd_cluster_token='test-lab-cluster',
            etcd_tls_enabled=False,
        )
        peers = ','.join(f'{name}=http://{hostvars[name]["ansible_host"]}:2380'
                         for name in hosts)
        self.assertIn(f'ETCD_INITIAL_CLUSTER="{peers}"', rendered)
        self.assertIn('ETCD_NAME="etcd01"', rendered)
        self.assertIn('ETCD_INITIAL_CLUSTER_TOKEN="test-lab-cluster"', rendered)
        self.assertNotIn('https://', rendered)

        csv = env.from_string(self.defaults['etcd_client_endpoints_csv']).render(
            etcd_cluster_hosts=hosts, etcd_tls_enabled=False,
            hostvars=hostvars, etcd_client_port=2379,
        )
        self.assertEqual(csv, ','.join('http://' + address + ':2379' for address in addresses))

    def test_lab_gate_precedes_any_remote_install(self):
        self.assertEqual(self.playbook[0]['ansible.builtin.import_playbook'],
                         'inventory-preflight.yml')
        preflight = yaml.safe_load((ROOT / 'playbooks/inventory-preflight.yml').read_text())
        self.assertTrue(preflight[0]['any_errors_fatal'])
        gate = self.playbook[1]
        self.assertEqual(gate['hosts'], 'localhost')
        self.assertTrue(gate['any_errors_fatal'])
        assert_text = str(gate['tasks'][0]['ansible.builtin.assert']['that'])
        self.assertIn('etcd_lab_plaintext_approved', assert_text)
        self.assertIn('etcd_tls_enabled', assert_text)
        self.assertEqual(self.playbook[2]['hosts'], 'etcd_nodes')
        self.assertFalse(self.playbook[2]['gather_facts'])
        self.assertIn('ansible.builtin.assert', self.playbook[2]['pre_tasks'][0])
        self.assertIn('ansible.builtin.setup', self.playbook[2]['pre_tasks'][1])
        self.assertEqual(self.playbook[2]['strategy'], 'linear')
        self.assertTrue(self.playbook[2]['any_errors_fatal'])
        self.assertNotIn('serial', self.playbook[2], 'all members must start before quorum wait')
        self.assertIn('ansible_play_hosts_all', str(self.playbook[2]['pre_tasks']))
        self.assertIn('etcd_lab_plaintext_approved', str(self.playbook[2]['pre_tasks']))
        self.assertIn('etcd_previous_member', str(self.playbook[2]['pre_tasks']))
        self.assertIn('ETCD_INITIAL_CLUSTER_TOKEN', str(self.playbook[2]['pre_tasks']))
        self.assertEqual(self.playbook[3]['roles'][0]['tasks_from'], 'verify')
        self.assertNotIn('postgresql', str(self.playbook[2]['roles']))
        self.assertNotIn('storage', str(self.playbook[2]['roles']))

    def test_lab_token_is_resolved_and_checked_before_role_execution(self):
        bootstrap = self.playbook[2]
        tasks = bootstrap['pre_tasks']
        self.assertNotIn('etcd_cluster_token', bootstrap.get('vars', {}))
        names = [task['name'] for task in tasks]
        fact_idx = names.index('Establish the deterministic etcd lab cluster token for each member')
        guard_idx = names.index('Require identical calculated etcd tokens before modifying services')
        self.assertLess(fact_idx, guard_idx)
        self.assertLess(guard_idx, names.index('Inspect pre-existing etcd member data without modifying it'))
        fact_expr = tasks[fact_idx]['ansible.builtin.set_fact']['etcd_cluster_token']
        self.assertIn("groups['etcd_nodes']", fact_expr)
        self.assertIn("hash('sha256')", fact_expr)
        assertions = str(tasks[guard_idx]['ansible.builtin.assert']['that'])
        self.assertIn('etcd_cluster_token', assertions)
        self.assertIn('unique | length', assertions)

    def test_member_verification_is_read_only_and_checks_consensus(self):
        forbidden = {'ansible.builtin.shell', 'ansible.builtin.apt',
                     'ansible.builtin.template', 'ansible.builtin.file',
                     'ansible.builtin.systemd_service'}
        for task in self.verify:
            with self.subTest(task=task['name']):
                self.assertFalse(forbidden.intersection(task))
                if 'ansible.builtin.command' in task:
                    self.assertFalse(task['changed_when'])
                    argv = task['ansible.builtin.command']['argv']
                    self.assertIn('--write-out=json', argv)
        verify_text = (ROLE / 'tasks/verify.yml').read_text()
        for expected in ('peerURLs', 'Status.header.member_id', 'Status.leader',
                         'etcd_cluster_hosts', 'member', 'endpoint'):
            self.assertIn(expected, verify_text)

    @unittest.skipUnless(shutil.which('ansible-playbook'),
                         'Requires ansible-playbook for controller-only gate test')
    def test_lab_gate_rejects_missing_ack_without_ssh(self):
        # Do not use --limit localhost: Ansible rejects an untargeted etcd play
        # before the local gate runs. any_errors_fatal stops all later plays.
        result = subprocess.run(
            ['ansible-playbook', '-i', 'inventory/examples/topology-3-vm.yml',
             'playbooks/etcd-bootstrap-lab.yml'],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
        )
        # Parse/runtime errors are normally printed to stderr by Ansible.
        # A non-zero rc alone does not prove our approval gate was reached.
        diagnostic = (
            f"Ansible return code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        self.assertNotEqual(result.returncode, 0, diagnostic)
        self.assertIn('Reject unapproved plaintext etcd deployment',
                      result.stdout, diagnostic)
        self.assertIn('failed=1', result.stdout, diagnostic)
        self.assertNotIn('PLAY [Install and bootstrap the initial three-member etcd lab]',
                         result.stdout, diagnostic)

    def test_etcd_package_bootstrap_keeps_first_run_safe(self):
        installs = [task for task in self.role if 'ansible.builtin.apt' in task]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0]['ansible.builtin.apt']['policy_rc_d'], 101)
        restart = next(t for t in self.role
                       if t['name'].startswith('Rolling restart an existing etcd member'))
        self.assertEqual(restart['throttle'], 1)
        self.assertIn('etcd_config_result.changed', restart['when'])
        self.assertIn('etcd_was_active.rc == 0', restart['when'])


if __name__ == '__main__':
    unittest.main()
