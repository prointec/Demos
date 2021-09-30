# -*- coding: utf-8 -*-

from odoo import fields, models, api, _ 
from odoo.tools import float_is_zero, float_compare,  DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT

from odoo.exceptions import Warning, RedirectWarning, UserError, ValidationError

# from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    x_payment_method_id = fields.Many2one("xpayment.method", string="Método pago DGT")


class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def _default_order_total(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['pos.order'].browse(active_id)
            return order.amount_total
        return False

    def _default_amount(self):
        order_amount = super(PosMakePayment, self)._default_amount()
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['pos.order'].browse(active_id)
            return order_amount + order.x_amount_return
        return False

    amount = fields.Float(digits=0, required=True, default=_default_amount)
    x_payment_return = fields.Float(string='Vuelto', digits=0)   # El vuelto
    x_order_total = fields.Float(string='Order Total', default=_default_order_total)


    @api.onchange('amount')
    def _onchange_xpos_amount_payment(self):
        self.x_payment_return = None
        if self.amount < 0:
            self.x_payment_return = abs(self.amount)


    @api.onchange('x_payment_return')
    def _onchange_amount_payment_return(self):
        if self.x_payment_return > 0:
            self.amount = -abs(self.x_payment_return)


    def check(self):
        """Check the order:
        if the order is not paid: continue payment,
        if the order is paid print ticket.
        """
        self.ensure_one()

        order = self.env['pos.order'].browse(self.env.context.get('active_id', False))
        currency = order.currency_id
        init_data = self.read()[0]
        
        current_session = order.current_cashier_session()

        payment_amount = order._get_rounded_amount(init_data['amount'])        
        if order.amount_total < 0:
            # es una devolución
            payment_net = payment_amount
        else:
            # es una factura 
            amount_return = order._get_rounded_amount(order.x_amount_return)
            payment_net = payment_amount - amount_return

            if amount_return:
                applied_return = min(amount_return, payment_amount)
                order.x_amount_return -= applied_return
                cash_statement = current_session.cash_register_id
                if cash_statement.state == 'confirm':
                    raise UserError(_("You cannot put/take money in/out for a bank statement which is closed."))
                if order.name == '/':
                    order.name = order.config_id.sequence_id._next()
                values = {
                    'date': cash_statement.date,
                    'statement_id': cash_statement.id,
                    'journal_id': cash_statement.journal_id.id,
                    'amount': applied_return, 
                    'payment_ref': 'Ingreso de vuelto ' + (order.pos_reference if order.pos_reference else order.name),
                    'x_source' : 'express',
                    'x_source_id' : order.id,                
                    'ref': current_session.name + ' - ' + order.name,
                }
                account = cash_statement.journal_id.company_id.transfer_account_id
                self.env['account.bank.statement.line'].with_context(counterpart_account_id=account.id).create(values)

                if applied_return < amount_return:
                    return self.launch_payment()

        if not float_is_zero(payment_net, precision_rounding=currency.rounding):
            order.add_payment({
                'pos_order_id': order.id,
                'amount': payment_net,
                'name': init_data['payment_name'],
                'payment_method_id': init_data['payment_method_id'][0],
            })
        
        # si la orden está pagada totalmente termina, sino vuelve a llamar a pagos
        if order._is_pos_order_paid():
            order.session_id = current_session.id 
            return order.process_pos_order_completed()

        return self.launch_payment()


    def launch_payment(self):
        amount = self._default_amount()
        name = 'Pago'
        if amount < 0:
            name = 'VUELTO'

        return {
            'name': name,
            'view_mode': 'form',
            'res_model': 'pos.make.payment',
            'view_id': False,
            'target': 'new',
            'views': False,
            'type': 'ir.actions.act_window',
            'context': self.env.context,
        }
