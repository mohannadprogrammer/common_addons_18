# -*- coding: utf-8 -*-
{
    'name': "Custody Management",
    'summary': "Manage employee cash custody, advances, and expense settlements",
    'description': """
Money Custody Management System
================================
Manage employee cash custody (cash advances).
Track outstanding balances.
Record expenses against custody.
Settle or close custody.
Integrate with Accounting.
Provide approvals and audit trails.
    """,
    'author': "Eng. Mohannad Waheed Ahmed",
    'website': "https://www.mhannadwaheed.site",
    'category': 'Accounting',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'hr', 'mail' , 'base_accounting_kit'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/custody_sequence.xml',
        'data/custody_data.xml',
        'wizards/custody_cash_return_wizard_view.xml',
        'wizards/custody_cancel_wizard_view.xml',
        'views/custody_view.xml',
        'views/settlement_view.xml',
        'views/custody_payment_view.xml',
        'views/report_views.xml',
        'views/res_users_view.xml',
        'views/res_config_settings_view.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
