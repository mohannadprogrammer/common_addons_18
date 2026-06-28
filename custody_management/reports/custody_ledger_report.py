# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CustodyLedgerReport(models.AbstractModel):
    _name = 'report.custody_management.report_custody_ledger'
    _description = 'Custody Ledger Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['custody.custody'].search([], order='request_date')
        return {
            'doc_ids': docs.ids,
            'doc_model': 'custody.custody',
            'docs': docs,
            'data': data,
        }


class CustodyLedgerReportWizard(models.TransientModel):
    _name = 'report.custody_ledger.wizard'
    _description = 'Custody Ledger Report Wizard'

    def action_print_report(self):
        return self.env.ref('custody_management.action_report_custody_ledger').report_action(self)
