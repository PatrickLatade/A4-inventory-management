## Access Control Audit

Current model as of 2026-03-13.

Status:

- Re-checked after auth hardening, CSRF enablement, and the loyalty admin route tightening.
- No route-classification changes were needed in this pass beyond what is already listed below.

- Public routes:
  - `auth.login`
  - `static`

- Authenticated routes for `staff` and `admin`:
  - `/`
  - `/api/search`
  - `/analytics`
  - `/dead-stock`
  - `/low-stock`
  - `/export/transactions`
  - `/import/items`
  - `/import/sales`
  - `/import/inventory`
  - `/transaction/out`
  - `/transaction/in`
  - `/transaction/items`
  - `/items/add`
  - `/inventory/in`
  - `/transaction/out/save`
  - `/transaction/order`
  - `/transaction/order/save`
  - `/transaction/orders/list`
  - `/api/order/<po_id>`
  - `/api/order/<po_id>/update`
  - `/api/order/<po_id>/cancel`
  - `/export/purchase-order/<po_id>/csv`
  - `/transaction/receive/<po_id>`
  - `/transaction/receive/confirm`
  - `/purchase-order/details/<po_id>`
  - `/reports/purchase-order/<po_id>`
  - `/reports/daily`
  - `/reports/range`
  - `/reports/sales-summary`
  - `/export/inventory-snapshot`
  - `/export/items-sold-today`
  - `/export/services-sold-today`
  - `/api/search/customers`
  - `/api/search/services`
  - `/api/customers/add`
  - `/api/customers/<customer_id>/vehicles`
  - `/api/customers/<customer_id>/vehicles/add`
  - `/customers`
  - `/api/customers/<customer_id>/transactions`
  - `/utang`
  - `/api/debt/<sale_id>`
  - `/api/debt/<sale_id>/pay`
  - `/api/debt/audit`
  - `/api/debt/summary`
  - `/api/debt/payments/<sale_id>`
  - `/debt/statement/<sale_id>`
  - `/api/loyalty/eligibility/<customer_id>`
  - `/api/loyalty/redeem`
  - `/api/loyalty/customer/<customer_id>/summary`
  - `/api/approvals/<approval_request_id>`
  - `/api/approvals/<approval_request_id>/cancel`
  - `/api/approvals/<approval_request_id>/resubmit`
  - `/cash-ledger`
  - `/api/cash/summary`
  - `/api/cash/entries`
  - `/api/cash/ledger`
  - `/api/cash/add`
  - `/logout`

- Admin-only routes:
  - `/dashboard`
  - `/dashboard/stock-movement`
  - `/dashboard/item-movement`
  - `/dashboard/top-items`
  - `/index2`
  - `/debug-integrity`
  - `/users`
  - `/users/toggle/<user_id>`
  - `/mechanics/add`
  - `/mechanics/toggle/<mechanic_id>`
  - `/sales/details/<reference_id>`
  - `/services/add`
  - `/services/toggle/<service_id>`
  - `/payment-methods/add`
  - `/payment-methods/toggle/<pm_id>`
  - `/api/audit/trail`
  - `/api/admin/sales`
  - `/api/item/<item_id>`
  - `/api/loyalty/programs`
  - `/api/loyalty/programs/<program_id>/toggle`
  - `/api/admin/approvals`
  - `/api/admin/approvals/<approval_request_id>`
  - `/api/admin/approvals/<approval_request_id>/approve`
  - `/api/admin/approvals/<approval_request_id>/revisions`
  - `/api/admin/approvals/<approval_request_id>/cancel`
  - `/api/order/<po_id>/approval/approve`
  - `/api/order/<po_id>/approval/revisions`
  - `/api/cash/delete/<entry_id>`

Notes:

- Global authentication is enforced in `app.py` for every non-public route.
- The entire `auth` blueprint is admin-only except `/login` and `/logout`.
- `Flask-WTF` CSRF protection applies to all unsafe methods globally.
- Purchase orders now use PO-specific JSON approval endpoints so PO status and approval status stay synchronized.
