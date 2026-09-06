"""Template and PostgreSQL 16 integration checks; dependencies supplied by CI.

Set POSTGRES_TEST_DSN only for an isolated disposable test PostgreSQL instance.
"""
import base64
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import uuid
import yaml
try:
    import jinja2
except ImportError:
    jinja2 = None
ROOT = Path(__file__).resolve().parents[1]


def environment():
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    env.filters.update(bool=lambda x: x is True or str(x).lower() in ['true','yes','1'],
                       ternary=lambda value,a,b: a if value else b,
                       b64encode=lambda s: base64.b64encode(str(s).encode()).decode(),
                       to_json=json.dumps,
                       to_nice_yaml=lambda value,**kw: yaml.safe_dump(value, **kw).rstrip())
    return env


def variables(env):
    cfg = yaml.safe_load((ROOT/'inventory/production/group_vars/all/main.yml').read_text())
    nodes = yaml.safe_load((ROOT/'inventory/production/hosts.yml').read_text())['all']['children']['postgresql_cluster']['hosts']
    cfg.update(nodes['pg-node-01'])
    cfg.update(inventory_hostname='pg-node-01', groups={'postgresql_cluster':list(nodes)}, hostvars=nodes,
               ansible_facts={'default_ipv4':{'interface':'eth0'}}, vault_ansible_become_password='dummy',
               vault_postgres_superuser_password='dummy',vault_postgres_replication_password='dummy',
               vault_postgres_rewind_password='dummy',vault_patroni_rest_password='dummy',
               vault_keepalived_auth_password='dummy123',vault_pgbackrest_repository_password='d'*40,
               item={'kind':'full','calendar':'Sun *-*-* 02:00:00 UTC'})
    def resolve(value):
        if isinstance(value, dict): return {k:resolve(v) for k,v in value.items()}
        if isinstance(value, list): return [resolve(v) for v in value]
        if isinstance(value, str) and '{{' in value:
            if re.fullmatch(r'\s*{{(?:(?!{{).)*}}\s*',value, re.S):
                return env.compile_expression(value.strip()[2:-2])(**cfg)
            return env.from_string(value).render(**cfg)
        return value
    for _ in range(3): cfg=resolve(cfg)
    return cfg


@unittest.skipIf(jinja2 is None, 'Jinja2/Ansible are unavailable locally; CI installs them')
class Templates(unittest.TestCase):
    def test_every_template_renders(self):
        env=environment();cfg=variables(env)
        for p in (ROOT/'roles').rglob('*.j2'):
            with self.subTest(template=str(p.relative_to(ROOT))):
                rendered=env.from_string(p.read_text()).render(**cfg)
                self.assertNotIn('{{',rendered)
                if p.name=='patroni.yml.j2':
                    obj=yaml.safe_load(rendered)
                    self.assertIsInstance(obj['bootstrap']['dcs']['synchronous_mode'],bool)
                    self.assertEqual(obj['postgresql']['authentication']['replication']['sslmode'],'prefer')

    def test_passwords_survive_exactly(self):
        env=environment();cfg=variables(env)
        template=env.from_string((ROOT/'roles/patroni/templates/patroni.yml.j2').read_text())
        for secret in ['#secret: with spaces','12345678901234567890','true','a"b\\c\nd','é ! @ {} []']:
            for name in ['vault_patroni_rest_password','vault_postgres_superuser_password',
                         'vault_postgres_replication_password','vault_postgres_rewind_password']:
                cfg[name]=secret
            obj=yaml.safe_load(template.render(**cfg))
            self.assertEqual(obj['restapi']['authentication']['password'],secret)
            for name in ['superuser','replication','rewind']:
                self.assertEqual(obj['postgresql']['authentication'][name]['password'],secret)

    def test_tls_templates_switch_all_control_and_data_plane_endpoints(self):
        env = environment()
        cfg = variables(env)
        cfg.update(
            patroni_rest_tls_enabled=True,
            patroni_rest_scheme='https',
            patroni_rest_tls_verify_client='optional',
            patroni_rest_tls_cert_file='/etc/patroni/tls/server.crt',
            patroni_rest_tls_key_file='/etc/patroni/tls/server.key',
            patroni_rest_tls_ca_file='/etc/patroni/tls/ca.crt',
            etcd_tls_enabled=True,
            etcd_client_scheme='https',
            etcd_tls_ca_file='/etc/etcd/tls/ca.crt',
            etcd_tls_server_cert_file='/etc/etcd/tls/server.crt',
            etcd_tls_server_key_file='/etc/etcd/tls/server.key',
            etcd_tls_peer_cert_file='/etc/etcd/tls/peer.crt',
            etcd_tls_peer_key_file='/etc/etcd/tls/peer.key',
            etcd_tls_client_cert_file='/etc/etcd/tls/client.crt',
            etcd_tls_client_key_file='/etc/etcd/tls/client.key',
            postgresql_tls_activation_enabled=True,
            haproxy_patroni_tls_ca_file='/etc/haproxy/tls/patroni-ca.crt',
        )
        patroni = yaml.safe_load(env.from_string(
            (ROOT / 'roles/patroni/templates/patroni.yml.j2').read_text()
        ).render(**cfg))
        self.assertEqual(patroni['restapi']['certfile'], '/etc/patroni/tls/server.crt')
        self.assertEqual(patroni['restapi']['verify_client'], 'optional')
        self.assertTrue(all(str(x).endswith(f":{cfg['etcd_client_port']}") for x in patroni['etcd3']['hosts']))
        self.assertEqual(patroni['etcd3']['protocol'], 'https')
        self.assertEqual(patroni['postgresql']['parameters']['ssl'], 'on')

        etcd = env.from_string((ROOT / 'roles/etcd/templates/etcd.j2').read_text()).render(**cfg)
        self.assertIn('ETCD_LISTEN_CLIENT_URLS="https://', etcd)
        self.assertIn('ETCD_CLIENT_CERT_AUTH="true"', etcd)
        self.assertIn('ETCD_PEER_CLIENT_CERT_AUTH="true"', etcd)

        haproxy = env.from_string((ROOT / 'roles/haproxy/templates/haproxy.cfg.j2').read_text()).render(**cfg)
        self.assertIn('http-check connect ssl verify required', haproxy)


