# راهنمای فارسی TLS در کلاستر PostgreSQL

در این پروژه سه سطح مستقل TLS وجود دارد:

1. PostgreSQL برای مسیر داده و اتصال برنامه؛
2. Patroni REST برای health check و API مدیریتی؛
3. etcd برای client و peer با mTLS.

هیچ‌کدام به‌صورت پیش‌فرض فعال نیستند. تعریف مسیر فایل به‌تنهایی سرویس را TLS
نمی‌کند و کلید یا گواهی هم توسط Ansible تولید نمی‌شود.

## پیش‌نیاز گواهی

برای هر نود، گواهی سرور را از CA سازمانی بگیرید. SAN باید تمام نام‌ها و IPهایی
را که واقعاً برای اتصال استفاده می‌شوند پوشش دهد. برای etcd علاوه بر گواهی
server، گواهی peer و یک گواهی client نیز لازم است. فایل CA باید زنجیره‌ی مورد
اعتماد را شامل شود.

منابع فایل‌ها را در متغیرهای inventory قرار دهید؛ کلید خصوصی را در Git عادی
قرار ندهید و از secret/file delivery تأییدشده استفاده کنید.

## ترتیب امن استقرار جدید

برای کلاستر تازه:

```yaml
patroni_rest_tls_enabled: true
patroni_rest_tls_cert_source: "files/tls/{{ inventory_hostname }}-patroni.crt"
patroni_rest_tls_key_source: "files/tls/{{ inventory_hostname }}-patroni.key"
patroni_rest_tls_ca_source: "files/tls/root-ca.crt"

etcd_tls_enabled: true
etcd_tls_ca_source: "files/tls/root-ca.crt"
etcd_tls_server_cert_source: "files/tls/{{ inventory_hostname }}-etcd-server.crt"
etcd_tls_server_key_source: "files/tls/{{ inventory_hostname }}-etcd-server.key"
etcd_tls_peer_cert_source: "files/tls/{{ inventory_hostname }}-etcd-peer.crt"
etcd_tls_peer_key_source: "files/tls/{{ inventory_hostname }}-etcd-peer.key"
etcd_tls_client_cert_source: "files/tls/{{ inventory_hostname }}-etcd-client.crt"
etcd_tls_client_key_source: "files/tls/{{ inventory_hostname }}-etcd-client.key"
```

سپس:

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/preflight.yml --ask-vault-pass -K
ansible-playbook -i inventory/production/hosts.yml \
  site.yml --ask-vault-pass -K
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-ha-monitoring.yml --ask-vault-pass -K
```

role قبل از پیکربندی سرویس‌ها PEM، تطابق certificate/key، زنجیره، زمان انقضا و
SANهای اعلام‌شده را بررسی می‌کند. تمام سه نود باید در اجرای تغییر حضور داشته
باشند؛ از `--limit` استفاده نکنید.

## فعال‌سازی PostgreSQL

ابتدا فایل‌های PostgreSQL را deploy کنید:

```yaml
postgresql_tls_certificate_deployment_enabled: true
```

بعد از بررسی خروجی، تنظیمات سرور را فعال کنید:

```yaml
postgresql_tls_activation_enabled: true
postgresql_tls_min_protocol_version: "TLSv1.2"
```

و playbook فعال‌سازی را اجرا کنید. پس از اثبات اتصال رمزنگاری‌شده، در مرحله‌ی
بعدی `postgresql_tls_internal_sslmode` را به `verify-full` ببرید و در پایان
`postgresql_tls_require_ssl: true` را با `harden-pg-hba.yml` اعمال کنید. ترتیب
را برعکس نکنید؛ قبل از `hostssl` باید replication، rewind و مسیر VIP آزمایش شده
باشند.

## کلاستر موجود etcd

تغییر HTTP به HTTPS روی یک quorum فعال به‌صورت عضو‌به‌عضو امن نیست. role این
حالت را متوقف می‌کند. برای مهاجرت کلاستر موجود، از
`playbooks/migrate-etcd-tls.yml` در یک maintenance window استفاده کنید؛ این
playbook snapshot
قابل‌بازگردانی و طرح هماهنگ برای هر سه etcd و Patroni نیاز است. تنها پس از
تأیید quorum، متغیر زیر را برای همان اجرای کنترل‌شده فعال کنید:

```yaml
etcd_tls_existing_cluster_migration_ack: true
```

پس از اعتبارسنجی، marker زیر روی همه‌ی نودها ثبت می‌شود:

```text
/etc/etcd/tls/.migration-complete
```

## بررسی سریع

```bash
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/validate.yml --ask-vault-pass -K
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/audit-postgresql-tls.yml --ask-vault-pass -K
```

اگر TLS روشن است، endpointهای Patroni با HTTPS و etcd با HTTPS/mTLS بررسی
می‌شوند. برای Prometheus نیز CA و، برای etcd، گواهی client را در
`monitoring/prometheus-scrape.example.yml` تنظیم کنید.
