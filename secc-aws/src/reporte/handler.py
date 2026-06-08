import json
import base64
from fpdf import FPDF
from datetime import datetime


ESCENARIOS = {
    'monolitica': 'Monolítica',
    'microservicios': 'Microservicios',
    'serverless': 'Serverless',
    'event_driven': 'Event-Driven',
    'hibrida': 'H\xedbrida'
}


def fmt_usd(valor):
    try:
        return f"${float(valor):,.2f} USD"
    except Exception:
        return str(valor)


def fmt_pct(valor):
    try:
        return f"{float(valor):.1f}%"
    except Exception:
        return str(valor)


def limpiar(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    reemplazos = {
        '\u2014': '-',
        '\u2013': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2022': '-',
        '\u00b7': '-',
        '\u2026': '...',
        '\u2192': '->',
        '\u00bb': '>>',
        '\u00ab': '<<',
    }
    for car, rep in reemplazos.items():
        texto = texto.replace(car, rep)
    texto = texto.encode('latin-1', errors='replace').decode('latin-1')
    return texto


class InformePDF(FPDF):

    DORADO = (200, 150, 12)
    VERDE  = (30, 124, 58)
    TEXTO  = (26, 26, 26)
    GRIS   = (85, 85, 85)
    FONDO  = (255, 248, 225)
    BLANCO = (255, 255, 255)
    ROJO   = (198, 40, 40)

    def header(self):
        self.set_fill_color(*self.DORADO)
        self.rect(0, 0, 210, 18, 'F')
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*self.BLANCO)
        self.set_xy(10, 4)
        self.cell(0, 10, 'SECC-AWS  |  Informe Ejecutivo de Costos', ln=False)
        self.ln(18)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*self.GRIS)
        self.cell(0, 8,
                  f'P\xe1gina {self.page_no()} - Generado por SECC-AWS - '
                  f'{datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC',
                  align='C')

    def titulo_seccion(self, texto):
        self.ln(4)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*self.DORADO)
        self.set_fill_color(*self.FONDO)
        self.set_x(10)
        self.cell(0, 8, f'  {limpiar(texto)}', ln=True, fill=True)
        self.set_draw_color(*self.DORADO)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def kv(self, clave, valor, color_valor=None):
        self.set_x(10)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*self.GRIS)
        self.cell(55, 6, limpiar(clave) + ':', ln=False)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*(color_valor or self.TEXTO))
        self.multi_cell(0, 6, limpiar(str(valor)))

    def parrafo(self, texto, size=9):
        self.set_x(10)
        self.set_font('Helvetica', '', size)
        self.set_text_color(*self.TEXTO)
        self.multi_cell(0, 5, limpiar(str(texto)))
        self.ln(2)

    def metrica_box(self, x, y, w, h, etiqueta, valor, color_valor=None):
        self.set_fill_color(*self.FONDO)
        self.set_draw_color(*self.DORADO)
        self.set_line_width(0.3)
        self.rect(x, y, w, h, 'FD')
        self.set_xy(x + 2, y + 1)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.GRIS)
        self.cell(w - 4, 4, limpiar(etiqueta), align='C')
        self.set_xy(x + 2, y + 5)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*(color_valor or self.TEXTO))
        self.cell(w - 4, 5, limpiar(str(valor)), align='C')


