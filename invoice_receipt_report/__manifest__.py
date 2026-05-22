{
    "name": "Invoice Receipt Report",
    'version': "18.0",
    "summary": "Invoice Receipt Report",
    'website': 'https://www.linkedin.com/in/samah-kandil-odoo',
    'author': 'Samah Kandil',
    'support': 'samahqandeel22@gmail.com',

    "depends": [
        'base',
        'account',
    ],

    "data": [
        "views/account_move_view.xml",
        "views/report.xml",

    ],

    'images': ['static/description/banner.png'],
    'license': "OPL-1",
    'installable': True,
    'application': True,
    'auto_install': False,

}
