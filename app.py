import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st

DB = Path(__file__).with_name('hidrogestion.db')
st.set_page_config(page_title='HidroGestión · Demo', page_icon='🌱', layout='wide')

@contextmanager
def conn():
    c = sqlite3.connect(DB, timeout=15)
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS mesas(id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, sector TEXT, capacidad INTEGER NOT NULL CHECK(capacidad>0));
        CREATE TABLE IF NOT EXISTS cultivos(id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY, codigo TEXT UNIQUE NOT NULL, cultivo_id INTEGER NOT NULL REFERENCES cultivos(id), mesa_id INTEGER REFERENCES mesas(id), fecha TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK(cantidad>0), etapa TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mermas(id INTEGER PRIMARY KEY, lote_id INTEGER NOT NULL REFERENCES lotes(id), fecha TEXT NOT NULL, cantidad INTEGER NOT NULL CHECK(cantidad>0), motivo TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS clientes(id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, cuit TEXT, domicilio TEXT);
        CREATE TABLE IF NOT EXISTS pedidos(id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes(id), fecha TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'Reservado');
        CREATE TABLE IF NOT EXISTS pedido_items(id INTEGER PRIMARY KEY, pedido_id INTEGER NOT NULL REFERENCES pedidos(id), cultivo_id INTEGER NOT NULL REFERENCES cultivos(id), cantidad INTEGER NOT NULL CHECK(cantidad>0), precio REAL NOT NULL CHECK(precio>=0));
        CREATE TABLE IF NOT EXISTS despachos(id INTEGER PRIMARY KEY, pedido_id INTEGER UNIQUE NOT NULL REFERENCES pedidos(id), fecha TEXT NOT NULL, conductor TEXT, observaciones TEXT);
        CREATE TABLE IF NOT EXISTS facturas(id INTEGER PRIMARY KEY, pedido_id INTEGER UNIQUE NOT NULL REFERENCES pedidos(id), fecha TEXT NOT NULL, tipo TEXT NOT NULL, numero TEXT NOT NULL, cae TEXT, importe REAL NOT NULL CHECK(importe>=0));
        CREATE TABLE IF NOT EXISTS cobranzas(id INTEGER PRIMARY KEY, factura_id INTEGER NOT NULL REFERENCES facturas(id), fecha TEXT NOT NULL, importe REAL NOT NULL CHECK(importe>0), medio TEXT NOT NULL, referencia TEXT);
        ''')
        if not c.execute('SELECT COUNT(*) FROM cultivos').fetchone()[0]:
            c.executemany('INSERT INTO cultivos(nombre) VALUES (?)', [('Lechuga mantecosa',),('Lechuga crespa',),('Rúcula',)])
            c.executemany('INSERT INTO mesas(nombre,sector,capacidad) VALUES (?,?,?)', [('M-01','Invernadero A',6000),('M-02','Invernadero A',4000),('M-03','Invernadero B',3000)])
            c.executemany('INSERT INTO lotes(codigo,cultivo_id,mesa_id,fecha,cantidad,etapa) VALUES (?,?,?,?,?,?)', [('H-001',1,1,'2026-11-01',5000,'Crecimiento'),('H-002',2,2,'2026-11-05',3000,'Germinación'),('H-003',3,3,'2026-10-20',2000,'Cosechable')])
            c.executemany('INSERT INTO mermas(lote_id,fecha,cantidad,motivo) VALUES (?,?,?,?)', [(1,'2026-11-10',250,'No germinación'),(1,'2026-11-17',100,'Daño'),(2,'2026-11-12',120,'No germinación'),(3,'2026-11-02',80,'Descarte')])
            c.executemany('INSERT INTO clientes(nombre,cuit,domicilio) VALUES (?,?,?)', [('Verdulería Norte','', 'Zona Norte'),('Distribuidora Sur','','CABA')])

def q(sql, params=()):
    with conn() as c:
        return pd.read_sql_query(sql,c,params=params)

def execute(sql, params=()):
    with conn() as c: return c.execute(sql,params).lastrowid

def opciones(tabla, campo='nombre'):
    rows=q(f'SELECT id,{campo} AS etiqueta FROM {tabla} ORDER BY {campo}')
    return dict(zip(rows['id'], rows['etiqueta']))

def stock():
    # Demonstration-only assumption: all unshipped surviving plants can be sold.
    return q('''SELECT c.id AS cultivo_id, c.nombre AS cultivo,
      COALESCE((SELECT SUM(l.cantidad) FROM lotes l WHERE l.cultivo_id=c.id),0) AS sembradas,
      COALESCE((SELECT SUM(m.cantidad) FROM mermas m JOIN lotes l ON l.id=m.lote_id WHERE l.cultivo_id=c.id),0) AS mermas,
      COALESCE((SELECT SUM(pi.cantidad) FROM pedido_items pi JOIN pedidos p ON p.id=pi.pedido_id WHERE pi.cultivo_id=c.id AND p.estado='Despachado'),0) AS despachadas,
      COALESCE((SELECT SUM(pi.cantidad) FROM pedido_items pi JOIN pedidos p ON p.id=pi.pedido_id WHERE pi.cultivo_id=c.id AND p.estado='Reservado'),0) AS reservadas
      FROM cultivos c ORDER BY c.nombre''').assign(
        stock_fisico=lambda d:d.sembradas-d.mermas-d.despachadas,
        disponible=lambda d:d.sembradas-d.mermas-d.despachadas-d.reservadas)

init()
st.title('🌱 HidroGestión')
st.caption('Prototipo local de funcionalidades · datos ficticios · no apto para operaciones reales')
modulo=st.sidebar.radio('Módulos', ['Inicio','Producción','Stock','Clientes y pedidos','Logística','Facturas / ARCA','Cuenta corriente','Tablas / Excel'])

if modulo=='Inicio':
    s=stock()
    a,b,c=st.columns(3)
    a.metric('Cultivos',len(s));b.metric('Unidades físicas',f"{int(s.stock_fisico.sum()):,}".replace(',','.'));c.metric('Disponibles sin reserva',f"{int(s.disponible.sum()):,}".replace(',','.'))
    st.info('Circuito previsto: siembra → mermas → disponibilidad → pedido reservado → despacho → factura → cobro.')
    st.warning('En esta demo las plantas sobrevivientes se consideran vendibles sin importar su etapa. La versión real distinguirá plantines, cosechables y stock comercial.')

elif modulo=='Producción':
    st.header('Producción / mesas y lotes')
    st.dataframe(q('''SELECT l.id,l.codigo,c.nombre AS cultivo,m.nombre AS mesa,l.fecha,l.cantidad,l.etapa,
       COALESCE((SELECT SUM(x.cantidad) FROM mermas x WHERE x.lote_id=l.id),0) AS merma,
       l.cantidad-COALESCE((SELECT SUM(x.cantidad) FROM mermas x WHERE x.lote_id=l.id),0) AS saldo
       FROM lotes l JOIN cultivos c ON c.id=l.cultivo_id LEFT JOIN mesas m ON m.id=l.mesa_id ORDER BY l.id'''),hide_index=True,use_container_width=True)
    t1,t2,t3=st.tabs(['Nueva siembra','Registrar merma','Mesas'])
    with t1:
        with st.form('sembrar'):
            cs=opciones('cultivos'); ms=opciones('mesas')
            cultivo=st.selectbox('Cultivo',list(cs),format_func=lambda i:cs[i]); mesa=st.selectbox('Mesa',list(ms),format_func=lambda i:ms[i])
            fecha=st.date_input('Fecha siembra',date.today()); cantidad=st.number_input('Cantidad inicial',min_value=1,value=500,step=1)
            etapa=st.selectbox('Etapa', ['Siembra','Germinación','Trasplante','Crecimiento','Cosechable'])
            if st.form_submit_button('Registrar siembra'):
                code='H-'+str(int(q('SELECT COALESCE(MAX(id),0) AS n FROM lotes').iloc[0].n)+1).zfill(3)
                execute('INSERT INTO lotes(codigo,cultivo_id,mesa_id,fecha,cantidad,etapa) VALUES (?,?,?,?,?,?)',(code,int(cultivo),int(mesa),fecha.isoformat(),int(cantidad),etapa))
                st.success(f'Lote {code} registrado.');st.rerun()
    with t2:
        lo=q('SELECT id,codigo FROM lotes'); lo_map=dict(zip(lo.id,lo.codigo))
        with st.form('mermas'):
            elegido=st.selectbox('Lote', list(lo_map),format_func=lambda i:lo_map[i]); fecha_m=st.date_input('Fecha de merma',date.today())
            n=st.number_input('Cantidad perdida',min_value=1,step=1,value=10)
            causa=st.selectbox('Motivo',['No germinación','Daño','Enfermedad','Descarte','Otro'])
            if st.form_submit_button('Guardar merma'):
                lote=q('SELECT fecha,cantidad FROM lotes WHERE id=?',(int(elegido),)).iloc[0]
                m=int(q('SELECT COALESCE(SUM(cantidad),0) AS n FROM mermas WHERE lote_id=?',(int(elegido),)).iloc[0].n)
                if fecha_m.isoformat()<lote.fecha or int(n)>int(lote.cantidad)-m: st.error('Fecha anterior a la siembra o merma superior al saldo.')
                else:
                    execute('INSERT INTO mermas(lote_id,fecha,cantidad,motivo) VALUES (?,?,?,?)',(int(elegido),fecha_m.isoformat(),int(n),causa))
                    st.success('Merma registrada');st.rerun()
    with t3:
        st.dataframe(q('SELECT * FROM mesas'),hide_index=True,use_container_width=True)
        with st.form('newmesa'):
            nombre=st.text_input('Nombre de mesa');sector=st.text_input('Sector');cap=st.number_input('Capacidad',min_value=1,value=1000)
            if st.form_submit_button('Agregar mesa'):
                if not nombre.strip():st.error('Ingresá el nombre de mesa')
                else:
                    try:execute('INSERT INTO mesas(nombre,sector,capacidad) VALUES (?,?,?)',(nombre.strip(),sector,int(cap)));st.rerun()
                    except sqlite3.IntegrityError:st.error('La mesa ya existe')

elif modulo=='Stock':
    st.header('Stock y disponibilidad comercial')
    st.dataframe(stock().drop(columns=['cultivo_id']),hide_index=True,use_container_width=True)
    st.caption('Saldo de prueba = sembradas − mermas − despachadas − reservadas. No identifica todavía lotes aptos por fecha, cosechas ni ubicaciones de picking.')

elif modulo=='Clientes y pedidos':
    st.header('Clientes y pedidos')
    st.dataframe(q('SELECT id,nombre,cuit,domicilio FROM clientes'),hide_index=True,use_container_width=True)
    t1,t2=st.tabs(['Registrar pedido','Nuevo cliente'])
    with t1:
        st.dataframe(q('''SELECT p.id,p.fecha,c.nombre AS cliente,p.estado,pi.cantidad,cu.nombre AS cultivo,pi.precio
        FROM pedidos p JOIN clientes c ON c.id=p.cliente_id JOIN pedido_items pi ON pi.pedido_id=p.id JOIN cultivos cu ON cu.id=pi.cultivo_id ORDER BY p.id DESC'''),hide_index=True,use_container_width=True)
        with st.form('newpedido'):
            cl=opciones('clientes'); cu=opciones('cultivos')
            cliente=st.selectbox('Cliente',list(cl),format_func=lambda i:cl[i]);cultivo=st.selectbox('Cultivo',list(cu),format_func=lambda i:cu[i]);cantidad=st.number_input('Unidades',min_value=1,value=100)
            precio=st.number_input('Precio unitario (demo)',min_value=0.0,value=1000.0,step=10.0)
            if st.form_submit_button('Reservar pedido'):
                with conn() as c:
                    # Prototype: no concurrent-user locking. Production needs atomic reservation.
                    d=stock().set_index('cultivo_id')
                    if int(cantidad)>int(d.loc[cultivo,'disponible']):st.error('No hay stock disponible suficiente.')
                    else:
                        p=c.execute('INSERT INTO pedidos(cliente_id,fecha,estado) VALUES (?,?,?)',(int(cliente),date.today().isoformat(),'Reservado')).lastrowid
                        c.execute('INSERT INTO pedido_items(pedido_id,cultivo_id,cantidad,precio) VALUES (?,?,?,?)',(p,int(cultivo),int(cantidad),float(precio)))
                        st.success(f'Pedido {p} reservado');st.rerun()
    with t2:
        with st.form('newcliente'):
            nombre=st.text_input('Razón social / nombre');cuit=st.text_input('CUIT (opcional en demo)');dom=st.text_input('Domicilio')
            if st.form_submit_button('Agregar cliente'):
                if nombre.strip():execute('INSERT INTO clientes(nombre,cuit,domicilio) VALUES (?,?,?)',(nombre,cuit,dom));st.rerun()
                else:st.error('Ingresá nombre')

elif modulo=='Logística':
    st.header('Logística / despacho')
    st.dataframe(q('''SELECT p.id AS pedido,c.nombre AS cliente,p.estado,pi.cantidad,cu.nombre AS cultivo
    FROM pedidos p JOIN clientes c ON c.id=p.cliente_id JOIN pedido_items pi ON pi.pedido_id=p.id JOIN cultivos cu ON cu.id=pi.cultivo_id ORDER BY p.id DESC'''),hide_index=True,use_container_width=True)
    pendientes=q("SELECT id FROM pedidos WHERE estado='Reservado'")
    if len(pendientes):
        with st.form('despacho'):
            pid=st.selectbox('Pedido reservado',list(pendientes.id));conductor=st.text_input('Conductor / repartidor');obs=st.text_input('Observaciones');fecha=st.date_input('Fecha de despacho',date.today())
            if st.form_submit_button('Confirmar salida física'):
                with conn() as c:
                    c.execute('INSERT INTO despachos(pedido_id,fecha,conductor,observaciones) VALUES (?,?,?,?)',(int(pid),fecha.isoformat(),conductor,obs))
                    c.execute("UPDATE pedidos SET estado='Despachado' WHERE id=?",(int(pid),))
                st.success('Despacho confirmado. Se libera la reserva y se descuenta stock físico.');st.rerun()
    else:st.info('No hay pedidos reservados para despachar.')

elif modulo=='Facturas / ARCA':
    st.header('Facturas / salida TXT')
    st.warning('TXT **genérico de intercambio**, no importable directamente en ARCA Comprobantes en Línea. No emite comprobantes ni obtiene CAE.')
    st.dataframe(q('''SELECT f.id,f.fecha,f.tipo,f.numero,c.nombre AS cliente,f.importe,f.cae,p.id AS pedido
       FROM facturas f JOIN pedidos p ON p.id=f.pedido_id JOIN clientes c ON c.id=p.cliente_id ORDER BY f.id DESC'''),hide_index=True,use_container_width=True)
    candidatos=q('''SELECT p.id,c.nombre AS cliente,ROUND(SUM(pi.cantidad*pi.precio),2) AS total
    FROM pedidos p JOIN clientes c ON c.id=p.cliente_id JOIN pedido_items pi ON pi.pedido_id=p.id
    WHERE p.estado='Despachado' AND NOT EXISTS(SELECT 1 FROM facturas f WHERE f.pedido_id=p.id) GROUP BY p.id,c.nombre''')
    if len(candidatos):
        with st.form('facturar'):
            i=st.selectbox('Pedido despachado',list(candidatos.id),format_func=lambda x:f"Pedido {x} · {candidatos.loc[candidatos.id==x,'cliente'].iloc[0]}")
            tipo=st.selectbox('Tipo comprobante',['A','B','C']);numero=st.text_input('Número fiscal efectivamente emitido (ej. 0001-00000001)');cae=st.text_input('CAE (opcional en demo)')
            st.write('Importe ilustrativo del pedido:',float(candidatos.loc[candidatos.id==i,'total'].iloc[0]))
            importe=st.number_input('Total final del comprobante',min_value=0.0,value=float(candidatos.loc[candidatos.id==i,'total'].iloc[0]))
            if st.form_submit_button('Registrar factura externa'):
                if not numero.strip():st.error('Indicá número de factura real.')
                else:
                    execute('INSERT INTO facturas(pedido_id,fecha,tipo,numero,cae,importe) VALUES (?,?,?,?,?,?)',(int(i),date.today().isoformat(),tipo,numero.strip(),cae.strip(),float(importe)))
                    st.success('Factura registrada, se genera débito en cuenta corriente.');st.rerun()
    exportar=q('''SELECT p.id AS pedido,c.nombre AS cliente,c.cuit,cu.nombre AS producto,pi.cantidad,pi.precio,
      ROUND(pi.cantidad*pi.precio,2) AS subtotal FROM pedidos p JOIN clientes c ON c.id=p.cliente_id
      JOIN pedido_items pi ON pi.pedido_id=p.id JOIN cultivos cu ON cu.id=pi.cultivo_id
      WHERE p.estado='Despachado' ORDER BY p.id''')
    st.download_button('Descargar TXT de intercambio |',exportar.to_csv(index=False,sep='|').encode('utf-8-sig'),file_name='pedidos_para_facturar_DEMO.txt',mime='text/plain')

elif modulo=='Cuenta corriente':
    st.header('Cuenta corriente y cobranzas')
    fact=q('''SELECT f.id AS factura_id,c.nombre AS cliente,f.tipo||' '||f.numero AS comprobante,f.importe,
     COALESCE((SELECT SUM(co.importe) FROM cobranzas co WHERE co.factura_id=f.id),0) AS cobrado
     FROM facturas f JOIN pedidos p ON p.id=f.pedido_id JOIN clientes c ON c.id=p.cliente_id ORDER BY f.id''')
    if len(fact):
        fact['saldo']=fact['importe']-fact['cobrado'];st.dataframe(fact,hide_index=True,use_container_width=True)
        pend=fact[fact.saldo>0.001]
        if len(pend):
            with st.form('pago'):
                fid=st.selectbox('Factura a imputar',list(pend.factura_id),format_func=lambda i:f"{pend.loc[pend.factura_id==i,'cliente'].iloc[0]} · {pend.loc[pend.factura_id==i,'comprobante'].iloc[0]}")
                maximo=float(pend.loc[pend.factura_id==fid,'saldo'].iloc[0]);importe=st.number_input('Cobranza a imputar',min_value=0.01,max_value=maximo,value=maximo,step=0.01)
                medio=st.selectbox('Medio de pago',['Transferencia','Efectivo','Cheque','Otro']);referencia=st.text_input('Referencia')
                if st.form_submit_button('Registrar cobranza'):
                    with conn() as c:
                        saldo=c.execute('SELECT f.importe-COALESCE((SELECT SUM(co.importe) FROM cobranzas co WHERE co.factura_id=f.id),0) FROM facturas f WHERE f.id=?',(int(fid),)).fetchone()[0]
                        if float(importe)>saldo+0.001:st.error('La imputación supera el saldo actual.')
                        else:c.execute('INSERT INTO cobranzas(factura_id,fecha,importe,medio,referencia) VALUES (?,?,?,?,?)',(int(fid),date.today().isoformat(),float(importe),medio,referencia));st.success('Cobranza imputada.');st.rerun()
    else:st.info('No hay facturas registradas. Primero despachá y registrá una factura desde el módulo anterior.')

else:
    st.header('Tablas abiertas / Excel')
    st.write('Estas son las tablas originales de la base de datos. Podés ver y descargar cada una para analizarla en Excel.')
    nombres=['mesas','cultivos','lotes','mermas','clientes','pedidos','pedido_items','despachos','facturas','cobranzas']
    tabla=st.selectbox('Tabla de datos',nombres)
    df=q(f'SELECT * FROM {tabla} ORDER BY id DESC')
    st.dataframe(df,hide_index=True,use_container_width=True)
    st.download_button('Descargar esta tabla en CSV',df.to_csv(index=False,sep=';').encode('utf-8-sig'),file_name=f'{tabla}.csv',mime='text/csv')
    st.download_button('Descargar la base SQLite completa',DB.read_bytes(),file_name='hidrogestion.db',mime='application/octet-stream')
    st.caption('Los IDs relacionan las tablas; el sistema muestra nombres descriptivos en las pantallas operativas. Para modificar registros se utilizan los formularios, no los archivos CSV.')
