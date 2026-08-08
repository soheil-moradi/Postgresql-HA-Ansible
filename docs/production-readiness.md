# ✅ Production Readiness

![Readiness](https://img.shields.io/badge/readiness-audit_available-success)

## One-command safe audit

```bash
./scripts/final-readiness-check.sh .
```

The script performs:

```text
1. duplicate-key check for critical YAML variables
2. syntax-check of all playbooks
3. safe production audits
4. final PostgreSQL HA validation
```

## Included safe audits

```text
audit-os-hardening.yml
audit-network-hardening.yml
audit-postgresql-tls.yml
audit-postgresql-ha-monitoring.yml
audit-backup-readiness.yml
audit-postgresql-logging.yml
audit-patch-readiness.yml
validate.yml
```

## Capabilities that require environment decisions

A repository-level pass does not mean these should be blindly enabled:

```text
firewall enforcement
PostgreSQL TLS / hostssl / verify-full
real application database/users
custom AppArmor enforcement
WAL archive destination
central log shipping
automated package changes
```

## Production gate checklist

### Platform

- [ ] three independent failure domains where practical
- [ ] stable DNS and NTP
- [ ] supported internal package repositories
- [ ] capacity headroom verified by host monitoring

### Database/HA

- [ ] `validate.yml` passes
- [ ] planned switchover tested
- [ ] hard Primary failure tested
- [ ] application retry behavior measured

### Security

- [ ] no `trust` HBA rules
- [ ] application roles follow least privilege
- [ ] real admin/application/monitoring CIDRs reviewed
- [ ] TLS decision documented
- [ ] secrets remain encrypted

### Monitoring

- [ ] all four DB/HA metric endpoints scraped
- [ ] alert rules verified against live metric names
- [ ] alert routing tested
- [ ] host metrics covered by external monitoring

### Recovery

- [ ] durable off-host backup destination selected
- [ ] continuous WAL archive verified
- [ ] retention configured
- [ ] restore/PITR test completed
- [ ] recovery time and recovery point recorded

### Operations

- [ ] rolling patch procedure tested
- [ ] node rebuild runbook understood
- [ ] logging/retention integrated
- [ ] on-call/operators know the VIP/service endpoint

## Before first Git commit

- remove local patch/backup artifacts;
- confirm no Vault plaintext/private keys exist;
- keep example values generic;
- review `git diff` and `git status`;
- run the final readiness script again.
