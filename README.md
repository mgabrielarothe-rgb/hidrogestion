# HidroGestión — prototipo de factibilidad

Aplicación de demostración en Python + Streamlit + SQLite. No necesita servidor de bases de datos para las primeras pruebas.

## Ejecutar

1. Instalá Python 3.11 o superior.
2. Abrí una terminal en esta carpeta.
3. Ejecutá `pip install -r requirements.txt`.
4. Ejecutá `streamlit run app.py`.
5. Se abrirá el navegador con las pantallas del sistema.

Al primer inicio se crea `hidrogestion.db` con registros **ficticios**. Es un archivo SQLite local, que puede abrirse con DB Browser for SQLite (gratuito) o consultarse desde el módulo «Tablas / Excel».

## Módulos incluidos

- **Producción:** lotes, mesas, siembras y mermas, con saldos por lote.
- **Stock:** disponibilidad comercial calculada: siembra menos merma, despachos y reservas de pedidos abiertos. Es una simplificación de prueba, no un control agronómico definitivo.
- **Clientes y pedidos:** registra pedidos por producto; exige stock disponible; deja reservas.
- **Despachos / logística:** prepara pedidos, confirma despacho y descuenta stock físico.
- **Facturas / ARCA:** registra manualmente datos de factura e importe, y permite exportar TXT delimitado por `|` a modo de archivo intermedio. **No es un layout oficial importable por Comprobantes en Línea.** Una integración fiscal real requerirá especificación del receptor o uso de WSFE y sus controles.
- **Cuentas corrientes:** debita por factura y permite registrar cobranzas imputadas, sin exceder saldos pendientes.
- **Tablas / Excel:** vista de registros y descargas CSV por cada tabla; además descarga de base de datos completa.

## Limitaciones deliberadas

**No usar para operaciones reales**: no incorpora seguridad multiusuario, backup automático, emisión fiscal, documentación de transporte, impuestos ni cierres contables. Antes de ponerlo en producción requiere transacciones atómicas para reservas concurrentes, trazabilidad por lote para el despacho, inventarios físicos, anulaciones, devoluciones y seguridad.

El prototipo no envía información fuera de tu computadora. No tiene conexión a ARCA, Supabase ni a otros sistemas. Si se aloja en la nube será necesario contratar hosting y base de datos persistente, y diseñar permisos y copias de seguridad.

## Diseño abierto de datos

Base SQLite con tablas legibles: `mesas`, `cultivos`, `lotes`, `mermas`, `clientes`, `pedidos`, `pedido_items`, `despachos`, `facturas`, `cobranzas`. Los saldos **no se escriben a mano**: se obtienen a partir de movimientos vinculados.

Se recomienda probar con información ficticia. Para borrar la demo y empezar de cero, cerrar la aplicación, borrar `hidrogestion.db` y volver a ejecutarla.
