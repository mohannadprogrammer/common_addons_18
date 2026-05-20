from odoo import fields, models


class ResCompany(models.Model):
    """
    Extend res.company with the six stock-valuation account pointers and an
    on/off master switch.

    These act as company-wide defaults that product categories can override.
    All fields are plain Many2one (not property fields) because Odoo 19 dropped
    ir.property-based Many2one fields in favour of direct relational fields.
    """

    _inherit = "res.company"

    # ── Master switch ─────────────────────────────────────────────────────────
    custom_stock_valuation_enabled = fields.Boolean(
        string="Automated Stock Valuation",
        default=True,
        help=(
            "Enable the Automated Stock Valuation Engine for this company.\n"
            "When disabled, no custom valuation journal entries are created "
            "for stock moves, vendor bills, or customer invoices."
        ),
    )

    property_stock_valuation_account_id = fields.Many2one(
        "account.account",
        string="Stock Valuation Account",
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', id)]",
    )
    property_stock_input_account_id = fields.Many2one(
        "account.account",
        string="Stock Input (GRNI)",
        domain="[('account_type', '=', 'liability_current'), ('company_ids', 'in', id)]",
    )
    property_stock_output_account_id = fields.Many2one(
        "account.account",
        string="Stock Output (Interim)",
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', id)]",
    )
    property_account_expense_categ_id = fields.Many2one(
        "account.account",
        string="Cost of Goods Sold",
        domain="[('account_type', '=', 'expense'), ('company_ids', 'in', id)]",
    )
    property_production_account_id = fields.Many2one(
        "account.account",
        string="Production Account",
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', id)]",
    )
    property_inventory_loss_account_id = fields.Many2one(
        "account.account",
        string="Inventory Loss Account",
        domain="[('account_type', '=', 'expense'), ('company_ids', 'in', id)]",
    )


class ResConfigSettings(models.TransientModel):
    """Expose the master switch and company-level stock valuation accounts in Settings."""

    _inherit = "res.config.settings"

    # ── Master switch (mirrors res.company field via related) ─────────────────
    custom_stock_valuation_enabled = fields.Boolean(
        string="Enable Automated Stock Valuation",
        related="company_id.custom_stock_valuation_enabled",
        readonly=False,
        help=(
            "Enable or disable the Automated Stock Valuation Engine for this company.\n"
            "When disabled, no custom valuation journal entries are created."
        ),
    )

    property_stock_valuation_account_id = fields.Many2one(
        "account.account",
        string="Stock Valuation",
        related="company_id.property_stock_valuation_account_id",
        readonly=False,
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', company_id)]",
    )
    property_stock_input_account_id = fields.Many2one(
        "account.account",
        string="Stock Input (GRNI)",
        related="company_id.property_stock_input_account_id",
        readonly=False,
        domain="[('account_type', '=', 'liability_current'), ('company_ids', 'in', company_id)]",
    )
    property_stock_output_account_id = fields.Many2one(
        "account.account",
        string="Stock Output (Interim)",
        related="company_id.property_stock_output_account_id",
        readonly=False,
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', company_id)]",
    )
    property_account_expense_categ_id = fields.Many2one(
        "account.account",
        string="Cost of Goods Sold",
        related="company_id.property_account_expense_categ_id",
        readonly=False,
        domain="[('account_type', '=', 'expense'), ('company_ids', 'in', company_id)]",
    )
    property_production_account_id = fields.Many2one(
        "account.account",
        string="Production Account",
        related="company_id.property_production_account_id",
        readonly=False,
        domain="[('account_type', '=', 'asset_current'), ('company_ids', 'in', company_id)]",
    )
    property_inventory_loss_account_id = fields.Many2one(
        "account.account",
        string="Inventory Loss Account",
        related="company_id.property_inventory_loss_account_id",
        readonly=False,
        domain="[('account_type', '=', 'expense'), ('company_ids', 'in', company_id)]",
    )
