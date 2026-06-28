# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )
    is_custody_user = fields.Boolean(string='Custody User',
                                     help='Can create and manage custodies')
    is_custody_approver = fields.Boolean(string='Custody Approver',
                                         help='Can approve custodies at manager level')
    is_custody_finance_approver = fields.Boolean(string='Custody Finance Approver',
                                                 help='Can approve custodies at finance level')
    custody_approval_limit = fields.Monetary(string='Custody Approval Limit',
                                             currency_field='company_currency_id',
                                             help='Maximum custody amount this user can approve')
    custody_team_leader_id = fields.Many2one('res.users', string='Custody Team Leader',
                                             help='Team leader responsible for this user\'s custodies')
