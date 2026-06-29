# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CustodyPayment(models.Model):
    _name = 'custody.payment'
    _description = 'Custody Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Payment Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    custody_id = fields.Many2one('custody.custody', string='Custody', required=True,
                                 ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  related='custody_id.employee_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='custody_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='custody_id.currency_id', store=True, readonly=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]")
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method',
                                        domain="[('payment_type', '=', 'outbound')]")
    date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    account_move_id = fields.Many2one('account.move', string='Accounting Entry',
                                      readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', tracking=True, copy=False)
    payment_type = fields.Selection([
        ('disbursement', 'Disbursement'),
        ('cash_return', 'Cash Return'),
    ], string='Payment Type', default='disbursement', required=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            company_id = self.env.company.id
            if vals.get('custody_id'):
                company_id = self.env['custody.custody'].browse(vals['custody_id']).company_id.id
            self.env['custody.custody']._ensure_company_sequence('custody.payment', company_id)
            vals['name'] = self.env['ir.sequence'].with_context(force_company=company_id).next_by_code('custody.payment') or _('New')
        return super().create(vals)

    def action_post(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft payments can be posted.'))
            record._create_account_move()

    def _create_account_move(self):
        self.ensure_one()
        custody = self.custody_id
        journal = self.journal_id or custody.payment_journal_id
        if not journal:
            raise UserError(_('Journal is required for payment.'))

        advance_account = custody.custody_account_id
        if not advance_account:
            advance_account = self.env['account.account'].with_company(self.company_id).search([
                ('account_type', '=', 'asset_receivable'),
                ('deprecated', '=', False),
            ], limit=1)
        if not advance_account:
            raise UserError(_('No receivable account found. Please configure a Custody Account on the custody.'))

        partner = self.employee_id.work_contact_id or self.employee_id.user_id.partner_id

        if self.payment_type == 'disbursement':
            # Debit: Employee Advance
            # Credit: Cash/Bank
            line_ids = [
                (0, 0, {
                    'name': 'Employee Advance - %s' % custody.name,
                    'account_id': advance_account.id,
                    'partner_id': partner.id if partner else False,
                    'debit': self.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                }),
                (0, 0, {
                    'name': 'Custody Disbursement - %s' % custody.name,
                    'account_id': journal.default_account_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'currency_id': self.currency_id.id,
                }),
            ]
        else:
            # Cash Return: Debit Cash/Bank, Credit Employee Advance
            line_ids = [
                (0, 0, {
                    'name': 'Cash Return - %s' % custody.name,
                    'account_id': journal.default_account_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                }),
                (0, 0, {
                    'name': 'Employee Advance Return - %s' % custody.name,
                    'account_id': advance_account.id,
                    'partner_id': partner.id if partner else False,
                    'debit': 0.0,
                    'credit': self.amount,
                    'currency_id': self.currency_id.id,
                }),
            ]

        move_vals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': '%s - %s' % (custody.name, self.name),
            'currency_id': self.currency_id.id,
            'line_ids': line_ids,
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.write({
            'account_move_id': move.id,
            'state': 'posted',
        })

        if self.payment_type == 'disbursement':
            custody.write({
                'state': 'paid',
                'paid_by': self.env.user.id,
                'paid_date': fields.Datetime.now(),
                'account_move_id': move.id,
            })
        elif self.payment_type == 'cash_return':
            total_settled = sum(custody.settlement_ids.filtered(lambda s: s.state == 'posted').mapped('amount'))
            total_cash_return = sum(custody.payment_ids.filtered(lambda p: p.payment_type == 'cash_return' and p.state == 'posted').mapped('amount'))
            remaining = custody.amount - total_settled - total_cash_return
            vals = {'cash_return_move_id': move.id}
            if remaining <= 0:
                if custody.state == 'settled':
                    vals.update({
                        'state': 'closed',
                        'closed_by': self.env.user.id,
                        'closed_date': fields.Datetime.now(),
                    })
                else:
                    vals['state'] = 'settled'
            custody.write(vals)

        custody.message_post(body=_('Payment %s of %s %s posted.') % (
            self.name, self.amount, self.currency_id.symbol or ''))

        return move

    def write(self, vals):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Cannot modify a posted payment.'))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Cannot delete a posted payment.'))
            if record.account_move_id:
                raise UserError(_('Cannot delete a payment with accounting entry.'))
        return super().unlink()
