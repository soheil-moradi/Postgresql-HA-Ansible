#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"
INV="inventory/production/hosts.yml"

echo "== 1/3: duplicate YAML keys =="
python3 scripts/project-self-check.py .

echo
echo "== 2/3: syntax-check all playbooks =="
while IFS= read -r pb; do
  printf '%-65s' "$pb"
  ansible-playbook -i "$INV" "$pb" --syntax-check >/dev/null
  echo " OK"
done < <(find playbooks -maxdepth 1 -type f -name '*.yml' | sort)

echo
echo "== 3/3: all safe production audits + HA validation =="
ansible-playbook \
  -i "$INV" \
  playbooks/finalize-production-readiness.yml \
  --ask-vault-pass \
  -K
