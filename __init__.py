#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .company import *
from .user import *
from .invoice import *
from .party import *

def register():
    Pool.register(
        Company,
        User,
        EInvoice,
        InvoiceLine,
        Party,
        module='nodux_einvoice_whmcs', type_='model')
    Pool.register(
        EInvoiceReport,
        module='nodux_einvoice_whmcs', type_='report')
