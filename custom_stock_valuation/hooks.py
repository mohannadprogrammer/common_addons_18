import logging

from odoo.fields import Command

_logger = logging.getLogger(__name__)

# Chart-of-accounts seed data: (field_name, account_name, code, account_type)
# Codes are illustrative defaults — adapt to your CoA if needed.
ACCOUNT_SEED = [
    ("property_stock_valuation_account_id", "Stock Valuation", "151000", "asset_current"),
    ("property_stock_input_account_id", "Stock Input (GRNI)", "251000", "liability_current"),
    ("property_stock_output_account_id", "Stock Output (Interim)", "152000", "asset_current"),
    ("property_account_expense_categ_id", "Cost of Goods Sold", "600000", "expense"),
    ("property_production_account_id", "Production / WIP Account", "153000", "asset_current"),
    ("property_inventory_loss_account_id", "Inventory Loss", "620000", "expense"),
]


def setup_accounts(env):
    """
    Post-init hook (Odoo 19 signature: receives ``env`` directly).

    Creates or retrieves the standard stock valuation accounts and assigns
    them to every company (company-level defaults) and to the default 'All'
    product category.

    Existing accounts are preserved — only missing fields are populated.

    Odoo 19 note: ``account.account`` uses ``company_ids`` (Many2many) instead
    of the legacy ``company_id`` (Many2one).
    """
    companies = env["res.company"].search([])

    for company in companies:
        _setup_company_accounts(env, company)

    _setup_category_accounts(env)


def _setup_company_accounts(env, company):
    """Seed accounts for a single company, skipping fields already set."""
    _logger.info("Setting up stock valuation accounts for company '%s'.", company.name)

    def _get_or_create_account(name, code, acc_type):
        acc = env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", company.id)],
            limit=1,
        )
        if not acc:
            try:
                acc = env["account.account"].create(
                    {
                        "name": name,
                        "code": code,
                        "account_type": acc_type,
                        "company_ids": [Command.link(company.id)],
                    }
                )
                _logger.info("Created account [%s] %s for company '%s'.", code, name, company.name)
            except Exception as exc:
                _logger.error(
                    "Could not create account %s (%s) for company '%s': %s",
                    code, name, company.name, exc,
                )
                return env["account.account"].browse()
        return acc

    accounts = {}
    for field_name, name, code, acc_type in ACCOUNT_SEED:
        if getattr(company, field_name):
            _logger.info(
                "Account '%s' already set on company '%s', skipping.", field_name, company.name
            )
            continue
        acc = _get_or_create_account(name, code, acc_type)
        if not acc:
            _logger.error(
                "Setup aborted for company '%s': could not obtain account '%s' [%s].",
                company.name, name, code,
            )
            return
        accounts[field_name] = acc.id

    if accounts:
        company.write(accounts)
        _logger.info(
            "Custom Stock Valuation Engine: %d accounts linked to company '%s'.",
            len(accounts), company.name,
        )


def _setup_category_accounts(env):
    """Seed account overrides on the 'All' product category, preserving existing."""
    categ = env.ref("product.product_category_all", raise_if_not_found=False)
    if not categ:
        _logger.warning(
            "product.product_category_all not found — category-level accounts were NOT set."
        )
        return

    missing = {}
    for field_name, name, code, acc_type in ACCOUNT_SEED:
        if getattr(categ, field_name):
            _logger.info(
                "Account '%s' already set on 'All' category, skipping.", field_name
            )
            continue
        acc = env["account.account"].search(
            [("code", "=", code)], limit=1
        )
        if acc:
            missing[field_name] = acc.id
        else:
            _logger.warning(
                "Account '%s' [%s] not found for 'All' category setup.", name, code
            )

    if missing:
        categ.write(missing)
        _logger.info(
            "Custom Stock Valuation Engine: %d accounts linked to product category 'All'.",
            len(missing),
        )
