# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SettlementReport(models.AbstractModel):
    _name = 'report.custody_management.report_settlement'
    _description = 'Settlement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if data and isinstance(data, dict) and data.get('date_from'):
            domain = [('expense_date', '>=', data.get('date_from')),
                      ('expense_date', '<=', data.get('date_to') or fields.Date.today())]
            if data.get('employee_id'):
                domain.append(('employee_id', '=', data['employee_id']))
            if data.get('custody_id'):
                domain.append(('custody_id', '=', data['custody_id']))
            docs = self.env['custody.settlement'].search(domain, order='expense_date')
        else:
            docs = self.env['custody.settlement'].browse(docids)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'custody.settlement',
            'docs': docs,
            'data': data,
        }


class SettlementReportWizard(models.TransientModel):
    _name = 'report.settlement.wizard'
    _description = 'Settlement Report Wizard'

    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee')
    custody_id = fields.Many2one('custody.custody', string='Custody')

    def action_print_report(self):
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'employee_id': self.employee_id.id,
            'custody_id': self.custody_id.id,
        }
        return self.env.ref('custody_management.action_report_settlement').report_action(self, data=data)
