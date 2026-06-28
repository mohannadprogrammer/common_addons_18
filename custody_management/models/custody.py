# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Custody(models.Model):
    _name = 'custody.custody'
    _description = 'Custody'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(string='Custody Number', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  default=lambda self: self.env.user.employee_id or False)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='employee_id.department_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='company_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary(string='Custody Amount', required=True, currency_field='currency_id')
    remaining_balance = fields.Monetary(string='Remaining Balance', currency_field='currency_id',
                                        compute='_compute_remaining_balance', store=True, readonly=True)
    total_settled = fields.Monetary(string='Total Settled', currency_field='currency_id',
                                    compute='_compute_remaining_balance', store=True, readonly=True)
    total_paid = fields.Monetary(string='Total Paid', currency_field='currency_id',
                                 compute='_compute_total_paid', store=True, readonly=True)
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    due_date = fields.Date(string='Due Date')
    journal_id = fields.Many2one('account.journal', string='Disbursement Journal',
                                 domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]")
    settlement_journal_id = fields.Many2one('account.journal', string='Settlement Journal',
                                            domain="[('type', 'in', ['bank', 'cash', 'general']), ('company_id', '=', company_id)]")
    settlement_account_id = fields.Many2one('account.account', string='Settlement Account',
                                            domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]",
                                            help="Receivable account used for custody settlement entries")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_approved', 'Manager Approved'),
        ('finance_approved', 'Finance Approved'),
        ('paid', 'Paid'),
        ('partially_settled', 'Partially Settled'),
        ('settled', 'Settled'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False, group_expand='_expand_states')

    settlement_ids = fields.One2many('custody.settlement', 'custody_id', string='Settlements',
                                     copy=False)
    payment_ids = fields.One2many('custody.payment', 'custody_id', string='Payments', copy=False)

    account_move_id = fields.Many2one('account.move', string='Disbursement Entry',
                                      readonly=True, copy=False)
    settlement_move_ids = fields.One2many('account.move', string='Settlement Entries',
                                          compute='_compute_settlement_moves', readonly=True)
    cash_return_move_id = fields.Many2one('account.move', string='Cash Return Entry',
                                          readonly=True, copy=False)

    settlement_count = fields.Integer(compute='_compute_settlement_count', string='Settlement Count')
    payment_count = fields.Integer(compute='_compute_payment_count', string='Payment Count')
    is_overdue = fields.Boolean(compute='_compute_overdue', string='Overdue', store=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    approved_date = fields.Datetime(string='Approval Date', readonly=True, copy=False)
    finance_approved_by = fields.Many2one('res.users', string='Finance Approved By',
                                          readonly=True, copy=False)
    finance_approved_date = fields.Datetime(string='Finance Approval Date', readonly=True, copy=False)
    paid_by = fields.Many2one('res.users', string='Paid By', readonly=True, copy=False)
    paid_date = fields.Datetime(string='Payment Date', readonly=True, copy=False)
    closed_by = fields.Many2one('res.users', string='Closed By', readonly=True, copy=False)
    closed_date = fields.Datetime(string='Closing Date', readonly=True, copy=False)
    cancelled_by = fields.Many2one('res.users', string='Cancelled By', readonly=True, copy=False)
    cancellation_reason = fields.Text(string='Cancellation Reason')

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    @api.depends('settlement_ids', 'settlement_ids.amount')
    def _compute_remaining_balance(self):
        for record in self:
            total_settled = sum(record.settlement_ids.mapped('amount'))
            record.total_settled = total_settled
            record.remaining_balance = record.amount - total_settled

    @api.depends('payment_ids', 'payment_ids.amount')
    def _compute_total_paid(self):
        for record in self:
            record.total_paid = sum(record.payment_ids.mapped('amount'))

    def _compute_settlement_moves(self):
        for record in self:
            record.settlement_move_ids = record.settlement_ids.mapped('account_move_id')

    def _compute_settlement_count(self):
        for record in self:
            record.settlement_count = len(record.settlement_ids)

    def _compute_payment_count(self):
        for record in self:
            record.payment_count = len(record.payment_ids)

    @api.depends('due_date', 'state')
    def _compute_overdue(self):
        for record in self:
            record.is_overdue = bool(
                record.due_date and record.due_date < fields.Date.today()
                and record.state in ('paid', 'partially_settled')
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        if 'settlement_journal_id' in fields_list and not res.get('settlement_journal_id'):
            res['settlement_journal_id'] = company.custody_settlement_journal_id.id
        if 'settlement_account_id' in fields_list and not res.get('settlement_account_id'):
            res['settlement_account_id'] = company.custody_settlement_account_id.id
        return res

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('custody.custody') or _('New')
        return super().create(vals)

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Custody amount must be greater than zero.'))

    def _check_can_modify(self):
        self.ensure_one()
        if self.state not in ('draft', 'cancelled'):
            raise UserError(_('Only draft or cancelled custodies can be modified.'))

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft custodies can be submitted.'))
            if not record.employee_id:
                raise UserError(_('Employee is required.'))
            if not record.purpose:
                raise UserError(_('Purpose is required.'))
        self.write({
            'state': 'submitted',
        })
        self.message_post(body=_('Custody submitted for approval.'))

    def action_manager_approve(self):
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Custody must be in Submitted state for manager approval.'))
        self.write({
            'state': 'manager_approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self.message_post(body=_('Custody approved by manager.'))

    def action_manager_reject(self):
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Custody must be in Submitted state to reject.'))
        self.write({'state': 'draft'})
        self.message_post(body=_('Custody rejected by manager.'))

    def action_finance_approve(self):
        for record in self:
            if record.state != 'manager_approved':
                raise UserError(_('Custody must be in Manager Approved state for finance approval.'))
            if not record.journal_id:
                raise UserError(_('Please select a disbursement journal.'))
        self.write({
            'state': 'finance_approved',
            'finance_approved_by': self.env.user.id,
            'finance_approved_date': fields.Datetime.now(),
        })
        self.message_post(body=_('Custody approved by finance.'))

    def action_finance_reject(self):
        for record in self:
            if record.state != 'manager_approved':
                raise UserError(_('Custody must be in Manager Approved state to reject.'))
        self.write({'state': 'draft'})
        self.message_post(body=_('Custody rejected by finance.'))

    def action_pay(self):
        self.ensure_one()
        if self.state != 'finance_approved':
            raise UserError(_('Custody must be Finance Approved before payment.'))
        if not self.journal_id:
            raise UserError(_('Disbursement journal is required.'))

        return {
            'name': _('Disburse Custody'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_custody_id': self.id,
                'default_amount': self.amount,
                'default_journal_id': self.journal_id.id,
            },
        }

    def action_cancel(self):
        for record in self:
            if record.state in ('closed', 'cancelled'):
                raise UserError(_('Custody is already closed or cancelled.'))
        return {
            'name': _('Cancel Custody'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_custody_id': self.id,
            },
        }

    def action_settle(self):
        self.ensure_one()
        if self.state not in ('paid', 'partially_settled'):
            raise UserError(_('Custody must be Paid or Partially Settled to submit settlements.'))
        return {
            'name': _('Settle Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.settlement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_custody_id': self.id,
            },
        }

    def action_return_cash(self):
        self.ensure_one()
        if self.state not in ('paid', 'partially_settled', 'settled'):
            raise UserError(_('Custody is not in a valid state for cash return.'))
        if self.remaining_balance <= 0:
            raise UserError(_('No remaining balance to return.'))
        return {
            'name': _('Return Cash'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.cash.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_custody_id': self.id,
                'default_amount': self.remaining_balance,
            },
        }

    def action_view_settlements(self):
        self.ensure_one()
        return {
            'name': _('Settlements'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.settlement',
            'view_mode': 'list,form',
            'domain': [('custody_id', '=', self.id)],
            'context': {'default_custody_id': self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'custody.payment',
            'view_mode': 'list,form',
            'domain': [('custody_id', '=', self.id)],
        }

    def action_view_disbursement_move(self):
        self.ensure_one()
        return {
            'name': _('Disbursement Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.account_move_id.id,
        }

    def action_view_settlement_moves(self):
        self.ensure_one()
        return {
            'name': _('Settlement Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.settlement_move_ids.ids)],
        }

    def _update_state_after_settlement(self):
        self.ensure_one()
        total_settled = sum(self.settlement_ids.filtered(lambda s: s.state == 'posted').mapped('amount'))
        if total_settled >= self.amount:
            self.write({'state': 'settled'})
        elif total_settled > 0:
            self.write({'state': 'partially_settled'})


class CustodyCancelWizard(models.TransientModel):
    _name = 'custody.cancel.wizard'
    _description = 'Custody Cancellation Wizard'

    custody_id = fields.Many2one('custody.custody', string='Custody', required=True)
    reason = fields.Text(string='Cancellation Reason', required=True)

    def action_confirm_cancel(self):
        self.custody_id.write({
            'state': 'cancelled',
            'cancelled_by': self.env.user.id,
            'cancellation_reason': self.reason,
        })
        self.custody_id.message_post(body=_('Custody cancelled. Reason: %s') % self.reason)
        return {'type': 'ir.actions.act_window_close'}
