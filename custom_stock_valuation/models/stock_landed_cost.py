import logging

from odoo import _, fields, models
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class StockLandedCost(models.Model):
    """
    Landed Costs – Validation
    DR  Stock Valuation          (asset)
    CR  Landed Cost Clearing     (expense or clearing liability)
    Timing: Upon Landed Cost Validation

    The vendor bill for the freight / insurance / etc. posts:
        DR  Landed Cost Clearing  /  CR  Accounts Payable

    This entry moves the cost from the clearing account into
    the stock valuation asset, correctly capitalising the landed cost.
    """

    _inherit = "stock.landed.cost"

    valuation_move_ids = fields.One2many(
        "account.move",
        "stock_landed_cost_valuation_id",
        string="Valuation Entries",
        readonly=True,
        copy=False,
        help="Journal entries generated on landed cost validation.",
    )

    def button_validate(self):
        res = super().button_validate()
        for lc in self.filtered(
            lambda l: l.state == "done" and l.company_id.custom_stock_valuation_enabled
        ):
            lc._post_landed_cost_valuation()
        return res

    def _post_landed_cost_valuation(self):
        """
        For each cost line, post:
            DR  Stock Valuation          (capitalise the landed cost)
            CR  Landed Cost Clearing     (the expense/clearing account on the
                                          cost product, typically linked to
                                          the vendor bill for the freight charge)

        Account resolution for the clearing side:
          1. cost_line.account_id  (explicitly set on the LC line)
          2. cost product's expense account  (product.property_account_expense_id)
          3. Company Stock Input / GR-IR     (module default fallback)
        """
        self.ensure_one()
        company = self.company_id
        rounding = company.currency_id.rounding

        journal = self.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("code", "=", "STJ"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        ) or self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)],
            limit=1,
        )

        if not journal:
            _logger.error(
                "Cannot post landed cost valuation for '%s': no general journal.",
                self.name,
            )
            return

        for cost_line in self.cost_lines:
            product = cost_line.product_id
            if not product:
                continue

            # Clearing account: where the freight/insurance cost sits before
            # being capitalised into stock.
            acc_clearing = (
                cost_line.account_id
                or product.property_account_expense_id
                or product.categ_id.property_stock_input_account_id
                or company.property_stock_input_account_id
            )
            acc_stock = (
                product.categ_id.property_stock_valuation_account_id
                or company.property_stock_valuation_account_id
            )

            if not acc_clearing or not acc_stock:
                _logger.warning(
                    "Landed cost valuation skipped for '%s' on LC '%s': "
                    "missing Stock Valuation or clearing account.",
                    product.display_name,
                    self.name,
                )
                continue

            # price_unit on a landed cost line is the TOTAL amount for that
            # cost type (not a per-unit price), so it is the correct entry amount.
            amount = cost_line.price_unit
            if float_is_zero(amount, precision_rounding=rounding):
                continue

            ref = f"LC/{self.name}/L{cost_line.id}"
            if self.env["account.move"].search(
                [("ref", "=", ref), ("company_id", "=", company.id)], limit=1
            ):
                continue

            move_vals = {
                "journal_id": journal.id,
                "ref": ref,
                "date": self.date or fields.Date.context_today(self),
                "move_type": "entry",
                "company_id": company.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": acc_stock.id,
                            "debit": amount,
                            "credit": 0.0,
                            "name": _("Landed cost: %s") % product.display_name,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": acc_clearing.id,
                            "debit": 0.0,
                            "credit": amount,
                            "name": _("Landed cost clearing: %s") % product.display_name,
                        },
                    ),
                ],
            }

            entry = self.env["account.move"].with_context(
                _stock_valuation_posting=True
            ).create(move_vals)
            entry.with_context(_stock_valuation_posting=True).action_post()
            entry.stock_landed_cost_valuation_id = self.id
