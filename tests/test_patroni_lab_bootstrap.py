"""Non-mutating lab bootstrap contracts; Ansible runtime tested separately."""
from pathlib import Path
import unittest
import yaml
import json
import jinja2

ROOT = Path(__file__).resolve().parents[1]

class PatroniLabBootstrap(unittest.TestCase):
    def setUp(self):
        self.playbook = yaml.safe_load((ROOT / 'playbooks/patroni-bootstrap-lab.yml').read_text())

    def test_first_step_is_existing_read_only_preflight(self):
        self.assertEqual(self.playbook[0]['ansible.builtin.import_playbook'], 'patroni-preflight-lab.yml')

    def test_approval_and_secrets_before_remote_mutations(self):
        self.assertEqual(self.playbook[1]['hosts'], 'localhost')
        gate = self.playbook[1]['tasks']
        self.assertIn('patroni_lab_bootstrap_approved', str(gate))
        self.assertTrue(gate[1]['no_log'])
        self.assertEqual(self.playbook[2]['hosts'], 'postgresql_nodes')
        self.assertIn('any_errors_fatal', self.playbook[2])
        self.assertIn('ansible_play_hosts_all', str(self.playbook[2]['tasks']))

    def test_no_storage_mutations_or_dcs_updates(self):
        dangerous = ('filesystem', 'lvol', 'lvg', 'mount', 'wipefs', 'mkfs', 'member add', 'member remove', 'etcdctl put', 'etcdctl del')
        text = (ROOT / 'playbooks/patroni-bootstrap-lab.yml').read_text()
        for word in dangerous:
            with self.subTest(word=word):
                self.assertNotIn('ansible.builtin.' + word + ':', text)
        self.assertIn('lab_existing_marker', text)
        self.assertIn('lab_existing_dcs', text)

    def test_role_defaults_render_without_legacy_group(self):
        defaults = yaml.safe_load((ROOT / 'roles/patroni/defaults/main.yml').read_text())
        hosts = {n: {'ansible_host': '192.0.2.' + str(i)}
                 for i,n in enumerate(('pg01','pg02','pg03'), 11)}
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(to_json=json.dumps, bool=lambda x: bool(x),
                           to_nice_yaml=lambda x, **kwargs: yaml.safe_dump(x, **kwargs).rstrip())
        defaults['patroni_dynamic_configuration']['synchronous_mode'] = False
        variables = dict(defaults, inventory_hostname='pg01', ansible_host='192.0.2.11',
                         groups={'postgresql_nodes':list(hosts),'etcd_nodes':list(hosts)},
                         hostvars=hosts, vault_patroni_rest_password='dummy1',
                         vault_postgres_superuser_password='dummy2',
                         vault_postgres_replication_password='dummy3',
                         vault_postgres_rewind_password='dummy4')
        config = yaml.safe_load(env.from_string(
            (ROOT/'roles/patroni/templates/patroni.yml.j2').read_text()).render(**variables))
        self.assertEqual(len(config['etcd3']['hosts']), 3)
        self.assertEqual(config['postgresql']['data_dir'], '/var/lib/postgresql/16/patroni')
        self.assertEqual(config['scope'], 'pg-lab')

    def test_patroni_role_refreshes_apt_before_installing_packages(self):
        tasks = yaml.safe_load((ROOT / 'roles/patroni/tasks/main.yml').read_text())
        self.assertEqual(tasks[0]['ansible.builtin.apt'], {
            'update_cache': True,
            'cache_valid_time': 3600,
        })
        self.assertEqual(tasks[1]['name'], 'Install postgresql-common before the server package')
        self.assertTrue(any(task.get('name') == 'Install PostgreSQL, Patroni, and Python driver packages'
                            for task in tasks[2:]))

    def test_primary_precedes_replica_start_and_sql_verification(self):
        starts = [i for i,play in enumerate(self.playbook) if isinstance(play,dict) and play.get('name','').startswith('Start ')]
        self.assertEqual(starts, [5,6])
        self.assertTrue(self.playbook[6]['serial'] == 1)
        self.assertIn('pg_stat_replication', str(self.playbook[7]))

if __name__ == '__main__':
    unittest.main()
