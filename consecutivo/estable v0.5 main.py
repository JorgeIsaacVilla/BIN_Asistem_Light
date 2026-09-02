import sys
import json
import psutil

from pathlib import Path
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal, QTime
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QProgressBar,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QTimeEdit,
    QCheckBox,
)


# ============================================================
# COLORES DE BIN
# ============================================================

FONDO = "#07080c"

PANEL = "#0d1016"
PANEL_SECUNDARIO = "#11151d"
PANEL_TAREA = "#10141c"

BORGONA = "#8f1638"
BORGONA_CLARO = "#d83261"
BORGONA_OSCURO = "#3a0b18"

TEXTO = "#f1f1f3"
TEXTO_SECUNDARIO = "#89909d"

VERDE = "#46df8e"
AMARILLO = "#ffc857"
AZUL = "#59baff"
ROJO = "#ff5364"
GRIS = "#858d9a"
MORADO = "#b982ff"


# ============================================================
# DÍAS
# ============================================================

DIAS_NOMBRES = [
    "L",
    "M",
    "X",
    "J",
    "V",
    "S",
    "D",
]


# Una tarea cambiará visualmente a PRÓXIMA
# cuando falten 15 minutos o menos.
UMBRAL_PROXIMA_SEGUNDOS = 15 * 60


# ============================================================
# UTILIDADES
# ============================================================

def dias_a_texto(dias):
    """
    Convierte:
        [0, 1, 2]
    en:
        L M X
    """

    if not dias:
        return "--"

    return " ".join(
        DIAS_NOMBRES[dia]
        for dia in sorted(dias)
    )


def duracion_a_segundos(texto):
    """
    Convierte HH:MM:SS a segundos.
    """

    try:

        horas, minutos, segundos = [
            int(valor)
            for valor in texto.split(":")
        ]

        return (
            horas * 3600
            + minutos * 60
            + segundos
        )

    except Exception:

        return 0


def hora_a_segundos(texto):
    """
    Convierte HH:MM a segundos desde medianoche.
    """

    try:

        horas, minutos = [
            int(valor)
            for valor in texto.split(":")
        ]

        return (
            horas * 3600
            + minutos * 60
        )

    except Exception:

        return 0


def segundos_a_hms(segundos):
    """
    Convierte segundos a HH:MM:SS.
    """

    segundos = max(
        0,
        int(segundos)
    )

    horas = segundos // 3600

    minutos = (
        segundos % 3600
    ) // 60

    segundos_restantes = (
        segundos % 60
    )

    return (
        f"{horas:02}:"
        f"{minutos:02}:"
        f"{segundos_restantes:02}"
    )


def describir_tiempo_restante(segundos):
    """
    Convierte una cantidad de segundos
    en un texto amigable para la interfaz.
    """

    segundos = max(
        0,
        int(segundos)
    )


    if segundos < 60:

        return (
            f"{segundos} s"
        )


    minutos = segundos // 60


    if minutos < 60:

        segundos_restantes = (
            segundos % 60
        )

        return (
            f"{minutos} min "
            f"{segundos_restantes} s"
        )


    horas = minutos // 60

    minutos_restantes = (
        minutos % 60
    )


    if horas < 24:

        if minutos_restantes:

            return (
                f"{horas} h "
                f"{minutos_restantes} min"
            )

        return (
            f"{horas} h"
        )


    dias = horas // 24

    horas_restantes = (
        horas % 24
    )


    if horas_restantes:

        return (
            f"{dias} día(s) "
            f"{horas_restantes} h"
        )


    return (
        f"{dias} día(s)"
    )

# ============================================================
# PANEL REUTILIZABLE
# ============================================================

class Panel(QFrame):

    def __init__(self):

        super().__init__()

        self.setObjectName(
            "panel"
        )
# ============================================================
# EDITOR DE TAREAS
# ============================================================

