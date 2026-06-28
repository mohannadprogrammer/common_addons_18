# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CustodyPaymentWizard(models.TransientModel):
    _name = 'custody.payment.wizard'
    _description = 'Custody Payment Wizard'

    custody_id = fields.Many2one('custody.custody', string='Custody', required=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 domain="[('type', 'in', ['bank', 'cash'])]")
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method',
                                        domain="[('payment_type', '=', 'outbound')]")
    date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='custody_id.currency_id', readonly=True)

    def action_pay(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('Payment amount must be greater than zero.'))
        if self.amount > self.custody_id.amount:
            raise UserError(_('Payment amount cannot exceed custody amount.'))

        payment = self.env['custody.payment'].create({
            'custody_id': self.custody_id.id,
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'date': self.date,
            'amount': self.amount,
            'payment_type': 'disbursement',
        })
        payment.action_post()
        return {'type': 'ir.actions.act_window_close'}
