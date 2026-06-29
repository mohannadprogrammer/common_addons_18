# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CustodySettlement(models.Model):
    _name = 'custody.settlement'
    _description = 'Custody Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expense_date desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Settlement Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    custody_id = fields.Many2one('custody.custody', string='Custody', required=True,
                                 ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  related='custody_id.employee_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='custody_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='custody_id.currency_id', store=True, readonly=True)
    expense_date = fields.Date(string='Expense Date', required=True, default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Product',
                                 domain="[('type', '=', 'consu')]")
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    description = fields.Text(string='Description', required=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    tax_ids = fields.Many2many('account.tax', string='Taxes',
                               domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]")
    total = fields.Monetary(string='Total', compute='_compute_total', store=True,
                            currency_field='currency_id')
    receipt = fields.Binary(string='Receipt Attachment')
    receipt_filename = fields.Char(string='Receipt Filename')

    account_move_id = fields.Many2one('account.move', string='Accounting Entry',
                                      readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', tracking=True, copy=False)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'expense_date', 'description')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s - %s' % (record.name or _('New'), record.description or '')

    @api.depends('amount', 'tax_ids')
    def _compute_total(self):
        for record in self:
            if not record.amount:
                record.total = 0.0
                continue
            tax_results = record.tax_ids.compute_all(
                record.amount,
                record.currency_id or record.company_id.currency_id,
                1.0,
                product=record.product_id,
                partner=record.vendor_id,
            )
            record.total = tax_results['total_included']

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            company_id = self.env.company.id
            if vals.get('custody_id'):
                company_id = self.env['custody.custody'].browse(vals['custody_id']).company_id.id
            self.env['custody.custody']._ensure_company_sequence('custody.settlement', company_id)
            vals['name'] = self.env['ir.sequence'].with_context(force_company=company_id).next_by_code('custody.settlement') or _('New')
        return super().create(vals)

    @api.constrains('amount', 'total', 'custody_id')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Settlement amount must be greater than zero.'))
            if record.total > record.custody_id.remaining_balance:
                raise ValidationError(_(
                    'Settlement total exceeds custody remaining balance. '
                    'Please check the amounts.'
                ))

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft settlements can be confirmed.'))
        self.write({'state': 'confirmed'})

    def action_post(self):
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Only confirmed settlements can be posted.'))
            record._create_account_move()

    def action_draft(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Posted settlements cannot be reset to draft.'))
            if record.account_move_id:
                raise UserError(_('Settlement with accounting entry cannot be reset.'))
        self.write({'state': 'draft'})

    def _create_account_move(self):
        self.ensure_one()
        custody = self.custody_id
        journal = custody.custody_journal_id or self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_('Please configure a custody journal on the custody.'))

        move_vals = {
            'journal_id': journal.id,
            'date': self.expense_date,
            'ref': '%s - %s' % (custody.name, self.name),
            'currency_id': self.currency_id.id,
            'line_ids': [],
        }

        # Debit: Expense account(s)
        debit_lines = []
        if self.tax_ids:
            tax_results = self.tax_ids.compute_all(
                self.amount, self.currency_id or self.company_id.currency_id,
                1.0, product=self.product_id, partner=self.vendor_id,
            )
            for tax_line in tax_results.get('taxes', []):
                account_id = tax_line.get('account_id') or tax_line.get('refund_account_id')
                if not account_id:
                    account = self.company_id._get_tax_account()
                    account_id = account.id if account else False
                if account_id:
                    debit_lines.append((0, 0, {
                        'name': tax_line.get('name', 'Tax'),
                        'account_id': account_id,
                        'debit': tax_line.get('amount', 0.0),
                        'credit': 0.0,
                        'currency_id': self.currency_id.id,
                    }))

        expense_account = self.product_id.property_account_expense_id
        if not expense_account:
            expense_account = self.product_id.categ_id.property_account_expense_categ_id
        if not expense_account:
            expense_account = self.env['account.account'].with_company(self.company_id).search([
                ('account_type', '=', 'expense'),
                ('deprecated', '=', False),
            ], limit=1)
        if not expense_account:
            raise UserError(_('No expense account found. Please configure product/category expense account.'))

        partner = self.employee_id.work_contact_id or self.employee_id.user_id.partner_id

        debit_lines.insert(0, (0, 0, {
            'name': self.description or 'Expense',
            'account_id': expense_account.id,
            'partner_id': partner.id if partner else False,
            'debit': self.amount,
            'credit': 0.0,
            'currency_id': self.currency_id.id,
        }))

        move_vals['line_ids'] = debit_lines

        # Credit: Employee Advance (Custody) account
        advance_account = custody.custody_account_id
        if not advance_account:
            advance_account = self.env['account.account'].with_company(self.company_id).search([
                ('account_type', '=', 'asset_receivable'),
                ('deprecated', '=', False),
            ], limit=1)
        if not advance_account:
            raise UserError(_('No receivable account found. Please configure a Custody Account on the custody.'))

        move_vals['line_ids'].append((0, 0, {
            'name': 'Employee Advance - %s' % custody.name,
            'account_id': advance_account.id,
            'partner_id': partner.id if partner else False,
            'debit': 0.0,
            'credit': self.total,
            'currency_id': self.currency_id.id,
        }))

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.write({
            'account_move_id': move.id,
            'state': 'posted',
        })

        # Update custody state
        custody._update_state_after_settlement()
        return move

    def write(self, vals):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Cannot modify a posted settlement.'))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_('Cannot delete a posted settlement.'))
            if record.account_move_id:
                raise UserError(_('Cannot delete a settlement with accounting entry.'))
        return super().unlink()
