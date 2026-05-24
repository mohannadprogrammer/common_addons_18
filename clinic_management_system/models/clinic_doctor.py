from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ClinicDoctor(models.Model):
    _name = 'clinic.doctor'
    _description = 'Clinic Doctor'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Doctor Name', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Related Contact', required=True
    )
    user_id = fields.Many2one('res.users', string='Related User')
    specialization = fields.Char(string='Specialization')
    product_id = fields.Many2one('product.product', string='Service Product',
                                  domain="[('type', '=', 'service')]",
                                  help='Service product used for appointments with this doctor')
    active = fields.Boolean(default=True)

    # Billing configuration
    billing_type = fields.Selection(
        [('percentage', 'Percentage of Visit Fee'), ('fixed', 'Fixed Amount per Visit')],
        string='Billing Type',
        required=True,
        default='percentage',
        tracking=True,
    )
    billing_percentage = fields.Float(
        string='Billing Percentage (%)',
        help='Percentage of the appointment invoice amount paid to the doctor',
    )
    billing_fixed_amount = fields.Float(
        string='Fixed Amount per Visit',
        help='Fixed amount paid to the doctor per appointment visit',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # Related appointments
    appointment_ids = fields.One2many(
        'clinic.appointment', 'doctor_id', string='Appointments'
    )
    appointment_count = fields.Integer(
        string='Appointments', compute='_compute_appointment_count'
    )

    # Related bills
    bill_ids = fields.One2many('account.move', 'doctor_id', string='Bills')
    bill_count = fields.Integer(
        string='Bills', compute='_compute_bill_count'
    )

    @api.depends('appointment_ids')
    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = len(rec.appointment_ids)

    @api.depends('bill_ids')
    def _compute_bill_count(self):
        for rec in self:
            rec.bill_count = len(rec.bill_ids)

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('doctor_id', '=', self.id)],
        }

    @api.constrains('billing_percentage')
    def _check_billing_percentage(self):
        for rec in self:
            if rec.billing_type == 'percentage' and not (0 < rec.billing_percentage <= 100):
                raise ValidationError('Billing percentage must be between 0 and 100.')

    @api.constrains('billing_fixed_amount')
    def _check_billing_fixed(self):
        for rec in self:
            if rec.billing_type == 'fixed' and rec.billing_fixed_amount <= 0:
                raise ValidationError('Fixed billing amount must be greater than 0.')

    def compute_doctor_earning(self, visit_fee):
        """Compute doctor earning based on billing config."""
        self.ensure_one()
        if self.billing_type == 'percentage':
            return visit_fee * (self.billing_percentage / 100.0)
        return self.billing_fixed_amount