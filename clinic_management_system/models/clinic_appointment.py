from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ClinicAppointment(models.Model):
    _name = 'clinic.appointment'
    _description = 'Clinic Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'appointment_date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New', tracking=True)
    patient_id = fields.Many2one('clinic.patient', string='Patient', required=True, tracking=True)
    doctor_id = fields.Many2one('clinic.doctor', string='Doctor', required=True, tracking=True,
                                group_expand='_expand_doctor_ids')
    shift_id = fields.Many2one('clinic.shift', string='Shift', tracking=True)
    appointment_date = fields.Datetime(string='Appointment Date', required=True, default=fields.Datetime.now, tracking=True)
    product_id = fields.Many2one('product.product', string='Service Product',
                                  domain="[('type', '=', 'service')]")
    visit_fee = fields.Monetary(string='Visit Fee', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Notes / Diagnosis')

    state = fields.Selection([
        ('draft', 'Scheduled'),
        ('invoiced', 'Invoiced'),
        ('waiting', 'Waiting'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
    ], string='Priority', default='0')
    color = fields.Integer(string='Color')
    kanban_state = fields.Selection([
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Kanban State', default='waiting')

    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice Status', readonly=True)
    invoice_payment_state = fields.Selection(related='invoice_id.payment_state', string='Invoice Payment Status', readonly=True)
    refund_invoice_id = fields.Many2one('account.move', string='Refund Invoice', readonly=True, copy=False)
    refund_invoice_payment_state = fields.Selection(related='refund_invoice_id.payment_state', string='Refund Payment Status', readonly=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.onchange('doctor_id')
    def _onchange_doctor_id(self):
        if self.doctor_id:
            self.product_id = self.doctor_id.product_id
            if self.doctor_id.product_id:
                self.visit_fee = self.doctor_id.product_id.list_price

    @api.model
    def _expand_doctor_ids(self, doctors, domain):
        for clause in domain:
            if isinstance(clause, (list, tuple)) and len(clause) >= 3 and clause[0] == 'shift_id' and clause[1] == '=':
                shift = self.env['clinic.shift'].browse(clause[2])
                if shift.exists() and shift.doctor_ids:
                    return shift.doctor_ids
                break
        shift_id = self.env.context.get('default_shift_id')
        if shift_id:
            shift = self.env['clinic.shift'].browse(shift_id)
            if shift.exists() and shift.doctor_ids:
                return shift.doctor_ids
        return self.env['clinic.doctor'].search([])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('clinic.appointment') or 'New'
        return super().create(vals_list)

    def action_create_invoice(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only scheduled appointments can be invoiced.'))
            if rec.invoice_id:
                raise UserError(_('Invoice already created for this appointment.'))
            partner = rec.patient_id.partner_id
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': rec.patient_id.name,
                    'phone': rec.patient_id.phone,
                })
                rec.patient_id.partner_id = partner
            invoice_line_vals = {
                'name': _('Consultation - %s') % rec.doctor_id.name,
                'quantity': 1,
                'price_unit': rec.visit_fee,
            }
            if rec.product_id:
                invoice_line_vals['product_id'] = rec.product_id.id
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'patient_id': rec.patient_id.id,
                'appointment_id': rec.id,
                'doctor_id': rec.doctor_id.id,
                'shift_id': rec.shift_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, invoice_line_vals)],
            })
            rec.write({'invoice_id': invoice.id, 'state': 'invoiced'})

    def action_waiting(self):
        for rec in self:
            if rec.state != 'invoiced':
                raise UserError(_('Only invoiced appointments can be checked in.'))
            rec.state = 'waiting'

    def action_start(self):
        for rec in self:
            if rec.state != 'waiting':
                raise UserError(_('Only waiting appointments can be started.'))
            rec.state = 'in_progress'

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only in-progress appointments can be completed.'))
            rec.state = 'done'

    def action_refund(self):
        for rec in self:
            if rec.state not in ('invoiced', 'in_progress', 'done'):
                raise UserError(_('Only invoiced, in-progress, or done appointments can be refunded.'))
            if not rec.invoice_id:
                raise UserError(_('No invoice found to refund.'))
            if rec.refund_invoice_id:
                raise UserError(_('Refund already processed for this appointment.'))
            refund = rec.invoice_id._reverse_moves(cancel=True)
            rec.write({'refund_invoice_id': refund.id, 'state': 'cancelled'})

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'invoiced', 'waiting'):
                raise UserError(_('Only scheduled, invoiced, or waiting appointments can be cancelled.'))
            rec.state = 'cancelled'

    def action_reset(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled appointments can be reset.'))
            rec.state = 'draft'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoice'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_id.id,
            }

    def action_view_refund(self):
        self.ensure_one()
        if self.refund_invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Refund'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.refund_invoice_id.id,
            }
