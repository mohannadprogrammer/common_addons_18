# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Gayathri V (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import datetime
from odoo.exceptions import UserError
from odoo import api, fields, models, _


class LabOrder(models.Model):
    """
    Lab Order model — mirrors Odoo Sale Order behaviour.

    Workflow
    --------
    draft  →  confirm  →  invoiced (invoice created & sent)
           →  paid     (invoice fully paid / registered)
           →  request_lab  (lab technician starts the tests)
           →  completed    (results ready)
           →  cancel   (allowed only from draft / confirm)

    The invoice is intentionally created right after order confirmation so
    that payment is collected *before* any lab work begins.
    """

    _name = 'lab.appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Lab Order'
    _order = 'appointment_date desc, id desc'

    # ------------------------------------------------------------------ #
    #  Identity / header fields                                           #
    # ------------------------------------------------------------------ #
    name = fields.Char(
        string='Order Reference',
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        help='Unique reference assigned to this lab order.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        readonly=True,
        help='User responsible for this lab order.',
    )
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        tracking=True,
        domain="[('is_patient', '=', True)]",
        context={'search_default_is_patient': 1, 'default_is_patient': 1},
        states={'draft': [('readonly', False)]},
        help='Patient for whom the lab order is created.',
    )
    date = fields.Date(
        string='Order Date',
        default=lambda s: fields.Datetime.now(),
        readonly=True,
        help='Date the lab order was created.',
    )
    appointment_date = fields.Date(
        string='Scheduled Date',
        default=lambda s: fields.Datetime.now(),
        tracking=True,
        help='Date/time the patient is expected to visit the lab.',
    )
    physician_id = fields.Many2one(
        'res.partner',
        string='Referred By',
        domain="[('is_physician', '=', True)]",
        context={'search_default_is_physician': 1, 'default_is_physician': 1},
        help='Physician who referred this patient.',
    )
    comment = fields.Text(string='Notes', help='Additional clinical notes.')
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'Normal'), ('2', 'High')],
        default='0',
        string='Priority',
    )

    # ------------------------------------------------------------------ #
    #  Order lines                                                        #
    # ------------------------------------------------------------------ #
    appointment_line_ids = fields.One2many(
        'lab.appointment.lines',
        'test_line_appointment_id',
        string='Lab Tests',
        help='Individual lab tests requested in this order.',
    )

    # ------------------------------------------------------------------ #
    #  Computed totals (mirrors sale.order)                               #
    # ------------------------------------------------------------------ #
    amount_untaxed = fields.Float(
        string='Untaxed Amount',
        compute='_compute_amounts',
        store=True,
    )
    amount_total = fields.Float(
        string='Total',
        compute='_compute_amounts',
        store=True,
    )

    # ------------------------------------------------------------------ #
    #  Smart-button counters                                              #
    # ------------------------------------------------------------------ #
    request_count = fields.Integer(
        compute='_compute_counts',
        string='Lab Requests',
        copy=False,
    )
    inv_count = fields.Integer(
        compute='_compute_counts',
        string='Invoices',
        copy=False,
    )

    # ------------------------------------------------------------------ #
    #  Status                                                             #
    # ------------------------------------------------------------------ #
    state = fields.Selection(
        [
            ('draft',       'Quotation'),        # mirrors SO 'draft'
            ('confirm',     'Order Confirmed'),  # mirrors SO 'sale'
            ('to_invoice',  'To Invoice'),       # invoice not yet created
            ('invoiced',    'Invoiced'),          # invoice created, awaiting payment
            ('paid',        'Paid'),             # payment registered → unlock lab
            ('request_lab', 'Lab In Progress'),  # lab work started
            ('completed',   'Results Ready'),    # results entered
            ('cancel',      'Cancelled'),
        ],
        string='Status',
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        default='draft',
    )

    # ------------------------------------------------------------------ #
    #  Invoice payment state (mirrors what sale order tracks)            #
    # ------------------------------------------------------------------ #
    invoice_payment_state = fields.Char(
        compute='_compute_invoice_payment_state',
        string='Payment Status',
        store=False,
    )

    # ================================================================== #
    #  ORM overrides                                                      #
    # ================================================================== #

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('lab.appointment')
                    or _('New')
                )
        return super().create(vals_list)

    # ================================================================== #
    #  Computed fields                                                    #
    # ================================================================== #

    @api.depends('appointment_line_ids.cost')
    def _compute_amounts(self):
        for order in self:
            total = sum(order.appointment_line_ids.mapped('cost'))
            order.amount_untaxed = total
            order.amount_total = total   # extend here if tax logic is needed

    def _compute_counts(self):
        LabRequest = self.env['lab.request']
        AccountMove = self.env['account.move']
        for order in self:
            order.request_count = LabRequest.search_count(
                [('app_id', '=', order.id)]
            )
            order.inv_count = AccountMove.search_count(
                [('lab_request_id', '=', order.id)]
            )

    def _compute_invoice_payment_state(self):
        """Summarise payment state of related invoices."""
        AccountMove = self.env['account.move']
        for order in self:
            invoices = AccountMove.search([('lab_request_id', '=', order.id)])
            if not invoices:
                order.invoice_payment_state = 'not_invoiced'
            elif all(inv.payment_state == 'paid' for inv in invoices):
                order.invoice_payment_state = 'paid'
            elif any(inv.payment_state in ('partial',) for inv in invoices):
                order.invoice_payment_state = 'partial'
            else:
                order.invoice_payment_state = 'not_paid'

    # ================================================================== #
    #  Action buttons — follow Sale Order pattern                         #
    # ================================================================== #

    def action_confirm_order(self):
        """
        Confirm the lab order (Draft → Confirmed).
        Sends a confirmation e-mail to the patient, then immediately moves
        to 'To Invoice' so the receptionist can create the invoice right away.
        """
        self.ensure_one()
        if not self.appointment_line_ids:
            raise UserError(_('Please add at least one lab test before confirming.'))

        # Confirmation e-mail
        message_body = (
            "Dear %s,<br>"
            "Your Lab Order <b>%s</b> has been confirmed.<br>"
            "Scheduled Date: %s<br><br>"
            "Please note that payment is required before the tests begin.<br><br>"
            "Thank you."
        ) % (self.patient_id.name, self.name, self.appointment_date)

        self.env['mail.mail'].create({
            'subject': 'Lab Order Confirmed – %s' % self.name,
            'body_html': message_body,
            'email_from': self.env.user.email or '',
            'email_to': self.patient_id.email,
        }).send()

        self.write({'state': 'to_invoice'})

    def action_create_invoice(self):
        """
        Create the customer invoice (To Invoice → Invoiced).

        The invoice is created immediately after order confirmation so the
        patient pays *before* any lab work starts — mirroring the
        prepayment flow used in some Sale Order configurations.
        """
        self.ensure_one()
        if not self.appointment_line_ids:
            raise UserError(_('Cannot invoice an order with no lab tests.'))

        AccountMove = self.env['account.move']
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale')], limit=1
        )
        prd_account_id = journal.default_account_id.id

        invoice_lines = []
        for line in self.appointment_line_ids:
            invoice_lines.append((0, 0, {
                'name': line.lab_test_id.lab_test,
                'price_unit': line.cost,
                'quantity': 1.0,
                'account_id': prd_account_id,
            }))

        invoice = AccountMove.create({
            'partner_id': self.patient_id.id,
            'state': 'draft',
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_origin': 'Lab Order: %s' % self.name,
            'lab_request_id': self.id,
            'is_lab_invoice': True,
            'invoice_line_ids': invoice_lines,
        })

        self.write({'state': 'invoiced'})

        # Open the newly created invoice for the user to review / send
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lab Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'view_id': self.env.ref('account.view_move_form').id,
        }

    def action_register_payment(self):
        """
        Shortcut: open the invoice wizard to register payment.
        Odoo will call the invoice's own payment flow; we listen to the
        invoice's payment_state via _action_check_payment_and_unlock().
        """
        self.ensure_one()
        invoices = self.env['account.move'].search(
            [('lab_request_id', '=', self.id), ('state', '=', 'posted')]
        )
        if not invoices:
            raise UserError(
                _('Please post (confirm) the invoice before registering payment.')
            )
        unpaid = invoices.filtered(lambda i: i.payment_state != 'paid')
        if not unpaid:
            raise UserError(_('All invoices are already paid.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_ids': unpaid.ids,
            },
        }

    def action_check_payment_and_unlock(self):
        """
        Called manually (or can be triggered by an invoice payment hook).
        Moves the order from 'invoiced' → 'paid' once all invoices are paid,
        unlocking the 'Request Lab' button for the technician.
        """
        self.ensure_one()
        invoices = self.env['account.move'].search(
            [('lab_request_id', '=', self.id)]
        )
        all_paid = invoices and all(
            inv.payment_state == 'paid' for inv in invoices
        )
        if not all_paid:
            raise UserError(
                _('Payment has not been fully received yet. '
                  'Please register payment on the invoice first.')
            )
        self.write({'state': 'paid'})

    def action_request_lab(self):
        """
        Start lab work (Paid → Lab In Progress).
        Only allowed after full payment is confirmed.
        """
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(
                _('The lab order must be fully paid before lab work can begin.')
            )
        for line in self.appointment_line_ids:
            lab_test = self.env['lab.test'].search(
                [('lab_test', '=', line.lab_test_id.lab_test)], limit=1
            )
            self.env['lab.request'].create({
                'lab_request_id': self.name,
                'app_id': self.id,
                'lab_requestor_id': self.patient_id.id,
                'lab_requesting_date': self.appointment_date,
                'test_request_id': line.lab_test_id.id,
                'request_line_ids': [
                    (6, 0, [x.id for x in lab_test.test_lines_ids])
                ],
            })
        self.write({'state': 'request_lab'})

    def action_mark_completed(self):
        """Mark the lab order as completed once results are ready."""
        self.ensure_one()
        if self.state != 'request_lab':
            raise UserError(_('Lab work must be in progress before marking as completed.'))
        self.write({'state': 'completed'})

    def action_cancel(self):
        """Cancel the lab order (only from draft or confirmed)."""
        for order in self:
            if order.state not in ('draft', 'confirm', 'to_invoice'):
                raise UserError(
                    _('Only draft or confirmed orders can be cancelled.')
                )
        return self.write({'state': 'cancel'})

    def action_set_to_draft(self):
        """Reset a cancelled order back to draft."""
        return self.write({'state': 'draft'})

    # ================================================================== #
    #  Smart-button actions                                               #
    # ================================================================== #

    def action_view_invoices(self):
        invoices = self.env['account.move'].search(
            [('lab_request_id', '=', self.id)]
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lab Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
        }

    def action_view_lab_requests(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lab Requests'),
            'res_model': 'lab.request',
            'view_mode': 'list,form',
            'domain': [('app_id', '=', self.id)],
        }