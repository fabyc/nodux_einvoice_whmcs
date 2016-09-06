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
