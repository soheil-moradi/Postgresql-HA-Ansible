"""Read-only Patroni lab preflight and independent inventory groups."""
import unittest
from pathlib import Path

import yaml
try:
    from jinja2 import Environment, StrictUndefined
except ImportError:
    Environment = None
    StrictUndefined = None

ROOT = Path(__file__).resolve().parents[1]


class PatroniLabPreflight(unittest.TestCase):
    def test_preflight_uses_nonmutating_modules_only(self):
        doc = yaml.safe_load((ROOT / 'playbooks/patroni-preflight-lab.yml').read_text())
        self.assertEqual(doc[0]['ansible.builtin.import_playbook'], 'inventory-preflight.yml')
        permitted = {'ansible.builtin.assert', 'ansible.builtin.include_role',
                     'ansible.builtin.command', 'ansible.builtin.stat', 'ansible.builtin.debug'}
        for play in doc[1:]:
            self.assertFalse(play['gather_facts'])
            self.assertTrue(play['any_errors_fatal'])
            for task in play['tasks']:
                with self.subTest(name=task['name']):
                    self.assertTrue(set(task) & permitted)
                    self.assertFalse(set(task) & {
                        'ansible.builtin.apt', 'ansible.builtin.file',
                        'ansible.builtin.systemd_service', 'ansible.builtin.template',
                        'ansible.builtin.mount'})
                    if 'ansible.builtin.command' in task:
                        self.assertFalse(task['changed_when'])

    def test_template_uses_separate_pg_and_etcd_groups_with_legacy_fallback(self):
        source = (ROOT / 'roles/patroni/templates/patroni.yml.j2').read_text()
        self.assertIn("groups.get('postgresql_nodes', groups.get('postgresql_cluster', []))", source)
        self.assertIn("groups.get('etcd_nodes', groups.get('postgresql_cluster', []))", source)
        self.assertIn('for host in etcd_hosts', source)
        self.assertIn('for host in pg_hosts', source)
        tls = (ROOT / 'roles/patroni/tasks/validate_internal_tls.yml').read_text()
        self.assertIn("groups.get('postgresql_nodes', groups.get('postgresql_cluster', []))", tls)

    @unittest.skipIf(Environment is None, 'Jinja2 is not installed')
    def test_template_separates_dcs_from_replication_hosts(self):
        # Independent groups must work without the deprecated group.
        from test_templates_and_access import environment, variables
        env = environment()
        cfg = variables(env)
        pg_hosts = ['pg01', 'pg02', 'pg03']
        etcd_hosts = ['kv01', 'kv02', 'kv03']
        cfg['groups'] = {'postgresql_nodes': pg_hosts, 'etcd_nodes': etcd_hosts}
        cfg['hostvars'] = {
            host: {'ansible_host': f'192.0.2.{10+i}'}
            for i, host in enumerate(pg_hosts + etcd_hosts)
        }
        cfg['inventory_hostname'] = pg_hosts[0]
        cfg['ansible_host'] = cfg['hostvars'][pg_hosts[0]]['ansible_host']
        rendered = env.from_string(
            (ROOT / 'roles/patroni/templates/patroni.yml.j2').read_text()
        ).render(**cfg)
        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed['etcd3']['hosts'],
                         [f'192.0.2.{i}:2379' for i in range(13,16)])
        hba = parsed['bootstrap']['pg_hba']
        for i in range(10,13):
            self.assertTrue(any(f'192.0.2.{i}/32' in rule for rule in hba))
        for i in range(13,16):
            self.assertFalse(any(f'192.0.2.{i}/32' in rule for rule in hba))


if __name__ == '__main__':
    unittest.main()
