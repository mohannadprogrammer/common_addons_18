# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AuditTrailReport(models.AbstractModel):
    _name = 'report.custody_management.report_audit_trail'
    _description = 'Audit Trail Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if data and isinstance(data, dict) and data.get('date_from'):
            domain = [('request_date', '>=', data.get('date_from')),
                      ('request_date', '<=', data.get('date_to') or fields.Date.today())]
            if data.get('employee_id'):
                domain.append(('employee_id', '=', data['employee_id']))
            if data.get('custody_id'):
                domain.append(('id', '=', data['custody_id']))
            docs = self.env['custody.custody'].search(domain, order='request_date')
        else:
            docs = self.env['custody.custody'].browse(docids)
        messages = self.env['mail.message'].search([
            ('model', '=', 'custody.custody'),
            ('res_id', 'in', docs.ids),
        ], order='date desc')
        return {
            'doc_ids': docs.ids,
            'doc_model': 'custody.custody',
            'docs': docs,
            'messages': messages,
            'data': data,
        }


class AuditTrailReportWizard(models.TransientModel):
    _name = 'report.audit_trail.wizard'
    _description = 'Audit Trail Report Wizard'

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
        return self.env.ref('custody_management.action_report_audit_trail').report_action(self, data=data)
