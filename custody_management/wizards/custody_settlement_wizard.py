# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CustodySettlementWizard(models.TransientModel):
    _name = 'custody.settlement.wizard'
    _description = 'Custody Settlement Wizard'

    custody_id = fields.Many2one('custody.custody', string='Custody', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  related='custody_id.employee_id', readonly=True)
    remaining_balance = fields.Monetary(string='Remaining Balance',
                                        related='custody_id.remaining_balance', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='custody_id.currency_id', readonly=True)
    line_ids = fields.One2many('custody.settlement.wizard.line', 'wizard_id',
                                string='Expense Lines')

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one expense line.'))

        for line in self.line_ids:
            settlement_vals = {
                'custody_id': self.custody_id.id,
                'expense_date': line.expense_date or fields.Date.today(),
                'product_id': line.product_id.id,
                'vendor_id': line.vendor_id.id,
                'description': line.description,
                'amount': line.amount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'receipt': line.receipt,
                'receipt_filename': line.receipt_filename,
            }
            settlement = self.env['custody.settlement'].create(settlement_vals)
            settlement.action_confirm()
            settlement.action_post()

        return {'type': 'ir.actions.act_window_close'}


class CustodySettlementWizardLine(models.TransientModel):
    _name = 'custody.settlement.wizard.line'
    _description = 'Custody Settlement Wizard Line'

    wizard_id = fields.Many2one('custody.settlement.wizard', string='Wizard',
                                 ondelete='cascade')
    expense_date = fields.Date(string='Expense Date', default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Product',
                                 domain="[('type', '=', 'consu')]")
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    description = fields.Text(string='Description', required=True)
    amount = fields.Monetary(string='Amount', required=True,
                             currency_field='currency_id')
    tax_ids = fields.Many2many('account.tax', string='Taxes',
                               domain="[('type_tax_use', '=', 'purchase')]")
    receipt = fields.Binary(string='Receipt')
    receipt_filename = fields.Char(string='Receipt Filename')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='wizard_id.currency_id', readonly=True)
