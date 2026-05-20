# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock Accounting 1212",
    'version': "1.0",
    'category': 'Inventory/Inventory',
    'summary': "Bridge between Stock and Accounting",
    'description': """
Filters the stock lines out of the reconciliation widget
    """,
    'depends': ['stock_account'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
