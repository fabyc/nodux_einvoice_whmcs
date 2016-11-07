#! -*- coding: utf8 -*-

import string
from trytond.model import ModelView, ModelSQL, fields, Workflow
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
import hashlib
import base64

__all__ = ['Company']
__metaclass__ = PoolMeta

class Company():
    'Company'
    __name__ = 'company.company'

    emission_code = fields.Selection([
           ('1', 'Normal'),
       ], 'Tipo de Emision', readonly= True)

    tipo_de_ambiente = fields.Selection([
           ('1', 'Pruebas'),
           ('2', 'Produccion'),
       ], 'Tipo de Ambiente')

    password_ws = fields.Char('Password WS', help=u'Ingrese la contraseña que le fue emitido por NODUX')
    user_ws = fields.Char('Usuario WS', help='Ingrese el usuario que le fue emitido por NODUX')
    password_pk12 = fields.Char('Password de la Firma Digital', help=u'Contraseña de la firma digital')
    logo = fields.Binary('Logo de su empresa', help='Logo para RIDE de sus facturas')

    password = fields.Function(fields.Char('Password WS'), getter='get_password', setter='set_password')
    user = fields.Function(fields.Char('Usuario WS'), getter='get_user', setter='set_user')
    pass_pk12 = fields.Function(fields.Char('Password de la firma digital'), getter='get_pk12p', setter='set_pk12p')
    establecimiento = fields.Char('Establecimiento', help=u'Establecimiento autorizado por el SRI ej.001')
    p_emision = fields.Char('Punto de Emision', help=u'Punto de emision ej.001')
    secuencia_factura = fields.Integer('Secuencia de Facturas', help=u'Secuencia ej. 234')
    secuencia_notaCredito = fields.Integer('Secuencia de Nota de Credito', help=u'Secuencia ej. 234')


    name_database = fields.Char('Base de datos para consulta de comprobantes electronicos')#base de datos creada para guardar datos de consultas facturas electronicas
    user_databse = fields.Char('Usuario de la base de datos postgres')#usuario de la base de datos postgres
    password_database = fields.Char('Password de la base de datos postgres')#password de la base de datos postgres
    host_database = fields.Char('IP Host')#ip host

    name_db = fields.Function(fields.Char('Base de datos para consulta de comprobantes electronicos'), getter='get_namedb', setter='set_namedb')
    user_db = fields.Function(fields.Char('Usuario de la base de datos postgres'), getter='get_userdb', setter='set_userdb')
    password_db = fields.Function(fields.Char('Password de la base de datos postgres'), getter='get_passworddb', setter='set_passworddb')
    host_db = fields.Function(fields.Char('IP Host'), getter='get_hostdb', setter='set_hostdb')


    @classmethod
    def __setup__(cls):
        super(Company, cls).__setup__()

    @staticmethod
    def default_establecimiento():
        return '001'

    @staticmethod
    def default_p_emision():
        return '001'

    @staticmethod
    def default_emission_code():
        return '1'

    @staticmethod
    def default_tipo_de_ambiente():
        return '2'

    def get_password(self, name):
        return 'x' * 10

    @classmethod
    def set_password(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'password_ws': base64.encodestring(value),
                        }])
        cls.write(*to_write)


    def get_user(self, name):
        return 'x' * 10

    @classmethod
    def set_user(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'user_ws': base64.encodestring(value),
                        }])
        cls.write(*to_write)

    def get_pk12p(self, name):
        return 'x' * 10

    @classmethod
    def set_pk12p(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'password_pk12': base64.encodestring(value),
                        }])
        cls.write(*to_write)

    def get_namedb(self, name):
        return 'x' * 10

    @classmethod
    def set_namedb(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'name_database': base64.encodestring(value),
                        }])
        cls.write(*to_write)

    def get_userdb(self, name):
        return 'x' * 10

    @classmethod
    def set_userdb(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'user_databse': base64.encodestring(value),
                        }])
        cls.write(*to_write)

    def get_passworddb(self, name):
        return 'x' * 10

    @classmethod
    def set_passworddb(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'password_database': base64.encodestring(value),
                        }])
        cls.write(*to_write)

    def get_hostdb(self, name):
        return 'x' * 10

    @classmethod
    def set_hostdb(cls, companys, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for company in companys:
            to_write.extend([[company], {
                        'host_database': base64.encodestring(value),
                        }])
        cls.write(*to_write)
