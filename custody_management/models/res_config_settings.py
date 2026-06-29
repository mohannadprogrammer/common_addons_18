from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    custody_management_activated = fields.Boolean(
        related='company_id.custody_management_activated',
        readonly=False,
        string='Activate Custody Management',
    )
    custody_payment_journal_id = fields.Many2one(
        'account.journal', string='Default Payment Journal',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        related='company_id.custody_payment_journal_id', readonly=False)
    custody_journal_id = fields.Many2one(
        'account.journal', string='Default Custody Journal',
        domain="[('type', 'in', ['bank', 'cash', 'general']), ('company_id', '=', company_id)]",
        related='company_id.custody_journal_id', readonly=False)
    custody_account_id = fields.Many2one(
        'account.account', string='Default Custody Account',
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]",
        related='company_id.custody_account_id', readonly=False)

    def set_values(self):
        super().set_values()
        if self.custody_management_activated:
            self.company_id._ensure_custody_sequences()


class ResCompany(models.Model):
    _inherit = 'res.company'

    custody_management_activated = fields.Boolean(
        string='Activate Custody Management',
        default=False,
        help="Enable custody management features for this company/branch",
    )
    custody_payment_journal_id = fields.Many2one(
        'account.journal', string='Default Payment Journal',
        domain="[('type', 'in', ['bank', 'cash'])]")
    custody_journal_id = fields.Many2one(
        'account.journal', string='Default Custody Journal',
        domain="[('type', 'in', ['bank', 'cash', 'general'])]")
    custody_account_id = fields.Many2one(
        'account.account', string='Default Custody Account',
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]")

    @api.model
    def create(self, vals):
        company = super().create(vals)
        if vals.get('custody_management_activated'):
            company._ensure_custody_sequences()
        return company

    def write(self, vals):
        res = super().write(vals)
        if vals.get('custody_management_activated'):
            for company in self:
                company._ensure_custody_sequences()
        return res

    def _ensure_custody_sequences(self):
        Sequence = self.env['ir.sequence'].sudo()
        sequences = [
            {'code': 'custody.custody', 'name': 'Custody Number', 'prefix': 'CST/'},
            {'code': 'custody.settlement', 'name': 'Settlement Number', 'prefix': 'STL/'},
            {'code': 'custody.payment', 'name': 'Payment Reference', 'prefix': 'PAY/'},
        ]
        for seq in sequences:
            if not Sequence.search([('code', '=', seq['code']), ('company_id', '=', self.id)], limit=1):
                template = Sequence.search([('code', '=', seq['code']), ('company_id', '=', False)], limit=1)
                if template:
                    template.copy({
                        'company_id': self.id,
                        'name': '%s - %s' % (template.name, self.name),
                    })
                else:
                    Sequence.create({
                        'name': '%s - %s' % (seq['name'], self.name),
                        'code': seq['code'],
                        'prefix': seq['prefix'],
                        'padding': 5,
                        'company_id': self.id,
                        'implementation': 'no_gap',
                    })
