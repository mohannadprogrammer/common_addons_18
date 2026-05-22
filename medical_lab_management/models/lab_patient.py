# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Gayathri V (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class LabPatient(models.Model):
    """
        This class represents Patient information in a laboratory system.
    """
    _name = 'lab.patient'
    _rec_name = 'name'
    _description = 'Patient'
    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning(vals_list)
        return super().create(vals_list)

    name = fields.Char(string="Name" , required=True)
    patient_id = fields.Many2one('res.partner', string='Partner',
                              required=True)
    patient_image = fields.Binary(string='Photo',
                                  help="Profile image for patient")
    patient = fields.Char(string='Patient', readonly=True)
    patient_sq = fields.Char(string='Patient SQ', default=lambda self: _('New'), readonly=True)
    title = fields.Selection([
        ('ms', 'Miss'),
        ('mister', 'Mister'),
        ('mrs', 'Mrs'),
    ], string='Title', default='mister', required=True)
    emergency_contact_id = fields.Many2one(
        'res.partner', string='Emergency Contact',
        help="Emergency contact number for patient")
    gender = fields.Selection(
        [('m', 'Male'), ('f', 'Female')], string='Gender',help="Gender of the patient", required=True)
    dob = fields.Date(string='Date Of Birth', help="Date of birth of patient")
    age = fields.Char(string='Age', help="Age of the patient",
                      compute='compute_age', store=True)
    blood_group = fields.Selection(
        [('A+', 'A+ve'), ('B+', 'B+ve'), ('O+', 'O+ve'),
         ('AB+', 'AB+ve'), ('A-', 'A-ve'), ('B-', 'B-ve'), ('O-', 'O-ve'),
         ('AB-', 'AB-ve')], 'Blood Group')
    id_proof_number = fields.Char(string='ID Proof Number',
                                  help="Fill id proof information")
    note = fields.Text(string='Note')
    date = fields.Datetime(string='Date Requested',
                           default=lambda s: fields.Datetime.now(),
                           help="Requested date of lab request")
    phone = fields.Char(string="Phone", 
                        help="Phone number of patient")
    email = fields.Char(string="Email",help="Email of patient")

    @api.depends('dob')
    def compute_age(self):
        """
           Compute the patient's age based on their date of birth.
           :param self: The record itself.
        """
        for data in self:
            if data.dob:
                dob = fields.Datetime.from_string(data.dob)
                date = fields.Datetime.from_string(data.date)
                delta = relativedelta(date, dob)
                data.age = str(delta.years) + ' ' + 'years'
            else:
                data.age = ''

    @api.model_create_multi
    def create(self, vals_list):
        """
            Create a new patient record and generate a unique patient ID
            :param self: The record itself.
            :param dict vals_list: A dictionary of values for creating the patient record.
            :return: The created patient record.
            :rtype: LabPatient
        """
        for vals in vals_list:
            sequence = self.env['ir.sequence'].next_by_code('lab.patient')
            vals['patient_sq'] = sequence or _('New')
        return super().create(vals_list)

    @api.onchange('patient')
    def detail_get(self):
        """
           Update patient contact details based on the selected partner
           :param self: The record itself.
        """
        self.phone = self.patient.phone
        self.email = self.patient.email
