from flask import Flask, render_template, Response
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.event import listens_for
from wtforms import form, fields, validators
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
from flask import request

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estadisticas_deportivas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'estadisticas'
db = SQLAlchemy(app)
admin = Admin(app, name='Admin', template_mode='bootstrap3')

class Equipo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    jugadores = db.relationship('Jugador', back_populates='equipo', lazy=True)
    estadisticas = db.relationship('Estadistica', back_populates='equipo', lazy=True)

    def __str__(self):
        return self.nombre


class Jugador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    numero_camiseta = db.Column(db.Integer, nullable=False)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    equipo = db.relationship('Equipo', back_populates='jugadores')

    def __str__(self):
        return self.nombre

class Estadistica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    equipo = db.relationship('Equipo', back_populates='estadisticas')
    partidos_ganados = db.Column(db.Integer, nullable=False)
    partidos_empatados = db.Column(db.Integer, nullable=False)
    partidos_perdidos = db.Column(db.Integer, nullable=False)
    goles = db.Column(db.Integer, nullable=False)
    remates_al_arco = db.Column(db.Integer, nullable=False)
    asistencia = db.Column(db.Integer, nullable=False)
    tarjetas_amarillas = db.Column(db.Integer, nullable=False)
    tarjetas_rojas = db.Column(db.Integer, nullable=False)

    probabilidad_ganar = db.Column(db.Float, default=0.0)
    probabilidad_perder = db.Column(db.Float, default=0.0)

    def __str__(self):
        return f'Equipo{self.equipo.nombre} - Prob. Ganar: {self.probabilidad_ganar:.2f}%, Prob. Perder: {self.probabilidad_perder:.2f}%'

@listens_for(Estadistica, 'before_update')
@listens_for(Estadistica, 'before_insert')
def calcular_probabilidades(mapper, connection, target):
    total_partidos = target.partidos_ganados + target.partidos_empatados + target.partidos_perdidos
    if total_partidos == 0:
        target.probabilidad_ganar = 0.0
        target.probabilidad_perder = 0.0
    else:
        target.probabilidad_ganar = (target.partidos_ganados / total_partidos) * 100.0
        target.probabilidad_perder = (target.partidos_perdidos / total_partidos) * 100.0


def generar_grafico(estadisticas):
    equipos = [estadistica.equipo.nombre for estadistica in estadisticas]
    partidos_ganados = [estadistica.partidos_ganados for estadistica in estadisticas]
    partidos_empatados = [estadistica.partidos_empatados for estadistica in estadisticas]
    partidos_perdidos = [estadistica.partidos_perdidos for estadistica in estadisticas]

    fig, ax = plt.subplots()
    bar_width = 0.2
    index = np.arange(len(equipos))

    bar1 = ax.bar(index, partidos_ganados, bar_width, label='Partidos Ganados')
    bar2 = ax.bar(index + bar_width, partidos_empatados, bar_width, label='Partidos Empatados')
    bar3 = ax.bar(index + 2 * bar_width, partidos_perdidos, bar_width, label='Partidos Perdidos')

    ax.set_xlabel('Equipos')
    ax.set_ylabel('Cantidad de Partidos')
    ax.set_title('Estadísticas de Partidos')
    ax.set_xticks(index + bar_width)
    
    # Rotar manualmente las etiquetas en 25 grados
    ax.set_xticklabels(equipos, rotation=10, ha="right")
    
    ax.legend()

    canvas = FigureCanvas(fig)
    output = BytesIO()
    canvas.print_png(output)
    return output.getvalue()


class EstadisticaForm(form.Form):
    equipo_id = fields.SelectField('Equipo', coerce=int, validators=[validators.DataRequired()])
    partidos_ganados = fields.IntegerField('Partidos Ganados', [validators.NumberRange(min=0)])
    partidos_empatados = fields.IntegerField('Partidos Empatados', [validators.NumberRange(min=0)])
    partidos_perdidos = fields.IntegerField('Partidos Perdidos', [validators.NumberRange(min=0)])
    goles = fields.IntegerField('Goles', [validators.NumberRange(min=0)])
    remates_al_arco = fields.IntegerField('Remates al Arco', [validators.NumberRange(min=0)])
    asistencia = fields.IntegerField('Asistencia', [validators.NumberRange(min=0)])
    tarjetas_amarillas = fields.IntegerField('Tarjetas Amarillas', [validators.NumberRange(min=0)])
    tarjetas_rojas = fields.IntegerField('Tarjetas Rojas', [validators.NumberRange(min=0)])

    def __init__(self, *args, **kwargs):
        super(EstadisticaForm, self).__init__(*args, **kwargs)
        # Configura el campo del equipo con opciones basadas en los equipos existentes
        self.equipo_id.choices = [(equipo.id, equipo.nombre) for equipo in Equipo.query.all()]


