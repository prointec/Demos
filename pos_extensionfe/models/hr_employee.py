# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class hrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_password = fields.Char(string='Contraseña', copy=False)
    x_is_cashier = fields.Boolean(string='Cajero', copy=False)
    x_cash_starting_amount = fields.Float(string='Monto Apertura Caja', copy=False,
                                        help='Establece el monto de apertura de caja para el cajero')

    @api.onchange('x_cash_starting_amount')
    def onchange_x_cash_starting_amount(self):
        self.ensure_one()
        if self.x_cash_starting_amount < 0:
            self.x_cash_starting_amount = abs(self.x_cash_starting_amount)
        