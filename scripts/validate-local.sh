#!/usr/bin/env bash
# CI-aligned local checks. Run as a process, never source this script.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

for cmd in ansible-playbook python git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'Missing dependency: %s (activate the project venv first)\n' "$cmd" >&2
    exit 2
  fi
done

printf '\n== Inventory preflight (controller only) ==\n'
ansible-playbook -i inventory/examples/topology-3-vm.yml playbooks/inventory-preflight.yml

# Parse every playbook before running tests that invoke ansible-playbook.
# This surfaces invalid roles/playbooks instead of an opaque controller-gate failure.
printf '\n== All Ansible entry points: syntax ==\n'
# The public inventory uses postgresql_nodes; legacy playbooks still expect
# postgresql_cluster. The second, syntax-only inventory aliases the groups
# without containing any company IP addresses or connecting to a host.
ansible-playbook \
  -i inventory/examples/topology-3-vm.yml \
  -i inventory/examples/syntax-legacy-alias.ini \
  site.yml playbooks/*.yml --syntax-check

printf '\n== Unit and optional integration tests ==\n'
python -m unittest discover -s tests -v

printf '\n== Git whitespace checks ==\n'
git diff --check
git diff --cached --check

printf '\nLocal validation complete. No deployment or disk operation was performed.\n'
