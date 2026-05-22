from odoo import api, models


class ReportClinicReceipt(models.AbstractModel):
    _name = 'report.clinic_management_system.receipt_invoice'
    _description = 'Clinic Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
        }
