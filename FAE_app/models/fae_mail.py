# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import poplib
from imaplib import IMAP4, IMAP4_SSL
from poplib import POP3, POP3_SSL
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)
MAX_POP_MESSAGES = 50
MAIL_TIMEOUT = 60
XML_DOC_TYPE = {'01': 'FE', '02': 'ND', '03': 'NC', '04': 'TE', '09': 'FEE'}
poplib._MAXLINE = 65536


class FaeMail(models.Model):
    """FAE POP/IMAP mail server account"""

    _name = 'xfae.mail'
    _description = 'FAE Mail Server'
    _order = 'priority'

    name = fields.Char('Nombre', required=True)
    active = fields.Boolean('Activo', default=True)
    state = fields.Selection([
        ('draft', 'No Confirmado'),
        ('done', 'Confirmado'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    server = fields.Char(string='Nombre de Servidor', readonly=True, help="Hostname or IP of the mail server", states={'draft': [('readonly', False)]})
    port = fields.Integer(string='Puerto', readonly=True, states={'draft': [('readonly', False)]})
    server_type = fields.Selection([
        ('pop', 'Servidor POP'),
        ('imap', 'Servidor IMAP'),
    ], string='Tipo de Servidor', index=True, required=True, default='imap')
    smtp_encryption = fields.Selection([('none', 'None'),
                                        ('starttls', 'TLS (STARTTLS)'),
                                        ('ssl', 'SSL/TLS')],
                                       string='Seguridad de conexión', required=True, default='none',
                                       help="Choose the connection encryption scheme:\n"
                                            "- None: SMTP sessions are done in cleartext.\n"
                                            "- TLS (STARTTLS): TLS encryption is requested at start of SMTP session (Recommended)\n"
                                            "- SSL/TLS: SMTP sessions are encrypted with SSL/TLS through a dedicated port (default: 465)")

    is_ssl = fields.Boolean('SSL/TLS', help="Connections are encrypted with SSL/TLS through a dedicated port (default: IMAPS=993, POP3S=995)")
    date = fields.Datetime(string='Última fecha de conexión', readonly=True)
    user = fields.Char(string='Usuario', readonly=True, states={'draft': [('readonly', False)]})
    password = fields.Char(string='Contraseña', readonly=True, states={'draft': [('readonly', False)]})
    priority = fields.Integer(string='Prioridad', readonly=True, states={'draft': [('readonly', False)]}, help="Defines the order of processing, lower values mean higher priority", default=5)
    type = fields.Selection([('in', 'Servidor de Correo Entrante'),('out', 'Servidor de Correo Saliente'),
                             ], string='Tipo', default='in')
    next_email = fields.Many2one('xfae.mail', string="Siguiente Correo")
    max_num_mail = fields.Integer(string='Límite diario')

    @api.onchange('server_type', 'is_ssl')
    def onchange_server_type(self):
        self.port = 0
        if self.server_type == 'pop':
            self.port = self.is_ssl and 995 or 110
        elif self.server_type == 'imap':
            self.port = self.is_ssl and 993 or 143
        else:
            self.server = ''

    @api.onchange('type')
    def onchange_type(self):
        self.port = 0
        if self.type == 'in' and self.server_type == 'pop':
            self.port = self.is_ssl and 995 or 110
        elif self.type == 'in' and self.server_type == 'imap':
            self.port = self.is_ssl and 993 or 143
        elif self.type == 'out':
            self.port = 25

    @api.model
    def create(self, values):
        res = super(FaeMail, self).create(values)
        return res

    def write(self, values):
        res = super(FaeMail, self).write(values)
        return res

    def unlink(self):
        res = super(FaeMail, self).unlink()
        return res

    def set_draft(self):
        self.write({'state': 'draft'})
        return True

    def connect(self):
        self.ensure_one()
        if self.server_type == 'imap':
            if self.is_ssl:
                connection = IMAP4_SSL(self.server, int(self.port))
            else:
                connection = IMAP4(self.server, int(self.port))
            connection.login(self.user, self.password)
        elif self.server_type == 'pop':
            if self.is_ssl:
                connection = POP3_SSL(self.server, int(self.port))
            else:
                connection = POP3(self.server, int(self.port))
            #TODO: use this to remove only unread messages
            #connection.user("recent:"+server.user)
            connection.user(self.user)
            connection.pass_(self.password)
        # Add timeout on socket
        connection.sock.settimeout(MAIL_TIMEOUT)

        return connection

    def button_confirm_login(self):
        for server in self:
            if self.type == 'in':
                try:
                    connection = server.connect()
                    server.write({'state': 'done'})
                except Exception as err:
                    _logger.info("Failed to connect to %s server %s.", server.server_type, server.name, exc_info=True)
                    raise UserError(_("Connection test failed: %s") % tools.ustr(err))
                finally:
                    try:
                        if connection:
                            if server.server_type == 'imap':
                                connection.close()
                            elif server.server_type == 'pop':
                                connection.quit()
                    except Exception:
                        # ignored, just a consequence of the previous exception
                        pass
        return True

    # def read_email(self):
    #     fae_email = self.env['xfae.mail'].search([('type', '=', 'in')])
    #
    #     for server in fae_email:
    #         try:
    #             connection = server.connect()
    #             server.write({'state': 'done'})
    #
    #             if server.server_type == 'imap':
    #                 num_Messages = len(connection.list()[1])
    #                 status, messages = connection.select("INBOX")
    #                 C = 5
    #                 messages = int(messages[0])
    #
    #                 for i in range(messages, messages - C, -1):
    #                     res, msg = connection.fetch(str(i), "(RFC822)")
    #                     for response in msg:
    #                         if isinstance(response, tuple):
    #                             msg = email.message_from_bytes(response[1])
    #
    #                             if msg.is_multipart():
    #                                 pdf_doc = ''
    #                                 complete_vals = {}
    #
    #                                 for part in msg.walk():
    #                                     content_type = part.get_content_type()
    #                                     content_disposition = str(part.get("Content-Disposition"))
    #                                     if content_type == "application/xml" or content_type == 'text/xml':
    #                                         filename = part.get_filename()
    #
    #                                         if filename:
    #                                             file = part.get_payload(decode=True)
    #                                             values = server.parser_xml(file)
    #                                             if complete_vals:
    #                                                 complete_vals.update(values)
    #                                             else:
    #                                                 complete_vals = values
    #
    #                                     if content_type == "application/pdf":
    #                                         filename = part.get_filename()
    #                                         if filename:
    #                                             pdf_doc = part.get_payload(decode=True)
    #
    #                                 if complete_vals:
    #                                     if pdf_doc:
    #                                         pdf = base64.encodebytes(pdf_doc)
    #
    #                                         vals = {
    #                                             'issuer_pdf': pdf,
    #                                         }
    #                                         complete_vals.update(vals)
    #
    #                                     clave = complete_vals['clave_hacienda']
    #                                     existing_incoming_document = self.env['x.fae.incoming.documents'] \
    #                                         .search([('clave_hacienda', '=', clave)])
    #
    #                                     if existing_incoming_document:
    #                                         for doc in existing_incoming_document:
    #                                             doc.write(complete_vals)
    #                                     else:
    #                                         res = self.env['x.fae.incoming.documents'].sudo().create(complete_vals)
    #
    #                 connection.close()
    #
    #             elif server.server_type == 'pop':
    #                 (messageCount, totalMessageSize) = connection.stat()
    #                 connection.list()
    #
    #                 for num in range(messageCount,0,-1):
    #                     (header, messages, octets) = connection.retr(num)
    #                     message = (b'\n').join(messages).decode('utf-8')
    #                     msg = Parser().parsestr(message)
    #
    #                     if (msg.is_multipart()):
    #                         pdf_doc = ''
    #                         complete_vals = {}
    #                         parts = msg.get_payload()
    #                         for n, part in enumerate(parts):
    #                             content_type = part.get_content_type()
    #                             if content_type == "application/xml" or content_type == "text/xml":
    #                                 attach_file_data = part.get_payload(decode=True)
    #                                 values = server.parser_xml(attach_file_data)
    #                                 if complete_vals:
    #                                     complete_vals.update(values)
    #                                 else:
    #                                     complete_vals = values
    #
    #                             if content_type == "application/pdf":
    #                                 pdf_doc = part.get_payload(decode=True)
    #
    #                         if complete_vals:
    #                             if pdf_doc:
    #                                 pdf = base64.encodebytes(pdf_doc)
    #                                 vals = {
    #                                     'issuer_pdf': pdf,
    #                                 }
    #                                 complete_vals.update(vals)
    #
    #                             clave = complete_vals['clave_hacienda']
    #                             existing_incoming_document = self.env['x.fae.incoming.documents'].search(
    #                                 [('clave_hacienda', '=', clave)])
    #
    #                             for doc in existing_incoming_document:
    #                                 doc.write(complete_vals)
    #                             else:
    #                                 res = self.env['x.fae.incoming.documents'].sudo().create(complete_vals)
    #                 connection.quit()
    #         except Exception as err:
    #             raise UserError(_("La conexión ha Fallado: %s") % tools.ustr(err))
    #     return True
    #
    # def parser_xml(self, docxml=None):
    #     # ESTA FUNCIÓN SE UTILIZA PARA PARSEAR EL CONTENIDO DE UN FICHERO XML
    #     doc = xml.dom.minidom.parseString(docxml)
    #     es_mensaje_hacienda = doc.getElementsByTagName('MensajeHacienda')
    #     clave_hacienda = doc.getElementsByTagName('Clave')[0].childNodes[0].data;
    #     document_type = clave_hacienda[29:31]
    #     values = {}
    #
    #     if clave_hacienda and not es_mensaje_hacienda:
    #         # EL ARCHIVO ES UN DOCUMENTO ELECTRÓNICO
    #         xml_doc = base64.encodebytes(docxml)
    #         document_type = XML_DOC_TYPE[document_type]
    #         issuer = doc.getElementsByTagName('Emisor')[0]
    #         receipt = doc.getElementsByTagName('Receptor')[0]
    #         invoice_resume = doc.getElementsByTagName('ResumenFactura')[0]
    #         invoice_resume_currency = invoice_resume.getElementsByTagName('CodigoTipoMoneda')[0]
    #         identification_type = receipt.getElementsByTagName('Tipo')[0].childNodes[0].data,
    #
    #         identification_types = self.env['xidentification.type'].search([('code', '=', identification_type)])
    #         identification_type_id = None
    #         for id_type in identification_types:
    #             identification_type_id = id_type.id
    #
    #         values = {
    #             'clave_hacienda': clave_hacienda,
    #             'consecutivo': doc.getElementsByTagName('NumeroConsecutivo')[0].childNodes[0].data,
    #             'bill_date': doc.getElementsByTagName('FechaEmision')[0].childNodes[0].data,
    #             'issuer_name': issuer.getElementsByTagName('Nombre')[0].childNodes[0].data,
    #             'issuer_identification_type': issuer.getElementsByTagName('Tipo')[0].childNodes[0].data,
    #             'issuer_identification_no': issuer.getElementsByTagName('Numero')[0].childNodes[0].data,
    #             'identification_type': identification_type_id,
    #             'identification_number': receipt.getElementsByTagName('Numero')[0].childNodes[0].data,
    #             'currency': invoice_resume_currency.getElementsByTagName('CodigoMoneda')[0].childNodes[0].data,
    #             'amount_tax': invoice_resume.getElementsByTagName('TotalImpuesto')[0].childNodes[0].data,
    #             'amount_total': invoice_resume.getElementsByTagName('TotalComprobante')[0].childNodes[0].data,
    #             'document_type': document_type,
    #             'issuer_xml_doc': xml_doc,
    #         }
    #     elif clave_hacienda:
    #         # EL ARCHIVO ES UNA MENSAJE DE HACIENDA
    #         xml_response = base64.encodebytes(docxml)
    #
    #         identification_type = doc.getElementsByTagName('TipoIdentificacionReceptor')[0].childNodes[0].data,
    #         identification_types = self.env['xidentification.type'].search([('code', '=', identification_type)])
    #         identification_type_id = None
    #         for id_type in identification_types:
    #             identification_type_id = id_type.id
    #
    #         values = {
    #             'issuer_identification_type': doc.getElementsByTagName('TipoIdentificacionEmisor')[0].childNodes[0].data,
    #             'issuer_identification_no': doc.getElementsByTagName('NumeroCedulaEmisor')[0].childNodes[0].data,
    #             'clave_hacienda': clave_hacienda,
    #             'issuer_xml_response': xml_response,
    #             'identification_type': identification_type_id,
    #             'identification_number': doc.getElementsByTagName('NumeroCedulaReceptor')[0].childNodes[0].data,
    #             }
    #
    #     return values
