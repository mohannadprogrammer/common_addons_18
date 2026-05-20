# Automated Stock Valuation Engine — Odoo 19

Automated perpetual inventory accounting for Odoo 19 Community Edition.
Generates all stock valuation journal entries automatically, replacing the
entries that are normally only available in the Enterprise edition.

---

## Video Demo

[Watch the demo on YouTube](https://youtu.be/4ArDmOCn3rc)

---

## Installation

1. Copy the `custom_stock_valuation` directory into your Odoo `addons` path.
2. Update the app list and install the module from the Apps menu.
3. The post-install hook automatically seeds the 6 required accounts with default codes.
4. Verify accounts in *Accounting → Settings → Automated Stock Valuation*.

## Configuration

> **Important:** Set your product category's **Costing Method** to **Periodic**
> (not Perpetual/Automated) to prevent the standard Odoo engine from
> interfering with this module's journal entries. The module handles all
> valuation posting itself.

1. Go to **Accounting → Settings → Automated Stock Valuation**
2. Enable the master toggle (enabled by default)
3. Select company-wide default accounts (pre-seeded by the install hook)
4. Go to **Inventory → Configuration → Product Categories**
5. Select a category and set **Costing Method → Periodic**
6. Optionally override accounts per category under the *Inventory Valuation Accounts* group
7. Repeat for each product category that uses stock valuation

---

## Accounting Flows

| Operation | DR | CR | Trigger |
|---|---|---|---|
| **Purchase Receipt** | Stock Valuation | Stock Input / GR-IR | `stock.move` done (incoming) |
| **Vendor Bill** | Stock Input / GR-IR | *(AP via standard bill)* | `account.move` posted (in_invoice) |
| **Sale Delivery** | Stock Output | Stock Valuation | `stock.move` done (outgoing) |
| **Customer Invoice** | *(AR via standard invoice)* | *(Sales Income via standard)* | Standard Odoo |
| **COGS Recognition** | Cost of Goods Sold | Stock Output | `account.move` posted (out_invoice) |
| **MFG — Raw Material** | Production / WIP | Stock Valuation | `stock.move` done (mrp_operation) |
| **MFG — Finished Goods** | Stock Valuation | Production / WIP | `stock.move` done (production_id set) |
| **Inventory Adjustment (loss)** | Inventory Loss | Stock Valuation | `stock.move` done (inventory/scrap) |
| **Inventory Adjustment (gain)** | Stock Valuation | Inventory Loss | `stock.move` done (inventory) |
| **Landed Costs** | Stock Valuation | LC Clearing | `stock.landed.cost` validated |

---

## Account Configuration

Accounts can be configured at two levels (category takes precedence):

1. **Company-wide defaults** — `Accounting > Settings > Automated Stock Valuation`
2. **Per product category** — `Inventory > Configuration > Product Categories`

### Required Accounts

| Field | Type | Purpose |
|---|---|---|
| Stock Valuation Account | Asset (Current) | Real-time stock value |
| Stock Input / GR-IR | Liability (Current) | Goods received, not yet invoiced |
| Stock Output (Interim) | Asset (Current) | Goods shipped, COGS not yet recognised |
| Cost of Goods Sold | Expense | P&L expense on sale |
| Production / WIP Account | Asset (Current) | Work-in-progress during manufacturing |
| Inventory Loss Account | Expense | Shrinkage and count adjustments |

The post-install hook (`setup_accounts`) seeds these accounts automatically
with the default codes below.  Adjust codes in `hooks.py` to match your CoA.

| Account | Default Code |
|---|---|
| Stock Valuation | 151000 |
| Stock Input (GRNI) | 251000 |
| Stock Output (Interim) | 152000 |
| Cost of Goods Sold | 600000 |
| Production / WIP | 153000 |
| Inventory Loss | 620000 |

---

## File Structure

```
custom_stock_valuation/
├── __manifest__.py
├── __init__.py
├── hooks.py                          # post_init_hook: seeds accounts
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py        # res.company fields + Settings bridge
│   ├── product_category.py           # Per-category account overrides
│   ├── stock_move.py                 # Receipt / delivery / MFG / adjustment entries
│   ├── account_move.py               # GR/IR clearing + COGS on invoice post
│   └── stock_landed_cost.py          # Landed cost capitalisation entry
├── views/
│   ├── res_config_settings_views.xml
│   └── product_category_views.xml
└── security/
    └── ir.model.access.csv
```

---

## Idempotency & Duplicate Protection

Every generated journal entry is identified by a structured `ref`:

| Operation | Ref Pattern |
|---|---|
| Purchase Receipt | `GR/<picking_name>` |
| Sale Delivery | `DO/<picking_name>` |
| MFG Consumption | `MFG-IN/<picking_name>` |
| MFG Finished Goods | `MFG-OUT/<picking_name>` |
| Inventory Adjustment | `INV-ADJ/<picking_name>` |
| GR/IR Clearing | `GRIR/CLR/<bill_name>/L<line_id>` |
| COGS | `COGS/<invoice_name>/L<line_id>` |
| Landed Cost | `LC/<lc_name>/L<line_id>` |

Before creating any entry the code checks:
1. `stock.move.valuation_move_id` is already set (fastest path)
2. An `account.move` with the same `ref` + `company_id` already exists

---

## Dependencies

- `stock`
- `account`
- `purchase`
- `sale_management`
- `mrp`
- `stock_landed_costs`

---

## Odoo 19 Compatibility Notes

- `account.account.company_ids` is a Many2many (not `company_id`).
  All account lookups and creations use `company_ids`.
- `stock.move.quantity` replaces `quantity_done`.
- `product.template.type == 'consu'` means **storable** in Odoo 19
  (was `'product'` in Odoo 16 and earlier).
- `post_init_hook` receives `env` directly (not `cr, registry`).
- `odoo.fields.Command` is used for M2M writes.
