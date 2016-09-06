#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
#! -*- coding: utf8 -*-
from trytond.pool import *
import logging
from importlib import import_module
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Bool, Eval, Id
from trytond.transaction import Transaction
import re

__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'

    commercial_name = fields.Char('Commercial Name')

    mandatory_accounting = fields.Selection([
            ('',''),
            ('SI', 'Si'),
            ('NO', 'No'),
            ], 'Mandatory Accounting', states={
                'invisible': Eval('type_document')!='04',
            }
            )
    contribuyente_especial = fields.Boolean(u'Contribuyente especial', states={
            'invisible': Eval('mandatory_accounting') != 'SI',
            }, help="Seleccione solo si es contribuyente especial"
        )
    contribuyente_especial_nro = fields.Char('Nro. Resolucion', states={
            'invisible': ~Eval('contribuyente_especial',True),
            'required': Eval('contribuyente_especial',True),
            }, help="Contribuyente Especial Nro.")

    type_document = fields.Selection([
                ('', ''),
                ('04', 'RUC'),
                ('05', 'Cedula'),
                ('06', 'Pasaporte'),
                ('07', 'Consumidor Final'),
            ], 'Type Document', states={
                'readonly': ~Eval('active', True),
            },  depends=['active'])

    contact_mechanisms2 = fields.One2Many('party.contact_mechanism', 'party',
        'Contact Mechanisms', help = u'Requerido ingresar un correo electronico')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'invalid_contact': (u'Es requerido ingresar un correo, para el envio de comprobantes electronicos'),
                'invalid_structure':('Correo electronico no cumple con la estructura (ejemplo@mail.com)')})

    @staticmethod
    def default_contribuyente_especial():
        return False

    @staticmethod
    def default_mandatory_accounting():
        return 'NO'

    @staticmethod
    def default_type_document():
        return '05'

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        for party in parties:
            party.validate_email()

    def validate_email(self):
        correo = ''
        correos = self.contact_mechanisms
        for c in correos:
            print c
            if c.type == 'email':
                correo = c.value
                if re.match("[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,3})", correo):
                    pass
                else:
                    self.raise_user_error('invalid_structure')
        if correo != '':
            pass

class BankAccountNumber:
    __name__ = 'bank.account.number'

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        new_sel = [
            ('checking_account', 'Checking Account'),
            ('saving_account', 'Saving Account'),
        ]
        if new_sel not in cls.type.selection:
            cls.type.selection.extend(new_sel)


class Company:
    __name__ = 'company.company'

    @classmethod
    def default_currency(cls):
        Currency = Pool().get('currency.currency')
        usd= Currency.search([('code','=','USD')])
        return usd[0].id

    @staticmethod
    def default_timezone():
        return 'America/Guayaquil'
