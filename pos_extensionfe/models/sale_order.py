# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import Warning, UserError, ValidationError

import datetime

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_employee_id = fields.Many2one('hr.employee', string='Vendedor', copy=True
                                    , help='Empleado que levantó la cotización')
    x_document_type = fields.Selection(string="Tipo Comprobante",
                                        selection=[('FE', 'Factura Electrónica'),
                                                ('TE', 'Tiquete Electrónico'), ], 
                                        )    
    x_sent_to_pos = fields.Boolean(default=False, )
    x_date_sent_pos = fields.Datetime(string="Fecha Enviado", )


    def send_to_pos(self):
        if self.x_sent_to_pos:
           raise ValidationError('Este presupuesto ya había sido enviado a caja')
        
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise ValidationError(_('It is not allowed to confirm an order in the following states: %s') % (', '.join(self._get_forbidden_state_confirm())))

        if not self.x_document_type:
            raise ValidationError('Debe seleccionar el tipo de comprobante que necesita el cliente')

        pos_config = self.env['pos.config'].search([('company_id','=', self.company_id.id),('active','=',True)], limit=1)
        if not pos_config:
            raise ValidationError('No existe un punto de venta definido en la compañía: %s' % (self.company_id.name))
        opened_session = self.env['pos.session'].search([('config_id','=',pos_config.id), ('state', '=', 'opened')], order='id desc')

        if not opened_session:
            raise ValidationError('No existe ninguna sesión de Punto de Venta abierta, en el punto de venta: %s ' % (pos_config.name))

        data_vals = {
            'name': '/',
            'session_id': opened_session[0].id,
            'user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'date_order': datetime.date.today(),
            'state': 'draft',
            'partner_id': self.partner_id.id,
            'x_name_to_print': self.partner_id.name,
            'x_document_type': self.x_document_type,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'pricelist_id': self.pricelist_id.id,
            'currency_rate': self.currency_rate,
            'crm_team_id': self.team_id.id,
            'note': self.note,
            'employee_id': self.x_employee_id.id,
            'x_sale_order_id': self.id
        }

        # pos_order = self.create_pos_order(data_vals)
        # crea el movimmiento en pos_order
        pos_order = self.env['pos.order'].create(data_vals)
        pos_order_id = pos_order.id
        for line in self.order_line:
            line_vals = {
                'order_id': pos_order_id,
                'full_product_name': line.name,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
                'price_subtotal_incl': line.price_total,
                'discount': line.discount,
                'company_id': line.company_id.id,
                'product_id': line.product_id.id,
                'qty': line.product_uom_qty,
            }
            res = self.env['pos.order.line'].create(line_vals)

        self.write({'state':'sale', 'date_order': fields.Datetime.now(), 'x_sent_to_pos': True, 'x_date_sent_pos': fields.Datetime.now() })

        # return pos_order

    # def create_pos_order(self, data_vals):
    #     res = self.env['pos.order'].create(data_vals)
    #     return res

    # def create_pos_order_line(self, so_line, order_id):
    #     line_vals = {
    #         'order_id': order_id,
    #         'full_product_name': so_line.name,
    #         'price_unit': so_line.price_unit,
    #         'price_subtotal': so_line.price_subtotal,
    #         'price_subtotal_incl': so_line.price_total,
    #         'discount': so_line.discount,
    #         'company_id': so_line.company_id.id,
    #         'product_id': so_line.product_id.id,
    #         'qty': so_line.product_uom_qty,
    #     }

    #     res = self.env['pos.order.line'].create(line_vals)
    #     return res