class TaskEditorDialog(QDialog):

    def __init__(
        self,
        parent=None,
        tarea=None,
        validador_conflictos=None,
        excluir_id=None
    ):

        super().__init__(
            parent
        )

        self.tarea = tarea

        self.validador_conflictos = (
            validador_conflictos
        )

        self.excluir_id = excluir_id

        self.setWindowTitle(
            "Configurar tarea"
        )

        self.setMinimumWidth(
            540
        )

        self.crear_interfaz()

        if tarea:
            self.cargar_tarea(
                tarea
            )


    # ========================================================
    # CREAR INTERFAZ
    # ========================================================

    def crear_interfaz(self):

        principal = QVBoxLayout(
            self
        )

        principal.setSpacing(
            14
        )


        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        titulo = QLabel(
            "CONFIGURACIÓN DE TAREA"
        )

        titulo.setObjectName(
            "tituloDialogo"
        )

        principal.addWidget(
            titulo
        )


        descripcion = QLabel(
            "Define cuándo y cómo debe entrar esta tarea "
            "en la cola de ejecución de BIN."
        )

        descripcion.setWordWrap(
            True
        )

        descripcion.setObjectName(
            "textoSecundario"
        )

        principal.addWidget(
            descripcion
        )


        # ----------------------------------------------------
        # FORMULARIO
        # ----------------------------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(
            12
        )


        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        self.nombre = QLineEdit()

        self.nombre.setPlaceholderText(
            "Ej: Publicar contenido de la mañana"
        )

        formulario.addRow(
            "Nombre:",
            self.nombre
        )


        # ----------------------------------------------------
        # HORA
        # ----------------------------------------------------

        self.hora = QTimeEdit()

        self.hora.setDisplayFormat(
            "HH:mm"
        )

        self.hora.setTime(
            QTime(
                5,
                40
            )
        )

        formulario.addRow(
            "Hora:",
            self.hora
        )


        # ----------------------------------------------------
        # REPETICIONES
        # ----------------------------------------------------

        self.veces = QSpinBox()

        self.veces.setRange(
            1,
            99999
        )

        self.veces.setValue(
            1
        )

        formulario.addRow(
            "Veces por ejecución:",
            self.veces
        )


        # ----------------------------------------------------
        # INTERVALO
        # ----------------------------------------------------

        intervalo_widget = QWidget()

        intervalo_layout = QHBoxLayout(
            intervalo_widget
        )

        intervalo_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )


        self.intervalo_valor = QSpinBox()

        self.intervalo_valor.setRange(
            1,
            99999
        )

        self.intervalo_valor.setValue(
            24
        )


        self.intervalo_unidad = QComboBox()

        self.intervalo_unidad.addItems(
            [
                "minutos",
                "horas",
                "días",
            ]
        )

        self.intervalo_unidad.setCurrentText(
            "horas"
        )


        intervalo_layout.addWidget(
            self.intervalo_valor
        )

        intervalo_layout.addWidget(
            self.intervalo_unidad
        )


        formulario.addRow(
            "Cada:",
            intervalo_widget
        )


        # ----------------------------------------------------
        # DURACIÓN ESTIMADA
        # ----------------------------------------------------

        self.duracion = QTimeEdit()

        self.duracion.setDisplayFormat(
            "HH:mm:ss"
        )

        self.duracion.setTime(
            QTime(
                0,
                10,
                0
            )
        )

        formulario.addRow(
            "Duración estimada:",
            self.duracion
        )


        principal.addLayout(
            formulario
        )


        # ----------------------------------------------------
        # DÍAS
        # ----------------------------------------------------

        titulo_dias = QLabel(
            "DÍAS DE EJECUCIÓN"
        )

        titulo_dias.setObjectName(
            "tituloPanel"
        )

        principal.addWidget(
            titulo_dias
        )


        dias_layout = QHBoxLayout()

        self.check_dias = []


        for indice, nombre in enumerate(
            DIAS_NOMBRES
        ):

            check = QCheckBox(
                nombre
            )

            check.setChecked(
                True
            )

            self.check_dias.append(
                check
            )

            dias_layout.addWidget(
                check
            )


        dias_layout.addStretch()


        principal.addLayout(
            dias_layout
        )


        # ----------------------------------------------------
        # AVISO
        # ----------------------------------------------------

        self.aviso = QLabel(
            "BIN comprobará automáticamente si este horario "
            "se solapa con otra tarea antes de guardarlo."
        )

        self.aviso.setWordWrap(
            True
        )

        self.aviso.setObjectName(
            "aviso"
        )

        principal.addWidget(
            self.aviso
        )


        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------

        botones = QDialogButtonBox(
            QDialogButtonBox.Save
            |
            QDialogButtonBox.Cancel
        )


        boton_guardar = botones.button(
            QDialogButtonBox.Save
        )

        boton_guardar.setText(
            "GUARDAR"
        )


        boton_cancelar = botones.button(
            QDialogButtonBox.Cancel
        )

        boton_cancelar.setText(
            "CANCELAR"
        )


        botones.accepted.connect(
            self.validar
        )

        botones.rejected.connect(
            self.reject
        )


        principal.addWidget(
            botones
        )


    # ========================================================
    # CARGAR TAREA EXISTENTE
    # ========================================================

    def cargar_tarea(
        self,
        tarea
    ):

        self.nombre.setText(
            tarea.get(
                "nombre",
                ""
            )
        )


        self.veces.setValue(
            tarea.get(
                "veces",
                1
            )
        )


        self.intervalo_valor.setValue(
            tarea.get(
                "intervalo_valor",
                24
            )
        )


        self.intervalo_unidad.setCurrentText(
            tarea.get(
                "intervalo_unidad",
                "horas"
            )
        )


        hora = QTime.fromString(
            tarea.get(
                "hora",
                "05:40"
            ),
            "HH:mm"
        )


        if hora.isValid():

            self.hora.setTime(
                hora
            )


        duracion = QTime.fromString(
            tarea.get(
                "duracion",
                "00:10:00"
            ),
            "HH:mm:ss"
        )


        if duracion.isValid():

            self.duracion.setTime(
                duracion
            )


        dias_tarea = tarea.get(
            "dias",
            []
        )


        for indice, check in enumerate(
            self.check_dias
        ):

            check.setChecked(
                indice
                in dias_tarea
            )


    # ========================================================
    # OBTENER DÍAS
    # ========================================================

    def obtener_dias(self):

        dias = []


        for indice, check in enumerate(
            self.check_dias
        ):

            if check.isChecked():

                dias.append(
                    indice
                )


        return dias


    # ========================================================
    # OBTENER DATOS
    # ========================================================

    def obtener_datos(self):

        hora = self.hora.time()

        duracion = self.duracion.time()


        return {

            "nombre":
                self.nombre.text().strip(),

            "hora":
                hora.toString(
                    "HH:mm"
                ),

            "veces":
                self.veces.value(),

            "intervalo_valor":
                self.intervalo_valor.value(),

            "intervalo_unidad":
                self.intervalo_unidad.currentText(),

            "dias":
                self.obtener_dias(),

            "duracion":
                duracion.toString(
                    "HH:mm:ss"
                ),

        }


    # ========================================================
    # VALIDAR
    # ========================================================

    def validar(self):

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        if not self.nombre.text().strip():

            QMessageBox.warning(
                self,
                "Nombre requerido",
                "La tarea necesita un nombre."
            )

            return


        # ----------------------------------------------------
        # DÍAS
        # ----------------------------------------------------

        dias = self.obtener_dias()


        if not dias:

            QMessageBox.warning(
                self,
                "Días requeridos",
                "Selecciona al menos un día de ejecución."
            )

            return


        # ----------------------------------------------------
        # COMPROBAR COLISIONES
        # ----------------------------------------------------

        if self.validador_conflictos:

            candidata = self.obtener_datos()


            conflictos = (
                self.validador_conflictos(
                    candidata,
                    excluir_id=self.excluir_id
                )
            )


            if conflictos:

                nombres = "\n".join(

                    (
                        f"• {tarea['nombre']}\n"
                        f"   Hora: {tarea['hora']}  |  "
                        f"Duración: {tarea['duracion']}"
                    )

                    for tarea in conflictos
                )


                QMessageBox.warning(

                    self,

                    "Conflicto de horario",

                    "BIN detectó una colisión.\n\n"

                    "Esta tarea coincide con:\n\n"

                    f"{nombres}\n\n"

                    "BIN solamente puede ejecutar una tarea "
                    "a la vez.\n\n"

                    "Modifica la hora, los días o la duración "
                    "estimada y vuelve a pulsar GUARDAR.\n\n"

                    "Los datos que introdujiste permanecerán "
                    "en esta ventana."
                )


                # ------------------------------------------------
                # MUY IMPORTANTE
                # ------------------------------------------------
                #
                # NO usamos self.accept()
                #
                # Por lo tanto la ventana NO se cierra.
                #
                # El usuario puede modificar los datos y
                # volver a guardar.
                # ------------------------------------------------

                return


        # ----------------------------------------------------
        # TODO CORRECTO
        # ----------------------------------------------------

        self.accept()


# ============================================================
# TARJETA VISUAL DE UNA TAREA
# ============================================================

