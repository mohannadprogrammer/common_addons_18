import logging

from odoo import _, api, fields, models
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    stock_landed_cost_valuation_id = fields.Many2one(
        "stock.landed.cost",
        string="Landed Cost Valuation",
        readonly=True,
        copy=False,
        help="Landed cost that generated this valuation entry.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # ORM override
    # ─────────────────────────────────────────────────────────────────────────

    def action_post(self):
        # Ensure invoice_date is always set before posting; required by Odoo 19
        # for tax computation and period locking.
        for move in self:
            if move.is_invoice(include_receipts=True) and not move.invoice_date:
                move.invoice_date = fields.Date.context_today(self)

        res = super().action_post()

        # Guard against re-entrant calls: _post_clearing_entry calls
        # action_post() on the entries it creates.  Those entries have
        # move_type="entry" so the type filter below already prevents
        # recursion, but the context flag makes the intent explicit and
        # protects against future changes.
        if self.env.context.get("_stock_valuation_posting"):
            return res

        for move in self.filtered(
            lambda m: m.state == "posted" and m.company_id.custom_stock_valuation_enabled
        ):
            if move.move_type in ("in_invoice", "in_refund"):
                # Purchase: Vendor Bill → clear GR/IR
                move._apply_grir_clearing()
            elif move.move_type in ("out_invoice", "out_refund"):
                # Sale: Customer Invoice → recognise COGS
                move._apply_cogs_recognition()

        return res

    # ─────────────────────────────────────────────────────────────────────────
    # Purchase: GR/IR clearing  (MIRO equivalent)
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_grir_clearing(self):
        """
        Purchase – Vendor Bill Validation
        ===================================
        The standard Odoo vendor bill posts:
            DR  Purchase/Expense account (line.account_id)
            CR  Accounts Payable

        On purchase *receipt* we already posted:
            DR  Stock Valuation
            CR  Stock Input / GR-IR  (liability cleared here)

        This method posts the clearing bridge:
            DR  Stock Input / GR-IR  ← wipes the liability from receipt
            CR  Purchase/Expense account ← offsets the debit from the bill

        Net result across all three entries:
            DR  Stock Valuation       (receipt)
            CR  Accounts Payable      (bill — remains open until payment)

        For a vendor credit note (in_refund) every direction reverses:
            DR  Purchase/Expense account
            CR  Stock Input / GR-IR
        """
        self.ensure_one()
        rounding = self.company_id.currency_id.rounding
        is_refund = self.move_type == "in_refund"

        for line in self.invoice_line_ids.filtered(
            lambda l: l.product_id and l.product_id.type in ("consu", "product")
        ):
            product = line.product_id
            company = self.company_id

            acc_grir = (
                product.categ_id.property_stock_input_account_id
                or company.property_stock_input_account_id
            )
            if not acc_grir:
                _logger.warning(
                    "GR/IR clearing skipped for product '%s' on bill '%s': "
                    "no Stock Input / GR-IR account configured.",
                    product.display_name,
                    self.name,
                )
                continue

            # line.price_subtotal is always positive; use it for the entry
            # amount so we stay currency-agnostic.  line.balance carries sign
            # from Odoo's journal perspective and is unreliable here.
            amount = line.price_subtotal
            if float_is_zero(amount, precision_rounding=rounding):
                continue

            ref = f"GRIR/CLR/{self.name}/L{line.id}"
            if self.env["account.move"].search(
                [("ref", "=", ref), ("company_id", "=", company.id)], limit=1
            ):
                continue

            if is_refund:
                # Vendor credit note: reverse the clearing
                # DR Purchase/Expense account  /  CR GR-IR
                debit_acc = line.account_id
                credit_acc = acc_grir
            else:
                # Normal vendor bill:
                # DR GR-IR (clears the liability from receipt)
                # CR Purchase/Expense account (offsets bill debit)
                debit_acc = acc_grir
                credit_acc = line.account_id

            self._post_clearing_entry(
                debit_acc=debit_acc,
                credit_acc=credit_acc,
                amount=amount,
                ref=ref,
                label=_("GR/IR clearing: %s") % product.display_name,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Sale: COGS recognition  (upon invoice validation)
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_cogs_recognition(self):
        """
        Sale – Customer Invoice Validation
        ====================================
        DR  Cost of Goods Sold   (expense)
        CR  Stock Output         (clearing asset)
        Timing: Upon Invoice Validation

        COGS is valued at standard cost (product.standard_price × invoiced qty).
        This clears the Stock Output clearing account that was debited on
        delivery and recognises the expense in the P&L.

        For credit notes (out_refund) the entry reverses:
        DR  Stock Output  /  CR  Cost of Goods Sold
        """
        self.ensure_one()
        rounding = self.company_id.currency_id.rounding
        is_refund = self.move_type == "out_refund"

        for line in self.invoice_line_ids.filtered(
            lambda l: l.product_id and l.product_id.type in ("consu", "product")
        ):
            product = line.product_id
            categ = product.categ_id
            company = self.company_id

            acc_output = (
                categ.property_stock_output_account_id
                or company.property_stock_output_account_id
            )
            acc_cogs = (
                categ.property_account_expense_categ_id
                or company.property_account_expense_categ_id
            )

            if not acc_output or not acc_cogs:
                _logger.warning(
                    "COGS recognition skipped for product '%s' on invoice '%s': "
                    "Stock Output or COGS account not configured.",
                    product.display_name,
                    self.name,
                )
                continue

            # Use invoiced quantity × standard cost.
            # line.quantity is always positive; direction is controlled by
            # the debit/credit swap below for refunds.
            cost = line.quantity * product.standard_price
            if float_is_zero(cost, precision_rounding=rounding):
                continue

            ref = f"COGS/{self.name}/L{line.id}"
            if self.env["account.move"].search(
                [("ref", "=", ref), ("company_id", "=", company.id)], limit=1
            ):
                continue

            if is_refund:
                # Credit note: reverse COGS — DR Stock Output / CR COGS
                debit_acc, credit_acc = acc_output, acc_cogs
            else:
                # Normal invoice: DR COGS / CR Stock Output
                debit_acc, credit_acc = acc_cogs, acc_output
            abs_cost = cost  # always positive after the branch above

            self._post_clearing_entry(
                debit_acc=debit_acc,
                credit_acc=credit_acc,
                amount=abs_cost,
                ref=ref,
                label=_("COGS: %s") % product.display_name,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Shared entry builder
    # ─────────────────────────────────────────────────────────────────────────

    def _post_clearing_entry(self, debit_acc, credit_acc, amount, ref, label=""):
        """
        Create and immediately post a balanced two-line journal entry.

        Journal selection priority:
          1. Stock journal (code='STJ') — keeps stock clearing entries separate
             from purchase/sale journals.
          2. Any other general journal for the company.
          3. The parent invoice's own journal (last resort).
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
            journal = self.journal_id  # last resort: use invoice's own journal

        if not journal:
            _logger.error(
                "Cannot post clearing entry '%s': no suitable journal found.", ref
            )
            return

        move_vals = {
            "journal_id": journal.id,
            "ref": ref,
            "date": self.date or fields.Date.context_today(self),
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

        entry = self.env["account.move"].with_context(
            _stock_valuation_posting=True
        ).create(move_vals)
        entry.with_context(_stock_valuation_posting=True).action_post()
        return entry