def generar_pdf(data: dict) -> bytes:
    pdf = InformePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(10, 22, 10)

    meta      = data.get('metadata', {})
    servicios = data.get('servicios', [])
    costo_est = data.get('costo_estimado', {})
    eval_pres = data.get('evaluacion_presupuesto', {})
    top3      = data.get('top_3_servicios', [])
    riesgo    = data.get('nivel_riesgo', {})
    pricing   = data.get('modelo_pricing', [])
    region    = data.get('region_recomendada', {})
    well      = data.get('well_architected', {})
    alt       = data.get('alternativa_menor_costo', {})
    migracion = data.get('analisis_migracion', {})
    bp        = data.get('buenas_practicas', {})
    limits    = data.get('limitaciones_estimado', [])
    resumen   = limpiar(data.get('resumen', ''))

    escenario_raw = meta.get('escenario', '')
    escenario_display = ESCENARIOS.get(escenario_raw, escenario_raw)

    # Portada
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*InformePDF.DORADO)
    pdf.set_x(10)
    pdf.cell(0, 8, 'Informe Ejecutivo de Estimaci\xf3n de Costos AWS', ln=True, align='C')
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*InformePDF.GRIS)
    pdf.set_x(10)
    pdf.cell(0, 5,
             f"Escenario: {limpiar(escenario_display)}   "
             f"Fecha: {meta.get('fecha_ejecucion','')[:10]}",
             ln=True, align='C')
    pdf.ln(4)

    # Metricas principales
    pdf.titulo_seccion('M\xe9tricas principales')
    y0 = pdf.get_y()
    bw = 31
    x0 = 10
    dentro = eval_pres.get('dentro_presupuesto', True)
    color_pres = InformePDF.VERDE if dentro else InformePDF.ROJO
    metricas = [
        ('Costo mensual',   fmt_usd(costo_est.get('costo_mensual', 0)), None),
        ('Costo horizonte', fmt_usd(costo_est.get('costo_horizonte', 0)), None),
        ('Periodo',         limpiar(costo_est.get('periodo', '')), None),
        ('% presupuesto',   fmt_pct(eval_pres.get('porcentaje_del_presupuesto', 0)), None),
        ('Estado',          'Dentro' if dentro else 'Excede', color_pres),
        ('Nivel riesgo',    limpiar(riesgo.get('clasificacion', '')), None),
    ]
    for i, (etq, val, col) in enumerate(metricas):
        pdf.metrica_box(x0 + i * (bw + 1), y0, bw, 12, etq, val, col)
    pdf.ln(16)

    # Resumen ejecutivo
    pdf.titulo_seccion('Resumen ejecutivo')
    pdf.parrafo(resumen)

    # Top 3 servicios
    pdf.titulo_seccion('Top 3 servicios de mayor costo')
    for i, s in enumerate(top3):
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 6, limpiar(f"#{i+1}  {s.get('servicio_aws','')}"), ln=True)
        pdf.kv('  Configuraci\xf3n', s.get('configuracion_minima', ''))
        pdf.kv('  Costo mensual', fmt_usd(s.get('costo_mensual', 0)), InformePDF.VERDE)
        pdf.kv('  % del total',   fmt_pct(s.get('porcentaje_del_total', 0)))
        pdf.ln(1)

    # Servicios propuestos
    pdf.titulo_seccion(f'Servicios propuestos ({len(servicios)} servicios)')

    # Encabezados de tabla
    pdf.set_fill_color(*InformePDF.FONDO)
    pdf.set_draw_color(*InformePDF.DORADO)
    pdf.set_line_width(0.3)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*InformePDF.DORADO)
    pdf.set_x(10)
    pdf.cell(60, 7, 'Servicio',          border=1, fill=True)
    pdf.cell(55, 7, 'Configuraci\xf3n',  border=1, fill=True)
    pdf.cell(30, 7, 'Precio unitario',   border=1, fill=True, align='R')
    pdf.cell(20, 7, 'Unidad',            border=1, fill=True, align='C')
    pdf.cell(25, 7, 'Costo mensual',     border=1, fill=True, align='R', ln=True)

    # Filas de servicios
    for i, s in enumerate(servicios):
        fill_color = InformePDF.FONDO if i % 2 == 0 else InformePDF.BLANCO
        pdf.set_fill_color(*fill_color)
        pdf.set_draw_color(220, 220, 220)
        pdf.set_line_width(0.2)

        # Nombre del servicio + justificación debajo
        nombre = limpiar(s.get('servicio_aws', ''))
        justif = limpiar(s.get('justificacion', ''))
        config = limpiar(s.get('configuracion_minima', ''))
        precio_unitario = s.get('precio_unitario', 0)
        if precio_unitario < 0.01:
            precio_str = f"${precio_unitario:.4f}"
        else:
            precio_str = f"${precio_unitario:.2f}"
        unidad = limpiar(s.get('unidad', ''))
        costo_mensual = fmt_usd(s.get('costo_mensual', 0))

        # Calcular altura de fila según contenido
        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*InformePDF.TEXTO)
        pdf.cell(60, 5, nombre, border='LRT', fill=True)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(*InformePDF.GRIS)
        pdf.cell(55, 5, config[:40], border='LRT', fill=True)
        pdf.set_text_color(*InformePDF.TEXTO)
        pdf.cell(30, 5, precio_str, border='LRT', fill=True, align='R')
        pdf.cell(20, 5, unidad[:12], border='LRT', fill=True, align='C')
        pdf.set_text_color(*InformePDF.VERDE)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(25, 5, costo_mensual, border='LRT', fill=True, align='R', ln=True)

        # Justificación en segunda línea
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.set_text_color(*InformePDF.GRIS)
        pdf.cell(60, 4, justif[:45], border='LRB', fill=True)
        pdf.set_text_color(*InformePDF.GRIS)
        pdf.cell(55, 4, config[40:80], border='LRB', fill=True)
        pdf.cell(30, 4, '', border='LRB', fill=True)
        pdf.cell(20, 4, '', border='LRB', fill=True)
        pdf.cell(25, 4, '', border='LRB', fill=True, ln=True)

    # Total mensual
    pdf.set_fill_color(*InformePDF.FONDO)
    pdf.set_draw_color(*InformePDF.DORADO)
    pdf.set_line_width(0.3)
    pdf.set_x(10)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*InformePDF.DORADO)
    pdf.cell(165, 7, 'Total mensual', border=1, fill=True, align='R')
    pdf.set_text_color(*InformePDF.TEXTO)
    pdf.cell(25, 7, fmt_usd(costo_est.get('costo_mensual', 0)), border=1, fill=True, align='R', ln=True)
    pdf.ln(3)

    # Well-Architected
    pdf.titulo_seccion('AWS Well-Architected - Optimizaci\xf3n de costos')
    costo_m    = float(costo_est.get('costo_mensual', 0))
    ahorro     = float(well.get('ahorro_estimado_usd', 0))
    optimizado = costo_m - ahorro
    y0 = pdf.get_y()
    bw = 59
    pdf.metrica_box(10,  y0, bw, 14, 'Costo actual',     fmt_usd(costo_m))
    pdf.metrica_box(71,  y0, bw, 14, 'Costo optimizado', fmt_usd(optimizado))
    pdf.metrica_box(132, y0, bw, 14, 'Ahorro estimado',  fmt_usd(ahorro), InformePDF.VERDE)
    pdf.ln(18)
    pdf.kv('Evaluaci\xf3n',    well.get('evaluacion', ''))
    pdf.kv('Recomendaci\xf3n', well.get('recomendacion', ''))

    # Modelo de pricing
    pdf.titulo_seccion('Modelo de pricing recomendado')
    for p in pricing:
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 6, limpiar(f"  {p.get('servicio_aws', '')}"), ln=True)
        pdf.kv('  Modelo',         p.get('modelo_recomendado', ''))
        pdf.kv('  Justificaci\xf3n',  p.get('justificacion', ''))
        pdf.ln(1)

    # Region recomendada + Motor + Licenciamiento
    pdf.titulo_seccion('Regi\xf3n recomendada')
    pdf.kv('Regi\xf3n',        region.get('region', ''))
    pdf.kv('Justificaci\xf3n', region.get('justificacion', ''))

    if region.get('motor_recomendado') and region.get('motor_recomendado') != 'N/A':
        pdf.ln(2)
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.VERDE)
        pdf.cell(0, 6, 'Motor de base de datos recomendado:', ln=True)
        pdf.kv('  Motor',          region.get('motor_recomendado', ''), InformePDF.VERDE)
        pdf.kv('  Justificaci\xf3n',  region.get('justificacion_motor', ''))

    ref_lic = region.get('referencia_licenciamiento', {})
    if ref_lic and any([
        ref_lic.get('costo_sqlserver_usd', 0),
        ref_lic.get('costo_oracle_usd', 0),
        ref_lic.get('costo_windows_server_usd', 0)
    ]):
        pdf.ln(2)
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 6, 'Referencia de licenciamiento (no incluido en el estimado):', ln=True)
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(*InformePDF.GRIS)
        pdf.multi_cell(0, 5, limpiar(ref_lic.get('nota', '')))
        pdf.ln(1)
        if ref_lic.get('costo_sqlserver_usd', 0):
            pdf.kv('  SQL Server en RDS',
                   f"+{fmt_usd(ref_lic.get('costo_sqlserver_usd', 0))}/mes",
                   InformePDF.ROJO)
        if ref_lic.get('costo_oracle_usd', 0):
            pdf.kv('  Oracle en RDS',
                   f"+{fmt_usd(ref_lic.get('costo_oracle_usd', 0))}/mes",
                   InformePDF.ROJO)
        if ref_lic.get('costo_windows_server_usd', 0):
            pdf.kv('  Windows Server en EC2',
                   f"+{fmt_usd(ref_lic.get('costo_windows_server_usd', 0))}/mes",
                   InformePDF.ROJO)

    # Alternativa de menor costo
    if alt.get('aplica'):
        pdf.titulo_seccion('Alternativa de menor costo')
        pdf.parrafo(alt.get('descripcion', ''))
        pdf.kv('Ahorro estimado', fmt_usd(alt.get('ahorro_estimado', 0)), InformePDF.VERDE)

    # Analisis de migracion
    if migracion.get('aplica'):
        pdf.titulo_seccion('An\xe1lisis de migraci\xf3n')
        pdf.kv('Costo actual (on-premise)', fmt_usd(migracion.get('costo_actual_estimado_usd', 0)))
        pdf.kv('Ahorro mensual estimado',   fmt_usd(migracion.get('ahorro_mensual_estimado_usd', 0)), InformePDF.VERDE)
        pdf.kv('Per\xedodo de retorno',     migracion.get('periodo_retorno_inversion', ''))

    # Buenas practicas
    pdf.titulo_seccion('Buenas pr\xe1cticas de gesti\xf3n de costos')
    etiquetas = bp.get('etiquetado_ejemplo', {})
    if etiquetas:
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 5, 'Etiquetado recomendado:', ln=True)
        for k, v in etiquetas.items():
            pdf.kv(f'  {k}', str(v))
        pdf.ln(2)
    pdf.kv('AWS Budgets',          bp.get('budgets', ''))
    pdf.kv('Cost Explorer',        bp.get('cost_explorer', ''))
    pdf.kv('Revisi\xf3n peri\xf3dica', bp.get('revision_periodica', ''))

    # Limitaciones
    pdf.titulo_seccion('Limitaciones del estimado')
    for lim in limits:
        pdf.set_x(10)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(*InformePDF.TEXTO)
        pdf.multi_cell(0, 5, '- ' + limpiar(str(lim)))

    # Pie
    pdf.ln(4)
    pdf.set_x(10)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(*InformePDF.GRIS)
    pdf.multi_cell(0, 4,
        'Este informe fue generado autom\xe1ticamente por SECC-AWS. '
        'Las estimaciones son orientativas y no constituyen compromisos '
        'contractuales de costos reales. Los precios se obtienen de la '
        'AWS Price List API en el momento de la consulta.')

    return bytes(pdf.output())


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        estimacion = body.get('estimacion')
        if not estimacion:
            return _response(400, None, error='El campo estimacion es requerido')
        pdf_bytes = generar_pdf(estimacion)
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type':        'application/pdf',
                'Content-Disposition': 'attachment; filename="informe_secc_aws.pdf"',
                'Access-Control-Allow-Origin': '*',
            },
            'body':            pdf_b64,
            'isBase64Encoded': True,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return _response(500, None, error=f'Error generando PDF: {str(e)}')


def _response(status, body, error=None):
    payload = {'error': error} if error else body
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(payload),
    }