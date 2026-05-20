from odoo import api, fields, models


class ProductCategory(models.Model):
    """
    Extend product.category with per-category account overrides.

    When set, these override the company-level defaults for all products
    belonging to this category.  Leave blank to inherit from the company.
    """

    _inherit = "product.category"

    # ── Computed helper: mirrors the company-level on/off switch ──────────────
    # Used by the view's `invisible` expression so the account fields collapse
    # when the Automated Stock Valuation Engine is disabled for the company.
    custom_stock_valuation_enabled = fields.Boolean(
        string="Automated Stock Valuation Enabled",
        compute="_compute_custom_stock_valuation_enabled",
        help="Technical field — reflects the company setting.",
    )

    @api.depends_context("company")
    def _compute_custom_stock_valuation_enabled(self):
        enabled = self.env.company.custom_stock_valuation_enabled
        for categ in self:
            categ.custom_stock_valuation_enabled = enabled

    # ── Per-category account overrides ────────────────────────────────────────
    property_stock_valuation_account_id = fields.Many2one(
        "account.account",
        string="Stock Valuation Account",
        domain="[('account_type', '=', 'asset_current')]",
        help="Asset account representing the real-time stock value.",
    )
    property_stock_input_account_id = fields.Many2one(
        "account.account",
        string="Stock Input / GR-IR",
        domain="[('account_type', '=', 'liability_current')]",
        help="Clearing account: credited on receipt, debited on vendor bill.",
    )
    property_stock_output_account_id = fields.Many2one(
        "account.account",
        string="Stock Output (Interim)",
        domain="[('account_type', '=', 'asset_current')]",
        help="Clearing account: debited on delivery, credited on COGS entry.",
    )
    property_account_expense_categ_id = fields.Many2one(
        "account.account",
        string="Cost of Goods Sold",
        domain="[('account_type', '=', 'expense')]",
        help="Expense account debited when a customer invoice is validated.",
    )
    property_production_account_id = fields.Many2one(
        "account.account",
        string="Production Account",
        domain="[('account_type', '=', 'asset_current')]",
        help="WIP account used during manufacturing.",
    )
    property_inventory_loss_account_id = fields.Many2one(
        "account.account",
        string="Inventory Loss Account",
        domain="[('account_type', '=', 'expense')]",
        help="Expense account for inventory shrinkage / adjustments.",
    )
