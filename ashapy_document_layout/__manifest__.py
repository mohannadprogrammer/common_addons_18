{
    'name': 'Ashapy Document Layout',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Ashapy Solar Energy Systems document layout for invoices and reports',
    'description': """
        Adds the Ashapy document layout option to Odoo's report layout settings.
        Features:
        - Centered company identity with Arabic/English branding
        - Contact information in header
        - Support info in footer
        - Clean monochrome grid-based invoice formatting
    """,
    'author': 'Ashapy',
    'website': '',
    'depends': ['web', 'account'],
    'data': [
        'report/ashapy_layout.xml',
        # 'report/ashapy_invoice_report.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'ashapy_document_layout/static/src/css/fonts.css',
        ]
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
