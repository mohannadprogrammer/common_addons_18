from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_patient = fields.Boolean(string='Is Patient', default=False)
    patient_appointment_ids = fields.One2many(
        'clinic.appointment', 'patient_id', string='Appointments'
    )
    appointment_count = fields.Integer(
        string='Appointments', compute='_compute_appointment_count'
    )

    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = len(rec.patient_appointment_ids)