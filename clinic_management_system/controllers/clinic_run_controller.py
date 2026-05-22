import json

from odoo import http
from odoo.http import request


class ClinicRunController(http.Controller):

    @http.route('/clinic_run/get_shifts', type='http', auth='user', methods=['POST'], csrf=False)
    def get_shifts(self):
        shifts = request.env['clinic.shift'].search([], order='date desc, id desc')
        stats = {'total': 0, 'draft': 0, 'open': 0, 'closed': 0}
        result = []
        for shift in shifts:
            stats['total'] += 1
            stats[shift.state] += 1
            result.append({
                'id': shift.id,
                'name': shift.name,
                'date': shift.date and shift.date.strftime('%Y-%m-%d') or '',
                'shift_type': shift.shift_type,
                'state': shift.state,
                'appointment_count': shift.appointment_count,
                'doctor_names': ', '.join(shift.doctor_ids.mapped('name')),
            })
        return request.make_json_response({'shifts': result, 'stats': stats})
