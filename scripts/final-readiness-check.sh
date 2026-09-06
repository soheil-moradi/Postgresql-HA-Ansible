#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${1:-.}"
if (( $# > 0 )); then shift; fi
cd "$PROJECT_DIR"
INV="inventory/production/hosts.yml"
ANSIBLE_FLAGS=("$@")
# A configured vault password file avoids interactive prompts. Otherwise the
# caller can pass --ask-vault-pass and -K explicitly.
python3 scripts/project-self-check.py .
python3 -m unittest discover -s tests -v
mapfile -t PLAYBOOKS < <(find playbooks -maxdepth 1 -type f -name '*.yml' | sort)
ansible-playbook -i "$INV" site.yml "${PLAYBOOKS[@]}" --syntax-check "${ANSIBLE_FLAGS[@]}"
ansible-playbook -i "$INV" playbooks/finalize-production-readiness.yml "${ANSIBLE_FLAGS[@]}"
