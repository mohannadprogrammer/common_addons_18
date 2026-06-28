from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    custody_settlement_journal_id = fields.Many2one(
        'account.journal', string='Default Settlement Journal',
        domain="[('type', 'in', ['bank', 'cash', 'general']), ('company_id', '=', company_id)]",
        related='company_id.custody_settlement_journal_id', readonly=False)
    custody_settlement_account_id = fields.Many2one(
        'account.account', string='Default Settlement Account',
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]",
        related='company_id.custody_settlement_account_id', readonly=False)


class ResCompany(models.Model):
    _inherit = 'res.company'

    custody_settlement_journal_id = fields.Many2one(
        'account.journal', string='Default Settlement Journal',
        domain="[('type', 'in', ['bank', 'cash', 'general'])]")
    custody_settlement_account_id = fields.Many2one(
        'account.account', string='Default Settlement Account',
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]")
