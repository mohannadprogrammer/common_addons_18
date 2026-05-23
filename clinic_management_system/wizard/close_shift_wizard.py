from odoo import models, fields, api, _


class CloseShiftWizard(models.TransientModel):
    _name = 'close.shift.wizard'
    _description = 'Close Shift Wizard'

    shift_id = fields.Many2one('clinic.shift', string='Shift', required=True, readonly=True)
    shift_name = fields.Char(string='Shift Reference', related='shift_id.name', readonly=True)
    total_revenue = fields.Monetary(string='Total Revenue', readonly=True, currency_field='currency_id')
    total_doctor_billing = fields.Monetary(string='Total Doctor Billing', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    billing_line_ids = fields.One2many('close.shift.billing.line', 'wizard_id', string='Doctor Billing Lines')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        shift_id = self.env.context.get('default_shift_id')
        if shift_id:
            shift = self.env['clinic.shift'].browse(shift_id)
            invoiced = shift.appointment_ids.filtered(
                lambda a: a.invoice_id and a.invoice_id.state == 'posted'
                          and not (a.refund_invoice_id and a.refund_invoice_payment_state == 'paid')
            )
            res['total_revenue'] = sum(a.invoice_id.amount_total for a in invoiced)
            lines = []
            for doctor in shift.doctor_ids:
                doctor_appointments = invoiced.filtered(lambda a: a.doctor_id == doctor)
                amount = sum(doctor.compute_doctor_earning(a.visit_fee) for a in doctor_appointments)
                lines.append((0, 0, {
                    'doctor_id': doctor.id,
                    'amount': amount,
                }))
            res['billing_line_ids'] = lines
            res['total_doctor_billing'] = sum(vals['amount'] for _, _, vals in lines)
        return res

    def action_confirm(self):
        shift = self.shift_id
        bills = self.env['account.move']
        for line in self.billing_line_ids:
            if line.amount:
                line_vals = {
                    'name': _('Consultation fees - Shift %s') % shift.name,
                    'quantity': 1,
                    'price_unit': line.amount,
                }
                if line.doctor_id.product_id:
                    line_vals['product_id'] = line.doctor_id.product_id.id
                bill = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'partner_id': line.doctor_id.partner_id.id,
                    'invoice_date': fields.Date.today(),
                    'shift_id': shift.id,
                    'doctor_id': line.doctor_id.id,
                    'ref': _('Doctor billing - %s - %s') % (shift.name, line.doctor_id.name),
                    'invoice_line_ids': [(0, 0, line_vals)],
                })
                bills |= bill
        shift.write({'end_time': fields.Datetime.now(), 'state': 'closed'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Doctor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bills.ids)],
        }


class CloseShiftBillingLine(models.TransientModel):
    _name = 'close.shift.billing.line'
    _description = 'Close Shift Billing Line'

    wizard_id = fields.Many2one('close.shift.wizard', string='Wizard', required=True, ondelete='cascade')
    doctor_id = fields.Many2one('clinic.doctor', string='Doctor', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
