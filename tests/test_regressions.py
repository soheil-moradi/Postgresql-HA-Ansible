import ast
import base64
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

DCS = load_module('dcs', 'library/patroni_dynamic_config.py')
NET = load_module('net', 'roles/network_hardening/files/network_policy.py')
BACKUP = load_module('backup', 'roles/postgresql_backup/files/ha_backup.py')

class Files(unittest.TestCase):
    def test_yaml_unique_keys(self):
        class Unique(yaml.SafeLoader):
            pass
        def mapping(loader, node, deep=False):
            result = {}
            for kn, vn in node.value:
                key = loader.construct_object(kn, deep=deep)
                if key in result:
                    raise ValueError('Duplicate key: ' + str(key))
                result[key] = loader.construct_object(vn, deep=deep)
            return result
        Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        for p in ROOT.rglob('*'):
            if '.git' in p.parts or not p.is_file():
                continue
            if p.suffix in ('.yml', '.yaml') or p.name.endswith('.yml.example'):
                with self.subTest(file=str(p.relative_to(ROOT))):
                    # A real encrypted Vault is intentionally opaque to YAML checks.
                    content = p.read_text()
                    if not content.startswith('$ANSIBLE_VAULT;'):
                        yaml.load(content, Loader=Unique)

    def test_python_compiles(self):
        for p in ROOT.rglob('*.py'):
            if '.git' not in p.parts:
                ast.parse(p.read_text(), filename=str(p))

    def test_bash_scripts_and_inline_shell_parse(self):
        for p in (ROOT / 'scripts').glob('*.sh'):
            subprocess.run(['bash', '-n', str(p)], check=True)
        def visit(obj):
            if isinstance(obj, list):
                for child in obj: yield from visit(child)
            if isinstance(obj, dict):
                value = obj.get('ansible.builtin.shell')
                if isinstance(value, str): yield value
                for child in obj.values(): yield from visit(child)
        for base in ['roles', 'playbooks']:
            for p in (ROOT / base).rglob('*.yml'):
                for script in visit(yaml.safe_load(p.read_text())):
                    # Replace expression-only arguments; no project commands are run.
                    rendered = re.sub(r'{{.*?}}', 'dummy', script, flags=re.S)
                    with self.subTest(file=str(p.relative_to(ROOT))):
                        subprocess.run(['bash', '-n'], input=rendered, text=True, check=True)

class PatroniRegression(unittest.TestCase):
    def handler(self, reload_rc, active_rc=0):
        tasks = yaml.safe_load((ROOT / 'roles/patroni/handlers/main.yml').read_text())
        script = tasks[1]['ansible.builtin.shell']
        stub = 'systemctl() { if [[ "$1" == "is-active" ]]; then return %d; else return %d; fi; }\n' % (active_rc, reload_rc)
        return subprocess.run(['bash', '-c', stub + script], capture_output=True, text=True)

    def test_reload_failure_propagates(self):
        result = self.handler(42)
        self.assertEqual(result.returncode, 42)
        self.assertNotIn('reloaded', result.stdout)

    def test_success_reports_reload(self):
        result = self.handler(0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'reloaded')

    def test_initial_install_does_not_reload_inactive_service(self):
        result = self.handler(42, 3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'inactive')

    def test_managed_subset_preserves_unrelated_settings(self):
        actual = {'postgresql': {'parameters': {'ssl': 'on', 'archive_mode': 'on', 'work_mem': '8MB'},
                                  'pg_hba': ['local all all peer']}, 'ttl': 30}
        original = copy.deepcopy(actual)
        desired = {'postgresql': {'parameters': {'work_mem': '8MB'}}}
        self.assertTrue(DCS.subset_matches(actual, desired))
        self.assertEqual(actual, original)
        desired['postgresql']['parameters']['work_mem'] = '16MB'
        self.assertFalse(DCS.subset_matches(actual, desired))

    def test_hba_order_matters(self):
        self.assertFalse(DCS.subset_matches({'hba': ['allow', 'reject']}, {'hba': ['reject', 'allow']}))

    def test_bool_does_not_match_integer(self):
        self.assertFalse(DCS.subset_matches({'enabled': 1}, {'enabled': True}))

    def test_config_request_serializes_special_secret(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"ttl":30}'
        with patch.object(DCS, 'urlopen', return_value=Response()) as mocked:
            self.assertEqual(DCS.request_config('http://node:8008', 'api', '#a: b"c', 'PATCH', {'ttl': 30}), {'ttl': 30})
        req = mocked.call_args.args[0]
        self.assertEqual(req.method, 'PATCH')
        self.assertEqual(req.full_url, 'http://node:8008/config')
        self.assertEqual(json.loads(req.data), {'ttl': 30})
        self.assertEqual(base64.b64decode(req.get_header('Authorization').split()[1]).decode(), 'api:#a: b"c')

