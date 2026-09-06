#!/usr/bin/env python3
"""Own only inet/pg_ha_guard. Never flush another firewall's ruleset."""
import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys

TABLE = 'pg_ha_guard'
CONF = Path('/etc/pg-ha-network.nft')
STATE = Path('/run/pg-ha-network-rollback.json')
UNIT = 'pg-ha-network-rollback'


def networks(values):
    result = []
    for value in values:
        net = ipaddress.ip_network(value, strict=True)
        if net.version != 4 or net.prefixlen == 0:
            raise ValueError('Only explicit IPv4 CIDRs narrower than /0 are supported')
        result.append(str(net))
    return [str(n) for n in ipaddress.collapse_addresses(ipaddress.ip_network(v) for v in result)]


def policy(data):
    nodes = [str(ipaddress.IPv4Address(v)) for v in data['nodes']]
    if len(set(nodes)) != 3:
        raise ValueError('Exactly three unique cluster IPv4 addresses are required')
    admin = networks(data['admin'])
    applications = networks(data['applications'])
    monitoring = networks(data['monitoring'])
    source = ipaddress.ip_address(data['ssh_source'])
    if not admin or not any(source in ipaddress.ip_network(n) for n in admin):
        raise ValueError('Observed SSH source must be included in reviewed admin CIDRs')
    vip = str(ipaddress.IPv4Address(data['vip']))
    ports = {k: int(v) for k, v in data['ports'].items()}
    if any(v < 1 or v > 65535 for v in ports.values()):
        raise ValueError('Invalid service port')
    internal_ports = [v for k,v in ports.items() if k != 'vip']
    if len(set(internal_ports)) != len(internal_ports):
        raise ValueError('Managed service ports must be distinct')
    def values(items):
        return '{ ' + ', '.join(dict.fromkeys(items)) + ' }'
    lines = [f'add table inet {TABLE}', f'flush table inet {TABLE}',
             f'table inet {TABLE} {{', ' chain input {',
             '  type filter hook input priority 10; policy accept;',
             '  iifname "lo" accept',
             f'  ip saddr {values(admin)} tcp dport {ports["ssh"]} accept',
             f'  ip saddr {values(nodes)} tcp dport {values([str(ports[k]) for k in ["postgres", "vip", "patroni", "etcd_client", "etcd_peer"]])} accept',
             f'  ip saddr {values(nodes)} ip protocol vrrp accept']
    if applications:
        lines.append(f'  ip saddr {values(applications)} ip daddr {vip} tcp dport {ports["vip"]} accept')
    # Prometheus also needs local/node-sourced HTTP probes. etcd API shares
    # its metrics port, so ONLY actual DB nodes get 2379 by default.
    metric_sources = networks(monitoring + [n + '/32' for n in nodes])
    lines.append(f'  ip saddr {values(metric_sources)} tcp dport {values([str(ports[k]) for k in ["patroni", "haproxy_metrics", "postgres_metrics"]])} accept')
    if data.get('allow_etcd_metrics_to_monitoring', False) and monitoring:
        lines.append(f'  ip saddr {values(monitoring)} tcp dport {ports["etcd_client"]} accept')
    lines += [f'  tcp dport {values(sorted(set(str(v) for v in ports.values()), key=int))} drop',
              '  ip protocol vrrp drop', '  meta l4proto 112 drop', ' }', '}', '']
    return '\n'.join(lines)


def command(argv, data=None, check=True):
    return subprocess.run(argv, input=data, text=True, capture_output=True, check=check)


def atomic(path, content):
    tmp = path.with_name(path.name + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def rollback():
    if not STATE.exists():
        return
    old = json.loads(STATE.read_text())
    command(['nft', '-f', '-'], old['rules'])
    if old['config'] is None:
        CONF.unlink(missing_ok=True)
    else:
        atomic(CONF, old['config'])
    STATE.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['render', 'apply', 'commit', 'rollback'])
    args = parser.parse_args()
    if args.operation == 'render':
        print(policy(json.load(sys.stdin)), end='')
        return
    with open('/run/pg-ha-network.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.operation == 'rollback':
            rollback()
            return
        if args.operation == 'commit':
            command(['systemctl', 'stop', UNIT + '.timer'], check=False)
            # A fired rollback job may already be queued; cancel it as well.
            command(['systemctl', 'stop', UNIT + '.service'], check=False)
            if not STATE.exists():
                raise RuntimeError('Rollback already ran; policy was not committed')
            STATE.unlink()
            print('committed')
            return
        if STATE.exists():
            raise RuntimeError('Another firewall change is awaiting commit or rollback')
        new = policy(json.load(sys.stdin))
        command(['nft', '-c', '-f', '-'], new)
        snapshot = command(['nft', 'list', 'table', 'inet', TABLE], check=False)
        if snapshot.returncode and 'No such file' not in snapshot.stderr:
            raise RuntimeError('Unable to read current managed firewall table')
        if snapshot.returncode == 0 and not CONF.exists():
            raise RuntimeError('Refusing to adopt a pre-existing pg_ha_guard table without managed persistence')
        old_rules = (f'add table inet {TABLE}\nflush table inet {TABLE}\n' + snapshot.stdout
                     if snapshot.returncode == 0 else f'add table inet {TABLE}\ndelete table inet {TABLE}\n')
        atomic(STATE, json.dumps({'rules': old_rules, 'config': CONF.read_text() if CONF.exists() else None}))
        try:
            command(['systemd-run', '--quiet', '--collect', '--unit=' + UNIT,
                     '--on-active=120s', '/usr/local/sbin/pg-ha-network', 'rollback'])
            command(['nft', '-f', '-'], new)
            atomic(CONF, new)
        except Exception:
            rollback()
            command(['systemctl', 'stop', UNIT + '.timer'], check=False)
            raise
        print('applied; automatic rollback pending for 120 seconds')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Network policy failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
