{
    "name": "Automated Stock Valuation Engine",
    "version": "18.0.2.1.0",
    "summary": "Full Automated Stock Valuation for Community Edition",
    "description": """
        Handles all stock valuation journal entries automatically:
        - Purchase: GR/IR (Goods Receipt / Invoice Receipt) clearing
        - Sale: COGS recognition and output account clearing
        - Manufacturing: raw material consumption and finished goods
        - Inventory adjustments (shrinkage / losses)
        - Landed Costs allocation
    """,
    "category": "Accounting",
    "author": "Abdelrahman Ashraf",
    "website": "https://www.linkedin.com/in/abdelrahman-ashraf-ahmed-ahmed/",
    "images": ["static/description/screenshots/icon.png"],
    "depends": [
        "stock",
        "account",
        "purchase",
        "sale_management",
        "mrp",
        "stock_landed_costs",
    ],
    "data": [
        # "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/product_category_views.xml",
    ],
    "post_init_hook": "setup_accounts",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
