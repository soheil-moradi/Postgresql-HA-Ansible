#!/usr/bin/python
"""Converge only the owned subset of Patroni DCS via its REST API.

Pure comparison/HTTP helpers are importable without Ansible for offline tests.
"""
import base64
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def subset_matches(actual, desired):
    if isinstance(desired, dict):
        return isinstance(actual, dict) and all(
            key in actual and subset_matches(actual[key], value)
            for key, value in desired.items()
        )
    return actual == desired and (isinstance(actual, bool) == isinstance(desired, bool))


def request_config(url, user, password, method='GET', desired=None, timeout=15, ca_file=None):
    if not url.startswith(('http://', 'https://')):
        raise ValueError('Patroni URL must use HTTP or HTTPS')
    auth = base64.b64encode((user + ':' + password).encode()).decode()
    data = None if desired is None else json.dumps(desired).encode()
    req = Request(url.rstrip('/') + '/config', data=data, method=method,
                  headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'})
    context = ssl.create_default_context(cafile=ca_file)
    with urlopen(req, timeout=timeout, context=context) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError('Patroni returned a non-object configuration')
    return result


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec=dict(
        url=dict(type='str', required=True), username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        desired=dict(type='dict', required=True), timeout=dict(type='int', default=15),
        ca_file=dict(type='path', default=None),
    ), supports_check_mode=True)
    p = module.params
    def call(method='GET', data=None):
        return request_config(p['url'], p['username'], p['password'], method, data,
                              p['timeout'], p['ca_file'])
    try:
        current = call()
        changed = not subset_matches(current, p['desired'])
        if changed and not module.check_mode:
            call('PATCH', p['desired'])
            if not subset_matches(call(), p['desired']):
                module.fail_json(msg='DCS readback differs from desired subset; investigate concurrent configuration changes.')
        module.exit_json(changed=changed, managed_keys=sorted(p['desired']),
                         msg='Desired subset converged; PostgreSQL restart, if needed, remains a separate rolling operation.')
    except HTTPError as exc:
        module.fail_json(msg='Patroni config API returned HTTP %s; no successful convergence was verified.' % exc.code)
    except (URLError, ValueError, OSError):
        module.fail_json(msg='Patroni config API request or readback failed; verify endpoint, authentication and DCS health.')


if __name__ == '__main__':
    main()
