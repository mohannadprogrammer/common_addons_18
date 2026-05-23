from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    patient_id = fields.Many2one("clinic.patient", string="Patient")
    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    doctor_id = fields.Many2one("clinic.doctor", string="Doctor")
    shift_id = fields.Many2one("clinic.shift", string="Shift")
    shift_state = fields.Selection(related='shift_id.state', string='Shift State', readonly=True)

    def write(self, vals):
        for rec in self:
            if rec.shift_id and rec.shift_id.state == 'closed':
                raise UserError(_('Cannot modify an invoice linked to a closed shift.'))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.shift_id and rec.shift_id.state == 'closed':
                raise UserError(_('Cannot delete an invoice linked to a closed shift.'))
        return super().unlink()
