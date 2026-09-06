# فهرست مستندات فارسی

راهنمای اصلی استقرار و عملیات در [راهنمای جامع فارسی](راهنمای-جامع-استقرار-و-عملیات.md)
قرار دارد. نام متغیرها، playbookها و فایل‌های فنی عمداً انگلیسی است تا مستقیماً
در repository قابل استفاده باشد.

## شروع سریع

- [راهنمای جامع استقرار و عملیات](راهنمای-جامع-استقرار-و-عملیات.md)
- [راهنمای TLS](راهنمای-tls.md)
- [ساخت کاربر و دیتابیس](راهنمای-ساخت-کاربر-و-دیتابیس.md)
- [معماری](architecture.md)
- [استقرار](deployment-guide.md)
- [پیش‌نیازها و preflight](preflight.md)
- [اعتبارسنجی](validation.md)
- [مرجع تنظیمات](configuration-reference.md)

## عملیات و بازیابی

- [راهنمای عملیات](operations-guide.md)
- [Failover و Switchover](failover-and-switchover.md)
- [پایش](monitoring.md)
- [ثبت رخداد](logging.md)
- [پشتیبان و بازیابی](backup-and-restore.md)
- [بازسازی نود](node-rebuild.md)
- [افزایش دیسک](disk-expansion.md)
- [عیب‌یابی](troubleshooting.md)

## امنیت

- [سخت‌سازی امنیتی](security-hardening.md)
- [سخت‌سازی شبکه](network-hardening.md)
- [مدیریت دسترسی PostgreSQL](postgresql-access-management.md)
- [فعال‌سازی TLS PostgreSQL](postgresql-tls-activation.md)
- [پورت‌ها و endpointها](ports-and-endpoints.md)
- [مدیریت secretها](secrets-management.md)

## پروژه و تغییرات

- [تصمیم‌های معماری](DECISIONS.md)
- [مراحل بعدی](NEXT_PHASES.md)
- [آمادگی production](production-readiness.md)
- [کامل بودن پروژه](project-completeness.md)
- [مدیریت patch](patch-management.md)

برای checklist نهایی، ابتدا preflight، سپس validation و در پایان auditهای backup،
شبکه، TLS و monitoring را اجرا کنید.
