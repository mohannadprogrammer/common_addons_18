# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CustodyCashReturnWizard(models.TransientModel):
    _name = 'custody.cash.return.wizard'
    _description = 'Custody Cash Return Wizard'

    custody_id = fields.Many2one('custody.custody', string='Custody', required=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 domain="[('type', 'in', ['bank', 'cash'])]")
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method',
                                        domain="[('payment_type', '=', 'inbound')]")
    date = fields.Date(string='Return Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='custody_id.currency_id', readonly=True)
    remaining_balance = fields.Monetary(string='Remaining Balance',
                                        related='custody_id.remaining_balance', readonly=True)

    def action_return(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('Return amount must be greater than zero.'))
        if self.amount > self.custody_id.remaining_balance:
            raise UserError(_('Return amount cannot exceed remaining balance.'))

        payment = self.env['custody.payment'].create({
            'custody_id': self.custody_id.id,
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'date': self.date,
            'amount': self.amount,
            'payment_type': 'cash_return',
        })
        payment.action_post()
        return {'type': 'ir.actions.act_window_close'}
