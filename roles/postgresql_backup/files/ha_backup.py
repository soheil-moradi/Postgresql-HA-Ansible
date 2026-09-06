#!/usr/bin/env python3
"""Fail closed if the shared off-host repository is unavailable."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


def verify_repository(config):
    mount = Path(config['mount'])
    destination = Path(config['destination'])
    if not mount.is_absolute() or not destination.is_absolute() or destination == mount:
        raise ValueError('Repository must be a directory inside an absolute mountpoint')
    if not destination.resolve().is_relative_to(mount.resolve()):
        raise ValueError('Repository resolves outside its configured mount')
    pgdata = config.get('pgdata')
    if pgdata and (destination.resolve().is_relative_to(Path(pgdata).resolve()) or Path(pgdata).resolve().is_relative_to(destination.resolve())):
        raise ValueError('Backup repository and PostgreSQL data directory must not contain each other')
    result = subprocess.run(['findmnt', '--json', '--mountpoint', str(mount), '-o',
                             'TARGET,SOURCE,FSTYPE,OPTIONS'], check=True, capture_output=True, text=True)
    entries = json.loads(result.stdout).get('filesystems', [])
    if len(entries) != 1:
        raise ValueError('Expected one exact off-host mountpoint')
    fs = entries[0]
    if fs['fstype'] not in ('nfs', 'nfs4') or fs['source'] != config['source']:
        raise ValueError('Repository mount type or source differs from reviewed off-host NFS repository')
    if any(v in fs['options'].split(',') for v in ['soft', 'softerr', 'softreval']):
        raise ValueError('A durable repository requires a hard NFS mount')
    if 'rw' not in fs['options'].split(','):
        raise ValueError('Repository is not mounted read/write')
    if not destination.is_dir() or not os.access(destination, os.R_OK | os.W_OK | os.X_OK):
        raise ValueError('Repository is not readable/writable by the backup user')


def primary(config):
    result = subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-h', '/var/run/postgresql',
                             '-p', str(config['port']), '-d', 'postgres', '-Atc',
                             'SELECT NOT pg_is_in_recovery();'], check=True, capture_output=True,
                            text=True, timeout=15)
    return result.stdout.strip() == 't'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['verify', 'full', 'diff', 'check', 'archive-push'])
    parser.add_argument('wal', nargs='?')
    args = parser.parse_args()
    config = json.loads(Path('/etc/pgbackrest/ha-repository.json').read_text())
    verify_repository(config)
    if args.action == 'verify':
        print('off-host repository verified')
        return
    cmd = ['/usr/bin/pgbackrest', '--stanza=' + config['stanza']]
    if args.action == 'archive-push':
        if not args.wal:
            raise ValueError('WAL path is required')
        subprocess.run(cmd + ['archive-push', args.wal], check=True)
        return
    if not primary(config):
        print('standby: scheduled backup/check skipped')
        return
    with open('/var/lib/pgbackrest/ha-backup.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if args.action == 'check':
                raise RuntimeError('Another backup is active; repeat readiness check afterward')
            print('another local backup is already running')
            return
        subprocess.run(cmd + ['check'], check=True)
        if args.action in ('full', 'diff'):
            subprocess.run(cmd + ['--type=' + args.action, 'backup'], check=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print('Backup operation failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
