# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

from odoo.exceptions import Warning, UserError, ValidationError


class PosSessionInherit(models.Model):
    _inherit = 'pos.session'

    x_employee_id = fields.Many2one('hr.employee', string='Cajero', index=True)

    x_cash_register_total_cash_payments = fields.Monetary(
        compute='_compute_cash_balance',
        string="+ Cash payments",
        help="Total of cash payments",
        readonly=True)
    x_cash_register_cashier_moves = fields.Monetary(
        compute='_compute_cash_balance',
        string='+ Cash in/out',
        help="In/Out movements of cash",
        readonly=True)
    

    @api.depends('payment_method_ids', 'order_ids', 'cash_register_balance_start', 'cash_register_id')
    def _compute_cash_balance(self):
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered('is_cash_count')[:1]
            # session.x_cash_register_cashier_moves = sum( l.amount for l in session.line_ids)
            session.x_cash_register_cashier_moves = sum( session.cash_register_id.mapped('line_ids').filtered(lambda cash_io : cash_io.x_source).mapped('amount') )
            if cash_payment_method:
                total_cash_payment = sum(session.order_ids.mapped('payment_ids').filtered(lambda payment: payment.payment_method_id == cash_payment_method).mapped('amount'))
                session.cash_register_total_entry_encoding = session.cash_register_id.total_entry_encoding + (
                    0.0 if session.state == 'closed' else total_cash_payment
                )
                session.cash_register_balance_end = session.cash_register_balance_start + session.cash_register_total_entry_encoding
                session.cash_register_difference = session.cash_register_balance_end_real - session.cash_register_balance_end
                session.x_cash_register_total_cash_payments = total_cash_payment or 0
                # session.x_cash_register_cashier_moves = session.cash_register_id.total_entry_encoding
            else:
                session.cash_register_total_entry_encoding = 0.0
                session.cash_register_balance_end = 0.0
                session.cash_register_difference = 0.0
                session.x_cash_register_total_cash_payments = 0.0
            if not session.x_cash_register_cashier_moves:
                session.x_cash_register_cashier_moves = 0.0

    def _check_if_no_draft_orders(self):
        draft_orders = self.order_ids.filtered(lambda order: order.state == 'draft' and not order.x_is_partial)
        if draft_orders:
            raise UserError(_(
                    'There are still orders in draft state in the session. '
                    'Pay or cancel the following orders to validate the session:\n%s'
                ) % ', '.join(draft_orders.mapped('name'))
            )
        return True

    def action_pos_session_closing_control(self):
        # se reemplementa esta función para no validar ordenes en draft
        self._check_pos_session_balance()
        for session in self:
            # if any(order.state == 'draft' for order in session.order_ids):
            #     raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            session.write({'state': 'closing_control', 'stop_at': fields.Datetime.now()})
            if not session.config_id.cash_control:
                session.action_pos_session_close()