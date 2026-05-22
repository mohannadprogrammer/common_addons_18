from odoo import models , fields , api , _
# Extend Invoice model
class AccountMove(models.Model):
    _inherit = "account.move"

    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient"
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment"
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor"
    )
    shift_id = fields.Many2one(
        "clinic.shift",
        string="Shift"
    )
    