@unittest.skipUnless(jinja2 and os.environ.get('POSTGRES_TEST_DSN') and shutil.which('psql'),
                     'Requires an isolated PostgreSQL 16 test DSN, psql, and Jinja2')
class AccessIntegration(unittest.TestCase):
    def run_sql(self, sql, check=True):
        result=subprocess.run(['psql',os.environ['POSTGRES_TEST_DSN'],'-X','-v','ON_ERROR_STOP=1','-At'],
                              input=sql,capture_output=True,text=True)
        if check and result.returncode:
            self.fail(result.stderr)
        return result

    def test_readwrite_downgrade_and_inherited_rights(self):
        suffix=uuid.uuid4().hex[:12]
        db='qa_ha_'+suffix;owner='qa_owner_'+suffix;reader='qa_reader_'+suffix;writer='qa_writer_'+suffix
        env=environment();template=env.from_string((ROOT/'roles/postgresql_access/templates/managed-access.sql.j2').read_text())
        cfg=dict(postgresql_managed_roles=[dict(name=owner),dict(name=reader,login=True,password='#a: b',password_version='v1')],
                 postgresql_managed_databases=[dict(name=db,owner=owner)],postgresql_managed_memberships=[],
                 postgresql_managed_access_profiles=[dict(database=db,schema='public',owner=owner,role=reader,level='readwrite')])
        try:
            self.run_sql(template.render(**cfg))
            self.run_sql(f'\\connect {db}\nSET ROLE {owner}; CREATE TABLE public.test (id serial PRIMARY KEY); RESET ROLE;')
            self.run_sql(f'\\connect {db}\nSET ROLE {reader}; INSERT INTO public.test DEFAULT VALUES;')
            cfg['postgresql_managed_access_profiles'][0]['level']='readonly'
            self.run_sql(template.render(**cfg))
            failed=self.run_sql(f'\\connect {db}\nSET ROLE {reader}; INSERT INTO public.test DEFAULT VALUES;',False)
            self.assertNotEqual(failed.returncode,0)
            self.run_sql(f'\\connect {db}\nSET ROLE {reader}; SELECT * FROM public.test;')
            self.run_sql(f'\\connect {db}\nSET ROLE {owner}; CREATE TABLE public.future (id serial); RESET ROLE;')
            failed=self.run_sql(f'\\connect {db}\nSET ROLE {reader}; INSERT INTO public.future DEFAULT VALUES;',False)
            self.assertNotEqual(failed.returncode,0)
            self.run_sql(f'CREATE ROLE {writer}; GRANT {writer} TO {reader};\n\\connect {db}\nGRANT INSERT ON public.test TO {writer};')
            failed=self.run_sql(template.render(**cfg),False)
            self.assertNotEqual(failed.returncode,0)
            self.assertIn('still inherits',failed.stderr)
        finally:
            self.run_sql(f'DROP DATABASE IF EXISTS {db}; DROP ROLE IF EXISTS {reader}; DROP ROLE IF EXISTS {writer}; DROP ROLE IF EXISTS {owner};',False)