class EstadisticaView(ModelView):
    column_display_pk = True
    column_list = ['equipo.nombre', 'partidos_ganados', 'partidos_empatados', 'partidos_perdidos',
                    'goles', 'remates_al_arco', 'asistencia', 'tarjetas_amarillas', 'tarjetas_rojas',
                    'probabilidad_ganar', 'probabilidad_perder']
    column_labels = {
        'equipo.nombre': 'Equipo',  
        'partidos_ganados': 'Partidos Ganados',
        'partidos_empatados': 'Partidos Empatados',
        'partidos_perdidos': 'Partidos Perdidos',
        'goles': 'Goles',
        'remates_al_arco': 'Remates al Arco',
        'asistencia': 'Asistencia',
        'tarjetas_amarillas': 'Tarjetas Amarillas',
        'tarjetas_rojas': 'Tarjetas Rojas',
        'probabilidad_ganar': 'Probabilidad Ganar',
        'probabilidad_perder': 'Probabilidad Perder',
    }
    column_formatters = {
        'probabilidad_ganar': lambda view, context, model, name: f'{model.probabilidad_ganar:.2f}%',
        'probabilidad_perder': lambda view, context, model, name: f'{model.probabilidad_perder:.2f}%'
    }

    form = EstadisticaForm

    def on_model_change(self, form, model, is_created):
        equipo_id = form.equipo_id.data if form.equipo_id.data else None
        model.equipo_id = equipo_id
        super().on_model_change(form, model, is_created)

class EquipoView(ModelView):
    column_display_pk = True
    column_list = ['nombre']

class JugadorView(ModelView):
    column_display_pk = True
    column_list = ['nombre', 'numero_camiseta', 'equipo.nombre']
    
admin.add_view(EquipoView(Equipo, db.session))
admin.add_view(JugadorView(Jugador, db.session))
admin.add_view(EstadisticaView(Estadistica, db.session))

# PAGINACION 
def paginate_query(query, page=1, per_page=5):
    """
    Paginación de cualquier consulta de SQLAlchemy.
    """
    return query.paginate(page=page, per_page=per_page)

# RUTAS PARA VISUALIZAR

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/equipos')
def equipos():
    page = request.args.get('page', 1, type=int)  # Obtener la página desde la URL
    equipos_paginated = paginate_query(Equipo.query, page=page, per_page=5)  # Llamar a la función global
    return render_template('equipos.html', equipos=equipos_paginated.items, pagination=equipos_paginated)


@app.route('/jugadores')
def jugadores():
    page = request.args.get('page', 1, type=int)
    jugadores_paginated = paginate_query(Jugador.query, page=page, per_page=8)
    return render_template('jugadores.html', jugadores=jugadores_paginated.items, pagination=jugadores_paginated)

@app.route('/estadisticas')
def estadisticas():
    estadisticas = Estadistica.query.all()
    return render_template('estadisticas.html', estadisticas=estadisticas)

@app.route('/equipo/<int:equipo_id>')
def equipo(equipo_id):
    equipo = Equipo.query.get(equipo_id)
    if equipo:
        jugadores = Jugador.query.filter_by(equipo_id=equipo.id).all()
        return render_template('equipo_jugador.html', equipo=equipo, jugadores=jugadores)
    else:
        return render_template('error.html', mensaje='Equipo no encontrado')

@app.route('/generar_pdf')
def generar_pdf():
    estadisticas = Estadistica.query.all()
    pdf_output = generar_informe_pdf(estadisticas)
    return Response(pdf_output, mimetype='application/pdf', headers={'Content-Disposition': 'inline;filename=informe.pdf'})

def generar_informe_pdf(estadisticas):
    # Crear un objeto PDF usando ReportLab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Crear un estilo para el título
    estilo_titulo = styles['Title']

    # Agregar un título al informe PDF
    titulo = Paragraph('Informe de Estadísticas Deportivas', estilo_titulo)
    doc.build([titulo])

    # Crear una tabla para las estadísticas
    data = [['Equipo', 'PG', 'PE', 'PP', 'Goles','RA','A','TA','TR', 'Prob. Ganar', 'Prob. Perder'],]
    for estadistica in estadisticas:
        data.append([estadistica.equipo.nombre,
                     estadistica.partidos_ganados,
                     estadistica.partidos_empatados,
                     estadistica.partidos_perdidos,
                     estadistica.goles, 
                     estadistica.remates_al_arco,
                     estadistica.asistencia,
                     estadistica.tarjetas_amarillas,
                     estadistica.tarjetas_rojas,
                     round(estadistica.probabilidad_ganar, 2), 
                     round(estadistica.probabilidad_perder, 2)])
    # Estilo para el encabezado de la tabla (fondo azul y línea naranja)
    estilo_encabezado = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1C3247')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.orange),
    ]
    
    tabla = Table(data, style=TableStyle(estilo_encabezado))

    # Generar gráfico
    grafico_bytes = generar_grafico(estadisticas)

    # Convertir la imagen de la gráfica a un objeto ImageReader
    grafico_reader = Image(BytesIO(grafico_bytes), width=400, height=300)

    # Agregar tanto la tabla como la gráfica al informe PDF
    doc.build([titulo, tabla, grafico_reader])

    # Retornar el contenido del buffer
    buffer.seek(0)
    return buffer.getvalue()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
