from odoo import models, fields,api
import base64
# from base64 import b64encode
import warnings
import qrcode
from io import BytesIO

class AccountMove(models.Model):
    _inherit = 'account.move'


    qr_image = fields.Binary("QR Code")#, compute='_generate_qr_code')
    einv_amount_sale_total = fields.Monetary(string="Amount sale total", compute="_compute_total", store='True',)
    einv_sa_delivery_date = fields.Date(string='Delivery Date', default=fields.Date.context_today, copy=False)
    einv_sa_show_delivery_date = fields.Boolean(compute='_compute_einv_show_delivery_date')
    einv_sa_qr_code_str = fields.Char(string='Zatka QR Code', compute='_compute_eniv_qr_code_str')
    einv_sa_confirmation_datetime = fields.Datetime(string='Confirmation Date', readonly=True, copy=False)

    einv_sa_confirmed = fields.Boolean(compute='_compute_einv_sa_confirmation_datetime', store=True)


    def _compute_einv_sa_confirmation_datetime(self):
        for move in self:
            move.einv_sa_confirmed = False
            if not move.einv_sa_confirmation_datetime and move.state == 'posted' \
                    and move.move_type in ('out_invoice', 'out_refund'):
                move.einv_sa_confirmed = True
                move.einv_sa_confirmation_datetime = move.create_date

    @api.depends('country_code', 'move_type')
    def _compute_einv_show_delivery_date(self):
        for move in self:
            # move.einv_sa_show_delivery_date = False
            move.einv_sa_show_delivery_date = move.country_code == 'US' and move.move_type in (
                'out_invoice', 'out_refund')

    @api.depends('amount_total', 'amount_untaxed', 'einv_sa_confirmation_datetime', 'company_id', 'company_id.vat')
    def _compute_eniv_qr_code_str(self):
        """ Generate the qr code for Saudi e-invoicing. Specs are available at the following link at page 23
        https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20210528_ZATCA_Electronic_Invoice_Security_Features_Implementation_Standards_vShared.pdf
        https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/QRCodeCreation.pdf
        """

        def get_qr_encoding(tag, field):
            company_name_byte_array = field.encode('UTF-8')
            company_name_tag_encoding = tag.to_bytes(length=1, byteorder='big')
            company_name_length_encoding = len(company_name_byte_array).to_bytes(length=1, byteorder='big')
            return company_name_tag_encoding + company_name_length_encoding + company_name_byte_array

        for record in self:
            qr_code_str = ''
            if record.einv_sa_confirmation_datetime or record.company_id.vat:
                seller_name_enc = get_qr_encoding(1, record.company_id.display_name)
                company_vat_enc = get_qr_encoding(2, record.company_id.vat)
                time_sa = fields.Datetime.context_timestamp(self.with_context(tz='Asia/Riyadh'),
                                                            record.einv_sa_confirmation_datetime)
                timestamp_enc = get_qr_encoding(3, time_sa.isoformat())
                invoice_total_enc = get_qr_encoding(4, str(record.amount_total))
                total_vat_enc = get_qr_encoding(5, str(record.currency_id.round(
                    record.amount_total - record.amount_untaxed)))

                str_to_encode = seller_name_enc + company_vat_enc + timestamp_enc + invoice_total_enc + total_vat_enc
                qr_code_str = base64.b64encode(str_to_encode).decode('UTF-8')
            record.einv_sa_qr_code_str = qr_code_str
