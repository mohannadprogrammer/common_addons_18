from odoo import models, fields, api, _


class ClinicPatient(models.Model):
    _name = "clinic.patient"
    _description = "Clinic Patient"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True, tracking=True)
    phone = fields.Char(string="Phone", required=True)
    age = fields.Integer(string="Age")
    gender = fields.Selection([
        ("male", "Male"),
        ("female", "Female"),
    ], string="Gender")
    address = fields.Text(string="Address")
    date_of_birth = fields.Date(string="Date of Birth")
    partner_id = fields.Many2one('res.partner', string='Related Contact')

    invoice_ids = fields.One2many("account.move", "patient_id", string="Invoices")
    appointment_ids = fields.One2many("clinic.appointment", "patient_id", string="Appointments")
    appointment_count = fields.Integer(string='Appointments', compute='_compute_appointment_count')

    @api.depends('appointment_ids')
    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = len(rec.appointment_ids)
