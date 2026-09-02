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
    QInputDialog,
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
                0,
                0
            )
        )

        # La duración estimada la calcula BIN.
        # El usuario puede verla, pero no modificarla.
        self.duracion.setReadOnly(
            True
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

                    "Modifica la hora o los días y vuelve a pulsar "
                    "GUARDAR. La duración la calcula BIN.\n\n"

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

    seleccion_solicitada = Signal(int)


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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.seleccion_solicitada.emit(self.tarea["id"])

        super().mousePressEvent(event)

    def actualizar_estado(self):
        estado = self.tarea.get("estado", "DETENIDA")

        colores = {
            "EN ESPERA": VERDE,
            "EJECUTANDO": VERDE,
            "EN PAUSA": AMARILLO,
            "PRÓXIMA": AZUL,
            "EN COLA": MORADO,
            "COMPLETADA": VERDE,
            "FINALIZADA": VERDE,
            "ERROR": ROJO,
            "DETENIDA": GRIS,
            "REQUIERE CONFIGURACIÓN": AMARILLO,
        }

        color = colores.get(estado, GRIS)

        self.estado.setText(f"● {estado}")
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

        acciones = self.tarea.get("acciones", [])
        texto_acciones = (
            f"{len(acciones)} acción(es)"
            if acciones
            else "SIN ACCIONES"
        )

        self.info.setText(
            f"Veces: {self.tarea.get('veces', 1)}"
            f"    |    Cada: {intervalo}\n"
            f"Días: {dias_a_texto(self.tarea.get('dias', []))}"
            f"    |    {texto_acciones}"
        )

        self.proxima.setText(
            self.tarea.get(
                "detalle_estado",
                f"Hora programada: {self.tarea.get('hora', '--:--')}",
            )
        )

        self.duracion.setText(
            f"Duración: {self.tarea.get('duracion', '00:00:00')}"
        )

        self.transcurrido.setText(
            f"Transcurrido: {self.tarea.get('transcurrido', '00:00:00')}"
        )

        self.progreso.setValue(
            int(self.tarea.get("progreso", 0))
        )

        if estado == "EJECUTANDO":
            self.boton_pausa.setText("PAUSAR")
            self.boton_pausa.setEnabled(True)

        elif estado == "EN PAUSA" and self.tarea.get("current_run_key"):
            self.boton_pausa.setText("CONTINUAR")
            self.boton_pausa.setEnabled(True)

        elif estado == "EN PAUSA":
            self.boton_pausa.setText("ACTIVAR")
            self.boton_pausa.setEnabled(True)

        elif estado == "DETENIDA":
            self.boton_pausa.setText("ACTIVAR")
            self.boton_pausa.setEnabled(True)

        else:
            self.boton_pausa.setText("CONTINUAR")
            self.boton_pausa.setEnabled(False)

        self.boton_ejecutar.setEnabled(
            estado not in ["EJECUTANDO", "EN COLA"]
            and not (
                estado == "EN PAUSA"
                and self.tarea.get("current_run_key")
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
        # ESTADO DEL MOTOR / SCHEDULER / RUTINAS
        # ====================================================

        self.tarea_ejecutando_id = None
        self.tarea_seleccionada_id = None

        self.rutina_borrador = []
        self.rutina_en_borrador = False
        self.inicio_grabacion = None
        self.duracion_rutina_borrador = 0

        self.ultimo_chat_sistema = ""

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
    def normalizar_tareas(self):
        for tarea in self.tareas:
            tarea.setdefault(
                "elapsed_seconds",
                duracion_a_segundos(
                    tarea.get("transcurrido", "00:00:00")
                ),
            )
            tarea.setdefault("runtime_started_at", None)
            tarea.setdefault("runtime_base_seconds", tarea.get("elapsed_seconds", 0))
            tarea.setdefault("current_run_key", None)
            tarea.setdefault("last_run_key", None)
            tarea.setdefault("queued_at", None)
            tarea.setdefault("completed_at", None)
            tarea.setdefault("ultima_ejecucion", tarea.get("completed_at"))
            tarea.setdefault("acciones", [])
            tarea.setdefault("accion_actual_indice", None)
            tarea.setdefault("duracion_origen", "legacy")
            tarea.setdefault(
                "detalle_estado",
                f"Hora programada: {tarea.get('hora', '--:--')}",
            )

            if tarea.get("estado") == "COMPLETADA":
                tarea["estado"] = "FINALIZADA"

            # Recuperación segura: si BIN se cerró con una tarea
            # ejecutándose o en cola, no la reanudamos a ciegas.
            if tarea.get("estado") in ["EJECUTANDO", "EN COLA"]:
                if tarea.get("current_run_key"):
                    tarea["estado"] = "EN PAUSA"
                else:
                    tarea["estado"] = "EN ESPERA"

                tarea["runtime_started_at"] = None
                tarea["runtime_base_seconds"] = tarea.get(
                    "elapsed_seconds", 0
                )


    def cargar_tareas(
        self
    ):

        if not self.archivo_tareas.exists():

            # Creamos copias independientes.
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
        chat_layout = QVBoxLayout(chat)

        titulo_chat = QLabel("CHAT CON BIN")
        titulo_chat.setObjectName("tituloPanel")

        self.mensaje_chat = QLabel("BIN: Hola. Estoy operativo.")
        self.mensaje_chat.setWordWrap(True)

        entrada_chat_layout = QHBoxLayout()

        self.entrada_chat = QLineEdit()
        self.entrada_chat.setPlaceholderText(
            "Escribe una indicación para BIN..."
        )

        self.boton_enviar_chat = QPushButton("ENVIAR")

        self.boton_enviar_chat.clicked.connect(
            self.procesar_chat
        )
        self.entrada_chat.returnPressed.connect(
            self.procesar_chat
        )

        entrada_chat_layout.addWidget(
            self.entrada_chat,
            1
        )
        entrada_chat_layout.addWidget(
            self.boton_enviar_chat
        )

        chat_layout.addWidget(titulo_chat)
        chat_layout.addWidget(self.mensaje_chat)
        chat_layout.addLayout(entrada_chat_layout)

        centro.addWidget(chat, 2)

        centro_widget = QWidget()
        centro_widget.setLayout(centro)

        cuerpo.addWidget(centro_widget, 8)


        # ====================================================
        # PANEL DERECHO
        # ====================================================

        acciones = Panel()
        acciones.setMinimumWidth(210)
        acciones.setMaximumWidth(260)

        acciones_layout = QVBoxLayout(acciones)

        titulo_acciones = QLabel("PANEL DE ACCIONES")
        titulo_acciones.setObjectName("tituloPanel")
        acciones_layout.addWidget(titulo_acciones)

        self.titulo_tarea_acciones = QLabel(
            "NINGUNA TAREA SELECCIONADA"
        )
        self.titulo_tarea_acciones.setWordWrap(True)
        self.titulo_tarea_acciones.setObjectName(
            "tituloTarea"
        )
        acciones_layout.addWidget(
            self.titulo_tarea_acciones
        )

        self.scroll_acciones = QScrollArea()
        self.scroll_acciones.setWidgetResizable(True)
        self.scroll_acciones.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.contenedor_acciones = QWidget()
        self.layout_acciones = QVBoxLayout(
            self.contenedor_acciones
        )
        self.layout_acciones.setAlignment(
            Qt.AlignTop
        )
        self.layout_acciones.setSpacing(6)

        self.scroll_acciones.setWidget(
            self.contenedor_acciones
        )
        acciones_layout.addWidget(
            self.scroll_acciones,
            1
        )

        self.boton_agregar_accion = QPushButton(
            "+ AÑADIR ACCIÓN"
        )
        self.boton_agregar_accion.clicked.connect(
            self.agregar_accion_manual
        )
        acciones_layout.addWidget(
            self.boton_agregar_accion
        )

        self.boton_guardar_rutina = QPushButton(
            "GUARDAR TAREA"
        )
        self.boton_guardar_rutina.setObjectName(
            "botonPrincipal"
        )
        self.boton_guardar_rutina.clicked.connect(
            self.guardar_rutina_como_tarea
        )
        self.boton_guardar_rutina.setEnabled(False)

        acciones_layout.addWidget(
            self.boton_guardar_rutina
        )

        cuerpo.addWidget(acciones)

        principal.addLayout(cuerpo, 1)

        self.refrescar_panel_acciones()


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

    def refrescar_lista_tareas(self):
        self.tarjetas = {}

        while self.layout_tareas.count():
            item = self.layout_tareas.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        for tarea in self.tareas:
            tarjeta = TaskCard(tarea)

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
            tarjeta.ejecutar_solicitado.connect(
                self.ejecutar_ahora
            )
            tarjeta.seleccion_solicitada.connect(
                self.seleccionar_tarea
            )

            self.tarjetas[tarea["id"]] = tarjeta
            self.layout_tareas.addWidget(tarjeta)

        self.actualizar_cabecera_operativa()

        # Durante la construcción inicial el panel derecho
        # todavía puede no existir.
        if hasattr(self, "layout_acciones"):
            self.refrescar_panel_acciones()


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

    def crear_nueva_tarea(self):
        dialogo = TaskEditorDialog(
            self,
            validador_conflictos=self.buscar_conflictos,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        datos = dialogo.obtener_datos()

        nuevo_id = max(
            [tarea.get("id", 0) for tarea in self.tareas],
            default=0,
        ) + 1

        nueva = {
            "id": nuevo_id,
            **datos,
            "estado": "EN ESPERA",
            "transcurrido": "00:00:00",
            "progreso": 0,
            "elapsed_seconds": 0,
            "runtime_base_seconds": 0,
            "runtime_started_at": None,
            "current_run_key": None,
            "last_run_key": None,
            "queued_at": None,
            "completed_at": None,
            "ultima_ejecucion": None,
            "acciones": [],
            "accion_actual_indice": None,
            "duracion_origen": "sin_calcular",
            "detalle_estado": "SIN ACCIONES · Duración sin calcular",
        }

        self.tareas.append(nueva)
        self.tarea_seleccionada_id = nuevo_id

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()

        self.actualizar_chat_bin(
            f"Creé la tarea '{nueva['nombre']}'. "
            "Todavía no tiene acciones. Puedes añadirlas "
            "desde el Panel de acciones o mostrarme una rutina."
        )


    # ========================================================
    # EDITAR TAREA
    # ========================================================

    def editar_tarea(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        if tarea.get("estado") in ["EJECUTANDO", "EN COLA"]:
            QMessageBox.information(
                self,
                "Tarea ocupada",
                "No puedes editar esta tarea mientras está "
                "ejecutándose o esperando en cola.",
            )
            return

        dialogo = TaskEditorDialog(
            self,
            tarea=tarea,
            validador_conflictos=self.buscar_conflictos,
            excluir_id=tarea_id,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        datos = dialogo.obtener_datos()
        tarea.update(datos)

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

    def copiar_tarea(self, tarea_id):
        original = self.obtener_tarea(tarea_id)

        if not original:
            return

        nuevo_id = max(
            [tarea.get("id", 0) for tarea in self.tareas],
            default=0,
        ) + 1

        copia = json.loads(json.dumps(original))

        copia["id"] = nuevo_id
        copia["nombre"] = original["nombre"] + " — copia"
        copia["estado"] = "DETENIDA"
        copia["progreso"] = 0
        copia["transcurrido"] = "00:00:00"
        copia["elapsed_seconds"] = 0
        copia["runtime_base_seconds"] = 0
        copia["runtime_started_at"] = None
        copia["current_run_key"] = None
        copia["last_run_key"] = None
        copia["queued_at"] = None
        copia["completed_at"] = None
        copia["ultima_ejecucion"] = None
        copia["accion_actual_indice"] = None
        copia["detalle_estado"] = "Copia detenida"

        self.tareas.append(copia)
        self.tarea_seleccionada_id = nuevo_id

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()


    # ========================================================
    # ELIMINAR TAREA
    # ========================================================

    def eliminar_tarea(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        if tarea.get("estado") in ["EJECUTANDO", "EN COLA"]:
            QMessageBox.information(
                self,
                "Tarea ocupada",
                "No puedes eliminar una tarea mientras está "
                "ejecutándose o esperando en cola.",
            )
            return

        respuesta = QMessageBox.question(
            self,
            "Eliminar tarea",
            f"¿Eliminar la tarea '{tarea['nombre']}'?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if respuesta != QMessageBox.Yes:
            return

        self.tareas = [
            item
            for item in self.tareas
            if item.get("id") != tarea_id
        ]

        if self.tarea_seleccionada_id == tarea_id:
            self.tarea_seleccionada_id = None

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()


    # ========================================================
    # PAUSAR / CONTINUAR / INICIAR
    # ========================================================

    # ========================================================
    # CHAT / PANEL DE ACCIONES / SELECCIÓN
    # ========================================================

    def actualizar_chat_bin(self, mensaje):
        self.ultimo_chat_sistema = mensaje

        if hasattr(self, "mensaje_chat"):
            self.mensaje_chat.setText(
                f"BIN: {mensaje}"
            )


    def procesar_chat(self):
        if not hasattr(self, "entrada_chat"):
            return

        texto = self.entrada_chat.text().strip()

        if not texto:
            return

        self.entrada_chat.clear()

        if self.tarea_seleccionada_id is None:
            self.actualizar_chat_bin(
                "Recibí tu mensaje, pero primero selecciona "
                "o crea una tarea para asociarle acciones. "
                "La IA local todavía no está conectada."
            )
            return

        tarea = self.obtener_tarea(
            self.tarea_seleccionada_id
        )

        if not tarea:
            self.actualizar_chat_bin(
                "La tarea seleccionada ya no existe."
            )
            return

        self.actualizar_chat_bin(
            f"Guardé el contexto de tu indicación para "
            f"'{tarea['nombre']}': “{texto}”. "
            "La IA local que convertirá este texto en acciones "
            "se conectará en una etapa posterior."
        )


    def seleccionar_tarea(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        self.tarea_seleccionada_id = tarea_id
        self.rutina_en_borrador = False

        self.refrescar_panel_acciones()

        self.actualizar_chat_bin(
            f"Seleccionaste '{tarea['nombre']}'. "
            "Sus pasos aparecen en el Panel de acciones."
        )


    def obtener_acciones_panel_actual(self):
        if self.rutina_en_borrador:
            return self.rutina_borrador

        if self.tarea_seleccionada_id is None:
            return None

        tarea = self.obtener_tarea(
            self.tarea_seleccionada_id
        )

        if not tarea:
            return None

        return tarea.setdefault("acciones", [])


    def refrescar_panel_acciones(self):
        if not hasattr(self, "layout_acciones"):
            return

        while self.layout_acciones.count():
            item = self.layout_acciones.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        acciones = self.obtener_acciones_panel_actual()

        if self.rutina_en_borrador:
            self.titulo_tarea_acciones.setText(
                "RUTINA NUEVA"
            )
            self.boton_agregar_accion.setEnabled(
                not self.grabando
            )
            self.boton_guardar_rutina.setText(
                "GUARDAR TAREA"
            )
            self.boton_guardar_rutina.setEnabled(
                not self.grabando
                and self.inicio_grabacion is None
                and self.duracion_rutina_borrador > 0
            )

            if self.grabando:
                aviso = QLabel(
                    "BIN está observando la demostración.\n\n"
                    "La captura automática de mouse y teclado "
                    "se conectará en una etapa posterior."
                )
                aviso.setWordWrap(True)
                aviso.setObjectName("textoSecundario")
                self.layout_acciones.addWidget(aviso)

        elif self.tarea_seleccionada_id is not None:
            tarea = self.obtener_tarea(
                self.tarea_seleccionada_id
            )

            if tarea:
                self.titulo_tarea_acciones.setText(
                    tarea.get("nombre", "TAREA")
                )

            self.boton_agregar_accion.setEnabled(True)
            self.boton_guardar_rutina.setText(
                "CAMBIOS GUARDADOS"
            )
            self.boton_guardar_rutina.setEnabled(False)

        else:
            self.titulo_tarea_acciones.setText(
                "NINGUNA TAREA SELECCIONADA"
            )
            self.boton_agregar_accion.setEnabled(False)
            self.boton_guardar_rutina.setText(
                "GUARDAR TAREA"
            )
            self.boton_guardar_rutina.setEnabled(False)

            aviso = QLabel(
                "Selecciona una tarea de la lista, crea una "
                "con + NUEVA o pulsa MOSTRAR RUTINA."
            )
            aviso.setWordWrap(True)
            aviso.setAlignment(Qt.AlignCenter)
            aviso.setObjectName("textoSecundario")
            self.layout_acciones.addWidget(aviso)
            return

        if acciones is None:
            return

        if not acciones:
            aviso = QLabel(
                "Esta rutina todavía no contiene acciones.\n\n"
                "Puedes añadirlas manualmente aquí. "
                "Más adelante BIN podrá capturarlas al mostrar "
                "una rutina o generarlas con la IA local."
            )
            aviso.setWordWrap(True)
            aviso.setAlignment(Qt.AlignCenter)
            aviso.setObjectName("textoSecundario")
            self.layout_acciones.addWidget(aviso)
            return

        for indice, accion in enumerate(acciones):
            tarjeta = QFrame()
            tarjeta.setObjectName("tarjetaTarea")

            layout = QVBoxLayout(tarjeta)
            layout.setContentsMargins(7, 6, 7, 6)
            layout.setSpacing(5)

            descripcion = QLabel(
                f"{indice + 1:02}. "
                f"{accion.get('descripcion', 'Acción')}"
            )
            descripcion.setWordWrap(True)

            if (
                not self.rutina_en_borrador
                and self.tarea_seleccionada_id is not None
            ):
                tarea = self.obtener_tarea(
                    self.tarea_seleccionada_id
                )
                if (
                    tarea
                    and tarea.get("estado") == "EJECUTANDO"
                    and tarea.get("accion_actual_indice") == indice
                ):
                    descripcion.setText(
                        "▶ "
                        + descripcion.text()
                    )

            botones = QHBoxLayout()

            subir = QPushButton("↑")
            bajar = QPushButton("↓")
            editar = QPushButton("EDITAR")
            eliminar = QPushButton("×")

            subir.setEnabled(indice > 0)
            bajar.setEnabled(
                indice < len(acciones) - 1
            )

            subir.clicked.connect(
                lambda checked=False, i=indice:
                self.mover_accion(i, -1)
            )
            bajar.clicked.connect(
                lambda checked=False, i=indice:
                self.mover_accion(i, 1)
            )
            editar.clicked.connect(
                lambda checked=False, i=indice:
                self.editar_accion_manual(i)
            )
            eliminar.clicked.connect(
                lambda checked=False, i=indice:
                self.eliminar_accion_manual(i)
            )

            botones.addWidget(subir)
            botones.addWidget(bajar)
            botones.addWidget(editar)
            botones.addWidget(eliminar)

            layout.addWidget(descripcion)
            layout.addLayout(botones)

            self.layout_acciones.addWidget(tarjeta)


    def agregar_accion_manual(self):
        acciones = self.obtener_acciones_panel_actual()

        if acciones is None:
            QMessageBox.information(
                self,
                "Selecciona una tarea",
                "Primero selecciona una tarea o inicia "
                "MOSTRAR RUTINA.",
            )
            return

        descripcion, aceptado = QInputDialog.getText(
            self,
            "Añadir acción",
            "Describe el paso que debe realizar BIN:",
        )

        descripcion = descripcion.strip()

        if not aceptado or not descripcion:
            return

        siguiente_id = max(
            [
                accion.get("id", 0)
                for accion in acciones
            ],
            default=0,
        ) + 1

        acciones.append(
            {
                "id": siguiente_id,
                "tipo": "manual",
                "descripcion": descripcion,
                "origen": "manual",
            }
        )

        self.guardar_cambios_acciones()


    def editar_accion_manual(self, indice):
        acciones = self.obtener_acciones_panel_actual()

        if (
            acciones is None
            or indice < 0
            or indice >= len(acciones)
        ):
            return

        actual = acciones[indice].get(
            "descripcion",
            "",
        )

        descripcion, aceptado = QInputDialog.getText(
            self,
            "Editar acción",
            "Descripción:",
            text=actual,
        )

        descripcion = descripcion.strip()

        if not aceptado or not descripcion:
            return

        acciones[indice]["descripcion"] = descripcion

        self.guardar_cambios_acciones()


    def eliminar_accion_manual(self, indice):
        acciones = self.obtener_acciones_panel_actual()

        if (
            acciones is None
            or indice < 0
            or indice >= len(acciones)
        ):
            return

        respuesta = QMessageBox.question(
            self,
            "Eliminar acción",
            "¿Eliminar este paso de la rutina?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if respuesta != QMessageBox.Yes:
            return

        acciones.pop(indice)

        self.guardar_cambios_acciones()


    def mover_accion(self, indice, direccion):
        acciones = self.obtener_acciones_panel_actual()

        if acciones is None:
            return

        destino = indice + direccion

        if (
            indice < 0
            or indice >= len(acciones)
            or destino < 0
            or destino >= len(acciones)
        ):
            return

        acciones[indice], acciones[destino] = (
            acciones[destino],
            acciones[indice],
        )

        self.guardar_cambios_acciones()


    def guardar_cambios_acciones(self):
        if self.rutina_en_borrador:
            self.refrescar_panel_acciones()
            return

        if self.tarea_seleccionada_id is None:
            return

        tarea = self.obtener_tarea(
            self.tarea_seleccionada_id
        )

        if not tarea:
            return

        self.recalcular_duracion_desde_acciones(
            tarea
        )

        if tarea.get("acciones"):
            if tarea.get("estado") == "REQUIERE CONFIGURACIÓN":
                tarea["estado"] = "EN ESPERA"

            tarea["detalle_estado"] = (
                f"{len(tarea['acciones'])} acción(es) configurada(s)"
            )
        else:
            tarea["detalle_estado"] = (
                "SIN ACCIONES · Duración sin calcular"
            )

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()


    def recalcular_duracion_desde_acciones(self, tarea):
        origen = tarea.get("duracion_origen")

        if origen in ["grabacion", "real"]:
            return

        acciones = tarea.get("acciones", [])

        if not acciones:
            tarea["duracion"] = "00:00:00"
            tarea["duracion_origen"] = "sin_calcular"
            return

        # Estimación provisional hasta que existan mediciones reales.
        segundos = max(
            5,
            len(acciones) * 5,
        )

        tarea["duracion"] = segundos_a_hms(
            segundos
        )
        tarea["duracion_origen"] = (
            "estimada_acciones"
        )


    def guardar_rutina_como_tarea(self):
        if (
            not self.rutina_en_borrador
            or self.grabando
            or self.duracion_rutina_borrador <= 0
        ):
            return

        duracion = segundos_a_hms(
            max(
                1,
                self.duracion_rutina_borrador,
            )
        )

        temporal = {
            "nombre": "",
            "hora": "05:40",
            "veces": 1,
            "intervalo_valor": 24,
            "intervalo_unidad": "horas",
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "duracion": duracion,
        }

        dialogo = TaskEditorDialog(
            self,
            tarea=temporal,
            validador_conflictos=self.buscar_conflictos,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        datos = dialogo.obtener_datos()

        nuevo_id = max(
            [tarea.get("id", 0) for tarea in self.tareas],
            default=0,
        ) + 1

        acciones = json.loads(
            json.dumps(
                self.rutina_borrador
            )
        )

        nueva = {
            "id": nuevo_id,
            **datos,
            "estado": "EN ESPERA",
            "transcurrido": "00:00:00",
            "progreso": 0,
            "elapsed_seconds": 0,
            "runtime_base_seconds": 0,
            "runtime_started_at": None,
            "current_run_key": None,
            "last_run_key": None,
            "queued_at": None,
            "completed_at": None,
            "ultima_ejecucion": None,
            "acciones": acciones,
            "accion_actual_indice": None,
            "duracion_origen": "grabacion",
            "detalle_estado": (
                f"{len(acciones)} acción(es) · "
                "Duración calculada desde la demostración"
            ),
        }

        self.tareas.append(nueva)

        self.rutina_borrador = []
        self.rutina_en_borrador = False
        self.duracion_rutina_borrador = 0
        self.inicio_grabacion = None
        self.tarea_seleccionada_id = nuevo_id

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()

        self.actualizar_chat_bin(
            f"Guardé la rutina como '{nueva['nombre']}'."
        )

    # ========================================================
    # MOTOR DE EJECUCIÓN / COLA / SCHEDULER
    # ========================================================

    def obtener_tarea_ejecutando(self):
        if self.tarea_ejecutando_id is None:
            return None

        return self.obtener_tarea(
            self.tarea_ejecutando_id
        )


    def obtener_duracion_total_tarea(self, tarea):
        duracion = duracion_a_segundos(
            tarea.get("duracion", "00:00:00")
        )

        if duracion > 0:
            return duracion

        acciones = tarea.get("acciones", [])

        if acciones:
            duracion = max(
                5,
                len(acciones) * 5,
            )
            tarea["duracion"] = segundos_a_hms(
                duracion
            )
            tarea["duracion_origen"] = (
                "estimada_acciones"
            )
            return duracion

        return 0


    def clave_programada_para_ahora(
        self,
        tarea,
        ahora=None,
    ):
        if ahora is None:
            ahora = datetime.now()

        if ahora.weekday() not in tarea.get(
            "dias",
            [],
        ):
            return None

        try:
            hora, minuto = [
                int(valor)
                for valor in tarea.get(
                    "hora",
                    ""
                ).split(":")
            ]
        except Exception:
            return None

        if (
            ahora.hour != hora
            or ahora.minute != minuto
        ):
            return None

        return (
            "sched-"
            + ahora.strftime("%Y%m%d-")
            + f"{hora:02}{minuto:02}"
        )


    def ejecutar_ahora(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        tarea_actual = self.obtener_tarea_ejecutando()

        if tarea_actual:
            mensaje = (
                f"La tarea '{tarea_actual['nombre']}' "
                "está en ejecución ahora."
            )

            QMessageBox.information(
                self,
                "BIN está ocupado",
                mensaje,
            )

            self.actualizar_chat_bin(
                mensaje
            )
            return

        if tarea.get("estado") == "EN PAUSA" and tarea.get(
            "current_run_key"
        ):
            self.continuar_ejecucion(
                tarea
            )
            return

        duracion_total = (
            self.obtener_duracion_total_tarea(
                tarea
            )
        )

        if duracion_total <= 0:
            mensaje = (
                f"La tarea '{tarea['nombre']}' todavía no "
                "tiene acciones ni una duración calculada."
            )
            QMessageBox.information(
                self,
                "Tarea sin acciones",
                mensaje,
            )
            self.actualizar_chat_bin(mensaje)
            tarea["estado"] = (
                "REQUIERE CONFIGURACIÓN"
            )
            tarea["detalle_estado"] = (
                "Añade acciones antes de ejecutar"
            )
            self.guardar_tareas_en_disco()
            self.actualizar_tarjeta_tarea(
                tarea["id"]
            )
            return

        ahora = datetime.now()

        run_key = self.clave_programada_para_ahora(
            tarea,
            ahora,
        )

        if run_key is None:
            run_key = (
                "manual-"
                + ahora.strftime(
                    "%Y%m%d-%H%M%S"
                )
            )

        self.iniciar_ejecucion(
            tarea,
            run_key=run_key,
            origen="manual",
        )


    def poner_en_cola(
        self,
        tarea,
        run_key,
    ):
        if tarea.get("estado") == "EN COLA":
            return

        tarea["estado"] = "EN COLA"
        tarea["current_run_key"] = run_key
        tarea["queued_at"] = (
            datetime.now().isoformat()
        )
        tarea["runtime_started_at"] = None
        tarea["detalle_estado"] = (
            "Esperando a que termine la tarea actual"
        )

        self.guardar_tareas_en_disco()
        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )

        actual = self.obtener_tarea_ejecutando()

        if actual:
            self.actualizar_chat_bin(
                f"'{tarea['nombre']}' quedó en cola porque "
                f"'{actual['nombre']}' está en ejecución."
            )


    def iniciar_ejecucion(
        self,
        tarea,
        run_key=None,
        origen="manual",
    ):
        duracion_total = (
            self.obtener_duracion_total_tarea(
                tarea
            )
        )

        if duracion_total <= 0:
            tarea["estado"] = (
                "REQUIERE CONFIGURACIÓN"
            )
            tarea["detalle_estado"] = (
                "No hay acciones para ejecutar"
            )
            self.guardar_tareas_en_disco()
            self.actualizar_tarjeta_tarea(
                tarea["id"]
            )
            return False

        ahora = datetime.now()

        if run_key is None:
            run_key = (
                "manual-"
                + ahora.strftime(
                    "%Y%m%d-%H%M%S"
                )
            )

        self.tarea_ejecutando_id = tarea["id"]
        self.tarea_seleccionada_id = tarea["id"]
        self.rutina_en_borrador = False

        tarea["estado"] = "EJECUTANDO"
        tarea["elapsed_seconds"] = 0
        tarea["runtime_base_seconds"] = 0
        tarea["transcurrido"] = "00:00:00"
        tarea["progreso"] = 0
        tarea["runtime_started_at"] = (
            ahora.isoformat()
        )
        tarea["current_run_key"] = run_key
        tarea["queued_at"] = None
        tarea["completed_at"] = None
        tarea["accion_actual_indice"] = None
        tarea["detalle_estado"] = (
            "Iniciando ejecución..."
        )

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText(
                "● BIN OCUPADO"
            )
            self.estado_bin.setStyleSheet(
                f"""
                color: {AMARILLO};
                font-weight: 800;
                """
            )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "BIN ESTÁ EJECUTANDO\n\n"
                f"{tarea['nombre']}\n\n"
                "Preparando la primera acción..."
            )

        if origen == "programada":
            self.actualizar_chat_bin(
                f"Inicié automáticamente "
                f"'{tarea['nombre']}' porque llegó "
                "su hora programada."
            )
        else:
            self.actualizar_chat_bin(
                f"Inicié '{tarea['nombre']}' "
                "con EJECUTAR AHORA."
            )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        return True


    def actualizar_motor_ejecucion(self):
        tarea = self.obtener_tarea_ejecutando()

        if not tarea:
            return

        if tarea.get("estado") != "EJECUTANDO":
            return

        inicio_texto = tarea.get(
            "runtime_started_at"
        )

        if not inicio_texto:
            return

        try:
            inicio = datetime.fromisoformat(
                inicio_texto
            )
        except Exception:
            self.finalizar_ejecucion_con_error(
                tarea,
                "No se pudo interpretar el tiempo "
                "de inicio de la ejecución.",
            )
            return

        ahora = datetime.now()

        base = int(
            tarea.get(
                "runtime_base_seconds",
                0,
            )
        )

        transcurrido = max(
            0,
            base
            + int(
                (
                    ahora - inicio
                ).total_seconds()
            ),
        )

        duracion_total = (
            self.obtener_duracion_total_tarea(
                tarea
            )
        )

        if duracion_total <= 0:
            self.finalizar_ejecucion_con_error(
                tarea,
                "La tarea no tiene una duración válida.",
            )
            return

        transcurrido = min(
            transcurrido,
            duracion_total,
        )

        tarea["elapsed_seconds"] = transcurrido
        tarea["transcurrido"] = (
            segundos_a_hms(
                transcurrido
            )
        )

        progreso = int(
            (
                transcurrido
                / duracion_total
            )
            * 100
        )

        progreso = min(
            100,
            max(
                0,
                progreso,
            ),
        )

        tarea["progreso"] = progreso

        acciones = tarea.get(
            "acciones",
            [],
        )

        if acciones:
            cantidad = len(acciones)

            if transcurrido >= duracion_total:
                indice = cantidad - 1
            else:
                indice = min(
                    cantidad - 1,
                    int(
                        (
                            transcurrido
                            / duracion_total
                        )
                        * cantidad
                    ),
                )

            indice_anterior = tarea.get(
                "accion_actual_indice"
            )

            tarea["accion_actual_indice"] = indice

            descripcion = acciones[indice].get(
                "descripcion",
                "Acción",
            )

            tarea["detalle_estado"] = (
                f"Acción {indice + 1}/{cantidad} · "
                f"{descripcion}"
            )

            if indice != indice_anterior:
                self.actualizar_chat_bin(
                    f"{tarea['nombre']} — acción "
                    f"{indice + 1}/{cantidad}: "
                    f"{descripcion}"
                )

                if hasattr(self, "mensaje_visor"):
                    self.mensaje_visor.setText(
                        "BIN ESTÁ EJECUTANDO\n\n"
                        f"{tarea['nombre']}\n\n"
                        f"ACCIÓN {indice + 1} DE {cantidad}\n"
                        f"{descripcion}"
                    )

                self.refrescar_panel_acciones()

        else:
            # Compatibilidad con las tareas antiguas del
            # motor v0.5 que ya tienen duración pero todavía
            # no contienen una lista semántica de acciones.
            tarea["detalle_estado"] = (
                f"Ejecutando rutina · {progreso}%"
            )

            if hasattr(self, "mensaje_visor"):
                self.mensaje_visor.setText(
                    "BIN ESTÁ EJECUTANDO\n\n"
                    f"{tarea['nombre']}\n\n"
                    f"PROGRESO {progreso}%"
                )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )

        if transcurrido >= duracion_total:
            self.finalizar_ejecucion(
                tarea
            )


    def pausar_ejecucion(self, tarea):
        if tarea.get("estado") != "EJECUTANDO":
            return

        inicio_texto = tarea.get(
            "runtime_started_at"
        )

        if inicio_texto:
            try:
                inicio = datetime.fromisoformat(
                    inicio_texto
                )
                adicional = int(
                    (
                        datetime.now() - inicio
                    ).total_seconds()
                )
            except Exception:
                adicional = 0
        else:
            adicional = 0

        base = int(
            tarea.get(
                "runtime_base_seconds",
                0,
            )
        )

        transcurrido = max(
            0,
            base + adicional,
        )

        duracion_total = (
            self.obtener_duracion_total_tarea(
                tarea
            )
        )

        if duracion_total > 0:
            transcurrido = min(
                transcurrido,
                duracion_total,
            )

        tarea["elapsed_seconds"] = transcurrido
        tarea["runtime_base_seconds"] = transcurrido
        tarea["transcurrido"] = (
            segundos_a_hms(
                transcurrido
            )
        )
        tarea["runtime_started_at"] = None
        tarea["estado"] = "EN PAUSA"
        tarea["detalle_estado"] = (
            "Ejecución pausada"
        )

        self.tarea_ejecutando_id = None

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText(
                "● BIN OPERATIVO"
            )
            self.estado_bin.setStyleSheet(
                f"""
                color: {VERDE};
                font-weight: 800;
                """
            )

        self.actualizar_chat_bin(
            f"Pausé '{tarea['nombre']}' en "
            f"{tarea['transcurrido']}."
        )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )
        self.guardar_tareas_en_disco()

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )


    def continuar_ejecucion(self, tarea):
        actual = self.obtener_tarea_ejecutando()

        if actual:
            mensaje = (
                f"La tarea '{actual['nombre']}' "
                "está en ejecución ahora."
            )
            QMessageBox.information(
                self,
                "BIN está ocupado",
                mensaje,
            )
            self.actualizar_chat_bin(
                mensaje
            )
            return

        if (
            tarea.get("estado") != "EN PAUSA"
            or not tarea.get("current_run_key")
        ):
            return

        self.tarea_ejecutando_id = tarea["id"]
        self.tarea_seleccionada_id = tarea["id"]

        tarea["estado"] = "EJECUTANDO"
        tarea["runtime_base_seconds"] = int(
            tarea.get(
                "elapsed_seconds",
                0,
            )
        )
        tarea["runtime_started_at"] = (
            datetime.now().isoformat()
        )
        tarea["detalle_estado"] = (
            "Continuando ejecución..."
        )

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText(
                "● BIN OCUPADO"
            )
            self.estado_bin.setStyleSheet(
                f"""
                color: {AMARILLO};
                font-weight: 800;
                """
            )

        self.actualizar_chat_bin(
            f"Continué '{tarea['nombre']}' "
            f"desde {tarea.get('transcurrido', '00:00:00')}."
        )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )
        self.refrescar_panel_acciones()
        self.guardar_tareas_en_disco()


    def finalizar_ejecucion(self, tarea):
        duracion_total = (
            self.obtener_duracion_total_tarea(
                tarea
            )
        )

        ahora = datetime.now()

        tarea["estado"] = "FINALIZADA"
        tarea["elapsed_seconds"] = duracion_total
        tarea["runtime_base_seconds"] = 0
        tarea["transcurrido"] = (
            segundos_a_hms(
                duracion_total
            )
        )
        tarea["progreso"] = 100
        tarea["last_run_key"] = tarea.get(
            "current_run_key"
        )
        tarea["current_run_key"] = None
        tarea["runtime_started_at"] = None
        tarea["queued_at"] = None
        tarea["completed_at"] = (
            ahora.isoformat()
        )
        tarea["ultima_ejecucion"] = (
            ahora.isoformat()
        )
        tarea["accion_actual_indice"] = None

        proxima = (
            self.calcular_proxima_ejecucion_tarea(
                tarea,
                desde=ahora
                + timedelta(seconds=1),
            )
        )

        ultima_texto = ahora.strftime(
            "%d/%m %H:%M"
        )

        if proxima:
            tarea["detalle_estado"] = (
                "FINALIZADA\n"
                f"Última ejecución: {ultima_texto}\n"
                "Próxima ejecución: "
                + self.formatear_proxima_ejecucion(
                    proxima
                )
            )
        else:
            tarea["detalle_estado"] = (
                "FINALIZADA\n"
                f"Última ejecución: {ultima_texto}\n"
                "Próxima ejecución: Sin programación"
            )

        self.tarea_ejecutando_id = None

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText(
                "● BIN OPERATIVO"
            )
            self.estado_bin.setStyleSheet(
                f"""
                color: {VERDE};
                font-weight: 800;
                """
            )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "EJECUCIÓN FINALIZADA\n\n"
                f"{tarea['nombre']}\n\n"
                "BIN está disponible."
            )

        self.actualizar_chat_bin(
            f"Finalicé '{tarea['nombre']}'. "
            + (
                "Próxima ejecución: "
                + self.formatear_proxima_ejecucion(
                    proxima
                )
                if proxima
                else "No tiene una próxima ejecución."
            )
        )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )


    def finalizar_ejecucion_con_error(
        self,
        tarea,
        mensaje,
    ):
        tarea["estado"] = "ERROR"
        tarea["runtime_started_at"] = None
        tarea["detalle_estado"] = mensaje
        tarea["accion_actual_indice"] = None

        self.tarea_ejecutando_id = None

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText(
                "● BIN CON ERROR"
            )
            self.estado_bin.setStyleSheet(
                f"""
                color: {ROJO};
                font-weight: 800;
                """
            )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "ERROR DE EJECUCIÓN\n\n"
                f"{tarea['nombre']}\n\n"
                f"{mensaje}"
            )

        self.actualizar_chat_bin(
            f"Error en '{tarea['nombre']}': "
            f"{mensaje}"
        )

        self.actualizar_tarjeta_tarea(
            tarea["id"]
        )
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )


    def iniciar_siguiente_en_cola(self):
        if self.obtener_tarea_ejecutando():
            return

        en_cola = [
            tarea
            for tarea in self.tareas
            if tarea.get("estado") == "EN COLA"
        ]

        if not en_cola:
            return

        en_cola.sort(
            key=lambda tarea:
            tarea.get(
                "queued_at",
                "",
            )
        )

        siguiente = en_cola[0]

        run_key = siguiente.get(
            "current_run_key"
        )

        self.iniciar_ejecucion(
            siguiente,
            run_key=run_key,
            origen="programada",
        )


    def calcular_proxima_ejecucion_tarea(
        self,
        tarea,
        desde=None,
    ):
        if desde is None:
            desde = datetime.now()

        try:
            hora, minuto = [
                int(valor)
                for valor in tarea.get(
                    "hora",
                    ""
                ).split(":")
            ]
        except Exception:
            return None

        dias = tarea.get("dias", [])

        if not dias:
            return None

        for desplazamiento in range(0, 8):
            fecha = desde + timedelta(
                days=desplazamiento
            )

            if fecha.weekday() not in dias:
                continue

            momento = fecha.replace(
                hour=hora,
                minute=minuto,
                second=0,
                microsecond=0,
            )

            if momento > desde:
                return momento

        return None


    def formatear_proxima_ejecucion(
        self,
        momento,
    ):
        ahora = datetime.now()

        hoy = ahora.date()
        fecha = momento.date()

        if fecha == hoy:
            dia_texto = "Hoy"
        elif fecha == (
            hoy + timedelta(days=1)
        ):
            dia_texto = "Mañana"
        else:
            nombres = [
                "Lunes",
                "Martes",
                "Miércoles",
                "Jueves",
                "Viernes",
                "Sábado",
                "Domingo",
            ]
            dia_texto = nombres[
                momento.weekday()
            ]

        segundos = max(
            0,
            int(
                (
                    momento - ahora
                ).total_seconds()
            ),
        )

        return (
            f"{dia_texto} · "
            f"{momento.strftime('%H:%M')} · "
            f"en {describir_tiempo_restante(segundos)}"
        )


    def actualizar_estado_pasivo_tarea(
        self,
        tarea,
    ):
        estado = tarea.get("estado")

        if estado in [
            "EJECUTANDO",
            "EN COLA",
            "EN PAUSA",
            "DETENIDA",
            "ERROR",
            "REQUIERE CONFIGURACIÓN",
        ]:
            return

        proxima = (
            self.calcular_proxima_ejecucion_tarea(
                tarea
            )
        )

        if estado == "FINALIZADA":
            ultima_texto = "--"

            ultima = tarea.get(
                "ultima_ejecucion"
            )

            if ultima:
                try:
                    ultima_texto = (
                        datetime.fromisoformat(
                            ultima
                        ).strftime(
                            "%d/%m %H:%M"
                        )
                    )
                except Exception:
                    ultima_texto = "--"

            if proxima:
                tarea["detalle_estado"] = (
                    "FINALIZADA\n"
                    f"Última ejecución: {ultima_texto}\n"
                    "Próxima ejecución: "
                    + self.formatear_proxima_ejecucion(
                        proxima
                    )
                )
            else:
                tarea["detalle_estado"] = (
                    "FINALIZADA\n"
                    f"Última ejecución: {ultima_texto}\n"
                    "Próxima ejecución: Sin programación"
                )
            return

        if proxima:
            segundos = int(
                (
                    proxima - datetime.now()
                ).total_seconds()
            )

            if (
                segundos
                <= UMBRAL_PROXIMA_SEGUNDOS
            ):
                tarea["estado"] = "PRÓXIMA"
            else:
                tarea["estado"] = "EN ESPERA"

            tarea["detalle_estado"] = (
                "Próxima ejecución: "
                + self.formatear_proxima_ejecucion(
                    proxima
                )
            )


    def actualizar_tarjeta_tarea(
        self,
        tarea_id,
    ):
        tarjeta = self.tarjetas.get(
            tarea_id
        )

        if tarjeta:
            tarjeta.actualizar_estado()


    def actualizar_tarjetas(self):
        for tarea in self.tareas:
            self.actualizar_estado_pasivo_tarea(
                tarea
            )

            tarjeta = self.tarjetas.get(
                tarea.get("id")
            )

            if tarjeta:
                tarjeta.actualizar_estado()


    def scheduler_tick(self):
        ahora = datetime.now()

        for tarea in self.tareas:
            estado = tarea.get("estado")

            if estado in [
                "DETENIDA",
                "EN PAUSA",
                "ERROR",
                "REQUIERE CONFIGURACIÓN",
            ]:
                continue

            run_key = (
                self.clave_programada_para_ahora(
                    tarea,
                    ahora,
                )
            )

            if not run_key:
                continue

            if tarea.get("last_run_key") == run_key:
                continue

            if tarea.get("current_run_key") == run_key:
                continue

            if (
                self.tarea_ejecutando_id
                == tarea.get("id")
            ):
                continue

            duracion_total = (
                self.obtener_duracion_total_tarea(
                    tarea
                )
            )

            if duracion_total <= 0:
                tarea["estado"] = (
                    "REQUIERE CONFIGURACIÓN"
                )
                tarea["detalle_estado"] = (
                    "Llegó la hora, pero no hay acciones "
                    "configuradas."
                )
                self.actualizar_chat_bin(
                    f"'{tarea['nombre']}' llegó a su hora, "
                    "pero todavía no tiene acciones."
                )
                continue

            actual = self.obtener_tarea_ejecutando()

            if actual:
                self.poner_en_cola(
                    tarea,
                    run_key,
                )
            else:
                self.iniciar_ejecucion(
                    tarea,
                    run_key=run_key,
                    origen="programada",
                )

        self.actualizar_tarjetas()
        self.actualizar_cabecera_operativa()


    def guardar_estado_runtime(self):
        # Guardado periódico para que una pausa, progreso,
        # cola o ejecución pueda recuperarse con seguridad.
        self.guardar_tareas_en_disco()

    def alternar_pausa_tarea(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        estado_actual = tarea.get(
            "estado",
            "DETENIDA",
        )

        if estado_actual == "EJECUTANDO":
            self.pausar_ejecucion(tarea)
            return

        if (
            estado_actual == "EN PAUSA"
            and tarea.get("current_run_key")
        ):
            self.continuar_ejecucion(tarea)
            return

        if estado_actual == "EN PAUSA":
            tarea["estado"] = "EN ESPERA"
            tarea["detalle_estado"] = (
                "Programación reactivada"
            )
            self.actualizar_chat_bin(
                f"Reactivé la programación de "
                f"'{tarea['nombre']}'."
            )

        elif estado_actual == "DETENIDA":
            candidata = tarea.copy()
            candidata["estado"] = "EN ESPERA"

            conflictos = self.buscar_conflictos(
                candidata,
                excluir_id=tarea_id,
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
                    "Edita su horario antes de activarla.",
                )
                return

            tarea["estado"] = "EN ESPERA"
            tarea["detalle_estado"] = (
                "Programación activada"
            )

            self.actualizar_chat_bin(
                f"Activé la programación de "
                f"'{tarea['nombre']}'."
            )

        else:
            # En espera, próxima o finalizada el botón aparece
            # bloqueado; por seguridad no cambiamos el estado.
            return

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()


    # ========================================================
    # CALCULAR PRÓXIMA TAREA
    # ========================================================

    def calcular_proxima_tarea(self):
        ahora = datetime.now()
        candidatas = []

        for tarea in self.tareas:
            estado = tarea.get("estado")

            if estado in [
                "DETENIDA",
                "EN PAUSA",
                "ERROR",
                "EJECUTANDO",
                "EN COLA",
                "REQUIERE CONFIGURACIÓN",
            ]:
                continue

            momento = (
                self.calcular_proxima_ejecucion_tarea(
                    tarea,
                    desde=ahora,
                )
            )

            if momento:
                candidatas.append(
                    (momento, tarea)
                )

        if not candidatas:
            return None

        candidatas.sort(
            key=lambda item: item[0]
        )

        return candidatas[0]


    # ========================================================
    # ACTUALIZAR CABECERA
    # ========================================================

    def actualizar_cabecera_operativa(self):
        # Esta función es deliberadamente segura durante el
        # arranque. Solo toca widgets de la cabecera.
        if hasattr(self, "contador_tareas"):
            self.contador_tareas.setText(
                "TAREAS GUARDADAS\n"
                f"{len(self.tareas)}"
            )

        if not hasattr(
            self,
            "proxima_cabecera",
        ):
            return

        proxima = self.calcular_proxima_tarea()

        if not proxima:
            self.proxima_cabecera.setText(
                "PRÓXIMA TAREA\n--"
            )
            return

        momento, tarea = proxima

        self.proxima_cabecera.setText(
            "PRÓXIMA TAREA\n"
            f"{tarea['nombre']} · "
            f"{self.formatear_proxima_ejecucion(momento)}"
        )


    # ========================================================
    # MOSTRAR / DETENER RUTINA
    # ========================================================

    def alternar_grabacion(self):
        if not self.grabando:
            self.grabando = True
            self.rutina_en_borrador = True
            self.rutina_borrador = []
            self.duracion_rutina_borrador = 0
            self.inicio_grabacion = datetime.now()

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

            self.actualizar_chat_bin(
                "Estoy observando la rutina. "
                "Cuando termines pulsa DETENER GRABACIÓN."
            )

            if hasattr(self, "mensaje_visor"):
                self.mensaje_visor.setText(
                    "BIN ESTÁ OBSERVANDO\n\n"
                    "Realiza la rutina que quieres enseñarme.\n\n"
                    "La captura automática de mouse y teclado "
                    "se conectará en una etapa posterior."
                )

            self.refrescar_panel_acciones()
            return

        # --------------------------------------------------------
        # DETENER GRABACIÓN
        # --------------------------------------------------------

        self.grabando = False

        ahora = datetime.now()

        if self.inicio_grabacion:
            segundos = max(
                1,
                int(
                    (
                        ahora
                        - self.inicio_grabacion
                    ).total_seconds()
                ),
            )
        else:
            segundos = 1

        self.duracion_rutina_borrador = segundos
        self.inicio_grabacion = None

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

        self.actualizar_chat_bin(
            "Detuve la grabación. "
            f"La demostración duró "
            f"{segundos_a_hms(segundos)}. "
            "Revisa el Panel de acciones y pulsa "
            "GUARDAR TAREA para abrir su configuración."
        )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "RUTINA CAPTURADA\n\n"
                f"Duración: {segundos_a_hms(segundos)}\n\n"
                "Revisa el Panel de acciones y "
                "pulsa GUARDAR TAREA."
            )

        self.refrescar_panel_acciones()


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

    def iniciar_temporizadores(self):
        # RELOJ
        self.timer_reloj = QTimer(self)
        self.timer_reloj.timeout.connect(
            self.actualizar_reloj
        )
        self.timer_reloj.start(1000)

        # SISTEMA
        self.timer_sistema = QTimer(self)
        self.timer_sistema.timeout.connect(
            self.actualizar_sistema
        )
        self.timer_sistema.start(1500)

        # MOTOR DE EJECUCIÓN
        self.timer_motor = QTimer(self)
        self.timer_motor.timeout.connect(
            self.actualizar_motor_ejecucion
        )
        self.timer_motor.start(250)

        # SCHEDULER AUTOMÁTICO
        self.timer_scheduler = QTimer(self)
        self.timer_scheduler.timeout.connect(
            self.scheduler_tick
        )
        self.timer_scheduler.start(1000)

        # GUARDADO PERIÓDICO DEL ESTADO
        self.timer_guardado_runtime = QTimer(self)
        self.timer_guardado_runtime.timeout.connect(
            self.guardar_estado_runtime
        )
        self.timer_guardado_runtime.start(5000)

        self.actualizar_reloj()
        self.actualizar_sistema()
        self.scheduler_tick()


    # ========================================================
    # ESTILOS
    # ========================================================

    def closeEvent(self, event):
        # Guardado seguro si BIN se cierra durante una ejecución.
        tarea = self.obtener_tarea_ejecutando()

        if tarea and tarea.get("estado") == "EJECUTANDO":
            inicio_texto = tarea.get(
                "runtime_started_at"
            )

            adicional = 0

            if inicio_texto:
                try:
                    inicio = datetime.fromisoformat(
                        inicio_texto
                    )
                    adicional = int(
                        (
                            datetime.now()
                            - inicio
                        ).total_seconds()
                    )
                except Exception:
                    adicional = 0

            base = int(
                tarea.get(
                    "runtime_base_seconds",
                    0,
                )
            )

            tarea["elapsed_seconds"] = max(
                0,
                base + adicional,
            )
            tarea["runtime_base_seconds"] = (
                tarea["elapsed_seconds"]
            )
            tarea["transcurrido"] = (
                segundos_a_hms(
                    tarea["elapsed_seconds"]
                )
            )
            tarea["runtime_started_at"] = None
            tarea["estado"] = "EN PAUSA"
            tarea["detalle_estado"] = (
                "Pausada al cerrar BIN"
            )

        # Las tareas en cola quedan pausadas para que BIN no
        # reanude trabajo a ciegas después de un reinicio.
        for item in self.tareas:
            if item.get("estado") == "EN COLA":
                item["estado"] = "EN PAUSA"
                item["runtime_started_at"] = None
                item["detalle_estado"] = (
                    "Pausada al cerrar BIN"
                )

        self.guardar_tareas_en_disco()

        event.accept()

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