class TaskCard(QFrame):

    ver_solicitado = Signal(int)

    copiar_solicitado = Signal(int)

    eliminar_solicitado = Signal(int)

    pausa_solicitada = Signal(int)

    ejecutar_solicitado = Signal(int)


    def __init__(
        self,
        tarea
    ):

        super().__init__()

        self.tarea = tarea

        self.setObjectName(
            "tarjetaTarea"
        )

        self.setMinimumWidth(
            0
        )

        self.crear_interfaz()

        self.actualizar_estado()


    # ========================================================
    # CREAR INTERFAZ
    # ========================================================

    def crear_interfaz(self):

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        layout.setSpacing(
            8
        )


        # ----------------------------------------------------
        # CABECERA
        # ----------------------------------------------------

        superior = QHBoxLayout()


        self.numero = QLabel(
            f"{self.tarea['id']:02}"
        )

        self.numero.setObjectName(
            "numeroTarea"
        )


        self.titulo = QLabel(
            self.tarea["nombre"]
        )

        self.titulo.setObjectName(
            "tituloTarea"
        )

        self.titulo.setWordWrap(
            True
        )


        self.estado = QLabel()

        self.estado.setAlignment(
            Qt.AlignRight
        )


        superior.addWidget(
            self.numero
        )

        superior.addWidget(
            self.titulo,
            1
        )

        superior.addWidget(
            self.estado
        )


        layout.addLayout(
            superior
        )


        # ----------------------------------------------------
        # INFORMACIÓN
        # ----------------------------------------------------

        self.info = QLabel()

        self.info.setObjectName(
            "textoSecundario"
        )

        self.info.setWordWrap(
            True
        )


        layout.addWidget(
            self.info
        )


        # ----------------------------------------------------
        # ESTADO / PRÓXIMA EJECUCIÓN
        # ----------------------------------------------------

        self.proxima = QLabel()

        self.proxima.setObjectName(
            "proximaTarea"
        )

        self.proxima.setWordWrap(
            True
        )


        layout.addWidget(
            self.proxima
        )


        # ----------------------------------------------------
        # TIEMPOS
        # ----------------------------------------------------

        tiempos = QHBoxLayout()


        self.duracion = QLabel()

        self.duracion.setObjectName(
            "textoSecundario"
        )


        self.transcurrido = QLabel()

        self.transcurrido.setObjectName(
            "textoSecundario"
        )


        tiempos.addWidget(
            self.duracion
        )

        tiempos.addStretch()

        tiempos.addWidget(
            self.transcurrido
        )


        layout.addLayout(
            tiempos
        )


        # ----------------------------------------------------
        # PROGRESO
        # ----------------------------------------------------

        self.progreso = QProgressBar()

        self.progreso.setRange(
            0,
            100
        )


        layout.addWidget(
            self.progreso
        )


        # ----------------------------------------------------
        # BOTONES PRINCIPALES
        # ----------------------------------------------------

        botones = QHBoxLayout()


        self.boton_ver = QPushButton(
            "VER"
        )


        self.boton_copiar = QPushButton(
            "COPIAR"
        )


        self.boton_pausa = QPushButton()


        botones.addWidget(
            self.boton_ver
        )

        botones.addWidget(
            self.boton_copiar
        )

        botones.addWidget(
            self.boton_pausa
        )


        layout.addLayout(
            botones
        )


        # ----------------------------------------------------
        # EJECUTAR AHORA
        # ----------------------------------------------------

        self.boton_ejecutar = QPushButton(
            "▶ EJECUTAR AHORA"
        )

        self.boton_ejecutar.setObjectName(
            "botonEjecutar"
        )


        layout.addWidget(
            self.boton_ejecutar
        )


        # ----------------------------------------------------
        # ELIMINAR
        # ----------------------------------------------------

        self.boton_eliminar = QPushButton(
            "ELIMINAR"
        )

        self.boton_eliminar.setObjectName(
            "botonEliminar"
        )


        layout.addWidget(
            self.boton_eliminar
        )


        # ----------------------------------------------------
        # EVENTOS
        # ----------------------------------------------------

        self.boton_ver.clicked.connect(

            lambda:
            self.ver_solicitado.emit(
                self.tarea["id"]
            )
        )


        self.boton_copiar.clicked.connect(

            lambda:
            self.copiar_solicitado.emit(
                self.tarea["id"]
            )
        )


        self.boton_eliminar.clicked.connect(

            lambda:
            self.eliminar_solicitado.emit(
                self.tarea["id"]
            )
        )


        self.boton_pausa.clicked.connect(

            lambda:
            self.pausa_solicitada.emit(
                self.tarea["id"]
            )
        )


        self.boton_ejecutar.clicked.connect(

            lambda:
            self.ejecutar_solicitado.emit(
                self.tarea["id"]
            )
        )


    # ========================================================
    # ACTUALIZAR ESTADO
    # ========================================================

    def actualizar_estado(self):

        estado = self.tarea.get(
            "estado",
            "DETENIDA"
        )


        colores = {

            "EN ESPERA":
                VERDE,

            "EJECUTANDO":
                VERDE,

            "EN PAUSA":
                AMARILLO,

            "PRÓXIMA":
                AZUL,

            "EN COLA":
                MORADO,

            "COMPLETADA":
                VERDE,

            "ERROR":
                ROJO,

            "DETENIDA":
                GRIS,
        }


        color = colores.get(
            estado,
            GRIS
        )


        self.estado.setText(
            f"● {estado}"
        )


        self.estado.setStyleSheet(

            f"""
            color: {color};
            font-weight: 800;
            font-size: 10px;
            """
        )


        intervalo = (

            f"{self.tarea.get('intervalo_valor', 1)} "
            f"{self.tarea.get('intervalo_unidad', 'días')}"
        )


        self.info.setText(

            f"Veces: "
            f"{self.tarea.get('veces', 1)}"

            f"    |    Cada: "
            f"{intervalo}\n"

            f"Días: "
            f"{dias_a_texto(self.tarea.get('dias', []))}"
        )


        self.proxima.setText(
            self.tarea.get(
                "detalle_estado",
                (
                    "Hora programada: "
                    f"{self.tarea.get('hora', '--:--')}"
                )
            )
        )


        self.duracion.setText(

            f"Duración: "
            f"{self.tarea.get('duracion', '00:00:00')}"
        )


        self.transcurrido.setText(

            f"Transcurrido: "
            f"{self.tarea.get('transcurrido', '00:00:00')}"
        )


        self.progreso.setValue(
            int(
                self.tarea.get(
                    "progreso",
                    0
                )
            )
        )


        if estado == "EN PAUSA":

            self.boton_pausa.setText(
                "CONTINUAR"
            )


        elif estado == "DETENIDA":

            self.boton_pausa.setText(
                "ACTIVAR"
            )


        else:

            self.boton_pausa.setText(
                "PAUSAR"
            )


        self.boton_ejecutar.setEnabled(

            estado not in [
                "EJECUTANDO",
                "EN COLA",
            ]

            and not (

                estado == "EN PAUSA"

                and

                self.tarea.get(
                    "current_run_key"
                )
            )
        )

# ============================================================
# VENTANA PRINCIPAL BIN
# ============================================================

