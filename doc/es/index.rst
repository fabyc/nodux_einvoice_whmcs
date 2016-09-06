Módulo para Facturar Electrónicamente 
#######################################################

El administrador de WHMCS realizará una petición al servidor xmlrpc,
en el cual se encuentra el método que guardará la factura, productos, clientes
e invocará a los métodos:
* Envio al SRI.
* Envío de correo electrónico al cliente.
* Guardar datos para la consulta web de comprobantes electrónicos.
* Sincronizar los archivos para la consulta web de comprobantes electrónicos.

En caso que la petición sea hecha con el tipo "Nota de Crédito" el proceso 
de llamadas de métodos es similar, la diferencia está al hacer el envió al 
SRI, se enviará con tipo Nota de Crédito, los datos de la nota de crédito
también se guardarán en el sistema.

######################################################
Consulta de RIDE

ADMINISTRADOR
El administrador podrá imprimir el RIDE desde la respectiva factura.

CLIENTES
Los clientes tienen la posibilidad de revisar los comprobantes elétronicos emitidos
por la empresa, desde su perfil de WHMCS.

######################################################
Se pueden ver las facturas y notas de créditos generadas en el Menú Comprobantes
Electrónicos, e imprimir el RIDE correspondiente a cada comprobante electrónico.
