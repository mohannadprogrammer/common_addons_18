# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    custody_id = fields.Many2one('custody.custody', string='Custody', readonly=True, copy=False)
    settlement_id = fields.Many2one('custody.settlement', string='Settlement', readonly=True, copy=False)
    payment_id = fields.Many2one('custody.payment', string='Custody Payment', readonly=True, copy=False)
