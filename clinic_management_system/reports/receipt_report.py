from odoo import api, models


class ReportClinicReceipt(models.AbstractModel):
    _name = 'report.clinic_management_system.receipt_invoice'
    _description = 'Clinic Receipt Invoice'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        formatted = {}
        for doc in docs:
            lines = []
            for line in doc.invoice_line_ids:
                lines.append({
                    'name': line.name,
                    'quantity': line.quantity,
                    'amount': self._format_amount(line.price_subtotal, doc.currency_id),
                })
            formatted[doc.id] = {
                'lines': lines,
                'subtotal': self._format_amount(doc.amount_untaxed, doc.currency_id),
                'tax': self._format_amount(doc.amount_tax, doc.currency_id) if doc.amount_tax else '',
                'total': self._format_amount(doc.amount_total, doc.currency_id),
                'residual': self._format_amount(doc.amount_residual, doc.currency_id) if doc.state == 'posted' and doc.payment_state != 'paid' else '',
            }
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
            'formatted': formatted,
        }

    def _format_amount(self, amount, currency):
        if not currency:
            return f'{amount:.2f}'
        symbol = currency.symbol or ''
        if currency.position == 'after':
            return f'{amount:.2f} {symbol}'
        return f'{symbol}{amount:.2f}'
