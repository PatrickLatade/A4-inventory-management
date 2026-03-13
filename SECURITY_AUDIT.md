## Security Audit

Audit date: 2026-03-13

Scope:

- Route protection and role enforcement
- CSRF and session handling
- SQL injection posture
- Input validation and client-side rendering risks
- Internet deployment blockers visible from the repo

### Findings

1. Medium: client-side DOM XSS risk still exists, but the highest-risk hotspots were reduced.
   - Status:
     - A shared `escapeHtml()` helper now exists in [templates/base.html](/c:/Dev/a4_inventory_system/templates/base.html#L839).
     - High-risk dynamic HTML paths in the sale, debt, and admin screens were partially sanitized:
       - [templates/transactions/out.html](/c:/Dev/a4_inventory_system/templates/transactions/out.html)
       - [templates/transactions/utang.html](/c:/Dev/a4_inventory_system/templates/transactions/utang.html)
       - [templates/users/users.html](/c:/Dev/a4_inventory_system/templates/users/users.html)
   - Remaining representative references:
     - [templates/transactions/out.html](/c:/Dev/a4_inventory_system/templates/transactions/out.html#L1371)
     - [templates/index.html](/c:/Dev/a4_inventory_system/templates/index.html#L463)
     - [templates/cash/cash_ledger.html](/c:/Dev/a4_inventory_system/templates/cash/cash_ledger.html#L1087)
     - [templates/users/users.html](/c:/Dev/a4_inventory_system/templates/users/users.html#L1988)
     - [templates/cash/cash_ledger.html](/c:/Dev/a4_inventory_system/templates/cash/cash_ledger.html#L1087)
   - Why it matters:
     - If an attacker can get HTML/JS-like content stored in names, notes, reference numbers, service names, item names, or customer fields, any remaining unsafe `innerHTML` path can execute it in another user’s browser.
     - Jinja autoescaping protects server-rendered HTML templates, but it does not protect JavaScript string templates assigned to `innerHTML`.
   - Recommended fix:
     - Continue replacing `innerHTML` usage with DOM node creation plus `textContent` where data is untrusted.
     - Where HTML templating in JS remains necessary, ensure every interpolated value passes through `escapeHtml()`.

2. Medium: authorization is improved, but staff-access policy is still broad and not yet explicitly reviewed as a business rule.
   - Representative references:
     - [ACCESS_CONTROL.md](/c:/Dev/a4_inventory_system/ACCESS_CONTROL.md)
     - [app.py](/c:/Dev/a4_inventory_system/app.py#L81)
   - Why it matters:
     - Current protection is mostly `logged-in` versus `admin-only`.
     - Staff can still reach a wide set of export/report/debt/customer endpoints. That may be correct, but it is a business-risk decision, not just a code decision.
   - Recommended fix:
     - Review the current staff-access surface route by route and shrink it where needed, especially exports, audit views, and financial pages.

3. Medium: report date inputs are not strongly validated before use.
   - Representative references:
     - [routes/reports_route.py](/c:/Dev/a4_inventory_system/routes/reports_route.py#L66)
     - [routes/reports_route.py](/c:/Dev/a4_inventory_system/routes/reports_route.py#L76)
     - [routes/reports_route.py](/c:/Dev/a4_inventory_system/routes/reports_route.py#L87)
   - Why it matters:
     - These routes accept date strings and pass them deeper into services without strict format validation.
     - This is not an obvious SQL injection issue because parameters are still bound, but it increases error-handling and abuse surface.
   - Recommended fix:
     - Validate all date query params as strict `YYYY-MM-DD` before processing.

4. Medium: login throttling is process-local only.
   - Representative references:
     - [auth/utils.py](/c:/Dev/a4_inventory_system/auth/utils.py#L11)
   - Why it matters:
     - It works on one process, but resets on restart and does not coordinate across multiple instances.
   - Recommended fix:
     - Move throttling to Redis or the database before multi-instance deployment.

5. Low: production serving entrypoints now exist, but deployment is still not complete.
   - Representative references:
     - [wsgi.py](/c:/Dev/a4_inventory_system/wsgi.py)
     - [run_waitress.py](/c:/Dev/a4_inventory_system/run_waitress.py)
     - [app.py](/c:/Dev/a4_inventory_system/app.py#L480)
   - Why it matters:
     - The repo now has a production-style entrypoint, but the default dev entrypoint still exists and deployment still requires reverse proxy, HTTPS, secrets, and operational setup.
   - Recommended fix:
     - Use `run_waitress.py` or `wsgi.py` for hosting and keep `python app.py` for local development only.
     - Complete the deployment items in [DEPLOYMENT_CHECKLIST.md](/c:/Dev/a4_inventory_system/DEPLOYMENT_CHECKLIST.md).

### What is already in better shape

- Non-public routes require login.
- Admin routes in the auth/admin surface are blocked from staff.
- CSRF protection is enabled through `Flask-WTF`.
- Session secret is environment-backed.
- Login now rotates session state and applies basic throttling.
- SQL queries are mostly parameterized.
- A production-oriented WSGI/Waitress startup path now exists.
- Several high-risk DOM XSS hotspots were sanitized with `escapeHtml()`.

### Recommended next security work

1. Finish the remaining `innerHTML` / DOM XSS cleanup.
2. Add strict validation helpers for date, numeric, and enum inputs.
3. Review staff-access policy on financial/export endpoints.
4. Move rate limiting to shared storage if deployment will use multiple processes or servers.
5. Add centralized audit logging for failed logins and privileged actions.
