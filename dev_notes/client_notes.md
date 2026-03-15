# Client Notes

## Vendor Data

Centralized vendor structure implemented on 2026-03-15

Current source of truth:
- vendors table

Linked usage:
- items.vendor_id for default / usual vendor
- purchase_orders.vendor_id for actual PO vendor

PO snapshot fields for analytics stability:
- vendor_name
- vendor_address
- vendor_contact_person
- vendor_contact_no
- vendor_email

vendor fields:
- vendor_name
- address
- contact_person
- contact_no
- email

UI workflow implemented:
- item creation uses vendor search / select / add modal
- purchase order creation uses vendor search / select / add modal
- missing vendor can be created inline from the modal

## Sales Rules

Cash on hand only tracks sales marked as **Cash Payment**

## Branch System

branch_id is already present in the system

Will be used when additional branches open

## Security Deployment Variables

FLASK_SECRET_KEY
SESSION_COOKIE_SECURE=1
SESSION_LIFETIME_HOURS
MAX_CONTENT_LENGTH_MB

## Login Throttling

Currently in-memory

Limitations:
- resets on restart
- not shared across multiple workers

Future upgrade: move to Redis or DB
