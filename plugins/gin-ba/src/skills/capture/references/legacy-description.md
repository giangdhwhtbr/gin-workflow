# Legacy description

The shape of a `description.md` with `Kind: legacy`. The header and the sections `## Summary`, `## Changes`, and `## Files` come from the `iteration.md` template; the three sections after them describe the feature as it works today.

## Rules

- Describe what the screenshots and the named code show, never what the feature should do.
- A value the evidence does not settle is `?`, with a matching item under `## Open questions`.
- Type is one of `text`, `number`, `money`, `date`, `datetime`, `boolean`, `choice (<values>)`, `file`, `link`, or `table`.
- Required is `yes`, `no`, or `?`.
- Rule states a check or a behaviour seen on the screen or in the code, with its source when it comes from code (`src/orders/validate.py:42`).
- One `### <Screen>` per screen, in the order a user meets them.

## Example

```markdown
# orders: 2026-05-11

<!-- template comment kept as written -->

Kind: legacy
Source: screenshots from the operations team
Previous: none
Confirmed: no

## Summary

Staff create and search sales orders. An order has a customer, one or more lines, and a status that moves from draft to submitted.

## Changes

none (as-is)

## Files

- `legacy/order-list.png`: Order list
- `legacy/order-form.png`: New order

## As-is behaviour

### Order list

Screenshot: `legacy/order-list.png`. Purpose: find an order and open it.

| Field | Type | Required | Rule |
|---|---|---|---|
| Order number | text | no | search matches the start of the number |
| Status | choice (draft, submitted, cancelled) | no | filter; default shows all |
| Created | date | no | sorted newest first |

Actions: New order (opens New order), open a row (opens the order), Export (`?`: format unknown).

### New order

Screenshot: `legacy/order-form.png`. Purpose: create a draft order.

| Field | Type | Required | Rule |
|---|---|---|---|
| Customer | choice (customer list) | yes | only active customers are listed |
| Delivery date | date | yes | not before today (`src/orders/validate.py:42`) |
| Lines | table | yes | at least one line; quantity is a whole number above 0 |
| Note | text | no | ? |

Actions: Save draft, Submit, Cancel.

## Rules

- A submitted order can no longer be edited (Order list, New order).
- The order number is assigned on save (`src/orders/service.py:88`).

## Open questions

- What format does Export produce, and which columns does it include?
- Is the Note field limited in length?
```
