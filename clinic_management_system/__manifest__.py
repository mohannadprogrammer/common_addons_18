{
    'name': 'Clinic Appointment Management',
    'version': '18.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Manage clinic appointments by shifts with doctor billing',
    'description': """
        Clinic Appointment Management
        ==============================
        - Day/Night shift management
        - Doctor assignment per shift
        - Patient appointment with Kanban view
        - Invoice generation per appointment visit
        - Doctor billing (percentage or fixed) on shift close
    """,
    'author': 'Clinic Module',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequance_data.xml',
        'views/appointment_veiws.xml',
        'views/clinic_doctor_views.xml',
        'views/clinic_shift_views.xml',
        'views/clinic_patient_views.xml',
        'views/menu_views.xml',
        'wizard/close_shift_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}