# -*- coding: utf-8 -*-

# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
import datetime
from trytond.model import ModelSQL, Workflow, fields, ModelView
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, Or, If
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.modules.company import CompanyReport
from trytond.report import Report
from lxml import etree
import base64
import xmlrpclib
import re
from xml.dom.minidom import parse, parseString
import time
from trytond.rpc import RPC
import os
from trytond.config import config
from trytond import backend
import collections
from itertools import islice, ifilter, chain, izip
import psycopg2
import psycopg2.extras
import urllib2

directory = config.get('database', 'path')
directory_xml = directory +'/factura.xml'

__all__ = ['EInvoice', 'InvoiceLine', 'EInvoiceReport']

_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']

_TYPE = [
    ('e_invoice', 'Electronic Invoice'),
    ('e_credit_note', 'Electronic Credit Note'),
]

tipoDocumento = {
    'e_invoice': '01',
    'e_credit_note': '04',
}

tipoIdentificacion = {
    '04' : '04',
    '05' : '05',
    '06' : '06',
    '07' : '07',
}

class EInvoice(Workflow, ModelSQL, ModelView):
    'EInvoice'
    __name__ = 'einvoice.einvoice'
    _order_name = 'invoice_date'

    company = fields.Many2One('company.company', 'Company', required=True,
        readonly=True, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    invoice_number = fields.Char('No. Comprobante', readonly=True)
    subtotal = fields.Numeric('Subtotal', readonly=True)
    iva = fields.Numeric('IVA', readonly=True)
    total = fields.Numeric('Total', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('send', 'Send'),
            ], 'State', readonly=True)

    type = fields.Selection(_TYPE, 'Type', select=True,
        required=True, states=_STATES, depends=_DEPENDS)
    mensaje = fields.Text('Mensaje de error SRI', readonly=True, states={
            'invisible': Eval('estado_sri') != 'NO AUTORIZADO',
            })
    estado_sri = fields.Char('Estado Facturacion-Electronica', size=24, readonly=True)
    path_xml = fields.Char(u'Path archivo xml de comprobante', readonly=True)
    path_pdf = fields.Char(u'Path archivo pdf de factura', readonly=True)
    numero_autorizacion = fields.Char(u'Número de Autorización')
    fecha_autorizacion = fields.Char('Fecha Autorizacion', readonly=True)
    invoice_date = fields.Date('Fecha Factura', readonly=True)
    lines = fields.One2Many('einvoice.einvoice.line', 'invoice', 'Lines',
        states=_STATES)
    id_reference = fields.Char('ID referencia factura', readonly=True)

    @classmethod
    def __setup__(cls):
        super(EInvoice, cls).__setup__()
        cls._check_modify_exclude = ['state', 'lines', 'estado_sri', 'mensaje'
                'invoice_report_cache', 'invoice_number', 'path_xml', 'path_pdf',
                'id_reference', 'numero_autorizacion']
        cls.__rpc__['save_invoice'] = RPC(check_access=False, readonly=False)
        cls.__rpc__['get_invoice'] = RPC(check_access=False, readonly=False)
        cls.__rpc__['get_path'] = RPC(check_access=False, readonly=False)
        cls._order.insert(0, ('invoice_date', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._error_messages.update({
                'modify_einvoice': ('You can not modify invoice "%s" because '
                    'it is send.'),
                'delete_einvoice': ('You can not delete invoice "%s" because '
                    'it is send.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        sql_table = cls.__table__()
        super(EInvoice, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        all_invoices = []
        for invoices, values in zip(actions, actions):
            if set(values) - set(cls._check_modify_exclude):
                cls.check_modify(invoices)
            all_invoices += invoices
        super(EInvoice, cls).write(*args)

    @classmethod
    def copy(cls, einvoices, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['invoice_number'] = None
        default.setdefault('invoice_date', None)
        return super(EInvoice, cls).copy(einvoices, default=default)


    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def check_modify(cls, einvoices):
        for einvoice in einvoices:
            if (einvoice.state in ('send')):
                cls.raise_user_error('modify_einvoice', (einvoice.invoice_number,))

    @classmethod
    def delete(cls, einvoices):
        cls.check_modify(einvoices)
        for einvoice in einvoices:
            if (einvoice.state in ('send')):
                cls.raise_user_error('delete_einvoice', (einvoice.invoice_number,))
        super(EInvoice, cls).delete(einvoices)

    def replace_character(self, cadena):
        reemplazo = {u"Â":"A", u"Á":"A", u"À":"A", u"Ä":"A", u"É":"E", u"È":"E", u"Ê":"E",u"Ë":"E",
            u"Í":"I",u"Ì":"I",u"Î":"I",u"Ï":"I",u"Ó":"O",u"Ò":"O",u"Ö":"O",u"Ô":"O",u"Ú":"U",u"Ù":"U",u"Ü":"U",
            u"Û":"U",u"á":"a",u"à":"a",u"â":"a",u"ä":"a",u"é":"e",u"è":"e",u"ê":"e",u"ë":"e",u"í":"i",u"ì":"i",
            u"ï":"i",u"î":"i",u"ó":"o",u"ò":"o",u"ô":"o",u"ö":"o",u"ú":"u",u"ù":"u",u"ü":"u",u"û":"u",u"ñ":"n",
            u"Ñ":"N"}
        regex = re.compile("(%s)" % "|".join(map(re.escape, reemplazo.keys())))
        nueva_cadena = regex.sub(lambda x: str(reemplazo[x.string[x.start():x.end()]]), cadena)
        return nueva_cadena

    def set_number(self):
        establecimiento = self.company.establecimiento
        p_emision = self.company.p_emision
        secuencia_factura = self.company.secuencia_factura
        secuencia_notaCredito = self.company.secuencia_notaCredito
        if self. type == 'e_invoice':
            if len(str(secuencia_factura)) == 1:
                number = str(establecimiento)+'-'+str(p_emision)+'-00000000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 2:
                number = str(establecimiento)+'-'+str(p_emision)+'-0000000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 3:
                number = str(establecimiento)+'-'+str(p_emision)+'-000000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 4:
                number = str(establecimiento)+'-'+str(p_emision)+'-00000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 5:
                number = str(establecimiento)+'-'+str(p_emision)+'-0000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 6:
                number = str(establecimiento)+'-'+str(p_emision)+'-000'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 7:
                number = str(establecimiento)+'-'+str(p_emision)+'-00'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 8:
                number = str(establecimiento)+'-'+str(p_emision)+'-0'+str(secuencia_factura)
            elif len(str(secuencia_factura)) == 9:
                number = str(establecimiento)+'-'+str(p_emision)+'-'+str(secuencia_factura)
            company = self.company
            company.secuencia_factura = secuencia_factura + 1
            company.save()
        else:
            if len(str(secuencia_notaCredito)) == 1:
                number = str(establecimiento)+'-'+str(p_emision)+'-00000000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 2:
                number = str(establecimiento)+'-'+str(p_emision)+'-0000000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 3:
                number = str(establecimiento)+'-'+str(p_emision)+'-000000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 4:
                number = str(establecimiento)+'-'+str(p_emision)+'-00000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 5:
                number = str(establecimiento)+'-'+str(p_emision)+'-0000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 6:
                number = str(establecimiento)+'-'+str(p_emision)+'-000'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 7:
                number = str(establecimiento)+'-'+str(p_emision)+'-00'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 8:
                number = str(establecimiento)+'-'+str(p_emision)+'-0'+str(secuencia_notaCredito)
            elif len(str(secuencia_notaCredito)) == 9:
                number = str(establecimiento)+'-'+str(p_emision)+'-'+str(secuencia_notaCredito)
            company = self.company
            company.secuencia_notaCredito = secuencia_notaCredito + 1
            company.save()
        vals = {'invoice_number': number}
        self.write([self], vals)

    def web_service(self):
        CONEXION = 'UD NO HA CONFIGURADO LOS DATOS DE CONEXION CON EL WS, \nCOMUNIQUESE CON EL ADMINISTRADOR DEL SISTEMA'
        pool = Pool()
        conexions = pool.get('res.user')
        conexion = conexions.search([('id', '=', 1)])
        if conexion:
            for c in conexion:
                if c.direccion:
                    address = c.cabecera+"://"+base64.decodestring(c.usuario)+":"+base64.decodestring(c.pass_db)+"@"+c.direccion+":"+c.puerto+"/"+base64.decodestring(c.name_db)
                    return address
                else:
                    self.raise_user_error(CONEXION)

    def send_mail_invoice(self, xml_element, access_key, send_m, s, server="localhost"):
        MAIL= u"Ud no ha configurado el correo del cliente. Diríjase a: \nTerceros->General->Medios de Contacto"
        pool = Pool()
        empresa = self.replace_character(self.company.party.name) #cambiado por self.elimina_tildes(self.company.party.name)
        empresa = empresa.replace(' ','_')
        empresa = empresa.lower()
        ahora = datetime.datetime.now()
        year = str(ahora.year)
        client = self.replace_character(self.party.name) #reemplazo self.party.name
        client = client.upper()
        empresa_ = self.replace_character(self.company.party.name) #reemplazo self.company.party.name
        ruc = self.company.party.vat_number
        if ahora.month < 10:
            month = '0'+ str(ahora.month)
        else:
            month = str(ahora.month)

        tipo_comprobante = self.type
        if tipo_comprobante == 'e_invoice':
            tipo = 'fact_'
            n_tipo = "FACTURA"
        if tipo_comprobante == 'e_credit_note':
            tipo = 'n_c_'
            n_tipo = "NOTA DE CREDITO"

        ruc = access_key[10:23]
        est = access_key[24:27]
        emi= access_key[27:30]
        sec = access_key[30:39]
        num_fac = est+'-'+emi+'-'+sec
        numero = ruc+'_'+num_fac
        name_pdf = tipo+numero+ '.pdf'
        name_xml = tipo+numero + '.xml'
        #nuevaruta =os.getcwd() +'/comprobantes/'+empresa+'/'+year+'/'+month +'/'
        nr = s.model.nodux_electronic_invoice_auth.conexiones.path_files(ruc, {})
        nuevaruta = nr +empresa+'/'+year+'/'+month +'/'
        new_save = 'comprobantes2/'+empresa+'/'+year+'/'+month +'/'
        ruta_xml = str(new_save+name_xml)
        ruta_pdf = str(new_save+name_pdf)
        self.write([self],{
            'path_xml': ruta_xml,
            'path_pdf': ruta_pdf})

        correos = pool.get('party.contact_mechanism')
        correo = correos.search([('type','=','email')])

        Report = Pool().get('einvoice.einvoice', type='report')
        report = Report.execute([self.id], {})
        email=''
        cont = 0
        for c in correo:
            if c.party == self.party:
                email = c.value
            if c.party == self.company.party:
                cont = cont +1
                f_e = c.value

        if email != '':
            to_email= email
        else :
            self.raise_user_error(MAIL)

        if send_m == '1':
            from_email = f_e
        else :
            from_email = f_e
        name = access_key + ".xml"
        reporte = xmlrpclib.Binary(report[1])
        xml_element = self.replace_character(xml_element)
        xml = xmlrpclib.Binary(xml_element.replace('><', '>\n<'))
        save_files = s.model.nodux_electronic_invoice_auth.conexiones.save_file(empresa, name_pdf, name_xml, reporte, xml, {})
        p_xml = nuevaruta + name_xml
        p_pdf = nuevaruta + name_pdf
        s.model.nodux_electronic_invoice_auth.conexiones.send_mail(name_pdf, name, p_xml, p_pdf, from_email, to_email, n_tipo, num_fac, client, empresa_, ruc, {})
        return True

    def connect_db(self):

        address_xml = self.web_service()
        s= xmlrpclib.ServerProxy(address_xml)

        pool = Pool()
        nombre = self.party.name
        cedula = self.party.vat_number
        ruc = self.company.party.vat_number
        nombre_e = self.company.party.name
        tipo = self.type
        fecha = str(self.invoice_date)
        empresa = self.company.party.name
        numero = self.invoice_number
        path_xml = self.path_xml
        path_pdf = self.path_pdf
        estado = self.estado_sri
        auth = self.numero_autorizacion
        correos = pool.get('party.contact_mechanism')
        correo = correos.search([('type','=','email')])
        for c in correo:
            if c.party == self.party:
                to_email = c.value
            if c.party == self.company.party:
                to_email_2 = c.value
        email_e= to_email_2
        email = to_email
        total = str(self.total)
        if self.estado_sri == 'AUTORIZADO':
            s.model.nodux_electronic_invoice_auth.conexiones.connect_db( nombre, cedula, ruc, nombre_e, tipo, fecha, empresa, numero, path_xml, path_pdf,estado, auth, email, email_e, total, {})

    def action_generate_invoice(self):
        PK12 = u'No ha configurado los datos de la empresa. Dirijase a: \n Empresa -> NODUX WS'
        AUTHENTICATE_ERROR = u'Error de datos de conexión al autorizador de \nfacturacion electrónica.\nVerifique: USUARIO Y CONTRASEÑA .'
        ACTIVE_ERROR = u"Ud. no se encuentra activo, verifique su pago. \nComuníquese con NODUX"
        WAIT_FOR_RECEIPT = 3
        TITLE_NOT_SENT = u'No se puede enviar el comprobante electronico al SRI'
        MESSAGE_SEQUENCIAL = u'Los comprobantes electrónicos deben ser enviados al SRI en orden secuencial'
        MESSAGE_TIME_LIMIT = u'Se ha excedido el límite de tiempo. Los comprobantes electrónicos deben ser enviados al SRI para su autorización, en un plazo máximo de 24 horas'
        WAIT_FOR_RECEIPT = 15
        pool = Pool()
        EInvoice = pool.get('einvoice.einvoice')
        usuario = self.company.user_ws
        password_u= self.company.password_ws
        access_key = self.generate_access_key()
        address_xml = self.web_service()
        s= xmlrpclib.ServerProxy(address_xml)

        name = self.company.party.name
        name_l=name.lower()
        name_l=name_l.replace(' ','_')
        name_r = self.replace_character(name_l)
        name_c = name_r+'.p12'

        authenticate, send_m, active = s.model.nodux_electronic_invoice_auth.conexiones.authenticate(usuario, password_u, {})
        if authenticate == '1':
            pass
        else:
            self.raise_user_error(AUTHENTICATE_ERROR)

        if active == '1':
            self.raise_user_error(ACTIVE_ERROR)
        else:
            pass

        nuevaruta = s.model.nodux_electronic_invoice_auth.conexiones.save_pk12(name_l, {})
        if self.type == 'e_invoice':
            factura1 = self.generate_xml_invoice()
            factura = etree.tostring(factura1, encoding = 'utf8', method = 'xml')
            a = s.model.nodux_electronic_invoice_auth.conexiones.validate_xml(factura, 'out_invoice', {})
            if a:
                self.raise_user_error(a)
            file_pk12 = base64.encodestring(nuevaruta+'/'+name_c)
            file_check = (nuevaruta+'/'+name_c)
            password = self.company.password_pk12
            error = s.model.nodux_electronic_invoice_auth.conexiones.check_digital_signature(file_check,{})
            if error == '1':
                self.raise_user_error('No se ha encontrado el archivo de firma digital (.p12)')

            signed_document= s.model.nodux_electronic_invoice_auth.conexiones.apply_digital_signature(factura, file_pk12, password,{})
            result = s.model.nodux_electronic_invoice_auth.conexiones.send_receipt(signed_document, {})
            if result != True:
                self.raise_user_error(result)

            if self.company.party.email:
                email = self.company.party.email
            else:
                self.raise_user_error('No ha configurado el correo de la empresa')

            doc_xml, m, auth, path, numero, num = s.model.nodux_electronic_invoice_auth.conexiones.request_authorization(access_key, name_r, 'out_invoice', signed_document,{})

            if doc_xml is None:
                msg = ' '.join(m)
                raise m
            if auth == 'NO AUTORIZADO':
                self.write([self],{
                    'estado_sri':'NO AUTORIZADO',
                    'numero_autorizacion': access_key,
                    'state':'draft'})
                return "Comprobante se ha enviado al SRI pero no se ha AUTORIZADO, reenvie su comprobante"
            else:
                self.write([self],{
                        'estado_sri':'AUTORIZADO',
                        'numero_autorizacion':access_key,
                        'state':'send'})
                self.send_mail_invoice(doc_xml, access_key, send_m, s)

        else:
            notaCredito1 = self.generate_xml_credit_note()
            notaCredito = etree.tostring(notaCredito1, encoding = 'utf8', method = 'xml')
            a = s.model.nodux_electronic_invoice_auth.conexiones.validate_xml(notaCredito, 'out_credit_note', {})
            if a:
                self.raise_user_error(a)
            file_pk12 = base64.encodestring(nuevaruta+'/'+name_c)
            file_check = (nuevaruta+'/'+name_c)
            password = self.company.password_pk12
            error = s.model.nodux_electronic_invoice_auth.conexiones.check_digital_signature(file_check,{})
            if error == '1':
                self.raise_user_error('No se ha encontrado el archivo de firma digital (.p12)')
            signed_document= s.model.nodux_electronic_invoice_auth.conexiones.apply_digital_signature(notaCredito, file_pk12, password,{})
            result = s.model.nodux_electronic_invoice_auth.conexiones.send_receipt(signed_document, {})
            if result != True:
                self.raise_user_error(result)

            if self.company.party.email:
                email = self.company.party.email
            else:
                self.raise_user_error('No ha configurado el correo de la empresa')

            doc_xml, m, auth, path, numero, num = s.model.nodux_electronic_invoice_auth.conexiones.request_authorization(access_key, name_r, 'out_credit_note', signed_document,{})

            if doc_xml is None:
                msg = ' '.join(m)
                raise m

            if auth == 'NO AUTORIZADO':
                self.write([self],{
                    'estado_sri':'NO AUTORIZADO',
                    'numero_autorizacion': access_key,
                    'state':'draft'})
                return "Comprobante se ha enviado al SRI pero no se ha AUTORIZADO, reenvie su comprobante"
            else:
                self.write([self],{
                        'estado_sri':'AUTORIZADO',
                        'numero_autorizacion':access_key,
                        'state':'send'})
                self.send_mail_invoice(doc_xml, access_key, send_m, s)

        return access_key

    @classmethod
    def get_path(cls, formato, numero_autorizacion, id_reference):
        database = 'compjoomfast'#base de datos creada para guardar datos de consultas facturas electronicas
        user = 'nodux' #usuario de la base de datos postgres
        password = 'noduxitondx24' #password de la base de datos postgres
        host = '162.248.52.245' #ip host
        Invoice = Pool().get('einvoice.einvoice')
        invoices = Invoice.search([('id_reference', '=', id_reference), ('type', '=', 'e_invoice')])
        for i in invoices:
            invoice = i
            numero_autorizacion = invoice.numero_autorizacion

        conn = psycopg2.connect(database=database,user= user, password=password, host=host)
        cur = conn.cursor()
        if formato == 'xml':
            invoice = cur.execute("SELECT path_xml FROM factura_web WHERE numero_autorizacion=%s",[numero_autorizacion])
            path_xml = cur.fetchone()
            xml_element = urllib2.urlopen('http://nodux.ec:8085/static/'+str(path_xml[0]))
            xml_element =etree.parse(xml_element)
            xml_element = etree.tostring(xml_element,pretty_print=True ,xml_declaration=True, encoding="utf-8")
            xml_element = xml_element.replace('&lt;', '<').replace('&gt;', '>')
            archivo = xmlrpclib.Binary(xml_element)


        if formato == 'pdf':
            invoice = cur.execute("SELECT path_pdf FROM factura_web WHERE numero_autorizacion=%s",[numero_autorizacion])
            path_pdf = cur.fetchone()
            pool = Pool()
            Invoices = pool.get('einvoice.einvoice')
            invoices = Invoices.search([('numero_autorizacion', '=', numero_autorizacion)])
            for i in invoices:
                invoice = i
            InvoiceReport = pool.get('einvoice.einvoice', type='report')
            report = InvoiceReport.execute([invoice.id], {})
            archivo = xmlrpclib.Binary(report[1])

        return archivo


    @classmethod
    def get_invoice(cls, identificacion):
        Company = Pool().get('company.company')
        companies = Company.search([('id', '=', 1)])
        for c in companies:
            company = c
        database = base64.decodestring(company.name_database)#base de datos creada para guardar datos de consultas facturas electronicas
        user = base64.decodestring(company.user_databse) #usuario de la base de datos postgres
        password = base64.decodestring(company.password_database) #password de la base de datos postgres
        host = base64.decodestring(company.host_database) #ip host
        ruc = company.party.vat_number
        conn = psycopg2.connect(database=database,user= user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("SELECT tipo, fecha, numero_comprobante, numero_autorizacion, total FROM factura_web WHERE cedula=%s and ruc=%s", (identificacion, ruc))
        result = cur.fetchall()
        invoices = []
        for r in result:
            invoices.append(r)
        return invoices

    @classmethod
    def save_invoice(cls, tipo, id_factura, date, maturity_date, subtotal, total, identificacion, items, firstname, lastname, email, address, city, state, country, phonenumber ):
        data = xmlrpclib.loads(items)
        lineas_producto = str(data[0]).split(", ")
        pool = Pool()
        Party = pool.get('party.party')
        Lines = pool.get('einvoice.einvoice.line')
        Invoice = pool.get('einvoice.einvoice')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Units = pool.get('product.uom')
        e_invoices_c = None
        if tipo == 'factura':
            type_ = 'e_invoice'
        else:
            type_ = 'e_credit_note'
        e_invoices_c = Invoice.search([('id_reference', '=', str(id_factura)), ('type', '=', type_)])
        if e_invoices_c:
            for invoice in e_invoices_c:
                if invoice.estado_sri == "NO AUTORIZADO":
                    invoice.action_generate_invoice()
                    invoice.connect_db()
                    return "Comprobante enviado con exito"
                elif invoice.estado_sri == "AUTORIZADO":
                    return "Comprobante ya ha sido enviado anteriormente"

        products = None
        parties = None
        direccion = "Loja"
        phone = ""
        name = str(firstname)+str(lastname)
        vat_number = str(identificacion)
        address = str(address)
        importeTotal = Decimal(total)
        totalSinImpuestos = Decimal(subtotal)
        date_str = str(date)
        parties = Party.search([('vat_number', '=', vat_number)])
        formatter_string = "%Y-%m-%d"
        datetime_object = datetime.datetime.strptime(date_str, formatter_string)
        fechaEmision = datetime_object.date()
        lineas = []
        if parties:
            for p in parties:
                party = p
        else:
            party = Party()
            if email:
                correo = str(email)
            else:
                correo = 'hola@nodux.ec'
            Contact = pool.get('party.contact_mechanism')
            Address = pool.get('party.address')
            party.name = name
            party.vat_number = vat_number
            party.save()
            contact_mechanisms = []
            contact_mechanisms.append({
                    'type':'email',
                    'value':correo,
                    'party':party.id
            })
            if phone != "":
                contact_mechanisms.append({
                        'type':'phone',
                        'value':phone,
                        'party':party.id,
                })
            party.address = Address.create([{
                    'street': address,
                    'party':party.id
            }])
            contact_mechanisms = Contact.create(contact_mechanisms)
            party.save()

        invoice = Invoice()
        invoice.company=1
        invoice.id_reference = str(id_factura)
        if tipo == 'factura':
            invoice.type = 'e_invoice'
        else:
            invoice.type = 'e_credit_note'
        invoice.save()
        cont = 1
        for l_p in lineas_producto:
            l_p1 = l_p.replace('[','').replace(']','').replace('(','').replace(')','').replace("'",'').replace(',','')
            l_p1 = l_p1.split(' -- ')
            descripcion = l_p1[0]
            precio = l_p1[1]
            if descripcion:
                products = Template.search([('name', '=', descripcion)])
            units = Units.search([('name', '=', 'Unit')])
            unit = 1
            if units:
                for u in units:
                    unit = u
            if products:
                for p in products:
                    product = p
            else:
                product = Template()
                product.name = descripcion
                product.list_price = Decimal(precio)
                product.cost_price = Decimal(0.0)
                product.type = 'service'
                product.cost_price_method = 'fixed'
                product.default_uom = unit
                product.save()
                product.products = Product.create([{
                    'code': descripcion[0:3]+str(product.id),
                    'template':product.id,
                }])
                product.save()

            lineas.append({
                'producto': product.id,
                'description': product.name,
                'unit_price': product.list_price,
                'quantity': 1,
                'invoice':invoice.id,
            })
        invoice.party= party.id
        invoice.subtotal= totalSinImpuestos
        invoice.iva= Decimal(importeTotal-totalSinImpuestos)
        invoice.total= importeTotal
        invoice.invoice_date=fechaEmision
        lines = Lines.create(lineas)
        invoice.save()
        invoice.set_number()
        invoice.action_generate_invoice()
        invoice.connect_db()
        return "Comprobante enviado con exito"

    def generate_xml_invoice(self):
        factura = etree.Element('factura')
        factura.set("id", "comprobante")
        factura.set("version", "1.1.0")

        # generar infoTributaria
        infoTributaria = self.get_tax_element()
        factura.append(infoTributaria)

        # generar infoFactura
        infoFactura = self.get_invoice_element()
        factura.append(infoFactura)

        #generar detalles
        detalles = self.get_detail_element()
        factura.append(detalles)
        return factura

    #generar nota de Credito
    def generate_xml_credit_note(self):
        notaCredito = etree.Element('notaCredito')
        notaCredito.set("id", "comprobante")
        notaCredito.set("version", "1.1.0")

        # generar infoTributaria
        infoTributaria = self.get_tax_element()
        notaCredito.append(infoTributaria)

        #generar infoNotaCredito
        infoNotaCredito = self.get_credit_note_element()
        notaCredito.append(infoNotaCredito)

        #generar detalles
        detalles = self.get_detail_credit_note()
        notaCredito.append(detalles)
        return notaCredito

    def get_tax_element(self):
        company = self.company
        number = self.invoice_number
        infoTributaria = etree.Element('infoTributaria')
        etree.SubElement(infoTributaria, 'ambiente').text = self.company.tipo_de_ambiente
        etree.SubElement(infoTributaria, 'tipoEmision').text = self.company.emission_code
        etree.SubElement(infoTributaria, 'razonSocial').text = self.replace_character(self.company.party.name)
        if self.company.party.commercial_name:
            etree.SubElement(infoTributaria, 'nombreComercial').text = self.company.party.commercial_name
        etree.SubElement(infoTributaria, 'ruc').text = self.company.party.vat_number
        etree.SubElement(infoTributaria, 'claveAcceso').text = self.generate_access_key()
        etree.SubElement(infoTributaria, 'codDoc').text = tipoDocumento[self.type]
        etree.SubElement(infoTributaria, 'estab').text = number[0:3]
        etree.SubElement(infoTributaria, 'ptoEmi').text = number[4:7]
        etree.SubElement(infoTributaria, 'secuencial').text = number[8:17]
        if self.company.party.addresses:
            etree.SubElement(infoTributaria, 'dirMatriz').text = self.company.party.addresses[0].street
        return infoTributaria

    def get_invoice_element(self):
        company = self.company
        party = self.party
        infoFactura = etree.Element('infoFactura')
        etree.SubElement(infoFactura, 'fechaEmision').text = self.invoice_date.strftime('%d/%m/%Y')
        if self.company.party.addresses:
            etree.SubElement(infoFactura, 'dirEstablecimiento').text = self.company.party.addresses[0].street
        if self.company.party.contribuyente_especial_nro:
            etree.SubElement(infoFactura, 'contribuyenteEspecial').text = self.company.party.contribuyente_especial_nro
        if self.company.party.mandatory_accounting:
            etree.SubElement(infoFactura, 'obligadoContabilidad').text = self.company.party.mandatory_accounting
        else :
            etree.SubElement(infoFactura, 'obligadoContabilidad').text = 'NO'
        if self.party.type_document:
            etree.SubElement(infoFactura, 'tipoIdentificacionComprador').text = tipoIdentificacion[self.party.type_document]
        else:
            self.raise_user_error("No ha configurado el tipo de identificacion del cliente")
        etree.SubElement(infoFactura, 'razonSocialComprador').text = self.replace_character(self.party.name)
        etree.SubElement(infoFactura, 'identificacionComprador').text = self.party.vat_number
        if self.party.addresses:
            etree.SubElement(infoFactura, 'direccionComprador').text = self.party.addresses[0].street
        etree.SubElement(infoFactura, 'totalSinImpuestos').text = '%.2f' % (self.subtotal)
        etree.SubElement(infoFactura, 'totalDescuento').text = '0.00' #descuento esta incluido en el precio poner 0.0 por defecto

        totalConImpuestos = etree.Element('totalConImpuestos')
        totalImpuesto = etree.Element('totalImpuesto')
        codigoPorcentaje = '3'
        codigo = '2'

        etree.SubElement(totalImpuesto, 'codigo').text = codigo
        etree.SubElement(totalImpuesto, 'codigoPorcentaje').text = codigoPorcentaje
        etree.SubElement(totalImpuesto, 'baseImponible').text = '{:.2f}'.format(self.subtotal)
        etree.SubElement(totalImpuesto, 'valor').text = '{:.2f}'.format(self.iva)
        totalConImpuestos.append(totalImpuesto)
        infoFactura.append(totalConImpuestos)
        etree.SubElement(infoFactura, 'propina').text = '0.00'
        etree.SubElement(infoFactura, 'importeTotal').text = '{:.2f}'.format(self.total)
        etree.SubElement(infoFactura, 'moneda').text = 'DOLAR'

        return infoFactura

    def get_detail_element(self):
        detalles = etree.Element('detalles')

        for line in self.lines:
            pool = Pool()
            detalle = etree.Element('detalle')
            Product = pool.get('product.product')
            product = None
            products = Product.search([('template', '=', line.producto.id)])
            for p in products:
                product = p
                if product:
                    etree.SubElement(detalle, 'codigoPrincipal').text = self.replace_character(product.code)
                else:
                    etree.SubElement(detalle, 'codigoPrincipal').text = '[COD0]'
            etree.SubElement(detalle, 'descripcion').text = self.replace_character(line.description)#fix_chars(line.description)
            etree.SubElement(detalle, 'cantidad').text = '%.2f' % (line.quantity)
            etree.SubElement(detalle, 'precioUnitario').text = '%.2f' % (line.unit_price)
            etree.SubElement(detalle, 'descuento').text = '0.00'
            etree.SubElement(detalle, 'precioTotalSinImpuesto').text = '%.2f' % (line.amount)
            impuestos = etree.Element('impuestos')
            impuesto = etree.Element('impuesto')
            etree.SubElement(impuesto, 'codigo').text = "2"
            etree.SubElement(impuesto, 'codigoPorcentaje').text = '3' #3iva14, 2iva12, 0iva0
            etree.SubElement(impuesto, 'tarifa').text = '14' #tarifas:14,12,0
            etree.SubElement(impuesto, 'baseImponible').text = '{:.2f}'.format(line.amount)
            etree.SubElement(impuesto, 'valor').text = '{:.2f}'.format(line.amount*Decimal(0.14))
            impuestos.append(impuesto)
            detalle.append(impuestos)
            detalles.append(detalle)
        return detalles

    def get_credit_note_element(self):
        pool = Pool()
        company = self.company
        Invoice = pool.get('einvoice.einvoice')
        motivo='Emitir factura con el mismo concepto'

        invoices = Invoice.search([('id_reference', '=', self.id_reference), ('type', '=', 'e_invoice'), ('id_reference', '!=', None)])
        for i in invoices:
            invoice = i
        infoNotaCredito = etree.Element('infoNotaCredito')
        etree.SubElement(infoNotaCredito, 'fechaEmision').text = self.invoice_date.strftime('%d/%m/%Y')
        etree.SubElement(infoNotaCredito, 'dirEstablecimiento').text = self.company.party.addresses[0].street
        if self.party.type_document:
            etree.SubElement(infoNotaCredito, 'tipoIdentificacionComprador').text = tipoIdentificacion[self.party.type_document]
        else:
            self.raise_user_error("No ha configurado el tipo de identificacion del cliente")
        etree.SubElement(infoNotaCredito, 'razonSocialComprador').text = self.replace_character(self.party.name) #self.party.name
        etree.SubElement(infoNotaCredito, 'identificacionComprador').text = self.party.vat_number
        if self.company.party.mandatory_accounting:
            etree.SubElement(infoNotaCredito, 'obligadoContabilidad').text = self.company.party.mandatory_accounting
        else :
            etree.SubElement(infoNotaCredito, 'obligadoContabilidad').text = 'NO'

        etree.SubElement(infoNotaCredito, 'rise').text = '01'
        etree.SubElement(infoNotaCredito, 'codDocModificado').text = '01'
        etree.SubElement(infoNotaCredito, 'numDocModificado').text = invoice.invoice_number
        etree.SubElement(infoNotaCredito, 'fechaEmisionDocSustento').text = invoice.invoice_date.strftime('%d/%m/%Y')
        etree.SubElement(infoNotaCredito, 'totalSinImpuestos').text = '%.2f'%(self.subtotal)
        etree.SubElement(infoNotaCredito, 'valorModificacion').text = '%.2f'%(self.total)
        etree.SubElement(infoNotaCredito, 'moneda').text = 'DOLAR'

        totalConImpuestos = etree.Element('totalConImpuestos')
        totalImpuesto = etree.Element('totalImpuesto')
        codigoPorcentaje = '3'
        codigo = '2'

        etree.SubElement(totalImpuesto, 'codigo').text = codigo
        etree.SubElement(totalImpuesto, 'codigoPorcentaje').text = codigoPorcentaje
        etree.SubElement(totalImpuesto, 'baseImponible').text = '{:.2f}'.format(self.subtotal)
        etree.SubElement(totalImpuesto, 'valor').text = '{:.2f}'.format(self.iva)
        totalConImpuestos.append(totalImpuesto)
        infoNotaCredito.append(totalConImpuestos)
        etree.SubElement(infoNotaCredito, 'motivo').text= self.replace_character(motivo)
        return infoNotaCredito

    #detalles de nota de credito
    def get_detail_credit_note(self):

        detalles = etree.Element('detalles')
        for line in self.lines:
            pool = Pool()
            detalle = etree.Element('detalle')
            Product = pool.get('product.product')
            product = None
            products = Product.search([('template', '=', line.producto.id)])
            for p in products:
                product = p
                if product:
                    etree.SubElement(detalle, 'codigoInterno').text = self.replace_character(product.code)
                else:
                    etree.SubElement(detalle, 'codigoInterno').text = '[COD0]'
            etree.SubElement(detalle, 'descripcion').text = self.replace_character(line.description)#fix_chars(line.description)
            etree.SubElement(detalle, 'cantidad').text = '%.2f' % (line.quantity)
            etree.SubElement(detalle, 'precioUnitario').text = '%.2f' % (line.unit_price)
            etree.SubElement(detalle, 'descuento').text = '0.00'
            etree.SubElement(detalle, 'precioTotalSinImpuesto').text = '%.2f' % (line.amount)
            impuestos = etree.Element('impuestos')
            impuesto = etree.Element('impuesto')
            etree.SubElement(impuesto, 'codigo').text = "2"
            etree.SubElement(impuesto, 'codigoPorcentaje').text = '3' #3iva14, 2iva12, 0iva0
            etree.SubElement(impuesto, 'tarifa').text = '14' #tarifas:14,12,0
            etree.SubElement(impuesto, 'baseImponible').text = '{:.2f}'.format(line.amount)
            etree.SubElement(impuesto, 'valor').text = '{:.2f}'.format(line.amount*Decimal(0.14))
            impuestos.append(impuesto)
            detalle.append(impuestos)
            detalles.append(detalle)
        return detalles

    def generate_access_key(self):
        f = self.invoice_date.strftime('%d%m%Y')
        t_cbte = tipoDocumento[self.type]
        ruc = self.company.party.vat_number
        t_amb=self.company.tipo_de_ambiente
        n_cbte= self.invoice_number
        cod= "14526873"
        t_ems= self.company.emission_code
        numero_cbte= n_cbte.replace('-','')
        #unimos todos los datos en una sola cadena
        key_temp=f+t_cbte+ruc+t_amb+numero_cbte+cod+t_ems

        #recorremos la cadena para ir guardando en una lista de enteros
        key = []
        for c in key_temp:
            key.append(int(c))
        key.reverse()
        factor = [2,3,4,5,6,7]
        stage1 = sum([n*factor[i%6] for i,n in enumerate(key)])
        stage2 = stage1 % 11
        digit = 11 - (stage2)
        if digit == 11:
            digit =0
        if digit == 10:
            digit = 1
        digit=str(digit)
        access_key= key_temp + digit
        return access_key

class InvoiceLine(ModelSQL, ModelView):
    'Invoice Line'
    __name__ = 'einvoice.einvoice.line'
    _rec_name = 'description'
    invoice = fields.Many2One('einvoice.einvoice', 'Invoice', ondelete='CASCADE',
        select=True)
    quantity = fields.Integer('Quantity')
    producto = fields.Many2One('product.template', 'Product')
    unit_price = fields.Numeric('Unit Price', digits=(16, 4))
    amount = fields.Function(fields.Numeric('Amount', digits=(16, 4)), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    sequence = fields.Integer('Sequence',
        states={
            'invisible': Bool(Eval('context', {}).get('standalone')),
            })

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()

        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'modify': ('You can not modify line "%(line)s" from invoice '
                    '"%(invoice)s" that is posted or paid.'),
                'create': ('You can not add a line to invoice "%(invoice)s" '
                    'that is posted, paid or cancelled.'),
                'account_different_company': (
                    'You can not create invoice line '
                    '"%(line)s" on invoice "%(invoice)s of company '
                    '"%(invoice_line_company)s because account "%(account)s '
                    'has company "%(account_company)s".'),
                'same_account_on_invoice': ('You can not create invoice line '
                    '"%(line)s" on invoice "%(invoice)s" because the invoice '
                    'uses the same account (%(account)s).'),
                })

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @fields.depends('quantity', 'unit_price')
    def on_change_with_amount(self):
        amount = (Decimal(str(self.quantity or '0.0'))
                * (self.unit_price or Decimal('0.0')))
        return amount

    def get_amount(self, name):
        return self.on_change_with_amount()


    @classmethod
    def check_modify(cls, lines):
        for line in lines:
            if (line.invoice
                    and line.invoice.state in ('posted', 'paid')):
                cls.raise_user_error('modify', {
                        'line': line.rec_name,
                        'invoice': line.invoice.rec_name
                        })

    @classmethod
    def delete(cls, lines):
        cls.check_modify(lines)
        super(InvoiceLine, cls).delete(lines)

    @classmethod
    def write(cls, *args):
        lines = sum(args[0::2], [])
        cls.check_modify(lines)
        super(InvoiceLine, cls).write(*args)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        return super(InvoiceLine, cls).copy(lines, default=default)

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('einvoice.einvoice')
        invoice_ids = []
        for vals in vlist:
            if vals.get('invoice'):
                invoice_ids.append(vals.get('invoice'))
        for invoice in Invoice.browse(invoice_ids):
            if invoice.state in ('send'):
                cls.raise_user_error('create', (invoice.rec_name,))
        return super(InvoiceLine, cls).create(vlist)


class EInvoiceReport(Report):
    __name__ = 'einvoice.einvoice'

    @classmethod
    def __setup__(cls):
        super(EInvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def execute(cls, ids, data):
        EInvoice = Pool().get('einvoice.einvoice')

        res = super(EInvoiceReport, cls).execute(ids, data)
        if len(ids) > 1:
            res = (res[0], res[1], True, res[3])
        else:
            einvoice = EInvoice(ids[0])
            if einvoice.invoice_number:
                res = (res[0], res[1], res[2], res[3] + ' - ' + einvoice.invoice_number)
        return res

    @classmethod
    def _get_records(cls, ids, model, data):
        with Transaction().set_context(language=False):
            return super(EInvoiceReport, cls)._get_records(ids[:1], model, data)

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        EInvoice = pool.get('einvoice.einvoice')

        einvoice = records[0]

        user = User(Transaction().user)
        localcontext['company'] = user.company
        if einvoice.numero_autorizacion:
            localcontext['barcode_img']=cls._get_barcode_img(EInvoice, einvoice)
        if einvoice.type == 'e_credit_note':
            localcontext['numero'] = cls._get_numero(EInvoice, einvoice)
            localcontext['fecha'] = cls._get_fecha(EInvoice, einvoice)
            localcontext['motivo'] = 'Emitir factura con el mismo concepto'
        localcontext['subtotal0'] = '0.0'
        localcontext['subtotal14'] = einvoice.subtotal

        return super(EInvoiceReport, cls).parse(report, records, data,
                localcontext=localcontext)

    @classmethod
    def _get_numero(cls, EInvoice, einvoice):
        numero = None
        invoices = EInvoice.search([('id_reference', '=', einvoice.id_reference), ('type', '=', 'e_invoice'), ('id_reference', '!=', None)])
        for i in invoices:
            numero = i.invoice_number
        return numero

    @classmethod
    def _get_fecha(cls, EInvoice, einvoice):
        fecha = None
        invoices = EInvoice.search([('id_reference', '=', einvoice.id_reference), ('type', '=', 'e_invoice'), ('id_reference', '!=', None)])
        for i in invoices:
            fecha = i.invoice_date
        return fecha

    @classmethod
    def _get_barcode_img(cls, EInvoice, einvoice):
        from barras import CodigoBarra
        from cStringIO import StringIO as StringIO
        # create the helper:
        codigobarra = CodigoBarra()
        output = StringIO()
        bars= einvoice.numero_autorizacion
        codigobarra.GenerarImagen(bars, output, basewidth=3, width=380, height=50, extension="PNG")
        image = buffer(output.getvalue())
        output.close()
        return image
