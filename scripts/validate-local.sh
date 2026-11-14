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

printf '\n== Unit and optional integration tests ==\n'
python -m unittest discover -s tests -v

printf '\n== All Ansible entry points: syntax ==\n'
ansible-playbook site.yml playbooks/*.yml --syntax-check

printf '\n== Git whitespace checks ==\n'
git diff --check
git diff --cached --check

printf '\nLocal validation complete. No deployment or disk operation was performed.\n'