class FirewallRegression(unittest.TestCase):
    def data(self):
        return dict(nodes=['10.0.0.11','10.0.0.12','10.0.0.13'], vip='10.0.0.10',
                    admin=['10.0.1.0/24'], applications=['10.0.2.0/24'], monitoring=['10.0.3.1/32'],
                    ssh_source='10.0.1.9', ports=dict(ssh=22,postgres=5432,vip=5432,patroni=8008,
                    etcd_client=2379,etcd_peer=2380,haproxy_metrics=8404,postgres_metrics=9187))

    def test_rejects_ssh_lockout(self):
        data = self.data(); data['ssh_source'] = '10.5.0.9'
        with self.assertRaises(ValueError): NET.policy(data)

    def test_rejects_cidr_injection(self):
        data = self.data(); data['applications'] = ['10.0.2.0/24; flush ruleset']
        with self.assertRaises(ValueError): NET.policy(data)

    def test_rejects_unrestricted_cidr(self):
        data = self.data(); data['admin'] = ['0.0.0.0/0']
        with self.assertRaises(ValueError): NET.policy(data)

    def test_manages_only_its_table(self):
        output = NET.policy(self.data())
        self.assertNotIn('flush ruleset', output)
        self.assertIn('flush table inet pg_ha_guard', output)
        self.assertIn('ip daddr 10.0.0.10 tcp dport 5432 accept', output)
        self.assertIn('meta l4proto 112 drop', output)

    def test_monitoring_does_not_implicitly_get_etcd_api(self):
        output = NET.policy(self.data())
        allows = [x for x in output.splitlines() if '10.0.3.1/32' in x]
        self.assertTrue(all('2379' not in x for x in allows))

    def test_explicit_etcd_metrics_access(self):
        data = self.data(); data['allow_etcd_metrics_to_monitoring'] = True
        self.assertIn('ip saddr { 10.0.3.1/32 } tcp dport 2379 accept', NET.policy(data))

    def test_rollback_restores_only_previous_owned_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'state.json'; conf = Path(tmp)/'policy.nft'
            state.write_text(json.dumps({'rules':'old owned table', 'config':'previous boot rules'}))
            conf.write_text('new boot rules')
            with patch.object(NET, 'STATE', state), patch.object(NET, 'CONF', conf), patch.object(NET, 'command') as cmd:
                NET.rollback()
            cmd.assert_called_once_with(['nft', '-f', '-'], 'old owned table')
            self.assertEqual(conf.read_text(), 'previous boot rules')
            self.assertFalse(state.exists())

    def test_first_activation_rollback_removes_new_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'state.json'; conf = Path(tmp)/'policy.nft'
            state.write_text(json.dumps({'rules':'remove owned table', 'config':None})); conf.write_text('new')
            with patch.object(NET, 'STATE', state), patch.object(NET, 'CONF', conf), patch.object(NET, 'command'):
                NET.rollback()
            self.assertFalse(conf.exists())

class BackupRegression(unittest.TestCase):
    def test_missing_mount_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'repo';dest.mkdir()
            cfg=dict(mount=tmp,destination=str(dest),source='nas:/backup')
            with patch.object(BACKUP.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['findmnt'])):
                with self.assertRaises(subprocess.CalledProcessError): BACKUP.verify_repository(cfg)

    def check_mount(self, fs):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'repo';dest.mkdir()
            cfg=dict(mount=tmp,destination=str(dest),source='nas:/backup')
            completed=subprocess.CompletedProcess([],0,json.dumps({'filesystems':[fs]}),'')
            with patch.object(BACKUP.subprocess, 'run', return_value=completed):
                BACKUP.verify_repository(cfg)

    def test_local_disk_fallback_is_rejected(self):
        with self.assertRaises(ValueError): self.check_mount(dict(fstype='xfs',source='/dev/sdb',options='rw'))

    def test_wrong_offhost_repository_is_rejected(self):
        with self.assertRaises(ValueError): self.check_mount(dict(fstype='nfs4',source='other:/backup',options='rw'))

    def test_readonly_repository_is_rejected(self):
        with self.assertRaises(ValueError): self.check_mount(dict(fstype='nfs4',source='nas:/backup',options='ro'))

    def test_reviewed_writable_repository_is_accepted(self):
        self.check_mount(dict(fstype='nfs4',source='nas:/backup',options='rw,relatime'))

    def test_repository_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            p=Path(tmp)/'repo';p.symlink_to(outside)
            with self.assertRaises(ValueError): BACKUP.verify_repository(dict(mount=tmp,destination=str(p),source='nas:/backup'))

if __name__ == '__main__':
    unittest.main()
