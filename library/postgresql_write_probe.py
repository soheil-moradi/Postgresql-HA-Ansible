#!/usr/bin/python
"""Commit an isolated marker via VIP, verify replicas, and remove only our schema."""
from contextlib import contextmanager
import time
import uuid


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec=dict(
        vip=dict(type='str', required=True), port=dict(type='int', default=5432),
        node_port=dict(type='int', default=5432), replicas=dict(type='list', elements='str', required=True),
        username=dict(type='str', required=True), password=dict(type='str', required=True, no_log=True),
        timeout=dict(type='int', default=30), sslmode=dict(type='str', default='prefer'),
    ), supports_check_mode=True)
    if module.check_mode:
        module.exit_json(changed=False, skipped=True, msg='Write probe is not executed in check mode')
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        module.fail_json(msg='python3-psycopg2 is required on the probe host')
    p = module.params
    token = uuid.uuid4().hex
    schema = 'ansible_ha_probe_' + token
    marker = 'ansible-ha-probe:' + token
    @contextmanager
    def connect(host, port):
        conn = psycopg2.connect(host=host, port=port, user=p['username'], password=p['password'],
                                dbname='postgres', connect_timeout=5, sslmode=p['sslmode'],
                                options='-c statement_timeout=15000 -c lock_timeout=5000')
        try:
            with conn:
                yield conn
        finally:
            conn.close()
    cleanup_error = False
    failure = None
    try:
        with connect(p['vip'], p['port']) as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
                cur.execute(sql.SQL('COMMENT ON SCHEMA {} IS %s').format(sql.Identifier(schema)), (marker,))
                cur.execute(sql.SQL('CREATE TABLE {}.marker (token text PRIMARY KEY)').format(sql.Identifier(schema)))
                cur.execute(sql.SQL('INSERT INTO {}.marker VALUES (%s)').format(sql.Identifier(schema)), (token,))
        # Exiting the connection context commits. Probe real committed data, not a temp table.
        for host in p['replicas']:
            deadline = time.monotonic() + p['timeout']
            verified = False
            while time.monotonic() < deadline:
                try:
                    with connect(host, p['node_port']) as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql.SQL('SELECT token FROM {}.marker').format(sql.Identifier(schema)))
                            verified = cur.fetchone() == (token,)
                    if verified:
                        break
                except psycopg2.Error:
                    pass
                time.sleep(1)
            if not verified:
                raise RuntimeError('Committed VIP marker was not observed on all replica endpoints')
    except (psycopg2.Error, RuntimeError):
        failure = 'Committed write or replica visibility check failed; inspect cluster health and replication lag.'
    finally:
        try:
            with connect(p['vip'], p['port']) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname=%s", (schema,))
                    row = cur.fetchone()
                    if row is not None:
                        if row != (marker,):
                            raise RuntimeError('Probe schema ownership marker mismatch')
                        cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        except (psycopg2.Error, RuntimeError):
            cleanup_error = True
    if failure or cleanup_error:
        module.fail_json(msg=failure or 'Write test passed but cleanup failed.',
                         cleanup_failed=cleanup_error, probe_schema=schema)
    module.exit_json(changed=True, committed_write=True, replica_count=len(p['replicas']), cleaned_up=True)


if __name__ == '__main__':
    main()
