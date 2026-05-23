from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ClinicShift(models.Model):
    _name = 'clinic.shift'
    _description = 'Clinic Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, shift_type'

    name = fields.Char(
        string='Shift Reference', readonly=True, copy=False, default='New'
    )
    shift_type = fields.Selection(
        [('day', 'Day Shift'), ('night', 'Night Shift')],
        string='Shift Type',
        required=True,
        tracking=True,
    )
    date = fields.Date(string='Date', required=True, default=fields.Date.today, tracking=True)
    start_time = fields.Datetime(string='Start Time', readonly=True, copy=False)
    end_time = fields.Datetime(string='End Time', readonly=True, copy=False)

    doctor_ids = fields.Many2many(
        'clinic.doctor',
        'clinic_shift_doctor_rel',
        'shift_id',
        'doctor_id',
        string='Doctors on Shift',
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('open', 'Open'), ('closed', 'Closed')],
        string='Status',
        default='draft',
        tracking=True,
    )

    appointment_ids = fields.One2many(
        'clinic.appointment', 'shift_id', string='Appointments'
    )
    appointment_count = fields.Integer(
        string='Appointments', compute='_compute_appointment_count'
    )
    customer_invoice_ids = fields.One2many(
        'account.move', 'shift_id', string='Customer Invoices',
        domain=[('move_type', '=', 'out_invoice')]
    )
    customer_invoice_count = fields.Integer(
        string='Customer Invoices', compute='_compute_customer_invoice_count', store=True
    )
    doctor_bill_ids = fields.One2many(
        'account.move', 'shift_id', string='Doctor Bills',
        domain=[('move_type', '=', 'in_invoice')]
    )
    doctor_bill_count = fields.Integer(
        string='Doctor Bills', compute='_compute_doctor_bill_count', store=True
    )
    doctor_count = fields.Integer(
        string='Doctors', compute='_compute_doctor_count', store=True
    )

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )

    # Summary fields computed at close
    total_revenue = fields.Float(
        string='Total Revenue', compute='_compute_totals', store=True
    )
    total_doctor_billing = fields.Float(
        string='Total Doctor Billing', compute='_compute_totals', store=True
    )

    @api.depends('appointment_ids.invoice_id.amount_total', 'appointment_ids.visit_fee', 'appointment_ids.state')
    def _compute_totals(self):
        for shift in self:
            invoiced_appointments = shift.appointment_ids.filtered(
                lambda a: a.invoice_id and a.invoice_id.state == 'posted'
            )
            shift.total_revenue = sum(a.invoice_id.amount_total for a in invoiced_appointments)
            shift.total_doctor_billing = sum(
                a.doctor_id.compute_doctor_earning(a.visit_fee)
                for a in invoiced_appointments
                if a.doctor_id
            )

    @api.depends('appointment_ids')
    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = len(rec.appointment_ids)

    @api.depends('customer_invoice_ids')
    def _compute_customer_invoice_count(self):
        for rec in self:
            rec.customer_invoice_count = len(rec.customer_invoice_ids)

    @api.depends('doctor_bill_ids')
    def _compute_doctor_bill_count(self):
        for rec in self:
            rec.doctor_bill_count = len(rec.doctor_bill_ids)

    @api.depends('doctor_ids')
    def _compute_doctor_count(self):
        for rec in self:
            rec.doctor_count = len(rec.doctor_ids)

    def action_view_customer_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('shift_id', '=', self.id), ('move_type', '=', 'out_invoice')],
        }

    def action_view_doctor_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Doctor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('shift_id', '=', self.id), ('move_type', '=', 'in_invoice')],
        }

    def action_view_doctors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Doctors'),
            'res_model': 'clinic.doctor',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.doctor_ids.ids)],
        }

    def write(self, vals):
        for rec in self:
            if rec.state == 'closed':
                raise UserError(_('Cannot modify a closed shift.'))
        if 'doctor_ids' in vals:
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_('Doctors can only be changed while the shift is in draft state.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('clinic.shift') or 'New'
        return super().create(vals_list)

    def action_open(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft shifts can be opened.'))
            if not rec.doctor_ids:
                raise UserError(_('Please assign at least one doctor before opening the shift.'))
            rec.start_time = fields.Datetime.now()
            rec.state = 'open'

    def action_close(self):
        """Open close shift wizard."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Only open shifts can be closed.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Close Shift'),
            'res_model': 'close.shift.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'default_shift_id': self.id},
        }

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'closed':
                raise UserError(_('Closed shifts cannot be reset.'))
            rec.state = 'draft'

    def action_view_appointments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Appointments'),
            'res_model': 'clinic.appointment',
            'view_mode': 'kanban,list,form',
            'domain': [('shift_id', '=', self.id)],
            'context': {'default_shift_id': self.id},
        }