class BIN(QMainWindow):

    def __init__(
        self
    ):

        super().__init__()


        # ====================================================
        # ESTADOS GENERALES
        # ====================================================

        self.grabando = False

        self.pantalla_completa = False


        # ====================================================
        # DIRECTORIOS
        # ====================================================

        self.directorio_bin = Path(
            __file__
        ).resolve().parent


        self.directorio_datos = (
            self.directorio_bin
            /
            "data"
        )


        self.archivo_tareas = (
            self.directorio_datos
            /
            "tareas.json"
        )


        self.directorio_datos.mkdir(
            parents=True,
            exist_ok=True
        )


        # ====================================================
        # TAREAS DE DEMOSTRACIÓN
        # ====================================================

        self.tareas_demo = [

            {
                "id": 1,

                "nombre":
                    "Crear contenido Alfora",

                "estado":
                    "EN PAUSA",

                "hora":
                    "05:00",

                "veces":
                    30,

                "intervalo_valor":
                    24,

                "intervalo_unidad":
                    "horas",

                "dias":
                    [
                        0,
                        1,
                        2,
                        3,
                        4,
                        5,
                        6
                    ],

                "duracion":
                    "00:18:42",

                "transcurrido":
                    "00:06:31",

                "progreso":
                    35,
            },

            {
                "id": 2,

                "nombre":
                    "Publicar en redes",

                "estado":
                    "EN ESPERA",

                "hora":
                    "05:40",

                "veces":
                    1,

                "intervalo_valor":
                    24,

                "intervalo_unidad":
                    "horas",

                "dias":
                    [
                        0,
                        1,
                        2,
                        3,
                        4,
                        5,
                        6
                    ],

                "duracion":
                    "00:10:00",

                "transcurrido":
                    "00:00:00",

                "progreso":
                    0,
            },

            {
                "id": 3,

                "nombre":
                    "Publicar segunda ronda",

                "estado":
                    "PRÓXIMA",

                "hora":
                    "07:30",

                "veces":
                    1,

                "intervalo_valor":
                    24,

                "intervalo_unidad":
                    "horas",

                "dias":
                    [
                        0,
                        1,
                        2,
                        3,
                        4,
                        5,
                        6
                    ],

                "duracion":
                    "00:10:00",

                "transcurrido":
                    "00:00:00",

                "progreso":
                    0,
            },

        ]


        # ====================================================
        # CARGAR TAREAS GUARDADAS
        # ====================================================

        self.tareas = (
            self.cargar_tareas()
            
        )

        self.normalizar_tareas()

        self.tarjetas = {}

        # ====================================================
        # VENTANA
        # ====================================================

        self.setWindowTitle(
            "BIN — Automatizador Inteligente"
        )


        self.resize(
            1550,
            900
        )


        self.setMinimumSize(
            1200,
            720
        )


        # ====================================================
        # INICIAR
        # ====================================================

        self.crear_interfaz()

        self.aplicar_estilos()

        self.iniciar_temporizadores()

        self.actualizar_cabecera_operativa()


    # ========================================================
    # CARGAR TAREAS DESDE DISCO
    # ========================================================
    # ========================================================
    # NORMALIZAR TAREAS
    # ========================================================

    def normalizar_tareas(
        self
    ):

        for tarea in self.tareas:

            tarea.setdefault(
                "elapsed_seconds",
                duracion_a_segundos(
                    tarea.get(
                        "transcurrido",
                        "00:00:00"
                    )
                )
            )


            tarea.setdefault(
                "runtime_started_at",
                None
            )


            tarea.setdefault(
                "current_run_key",
                None
            )


            tarea.setdefault(
                "last_run_key",
                None
            )


            tarea.setdefault(
                "queued_at",
                None
            )


            tarea.setdefault(
                "completed_at",
                None
            )


            tarea.setdefault(
                "detalle_estado",
                (
                    "Hora programada: "
                    f"{tarea.get('hora', '--:--')}"
                )
            )


            # Si BIN fue cerrado durante una ejecución,
            # dejamos esa tarea pausada al volver a abrir.

            if tarea.get(
                "estado"
            ) in [
                "EJECUTANDO",
                "EN COLA",
            ]:

                if tarea.get(
                    "current_run_key"
                ):

                    tarea["estado"] = (
                        "EN PAUSA"
                    )

                else:

                    tarea["estado"] = (
                        "EN ESPERA"
                    )


                tarea["runtime_started_at"] = None


    # ========================================================
    # CARGAR TAREAS DESDE DISCO
    # ========================================================

    def cargar_tareas(
        self
    ):

        if not self.archivo_tareas.exists():

            # Si todavía no existe tareas.json,
            # usamos las tareas de demostración.

            tareas = [

                tarea.copy()

                for tarea in self.tareas_demo
            ]


            return tareas


        try:

            with open(
                self.archivo_tareas,
                "r",
                encoding="utf-8"
            ) as archivo:

                datos = json.load(
                    archivo
                )


            if isinstance(
                datos,
                list
            ):

                return datos


        except Exception as error:

            print(
                "Error cargando tareas:",
                error
            )


        # Si hubo un problema leyendo el JSON,
        # BIN vuelve a las tareas demo.

        return [

            tarea.copy()

            for tarea in self.tareas_demo
        ]
    # ========================================================
    # GUARDAR TAREAS EN DISCO
    # ========================================================

    def guardar_tareas_en_disco(
        self
    ):

        try:

            archivo_temporal = (
                self.archivo_tareas.with_suffix(
                    ".tmp"
                )
            )


            with open(
                archivo_temporal,
                "w",
                encoding="utf-8"
            ) as archivo:

                json.dump(
                    self.tareas,
                    archivo,
                    ensure_ascii=False,
                    indent=4
                )


            archivo_temporal.replace(
                self.archivo_tareas
            )


        except Exception as error:

            QMessageBox.critical(

                self,

                "Error guardando tareas",

                "BIN no pudo guardar las tareas.\n\n"

                f"{error}"
            )


    # ========================================================
    # CREAR INTERFAZ PRINCIPAL
    # ========================================================

    def crear_interfaz(
        self
    ):

        contenedor = QWidget()

        self.setCentralWidget(
            contenedor
        )


        principal = QVBoxLayout(
            contenedor
        )


        principal.setContentsMargins(
            10,
            10,
            10,
            10
        )


        principal.setSpacing(
            8
        )


        # ====================================================
        # CABECERA
        # ====================================================

        cabecera = Panel()

        layout_cabecera = QHBoxLayout(
            cabecera
        )


        # ----------------------------------------------------
        # IDENTIDAD
        # ----------------------------------------------------

        identidad = QVBoxLayout()


        logo = QLabel(
            "BIN"
        )

        logo.setObjectName(
            "logo"
        )


        subtitulo = QLabel(
            "AUTOMATIZADOR INTELIGENTE"
        )

        subtitulo.setObjectName(
            "textoSecundario"
        )


        identidad.addWidget(
            logo
        )

        identidad.addWidget(
            subtitulo
        )


        layout_cabecera.addLayout(
            identidad
        )


        # ----------------------------------------------------
        # MOSTRAR RUTINA
        # ----------------------------------------------------

        self.boton_grabar = QPushButton(
            "● MOSTRAR RUTINA"
        )


        self.boton_grabar.setObjectName(
            "botonGrabar"
        )


        self.boton_grabar.clicked.connect(
            self.alternar_grabacion
        )


        layout_cabecera.addWidget(
            self.boton_grabar
        )


        # ----------------------------------------------------
        # PANTALLA COMPLETA
        # ----------------------------------------------------

        self.boton_pantalla_completa = QPushButton(
            "⛶ PANTALLA COMPLETA"
        )


        self.boton_pantalla_completa.setObjectName(
            "botonPantallaCompleta"
        )


        self.boton_pantalla_completa.clicked.connect(
            self.alternar_pantalla_completa
        )


        layout_cabecera.addWidget(
            self.boton_pantalla_completa
        )


        layout_cabecera.addStretch()


        # ----------------------------------------------------
        # TAREAS GUARDADAS
        # ----------------------------------------------------

        self.contador_tareas = QLabel()

        self.contador_tareas.setObjectName(
            "infoCabecera"
        )


        layout_cabecera.addWidget(
            self.contador_tareas
        )


        # ----------------------------------------------------
        # PRÓXIMA TAREA
        # ----------------------------------------------------

        self.proxima_cabecera = QLabel(
            "PRÓXIMA TAREA\n--"
        )


        self.proxima_cabecera.setObjectName(
            "infoCabecera"
        )


        layout_cabecera.addWidget(
            self.proxima_cabecera
        )


        # ----------------------------------------------------
        # ESTADO DE BIN
        # ----------------------------------------------------

        self.estado_bin = QLabel(
            "● BIN OPERATIVO"
        )


        self.estado_bin.setObjectName(
            "estado"
        )


        layout_cabecera.addWidget(
            self.estado_bin
        )


        # ----------------------------------------------------
        # RELOJ
        # ----------------------------------------------------

        self.hora = QLabel(
            "00:00:00"
        )


        self.hora.setObjectName(
            "hora"
        )


        layout_cabecera.addWidget(
            self.hora
        )


        principal.addWidget(
            cabecera
        )


        # ====================================================
        # CUERPO
        # ====================================================

        cuerpo = QHBoxLayout()

        cuerpo.setSpacing(
            8
        )


        # ====================================================
        # PANEL IZQUIERDO
        # ====================================================

        panel_tareas = (
            self.crear_panel_tareas()
        )


        panel_tareas.setMinimumWidth(
            360
        )


        cuerpo.addWidget(
            panel_tareas,
            3
        )


        # ====================================================
        # CENTRO
        # ====================================================

        centro = QVBoxLayout()

        centro.setSpacing(
            8
        )


        # ====================================================
        # VISOR PRINCIPAL
        # ====================================================

        visor = QFrame()

        visor.setObjectName(
            "visorPrincipal"
        )


        visor_layout = QVBoxLayout(
            visor
        )


        titulo_visor = QLabel(
            "VISOR EN TIEMPO REAL — ESCRITORIO DE BIN"
        )


        titulo_visor.setObjectName(
            "tituloVisor"
        )


        visor_layout.addWidget(
            titulo_visor
        )


        pantalla = QFrame()

        pantalla.setObjectName(
            "pantalla"
        )


        pantalla_layout = QVBoxLayout(
            pantalla
        )


        self.mensaje_visor = QLabel(
            "ESCRITORIO DE BIN\n\n"
            "Aquí veremos en tiempo real "
            "lo que BIN está viendo y ejecutando."
        )


        self.mensaje_visor.setAlignment(
            Qt.AlignCenter
        )


        self.mensaje_visor.setObjectName(
            "mensajeVisor"
        )


        pantalla_layout.addWidget(
            self.mensaje_visor
        )


        visor_layout.addWidget(
            pantalla,
            1
        )


        centro.addWidget(
            visor,
            8
        )


        # ====================================================
        # RENDIMIENTO DEL PC
        # ====================================================

        rendimiento = Panel()

        rendimiento_layout = QHBoxLayout(
            rendimiento
        )


        self.cpu_label = QLabel(
            "CPU   0 %"
        )


        self.ram_label = QLabel(
            "RAM   0 %"
        )


        self.gpu_label = QLabel(
            "GPU   PENDIENTE"
        )


        self.temp_label = QLabel(
            "TEMP   PENDIENTE"
        )


        for etiqueta in [

            self.cpu_label,
            self.ram_label,
            self.gpu_label,
            self.temp_label,

        ]:

            etiqueta.setObjectName(
                "monitor"
            )


            rendimiento_layout.addWidget(
                etiqueta
            )


        centro.addWidget(
            rendimiento,
            1
        )


        # ====================================================
        # CHAT CON BIN
        # ====================================================

        chat = Panel()

        chat_layout = QVBoxLayout(
            chat
        )


        titulo_chat = QLabel(
            "CHAT CON BIN"
        )


        titulo_chat.setObjectName(
            "tituloPanel"
        )


        self.mensaje_chat = QLabel(
            "BIN: Hola. Estoy operativo."
        )


        self.mensaje_chat.setWordWrap(
            True
        )


        chat_layout.addWidget(
            titulo_chat
        )


        chat_layout.addWidget(
            self.mensaje_chat
        )


        centro.addWidget(
            chat,
            2
        )


        centro_widget = QWidget()

        centro_widget.setLayout(
            centro
        )


        cuerpo.addWidget(
            centro_widget,
            8
        )


        # ====================================================
        # PANEL DERECHO
        # ====================================================

        acciones = Panel()


        acciones.setMinimumWidth(
            210
        )


        acciones.setMaximumWidth(
            260
        )


        acciones_layout = QVBoxLayout(
            acciones
        )


        titulo_acciones = QLabel(
            "PANEL DE ACCIONES"
        )


        titulo_acciones.setObjectName(
            "tituloPanel"
        )


        acciones_layout.addWidget(
            titulo_acciones
        )


        mensaje_acciones = QLabel(

            "Cuando pulses\n"
            "\"Mostrar rutina\",\n\n"

            "las acciones que BIN\n"
            "interprete aparecerán aquí."
        )


        mensaje_acciones.setWordWrap(
            True
        )


        mensaje_acciones.setAlignment(
            Qt.AlignCenter
        )


        mensaje_acciones.setObjectName(
            "textoSecundario"
        )


        acciones_layout.addStretch()


        acciones_layout.addWidget(
            mensaje_acciones
        )


        acciones_layout.addStretch()


        self.boton_guardar_rutina = QPushButton(
            "GUARDAR TAREA"
        )


        self.boton_guardar_rutina.setObjectName(
            "botonPrincipal"
        )


        acciones_layout.addWidget(
            self.boton_guardar_rutina
        )


        cuerpo.addWidget(
            acciones
        )


        principal.addLayout(
            cuerpo,
            1
        )


    # ========================================================
    # CREAR PANEL DE TAREAS
    # ========================================================

    def crear_panel_tareas(
        self
    ):

        self.panel_tareas = Panel()


        layout = QVBoxLayout(
            self.panel_tareas
        )


        # ----------------------------------------------------
        # CABECERA
        # ----------------------------------------------------

        cabecera = QHBoxLayout()


        titulo = QLabel(
            "LISTA DE TAREAS"
        )


        titulo.setObjectName(
            "tituloPanel"
        )


        self.boton_nueva_tarea = QPushButton(
            "+ NUEVA"
        )


        self.boton_nueva_tarea.clicked.connect(
            self.crear_nueva_tarea
        )


        cabecera.addWidget(
            titulo
        )


        cabecera.addStretch()


        cabecera.addWidget(
            self.boton_nueva_tarea
        )


        layout.addLayout(
            cabecera
        )


        # ----------------------------------------------------
        # ÁREA DE SCROLL
        # ----------------------------------------------------

        self.scroll_tareas = QScrollArea()


        self.scroll_tareas.setWidgetResizable(
            True
        )


        self.scroll_tareas.setObjectName(
            "scrollTareas"
        )


        # ----------------------------------------------------
        # NUNCA SCROLL HORIZONTAL
        # ----------------------------------------------------

        self.scroll_tareas.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )


        # ----------------------------------------------------
        # SCROLL VERTICAL SOLO SI HACE FALTA
        # ----------------------------------------------------

        self.scroll_tareas.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )


        self.contenedor_tareas = QWidget()


        self.layout_tareas = QVBoxLayout(
            self.contenedor_tareas
        )


        self.layout_tareas.setAlignment(
            Qt.AlignTop
        )


        self.layout_tareas.setSpacing(
            10
        )


        self.layout_tareas.setContentsMargins(
            2,
            2,
            4,
            2
        )


        self.scroll_tareas.setWidget(
            self.contenedor_tareas
        )


        layout.addWidget(
            self.scroll_tareas
        )


        self.refrescar_lista_tareas()


        return self.panel_tareas


    # ========================================================
    # REFRESCAR LISTA DE TAREAS
    # ========================================================

    def refrescar_lista_tareas(
        self
    ):

        self.tarjetas = {}


        # ----------------------------------------------------
        # ELIMINAR TARJETAS VIEJAS
        # ----------------------------------------------------

        while self.layout_tareas.count():

            item = self.layout_tareas.takeAt(
                0
            )


            widget = item.widget()


            if widget:

                widget.deleteLater()


        # ----------------------------------------------------
        # CREAR TARJETAS NUEVAS
        # ----------------------------------------------------

        for tarea in self.tareas:

            tarjeta = TaskCard(
                tarea
            )


            tarjeta.ver_solicitado.connect(
                self.editar_tarea
            )


            tarjeta.copiar_solicitado.connect(
                self.copiar_tarea
            )


            tarjeta.eliminar_solicitado.connect(
                self.eliminar_tarea
            )


            tarjeta.pausa_solicitada.connect(
                self.alternar_pausa_tarea
            )


            self.tarjetas[
                tarea["id"]
            ] = tarjeta


            self.layout_tareas.addWidget(
                tarjeta
            )


        self.actualizar_cabecera_operativa()


    # ========================================================
    # OBTENER TAREA
    # ========================================================

    def obtener_tarea(
        self,
        tarea_id
    ):

        for tarea in self.tareas:

            if tarea.get(
                "id"
            ) == tarea_id:

                return tarea


        return None


    # ========================================================
    # CREAR NUEVA TAREA
    # ========================================================

    def crear_nueva_tarea(
        self
    ):

        dialogo = TaskEditorDialog(

            self,

            validador_conflictos=
                self.buscar_conflictos
        )


        if dialogo.exec() != QDialog.Accepted:

            return


        datos = (
            dialogo.obtener_datos()
        )


        nuevo_id = max(

            [
                tarea.get(
                    "id",
                    0
                )

                for tarea in self.tareas
            ],

            default=0

        ) + 1


        nueva = {

            "id":
                nuevo_id,

            **datos,

            "estado":
                "EN ESPERA",

            "transcurrido":
                "00:00:00",

            "progreso":
                0,

        }


        self.tareas.append(
            nueva
        )


        self.guardar_tareas_en_disco()


        self.refrescar_lista_tareas()


    # ========================================================
    # EDITAR TAREA
    # ========================================================

    def editar_tarea(
        self,
        tarea_id
    ):

        tarea = self.obtener_tarea(
            tarea_id
        )


        if not tarea:

            return


        dialogo = TaskEditorDialog(

            self,

            tarea=tarea,

            validador_conflictos=
                self.buscar_conflictos,

            excluir_id=tarea_id
        )


        if dialogo.exec() != QDialog.Accepted:

            return


        datos = (
            dialogo.obtener_datos()
        )


        tarea.update(
            datos
        )


        self.guardar_tareas_en_disco()


        self.refrescar_lista_tareas()


    # ========================================================
    # CREAR INTERVALOS SEMANALES
    # ========================================================

    def crear_intervalos_semanales(
        self,
        tarea
    ):

        """
        Cada semana tiene:
        7 días * 86400 segundos.

        Esta función convierte una tarea en intervalos
        absolutos dentro de una semana.

        También permite detectar tareas que atraviesan
        la medianoche.
        """

        segundos_dia = (
            24
            *
            60
            *
            60
        )


        segundos_semana = (
            7
            *
            segundos_dia
        )


        inicio_dia = (
            hora_a_segundos(
                tarea["hora"]
            )
        )


        duracion = (
            duracion_a_segundos(
                tarea["duracion"]
            )
        )


        intervalos = []


        for dia in tarea.get(
            "dias",
            []
        ):

            inicio = (
                dia * segundos_dia
                +
                inicio_dia
            )


            fin = (
                inicio
                +
                duracion
            )


            intervalos.append(
                (
                    inicio,
                    fin
                )
            )


            # ------------------------------------------------
            # DUPLICADOS DESPLAZADOS
            # ------------------------------------------------
            #
            # Nos permite detectar correctamente:
            #
            # Domingo 23:55
            # hasta
            # Lunes 00:15
            #
            # ------------------------------------------------

            intervalos.append(
                (
                    inicio
                    -
                    segundos_semana,

                    fin
                    -
                    segundos_semana
                )
            )


            intervalos.append(
                (
                    inicio
                    +
                    segundos_semana,

                    fin
                    +
                    segundos_semana
                )
            )


        return intervalos


    # ========================================================
    # DETECTAR COLISIONES
    # ========================================================

    def buscar_conflictos(
        self,
        candidata,
        excluir_id=None
    ):

        conflictos = []


        intervalos_candidata = (
            self.crear_intervalos_semanales(
                candidata
            )
        )


        for tarea in self.tareas:

            # ------------------------------------------------
            # IGNORAR LA MISMA TAREA AL EDITARLA
            # ------------------------------------------------

            if excluir_id is not None:

                if tarea.get(
                    "id"
                ) == excluir_id:

                    continue


            # ------------------------------------------------
            # UNA TAREA DETENIDA NO RESERVA HORARIO
            # ------------------------------------------------

            if tarea.get(
                "estado"
            ) == "DETENIDA":

                continue


            intervalos_existente = (
                self.crear_intervalos_semanales(
                    tarea
                )
            )


            conflicto_encontrado = False


            for (
                inicio_candidata,
                fin_candidata
            ) in intervalos_candidata:


                for (
                    inicio_existente,
                    fin_existente
                ) in intervalos_existente:


                    hay_solapamiento = (

                        inicio_candidata
                        <
                        fin_existente

                        and

                        inicio_existente
                        <
                        fin_candidata
                    )


                    if hay_solapamiento:

                        conflicto_encontrado = True

                        break


                if conflicto_encontrado:

                    break


            if conflicto_encontrado:

                conflictos.append(
                    tarea
                )


        return conflictos


    # ========================================================
    # COPIAR TAREA
    # ========================================================

    def copiar_tarea(
        self,
        tarea_id
    ):

        original = self.obtener_tarea(
            tarea_id
        )


        if not original:

            return


        nuevo_id = max(

            [
                tarea.get(
                    "id",
                    0
                )

                for tarea in self.tareas
            ],

            default=0

        ) + 1


        # Copia profunda sencilla mediante JSON,
        # suficiente para nuestros datos actuales.

        copia = json.loads(
            json.dumps(
                original
            )
        )


        copia["id"] = (
            nuevo_id
        )


        copia["nombre"] = (
            original["nombre"]
            +
            " — copia"
        )


        copia["estado"] = (
            "DETENIDA"
        )


        copia["progreso"] = 0


        copia["transcurrido"] = (
            "00:00:00"
        )


        self.tareas.append(
            copia
        )


        self.guardar_tareas_en_disco()


        self.refrescar_lista_tareas()


    # ========================================================
    # ELIMINAR TAREA
    # ========================================================

    def eliminar_tarea(
        self,
        tarea_id
    ):

        tarea = self.obtener_tarea(
            tarea_id
        )


        if not tarea:

            return


        respuesta = QMessageBox.question(

            self,

            "Eliminar tarea",

            f"¿Eliminar la tarea "
            f"'{tarea['nombre']}'?",

            QMessageBox.Yes
            |
            QMessageBox.No
        )


        if respuesta != QMessageBox.Yes:

            return


        self.tareas = [

            item

            for item in self.tareas

            if item.get(
                "id"
            ) != tarea_id
        ]


        self.guardar_tareas_en_disco()


        self.refrescar_lista_tareas()


    # ========================================================
    # PAUSAR / CONTINUAR / INICIAR
    # ========================================================

    def alternar_pausa_tarea(
        self,
        tarea_id
    ):

        tarea = self.obtener_tarea(
            tarea_id
        )


        if not tarea:

            return


        estado_actual = tarea.get(
            "estado",
            "DETENIDA"
        )


        if estado_actual == "EN PAUSA":

            tarea["estado"] = (
                "EN ESPERA"
            )


        elif estado_actual == "DETENIDA":

            # ------------------------------------------------
            # AL REACTIVAR UNA TAREA COMPROBAMOS CONFLICTOS
            # ------------------------------------------------

            candidata = tarea.copy()

            candidata["estado"] = (
                "EN ESPERA"
            )


            conflictos = self.buscar_conflictos(

                candidata,

                excluir_id=tarea_id
            )


            if conflictos:

                nombres = "\n".join(

                    f"• {item['nombre']}"

                    for item in conflictos
                )


                QMessageBox.warning(

                    self,

                    "No se puede iniciar",

                    "BIN detectó que esta tarea "
                    "colisiona con:\n\n"

                    f"{nombres}\n\n"

                    "Edita su horario antes de "
                    "activarla."
                )

                return


            tarea["estado"] = (
                "EN ESPERA"
            )


        else:

            tarea["estado"] = (
                "EN PAUSA"
            )


        self.guardar_tareas_en_disco()


        self.refrescar_lista_tareas()


    # ========================================================
    # CALCULAR PRÓXIMA TAREA
    # ========================================================

    def calcular_proxima_tarea(
        self
    ):

        ahora = datetime.now()

        candidatas = []


        for tarea in self.tareas:

            estado = tarea.get(
                "estado"
            )


            if estado in [

                "DETENIDA",
                "EN PAUSA",
                "ERROR",

            ]:

                continue


            try:

                hora, minuto = [

                    int(valor)

                    for valor
                    in tarea["hora"].split(":")
                ]

            except Exception:

                continue


            dias = tarea.get(
                "dias",
                []
            )


            for desplazamiento in range(
                0,
                8
            ):

                fecha = (

                    ahora
                    +
                    timedelta(
                        days=desplazamiento
                    )
                )


                if fecha.weekday() not in dias:

                    continue


                momento = fecha.replace(

                    hour=hora,

                    minute=minuto,

                    second=0,

                    microsecond=0
                )


                if momento >= ahora:

                    candidatas.append(
                        (
                            momento,
                            tarea
                        )
                    )

                    break


        if not candidatas:

            return None


        candidatas.sort(
            key=lambda item:
            item[0]
        )


        return candidatas[0]


    # ========================================================
    # ACTUALIZAR CABECERA
    # ========================================================

    def actualizar_cabecera_operativa(
        self
    ):

        if hasattr(
            self,
            "contador_tareas"
        ):

            self.contador_tareas.setText(

                "TAREAS GUARDADAS\n"
                f"{len(self.tareas)}"
            )


        if not hasattr(
            self,
            "proxima_cabecera"
        ):

            return


        proxima = (
            self.calcular_proxima_tarea()
        )


        if not proxima:

            self.proxima_cabecera.setText(
                "PRÓXIMA TAREA\n--"
            )

            return


        momento, tarea = proxima


        ahora = datetime.now()


        diferencia = (
            momento
            -
            ahora
        )


        segundos = max(

            0,

            int(
                diferencia.total_seconds()
            )
        )


        minutos = (
            segundos
            //
            60
        )


        if minutos < 1:

            tiempo = (
                "en menos de 1 min"
            )


        elif minutos < 60:

            tiempo = (
                f"en {minutos} min"
            )


        elif minutos < 1440:

            horas = (
                minutos
                //
                60
            )

            minutos_restantes = (
                minutos
                %
                60
            )


            if minutos_restantes:

                tiempo = (
                    f"en {horas} h "
                    f"{minutos_restantes} min"
                )

            else:

                tiempo = (
                    f"en {horas} h"
                )


        else:

            dias = (
                minutos
                //
                1440
            )

            tiempo = (
                f"en {dias} día(s)"
            )


        self.proxima_cabecera.setText(

            "PRÓXIMA TAREA\n"

            f"{tarea['nombre']} · "
            f"{tiempo}"
        )


    # ========================================================
    # MOSTRAR / DETENER RUTINA
    # ========================================================

    def alternar_grabacion(
        self
    ):

        self.grabando = (
            not self.grabando
        )


        if self.grabando:

            self.boton_grabar.setText(
                "■ DETENER GRABACIÓN"
            )


            self.estado_bin.setText(
                "● BIN OBSERVANDO"
            )


            self.estado_bin.setStyleSheet(

                f"""
                color: {AMARILLO};
                font-weight: 800;
                """
            )


        else:

            self.boton_grabar.setText(
                "● MOSTRAR RUTINA"
            )


            self.estado_bin.setText(
                "● BIN OPERATIVO"
            )


            self.estado_bin.setStyleSheet(

                f"""
                color: {VERDE};
                font-weight: 800;
                """
            )


    # ========================================================
    # PANTALLA COMPLETA
    # ========================================================

    def alternar_pantalla_completa(
        self
    ):

        self.pantalla_completa = (
            not self.pantalla_completa
        )


        if self.pantalla_completa:

            self.showFullScreen()


            self.boton_pantalla_completa.setText(
                "⛶ SALIR DE PANTALLA COMPLETA"
            )


        else:

            self.showNormal()


            self.boton_pantalla_completa.setText(
                "⛶ PANTALLA COMPLETA"
            )


    # ========================================================
    # RELOJ
    # ========================================================

    def actualizar_reloj(
        self
    ):

        self.hora.setText(

            datetime.now().strftime(
                "%H:%M:%S"
            )
        )


        self.actualizar_cabecera_operativa()


    # ========================================================
    # MONITOREO DEL SISTEMA
    # ========================================================

    def actualizar_sistema(
        self
    ):

        cpu = psutil.cpu_percent()


        memoria = (
            psutil.virtual_memory()
        )


        self.cpu_label.setText(

            f"CPU   "
            f"{cpu:.0f} %"
        )


        self.ram_label.setText(

            f"RAM   "
            f"{memoria.percent:.0f} %"
        )


    # ========================================================
    # TEMPORIZADORES
    # ========================================================

    def iniciar_temporizadores(
        self
    ):

        # ----------------------------------------------------
        # RELOJ
        # ----------------------------------------------------

        self.timer_reloj = QTimer(
            self
        )


        self.timer_reloj.timeout.connect(
            self.actualizar_reloj
        )


        self.timer_reloj.start(
            1000
        )


        # ----------------------------------------------------
        # SISTEMA
        # ----------------------------------------------------

        self.timer_sistema = QTimer(
            self
        )


        self.timer_sistema.timeout.connect(
            self.actualizar_sistema
        )


        self.timer_sistema.start(
            1500
        )


        self.actualizar_reloj()

        self.actualizar_sistema()


    # ========================================================
    # ESTILOS
    # ========================================================

    def aplicar_estilos(
        self
    ):

        self.setStyleSheet(

            f"""

            /* =================================================
               VENTANA
            ================================================= */

            QMainWindow {{

                background-color:
                    {FONDO};

            }}


            QWidget {{

                color:
                    {TEXTO};

                font-family:
                    "Segoe UI";

                font-size:
                    13px;

            }}


            /* =================================================
               PANELES
            ================================================= */

            QFrame#panel {{

                background-color:
                    {PANEL};

                border:
                    1px solid
                    {BORGONA_OSCURO};

                border-radius:
                    10px;

            }}


            QFrame#visorPrincipal {{

                background-color:
                    {PANEL};

                border:
                    1px solid
                    {BORGONA};

                border-radius:
                    11px;

            }}


            QFrame#tarjetaTarea {{

                background-color:
                    {PANEL_TAREA};

                border:
                    1px solid
                    #282e38;

                border-radius:
                    9px;

            }}


            QFrame#tarjetaTarea:hover {{

                border:
                    1px solid
                    {BORGONA};

            }}


            QFrame#pantalla {{

                background-color:
                    #020306;

                border:
                    2px solid
                    {BORGONA};

                border-radius:
                    9px;

            }}


            /* =================================================
               LOGO
            ================================================= */

            QLabel#logo {{

                color:
                    {BORGONA_CLARO};

                font-size:
                    30px;

                font-weight:
                    900;

                letter-spacing:
                    6px;

            }}


            /* =================================================
               TÍTULOS
            ================================================= */

            QLabel#tituloPanel {{

                color:
                    #ff6686;

                font-size:
                    12px;

                font-weight:
                    800;

            }}


            QLabel#tituloVisor {{

                color:
                    #ff7895;

                font-size:
                    13px;

                font-weight:
                    900;

            }}


            QLabel#tituloDialogo {{

                color:
                    #ff7895;

                font-size:
                    18px;

                font-weight:
                    900;

            }}


            /* =================================================
               TEXTOS
            ================================================= */

            QLabel#textoSecundario {{

                color:
                    {TEXTO_SECUNDARIO};

                font-size:
                    10px;

            }}


            QLabel#tituloTarea {{

                font-weight:
                    700;

            }}


            QLabel#numeroTarea {{

                color:
                    #ff7893;

                font-weight:
                    900;

            }}


            QLabel#proximaTarea {{

                color:
                    #b4bbc6;

                font-size:
                    11px;

            }}


            QLabel#estado {{

                color:
                    {VERDE};

                font-weight:
                    800;

            }}


            QLabel#infoCabecera {{

                color:
                    #b7bdc8;

                font-size:
                    10px;

                font-weight:
                    600;

                padding:
                    0px 10px;

            }}


            QLabel#hora {{

                font-family:
                    Consolas;

                font-size:
                    17px;

                font-weight:
                    bold;

            }}


            QLabel#monitor {{

                font-family:
                    Consolas;

                font-size:
                    14px;

                font-weight:
                    600;

            }}


            QLabel#mensajeVisor {{

                color:
                    #454c57;

                font-size:
                    22px;

                font-weight:
                    800;

            }}


            QLabel#aviso {{

                background-color:
                    #161019;

                color:
                    #d6a4b0;

                border:
                    1px solid
                    {BORGONA_OSCURO};

                border-radius:
                    6px;

                padding:
                    10px;

            }}


            /* =================================================
               BOTONES
            ================================================= */

            QPushButton {{

                background-color:
                    {PANEL_SECUNDARIO};

                border:
                    1px solid
                    #303743;

                border-radius:
                    6px;

                padding:
                    7px 10px;

            }}


            QPushButton:hover {{

                border:
                    1px solid
                    {BORGONA_CLARO};

                background-color:
                    #181d26;

            }}


            QPushButton:pressed {{

                background-color:
                    {BORGONA_OSCURO};

            }}


            QPushButton#botonGrabar {{

                color:
                    #ff718f;

                border:
                    1px solid
                    {BORGONA};

                font-weight:
                    bold;

                padding:
                    10px 18px;

            }}


            QPushButton#botonPantallaCompleta {{

                color:
                    #d7dbe2;

                border:
                    1px solid
                    #353d49;

                font-weight:
                    600;

                padding:
                    10px 18px;

            }}


            QPushButton#botonPantallaCompleta:hover {{

                color:
                    #ff718f;

                border:
                    1px solid
                    {BORGONA_CLARO};

            }}


            QPushButton#botonPrincipal {{

                background-color:
                    {BORGONA_OSCURO};

                border:
                    1px solid
                    {BORGONA_CLARO};

                color:
                    #ff88a1;

                font-weight:
                    bold;

            }}


            QPushButton#botonEliminar {{

                color:
                    #ff6979;

            }}


            /* =================================================
               CAMPOS
            ================================================= */

            QLineEdit,
            QSpinBox,
            QComboBox,
            QTimeEdit {{

                background-color:
                    #090d12;

                border:
                    1px solid
                    #343b46;

                border-radius:
                    6px;

                padding:
                    7px;

            }}


            QLineEdit:focus,
            QSpinBox:focus,
            QComboBox:focus,
            QTimeEdit:focus {{

                border:
                    1px solid
                    {BORGONA_CLARO};

            }}


            /* =================================================
               CHECKBOX
            ================================================= */

            QCheckBox {{

                spacing:
                    6px;

            }}


            QCheckBox::indicator {{

                width:
                    16px;

                height:
                    16px;

            }}


            /* =================================================
               PROGRESO
            ================================================= */

            QProgressBar {{

                background-color:
                    #1a1e26;

                border:
                    none;

                border-radius:
                    4px;

                height:
                    7px;

                text-align:
                    center;

                color:
                    transparent;

            }}


            QProgressBar::chunk {{

                background-color:
                    {BORGONA_CLARO};

                border-radius:
                    4px;

            }}


            /* =================================================
               SCROLL
            ================================================= */

            QScrollArea#scrollTareas {{

                background:
                    transparent;

                border:
                    none;

            }}


            QScrollArea#scrollTareas
            > QWidget
            > QWidget {{

                background:
                    transparent;

            }}


            QScrollBar:vertical {{

                background:
                    transparent;

                width:
                    8px;

            }}


            QScrollBar::handle:vertical {{

                background:
                    #343b46;

                min-height:
                    35px;

                border-radius:
                    4px;

            }}


            QScrollBar::handle:vertical:hover {{

                background:
                    {BORGONA};

            }}


            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{

                height:
                    0px;

            }}


            /* =================================================
               DIÁLOGOS
            ================================================= */

            QDialog {{

                background-color:
                    {FONDO};

            }}

            """
        )


# ============================================================
# INICIAR APLICACIÓN
# ============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )


    app.setStyle(
        "Fusion"
    )


    bin_app = BIN()


    bin_app.show()


    sys.exit(
        app.exec()
    )