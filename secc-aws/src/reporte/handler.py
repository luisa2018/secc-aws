import json
import base64
from fpdf import FPDF
from datetime import datetime


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
        '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '-', '\u00b7': '-',
        '\u2026': '...', '\u00e9': 'e', '\u00f3': 'o', '\u00fa': 'u',
        '\u00ed': 'i', '\u00e1': 'a', '\u00f1': 'n', '\u00fc': 'u',
        '\u00e0': 'a', '\u00e8': 'e', '\u00ec': 'i', '\u00f2': 'o',
        '\u00f9': 'u',
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
                  f'Pagina {self.page_no()} - Generado por SECC-AWS - '
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

    # Portada
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*InformePDF.DORADO)
    pdf.set_x(10)
    pdf.cell(0, 8, 'Informe Ejecutivo de Estimacion de Costos AWS', ln=True, align='C')
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*InformePDF.GRIS)
    pdf.set_x(10)
    pdf.cell(0, 5,
             f"Escenario: {limpiar(meta.get('escenario',''))}   "
             f"Fecha: {meta.get('fecha_ejecucion','')[:10]}",
             ln=True, align='C')
    pdf.ln(4)

    # Metricas principales
    pdf.titulo_seccion('Metricas principales')
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
        pdf.kv('  Configuracion', s.get('configuracion_minima', ''))
        pdf.kv('  Costo mensual', fmt_usd(s.get('costo_mensual', 0)), InformePDF.VERDE)
        pdf.kv('  % del total',   fmt_pct(s.get('porcentaje_del_total', 0)))
        pdf.ln(1)

    # Servicios propuestos
    pdf.titulo_seccion(f'Servicios propuestos ({len(servicios)} servicios)')
    for i, s in enumerate(servicios):
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.DORADO)
        fill_color = InformePDF.FONDO if i % 2 == 0 else InformePDF.BLANCO
        pdf.set_fill_color(*fill_color)
        pdf.cell(0, 7, limpiar(f"  {s.get('servicio_aws', '')}"), ln=True, fill=True)
        pdf.kv('  Configuracion',  s.get('configuracion_minima', ''))
        pdf.kv('  Justificacion',  s.get('justificacion', ''))
        precio_str = f"${s.get('precio_unitario', 0):.4f} / {limpiar(s.get('unidad', ''))}"
        pdf.kv('  Precio unitario', precio_str)
        pdf.kv('  Costo mensual',   fmt_usd(s.get('costo_mensual', 0)), InformePDF.VERDE)
        pdf.ln(2)

    # Well-Architected
    pdf.titulo_seccion('AWS Well-Architected - Optimizacion de costos')
    costo_m    = float(costo_est.get('costo_mensual', 0))
    ahorro     = float(well.get('ahorro_estimado_usd', 0))
    optimizado = costo_m - ahorro
    y0 = pdf.get_y()
    bw = 59
    pdf.metrica_box(10,  y0, bw, 14, 'Costo actual',     fmt_usd(costo_m))
    pdf.metrica_box(71,  y0, bw, 14, 'Costo optimizado', fmt_usd(optimizado))
    pdf.metrica_box(132, y0, bw, 14, 'Ahorro estimado',  fmt_usd(ahorro), InformePDF.VERDE)
    pdf.ln(18)
    pdf.kv('Evaluacion',    well.get('evaluacion', ''))
    pdf.kv('Recomendacion', well.get('recomendacion', ''))

    # Modelo de pricing
    pdf.titulo_seccion('Modelo de pricing recomendado')
    for p in pricing:
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 6, limpiar(f"  {p.get('servicio_aws', '')}"), ln=True)
        pdf.kv('  Modelo',        p.get('modelo_recomendado', ''))
        pdf.kv('  Justificacion', p.get('justificacion', ''))
        pdf.ln(1)

    # Region recomendada
    pdf.titulo_seccion('Region recomendada')
    pdf.kv('Region',        region.get('region', ''))
    pdf.kv('Justificacion', region.get('justificacion', ''))

    # Alternativa de menor costo
    if alt.get('aplica'):
        pdf.titulo_seccion('Alternativa de menor costo')
        pdf.parrafo(alt.get('descripcion', ''))
        pdf.kv('Ahorro estimado', fmt_usd(alt.get('ahorro_estimado', 0)), InformePDF.VERDE)

    # Analisis de migracion
    if migracion.get('aplica'):
        pdf.titulo_seccion('Analisis de migracion')
        pdf.kv('Costo actual (on-premise)', fmt_usd(migracion.get('costo_actual_estimado_usd', 0)))
        pdf.kv('Ahorro mensual estimado',   fmt_usd(migracion.get('ahorro_mensual_estimado_usd', 0)), InformePDF.VERDE)
        pdf.kv('Periodo de retorno',        migracion.get('periodo_retorno_inversion', ''))

    # Buenas practicas
    pdf.titulo_seccion('Buenas practicas de gestion de costos')
    etiquetas = bp.get('etiquetado_ejemplo', {})
    if etiquetas:
        pdf.set_x(10)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*InformePDF.DORADO)
        pdf.cell(0, 5, 'Etiquetado recomendado:', ln=True)
        for k, v in etiquetas.items():
            pdf.kv(f'  {k}', str(v))
        pdf.ln(2)
    pdf.kv('AWS Budgets',        bp.get('budgets', ''))
    pdf.kv('Cost Explorer',      bp.get('cost_explorer', ''))
    pdf.kv('Revision periodica', bp.get('revision_periodica', ''))

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
        'Este informe fue generado automaticamente por SECC-AWS. '
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