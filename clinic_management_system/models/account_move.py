from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    patient_id = fields.Many2one("clinic.patient", string="Patient")
    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    doctor_id = fields.Many2one("clinic.doctor", string="Doctor")
    shift_id = fields.Many2one("clinic.shift", string="Shift")
    shift_state = fields.Selection(related='shift_id.state', string='Shift State', readonly=True)

