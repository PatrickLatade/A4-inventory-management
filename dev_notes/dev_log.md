# Dev Log / Architecture Notes

## Architecture

Search is now handled by `inventory_service`

Index route only loads top 50 rows

Search route in `app.py` below index route

### Service Structure

transaction_services
- handles transactional operations like adding new items

inventory_services
- search and inventory QOL features

routes_api.py
- API routes
- dashboard logic

transaction_route.py
- handles IN and OUT database saving

reports_services
- reusable reporting functions

reports_routes
- reporting endpoints

utils
- date formatting utilities

## UI

base.html is the central design template

## Database

Database migrated from SQLite → PostgreSQL

## Vendor Centralization

Implemented 2026-03-15

Vendor data now lives in a dedicated vendors table.

Current behavior
- Items store `vendor_id` as the default / usual vendor.
- Purchase orders store `vendor_id` plus frozen vendor snapshot fields for reporting and analytics.
- Vendor add/select flow is shared across `items.html` and `order.html`.
- New vendors can be created inline from the item and PO forms.

Validation / UX
- Item creation now requires vendor selection in both frontend and backend.
- PO creation now requires vendor selection in both frontend and backend.
- Missing-item add flow from loyalty, Stock IN, and PO now pre-fills the item name in `items.html`.

Audit / Admin
- Audit trail item detail modal now resolves vendor name from `vendor_id` via the vendor master table.

## Debt Feature

Relevant files
- debt_service
- debt_route
- utang.html

## Query Example for PO History

SELECT change_reason, quantity, transaction_date, user_name, notes
FROM inventory_transactions
WHERE reference_id = ?
AND reference_type = 'PURCHASE_ORDER'
AND transaction_type = 'IN'
ORDER BY transaction_date ASC
