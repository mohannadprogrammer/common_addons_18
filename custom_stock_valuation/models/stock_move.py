import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)

# Keys used in the accounts dict returned by _get_valuation_accounts()
_ACC_STOCK = "stock"
_ACC_INPUT = "input"
_ACC_OUTPUT = "output"
_ACC_COGS = "cogs"
_ACC_PRODUCTION = "production"
_ACC_INV_LOSS = "inv_loss"


class StockMove(models.Model):
    _inherit = "stock.move"

    # ── Stored link to the generated valuation journal entry ──────────────────
    valuation_move_id = fields.Many2one(
        "account.move",
        string="Valuation Journal Entry",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_valuation_accounts(self):
        """
        Return a dict of account.account records for the current move.

        Category accounts take precedence over company defaults.
        """
        self.ensure_one()
        categ = self.product_id.categ_id
        company = self.company_id

        def _pick(field):
            return getattr(categ, field, False) or getattr(company, field, False)

        return {
            _ACC_STOCK: _pick("property_stock_valuation_account_id"),
            _ACC_INPUT: _pick("property_stock_input_account_id"),
            _ACC_OUTPUT: _pick("property_stock_output_account_id"),
            _ACC_COGS: _pick("property_account_expense_categ_id"),
            _ACC_PRODUCTION: _pick("property_production_account_id"),
            _ACC_INV_LOSS: _pick("property_inventory_loss_account_id"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            # Carry the PO unit price onto the move for accurate valuation.
            if move.purchase_line_id and float_is_zero(
                move.price_unit, precision_rounding=move.company_id.currency_id.rounding
            ):
                move.price_unit = move.purchase_line_id.price_unit
        return moves

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        done_moves = self.filtered(
            lambda m: (
                m.state == "done"
                and not m.valuation_move_id
                and m.company_id.custom_stock_valuation_enabled
            )
        )
        if done_moves:
            done_moves._generate_valuation_entries()
        return res

    # ─────────────────────────────────────────────────────────────────────────
    # Valuation entry dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_valuation_entries(self):
        """
        Dispatch to the correct accounting template based on move type.

        Supported operations
        --------------------
        incoming        → Purchase receipt       (DR Stock Valuation / CR Stock Input)
        outgoing        → Sale delivery          (DR Stock Output / CR Stock Valuation)
        mrp_operation   → MFG raw-material cons. (DR Production / CR Stock Valuation)
        MFG finished    → MFG finished goods     (DR Stock Valuation / CR Production)
        inventory/scrap → Inventory adjustment   (DR Inv Loss / CR Stock Valuation or reversed)

        Only storable products (``type == 'consu'`` in Odoo 19) generate
        valuation entries.  Services and non-tracked consumables are skipped.
        """
        for move in self:
            # ── Guard: only storable products carry stock value ───────────────
            # In Odoo 19 'consu' = storable (was 'product' in Odoo 16 and below).
            # 'service' and legacy 'consu' (consumable) carry no stock value.
            if not move.product_id or move.product_id.type not in ("consu", "product"):
                continue

            ptype = move.picking_type_id.code if move.picking_type_id else False

            try:
                # ── Return-picking detection ─────────────────────────────────
                # origin_returned_move_id is set on moves that reverse a
                # previous delivery / receipt (sale return, purchase return).
                if move.origin_returned_move_id:
                    orig_code = move.origin_returned_move_id.picking_type_id.code
                    if orig_code == "outgoing":
                        move._post_sale_return()
                    elif orig_code == "incoming":
                        move._post_purchase_return()
                    continue

                if ptype == "incoming":
                    move._post_purchase_receipt()

                elif ptype == "outgoing":
                    move._post_sale_delivery()

                elif ptype == "mrp_operation":
                    move._post_mrp_consumption()

                elif move.scrapped or ptype == "inventory":
                    move._post_inventory_adjustment()

                elif move.production_id and not move.raw_material_production_id:
                    move._post_mrp_finished_goods()

                # Internal transfers (ptype == 'internal') intentionally produce
                # no entry here — value stays within Stock Valuation.
                # Override _post_internal_transfer() if inter-location pricing
                # or inter-company valuation is required.

            except UserError:
                raise
            except Exception as exc:
                _logger.exception(
                    "Error generating valuation entry for stock.move(id=%s, ref=%s): %s",
                    move.id,
                    move.reference or move.name,
                    exc,
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Per-operation entry builders
    # ─────────────────────────────────────────────────────────────────────────

    def _post_purchase_receipt(self):
        """
        Purchase – Receiving Goods
        DR  Stock Valuation  (asset)
        CR  Stock Input/GRNI (clearing liability)
        Timing: Upon Receipt
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_INPUT],
            "Purchase Receipt",
        )

        amount = self._get_purchase_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_STOCK],
            credit_acc=accounts[_ACC_INPUT],
            amount=amount,
            ref=self._valuation_ref("GR"),
            label=_("Stock receipt: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_sale_return(self):
        """
        Sale – Return from Customer
        DR  Stock Valuation  (asset)
        CR  Stock Output     (clearing asset)
        Timing: Upon Return Receipt

        Reverses the original sale delivery entry.
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_OUTPUT],
            "Sale Return",
        )

        amount = self._get_standard_cost_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_STOCK],
            credit_acc=accounts[_ACC_OUTPUT],
            amount=amount,
            ref=self._valuation_ref("RET"),
            label=_("Sale return: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_purchase_return(self):
        """
        Purchase – Return to Vendor
        DR  Stock Input / GRNI  (clearing liability)
        CR  Stock Valuation     (asset)
        Timing: Upon Return Shipment

        Reverses the original purchase receipt entry.
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_INPUT],
            "Purchase Return",
        )

        amount = self._get_purchase_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_INPUT],
            credit_acc=accounts[_ACC_STOCK],
            amount=amount,
            ref=self._valuation_ref("PRET"),
            label=_("Purchase return: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_sale_delivery(self):
        """
        Sale – Shipping Goods
        DR  Stock Output (clearing) 
        CR  Stock Valuation (asset)
        Timing: Upon Delivery
        Note: COGS entry is created upon invoice validation (see account_move.py).
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_OUTPUT],
            "Sale Delivery",
        )

        amount = self._get_standard_cost_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_OUTPUT],
            credit_acc=accounts[_ACC_STOCK],
            amount=amount,
            ref=self._valuation_ref("DO"),
            label=_("Stock shipment: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_mrp_consumption(self):
        """
        Manufacturing – Raw Material Consumption
        DR  Production Account  (WIP asset)
        CR  Stock Valuation     (asset)
        Timing: Upon Consumption
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_PRODUCTION],
            "Manufacturing Consumption",
        )

        amount = self._get_standard_cost_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_PRODUCTION],
            credit_acc=accounts[_ACC_STOCK],
            amount=amount,
            ref=self._valuation_ref("MFG-IN"),
            label=_("MFG consumption: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_mrp_finished_goods(self):
        """
        Manufacturing – Finished Goods Receipt
        DR  Stock Valuation    (asset)
        CR  Production Account (WIP asset)
        Timing: Upon Marking Done
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_PRODUCTION],
            "Manufacturing Finished Goods",
        )

        amount = self._get_standard_cost_amount()
        if float_is_zero(amount, precision_rounding=self.company_id.currency_id.rounding):
            return

        entry = self._create_valuation_entry(
            debit_acc=accounts[_ACC_STOCK],
            credit_acc=accounts[_ACC_PRODUCTION],
            amount=amount,
            ref=self._valuation_ref("MFG-OUT"),
            label=_("MFG finished goods: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    def _post_inventory_adjustment(self):
        """
        Inventory Loss / Shrinkage
        DR  Inventory Loss  (expense)
        CR  Stock Valuation (asset)
        Timing: Upon Adjustment

        Scrap moves are always losses (product leaves the company).

        For positive inventory-count adjustments (cycle count found more stock):
        DR  Stock Valuation (asset)
        CR  Inventory Loss  (expense)  ← treated as a gain/reversal
        """
        self.ensure_one()
        accounts = self._get_valuation_accounts()
        self._require_accounts(
            accounts,
            [_ACC_STOCK, _ACC_INV_LOSS],
            "Inventory Adjustment",
        )

        rounding = self.company_id.currency_id.rounding

        if self.scrapped:
            # Scrap: always a loss regardless of quantity sign.
            # qty is positive (units scrapped) and product leaves stock.
            qty = self.quantity
            is_loss = True
        else:
            # Inventory adjustment: quantity is the *net change*
            # negative → shrinkage (loss), positive → surplus (gain)
            qty = self.quantity
            is_loss = qty < 0

        amount = abs(qty) * self.product_id.standard_price
        if float_is_zero(amount, precision_rounding=rounding):
            return

        if is_loss:
            # DR Inventory Loss / CR Stock Valuation
            debit_acc = accounts[_ACC_INV_LOSS]
            credit_acc = accounts[_ACC_STOCK]
        else:
            # DR Stock Valuation / CR Inventory Loss  (gain)
            debit_acc = accounts[_ACC_STOCK]
            credit_acc = accounts[_ACC_INV_LOSS]

        prefix = "SCRAP" if self.scrapped else "INV-ADJ"
        entry = self._create_valuation_entry(
            debit_acc=debit_acc,
            credit_acc=credit_acc,
            amount=amount,
            ref=self._valuation_ref(prefix),
            label=_("Inventory adjustment: %s") % self.product_id.display_name,
        )
        self.valuation_move_id = entry

    # ─────────────────────────────────────────────────────────────────────────
    # Amount computation helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_purchase_amount(self):
        """
        Return the valuation amount in company currency for a purchase receipt.

        Price priority:
          1. move.price_unit  (already set in create() from PO line)
          2. purchase_line_id.price_unit
          3. product.standard_price  (fallback for non-PO receipts)

        Currency conversion is always applied when the PO currency differs
        from the company currency, using the exchange rate on the move date.
        """
        self.ensure_one()
        comp_currency = self.company_id.currency_id
        date = self.date or fields.Date.context_today(self)

        # Determine unit price and its currency
        if self.purchase_line_id:
            po_line = self.purchase_line_id
            price = self.price_unit or po_line.price_unit
            src_currency = po_line.currency_id or comp_currency
        else:
            price = self.price_unit or self.product_id.standard_price
            src_currency = comp_currency

        total = price * self.quantity

        # Convert to company currency when needed
        if src_currency and src_currency != comp_currency:
            total = src_currency._convert(
                total, comp_currency, self.company_id, date
            )
        return total

    def _get_standard_cost_amount(self):
        """Return |qty| × standard_price in company currency."""
        self.ensure_one()
        return abs(self.quantity) * self.product_id.standard_price

    # ─────────────────────────────────────────────────────────────────────────
    # Journal entry creation
    # ─────────────────────────────────────────────────────────────────────────

    def _get_valuation_journal(self):
        """
        Return the stock valuation journal.

        Prefers a journal named/code 'STJ' (standard Odoo stock journal),
        then any general journal for the company.
        """
        self.ensure_one()
        journal = self.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("code", "=", "STJ"),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not journal:
            journal = self.env["account.journal"].search(
                [
                    ("type", "=", "general"),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        if not journal:
            raise UserError(
                _("No general journal found for company %s. "
                  "Please create a journal of type 'Miscellaneous'.")
                % self.company_id.name
            )
        return journal

    def _valuation_ref(self, prefix):
        """
        Build a unique, human-readable reference for the journal entry.

        Format: ``<PREFIX>/<picking_or_move_name>/<move_id>``

        The move id suffix guarantees uniqueness when a single picking contains
        multiple product lines that each generate their own valuation entry.
        """
        self.ensure_one()
        base = self.picking_id.name if self.picking_id else (self.name or "MV")
        return f"{prefix}/{base}/{self.id}"

    def _create_valuation_entry(self, debit_acc, credit_acc, amount, ref, label=""):
        """
        Create and post a balanced two-line journal entry.

        Idempotency guards (in order):
          1. ``valuation_move_id`` already set on this move → return it.
          2. An ``account.move`` with matching ref + company_id already posted →
             return it (protects against concurrent duplicate calls).
        """
        self.ensure_one()

        # Guard: do not double-post
        if self.valuation_move_id:
            return self.valuation_move_id

        existing = self.env["account.move"].search(
            [
                ("ref", "=", ref),
                ("company_id", "=", self.company_id.id),
                ("state", "=", "posted"),
            ],
            limit=1,
        )
        if existing:
            return existing

        journal = self._get_valuation_journal()
        move_date = self.date or fields.Date.context_today(self)

        move_vals = {
            "journal_id": journal.id,
            "ref": ref,
            "date": move_date,
            "move_type": "entry",
            "company_id": self.company_id.id,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "account_id": debit_acc.id,
                        "debit": amount,
                        "credit": 0.0,
                        "name": label,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "account_id": credit_acc.id,
                        "debit": 0.0,
                        "credit": amount,
                        "name": label,
                    },
                ),
            ],
        }

        account_move = self.env["account.move"].create(move_vals)
        account_move.action_post()
        return account_move

    # ─────────────────────────────────────────────────────────────────────────
    # Validation helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _require_accounts(self, accounts, keys, operation_name):
        """
        Raise a UserError if any of the requested account keys are missing.
        """
        self.ensure_one()
        missing = [k for k in keys if not accounts.get(k)]
        if missing:
            raise UserError(
                _(
                    "%(op)s: the following accounts are not configured for "
                    "product '%(product)s' (category: %(categ)s).\n"
                    "Missing: %(missing)s\n\n"
                    "Please configure them in the product category or in "
                    "Accounting > Settings > Automated Stock Valuation."
                )
                % {
                    "op": operation_name,
                    "product": self.product_id.display_name,
                    "categ": self.product_id.categ_id.complete_name,
                    "missing": ", ".join(missing),
                }
            )
