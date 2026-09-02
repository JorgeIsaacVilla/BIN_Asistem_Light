import sys
import json
import psutil
import ctypes
import time
import shutil
import subprocess
from ctypes import wintypes

try:
    import winreg
except ImportError:
    winreg = None

try:
    import mss
except ImportError:
    mss = None

try:
    from pynput import mouse as pynput_mouse
    from pynput import keyboard as pynput_keyboard
except ImportError:
    pynput_mouse = None
    pynput_keyboard = None

from pathlib import Path
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal, QTime, QThread
from PySide6.QtGui import QImage, QPixmap
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
# CAPTURA / WINDOWS
# ============================================================

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# ============================================================
# CONTROL DE MOUSE / VENTANA
# ============================================================

GWL_EXSTYLE = -20

WS_EX_TRANSPARENT = 0x00000020

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_BOTTOM = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

MOUSEEVENTF_WHEEL = 0x0800

MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
SWP_SHOWWINDOW = 0x0040


# ============================================================
# SENDINPUT PRIVADO DE BIN
# ============================================================


class BINMouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class BINInputUnion(ctypes.Union):
    _fields_ = [
        ("mi", BINMouseInput),
    ]


class BINInput(ctypes.Structure):
    _anonymous_ = ("union",)

    _fields_ = [
        ("type", ctypes.c_uint32),
        ("union", BINInputUnion),
    ]


BIN_SEND_INPUT = None

if sys.platform == "win32":
    try:
        _bin_user32 = ctypes.WinDLL(
            "user32",
            use_last_error=True,
        )

        BIN_SEND_INPUT = _bin_user32.SendInput

        BIN_SEND_INPUT.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(BINInput),
            ctypes.c_int,
        ]

        BIN_SEND_INPUT.restype = ctypes.c_uint32

    except Exception:
        BIN_SEND_INPUT = None

# ============================================================
# MENSAJES VIRTUALES DE MOUSE / WINDOWS
# ============================================================

WM_MOUSEMOVE = 0x0200

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203

WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205

WM_MOUSEWHEEL = 0x020A

MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002
CWP_SKIPTRANSPARENT = 0x0004

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

    return " ".join(DIAS_NOMBRES[dia] for dia in sorted(dias))


def duracion_a_segundos(texto):
    """
    Convierte HH:MM:SS a segundos.
    """

    try:

        horas, minutos, segundos = [int(valor) for valor in texto.split(":")]

        return horas * 3600 + minutos * 60 + segundos

    except Exception:

        return 0


def hora_a_segundos(texto):
    """
    Convierte HH:MM a segundos desde medianoche.
    """

    try:

        horas, minutos = [int(valor) for valor in texto.split(":")]

        return horas * 3600 + minutos * 60

    except Exception:

        return 0


def segundos_a_hms(segundos):
    """
    Convierte segundos a HH:MM:SS.
    """

    segundos = max(0, int(segundos))

    horas = segundos // 3600

    minutos = (segundos % 3600) // 60

    segundos_restantes = segundos % 60

    return f"{horas:02}:" f"{minutos:02}:" f"{segundos_restantes:02}"


def describir_tiempo_restante(segundos):
    """
    Convierte una cantidad de segundos
    en un texto amigable para la interfaz.
    """

    segundos = max(0, int(segundos))

    if segundos < 60:

        return f"{segundos} s"

    minutos = segundos // 60

    if minutos < 60:

        segundos_restantes = segundos % 60

        return f"{minutos} min " f"{segundos_restantes} s"

    horas = minutos // 60

    minutos_restantes = minutos % 60

    if horas < 24:

        if minutos_restantes:

            return f"{horas} h " f"{minutos_restantes} min"

        return f"{horas} h"

    dias = horas // 24

    horas_restantes = horas % 24

    if horas_restantes:

        return f"{dias} día(s) " f"{horas_restantes} h"

    return f"{dias} día(s)"


# ============================================================
# PANEL REUTILIZABLE
# ============================================================
# ============================================================
# CAPTURA DE PANTALLA
# ============================================================


class ScreenCaptureThread(QThread):

    frame_ready = Signal(QImage)

    error_captura = Signal(str)

    def __init__(
        self,
        monitor_index=1,
        fps=10,
        parent=None,
    ):

        super().__init__(parent)

        self.monitor_index = monitor_index

        self.fps = max(
            1,
            min(
                30,
                int(fps),
            ),
        )

        self.intervalo_ms = max(
            1,
            int(1000 / self.fps),
        )

        self._capturando = False

    def run(self):

        if mss is None:

            self.error_captura.emit("La librería MSS no está instalada.")

            return

        self._capturando = True

        try:

            with mss.mss() as capturador:

                monitores = capturador.monitors

                if len(monitores) <= 1:

                    self.error_captura.emit(
                        "BIN no encontró ningún monitor disponible."
                    )

                    return

                indice = self.monitor_index

                if indice <= 0 or indice >= len(monitores):

                    indice = 1

                monitor = monitores[indice]

                while self._capturando:

                    captura = capturador.grab(monitor)

                    imagen = QImage(
                        captura.rgb,
                        captura.width,
                        captura.height,
                        captura.width * 3,
                        QImage.Format_RGB888,
                    ).copy()

                    self.frame_ready.emit(imagen)

                    self.msleep(self.intervalo_ms)

        except Exception as error:

            self.error_captura.emit(str(error))

        finally:

            self._capturando = False

    def detener(self):

        self._capturando = False


# ============================================================
# VISOR INTERACTIVO
# ============================================================


class VisorInteractivo(QLabel):

    punto_solicitado = Signal(
        float,
        float,
    )

    doble_click_solicitado = Signal(
        float,
        float,
    )

    click_derecho_solicitado = Signal(
        float,
        float,
    )

    scroll_solicitado = Signal(
        float,
        float,
        int,
    )

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.setMouseTracking(True)

        # ----------------------------------------------------
        # NECESARIO PARA DISTINGUIR
        # CLIC SIMPLE DE DOBLE CLIC
        # ----------------------------------------------------

        self._click_pendiente = None

        self._timer_click = QTimer(self)

        self._timer_click.setSingleShot(True)

        self._timer_click.timeout.connect(self._emitir_click_pendiente)

    # ========================================================
    # CONVERTIR POSICIÓN DEL QLABEL
    # A POSICIÓN NORMALIZADA DE LA IMAGEN
    # ========================================================

    def _normalizar_posicion(
        self,
        posicion,
    ):
        pixmap = self.pixmap()

        if pixmap is None or pixmap.isNull():
            return None

        ancho_pixmap = pixmap.width()

        alto_pixmap = pixmap.height()

        if ancho_pixmap <= 0 or alto_pixmap <= 0:
            return None

        offset_x = (self.width() - ancho_pixmap) / 2

        offset_y = (self.height() - alto_pixmap) / 2

        x_local = posicion.x() - offset_x

        y_local = posicion.y() - offset_y

        # ----------------------------------------------------
        # IGNORAR BANDAS VACÍAS DE KEEP ASPECT RATIO
        # ----------------------------------------------------

        if (
            x_local < 0
            or y_local < 0
            or x_local >= ancho_pixmap
            or y_local >= alto_pixmap
        ):
            return None

        x_normalizado = x_local / ancho_pixmap

        y_normalizado = y_local / alto_pixmap

        return (
            float(x_normalizado),
            float(y_normalizado),
        )

    # ========================================================
    # INTERVALO DE DOBLE CLIC DE WINDOWS
    # ========================================================

    def _intervalo_doble_click(
        self,
    ):
        intervalo = 300

        if sys.platform == "win32":

            try:

                intervalo = int(ctypes.windll.user32.GetDoubleClickTime())

            except Exception:

                pass

        return max(
            150,
            intervalo + 40,
        )

    # ========================================================
    # EMITIR CLIC SIMPLE PENDIENTE
    # ========================================================

    def _emitir_click_pendiente(
        self,
    ):
        if self._click_pendiente is None:
            return

        (
            x_normalizado,
            y_normalizado,
        ) = self._click_pendiente

        self._click_pendiente = None

        self.punto_solicitado.emit(
            x_normalizado,
            y_normalizado,
        )

    # ========================================================
    # CLIC SIMPLE / DERECHO
    # ========================================================

    def mousePressEvent(
        self,
        event,
    ):
        posicion = self._normalizar_posicion(event.position())

        if posicion is None:

            event.ignore()

            return

        (
            x_normalizado,
            y_normalizado,
        ) = posicion

        # ----------------------------------------------------
        # CLIC IZQUIERDO
        #
        # Esperamos unos milisegundos antes de emitirlo
        # para comprobar que no se convierta en doble clic.
        # ----------------------------------------------------

        if event.button() == Qt.LeftButton:

            self._click_pendiente = (
                x_normalizado,
                y_normalizado,
            )

            self._timer_click.start(self._intervalo_doble_click())

            event.accept()

            return

        # ----------------------------------------------------
        # CLIC DERECHO
        # ----------------------------------------------------

        if event.button() == Qt.RightButton:

            self._timer_click.stop()

            self._click_pendiente = None

            self.click_derecho_solicitado.emit(
                x_normalizado,
                y_normalizado,
            )

            event.accept()

            return

        super().mousePressEvent(event)

    # ========================================================
    # DOBLE CLIC
    # ========================================================

    def mouseDoubleClickEvent(
        self,
        event,
    ):
        if event.button() != Qt.LeftButton:

            super().mouseDoubleClickEvent(event)

            return

        posicion = self._normalizar_posicion(event.position())

        if posicion is None:

            event.ignore()

            return

        # ----------------------------------------------------
        # CANCELAR EL CLIC SIMPLE PENDIENTE
        # ----------------------------------------------------

        self._timer_click.stop()

        self._click_pendiente = None

        (
            x_normalizado,
            y_normalizado,
        ) = posicion

        self.doble_click_solicitado.emit(
            x_normalizado,
            y_normalizado,
        )

        event.accept()

    # ========================================================
    # RUEDA / SCROLL
    # ========================================================

    def wheelEvent(
        self,
        event,
    ):
        posicion = self._normalizar_posicion(event.position())

        if posicion is None:

            event.ignore()

            return

        delta = int(event.angleDelta().y())

        if delta == 0:

            event.ignore()

            return

        (
            x_normalizado,
            y_normalizado,
        ) = posicion

        self.scroll_solicitado.emit(
            x_normalizado,
            y_normalizado,
            delta,
        )

        event.accept()


class Panel(QFrame):

    def __init__(self):

        super().__init__()

        self.setObjectName("panel")


class ConflictDialog(QDialog):
    """Diálogo compacto y desplazable para conflictos de horario."""

    def __init__(
        self,
        parent=None,
        titulo="Conflicto de horario",
        contenido="",
    ):
        super().__init__(parent)

        self.setWindowTitle(titulo)
        self.setFixedSize(280, 280)

        principal = QVBoxLayout(self)
        principal.setContentsMargins(10, 10, 10, 10)
        principal.setSpacing(8)

        etiqueta_titulo = QLabel(titulo.upper())
        etiqueta_titulo.setObjectName("tituloDialogo")
        etiqueta_titulo.setWordWrap(True)
        principal.addWidget(etiqueta_titulo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        contenedor = QWidget()
        contenido_layout = QVBoxLayout(contenedor)
        contenido_layout.setContentsMargins(6, 6, 6, 6)

        etiqueta_contenido = QLabel(contenido)
        etiqueta_contenido.setWordWrap(True)
        etiqueta_contenido.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        etiqueta_contenido.setObjectName("textoSecundario")
        contenido_layout.addWidget(etiqueta_contenido)
        contenido_layout.addStretch()

        scroll.setWidget(contenedor)
        principal.addWidget(scroll, 1)

        botones = QDialogButtonBox(QDialogButtonBox.Close)
        boton_cerrar = botones.button(QDialogButtonBox.Close)

        if boton_cerrar is not None:
            boton_cerrar.setText("CERRAR")

        botones.rejected.connect(self.reject)
        principal.addWidget(botones)


# ============================================================
# EDITOR DE TAREAS
# ============================================================


class TaskEditorDialog(QDialog):

    def __init__(
        self, parent=None, tarea=None, validador_conflictos=None, excluir_id=None
    ):

        super().__init__(parent)

        self.tarea = tarea

        self.validador_conflictos = validador_conflictos

        self.excluir_id = excluir_id

        self.setWindowTitle("Configurar tarea")

        self.setMinimumWidth(540)

        self.crear_interfaz()

        if tarea:
            self.cargar_tarea(tarea)

    # ========================================================
    # CREAR INTERFAZ
    # ========================================================

    def crear_interfaz(self):

        principal = QVBoxLayout(self)

        principal.setSpacing(14)

        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        titulo = QLabel("CONFIGURACIÓN DE TAREA")

        titulo.setObjectName("tituloDialogo")

        principal.addWidget(titulo)

        descripcion = QLabel(
            "Define cuándo y cómo debe entrar esta tarea "
            "en la cola de ejecución de BIN."
        )

        descripcion.setWordWrap(True)

        descripcion.setObjectName("textoSecundario")

        principal.addWidget(descripcion)

        # ----------------------------------------------------
        # FORMULARIO
        # ----------------------------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(12)

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        self.nombre = QLineEdit()

        self.nombre.setPlaceholderText("Ej: Publicar contenido de la mañana")

        formulario.addRow("Nombre:", self.nombre)

        # ----------------------------------------------------
        # HORA
        # ----------------------------------------------------

        self.hora = QTimeEdit()

        self.hora.setDisplayFormat("HH:mm")

        self.hora.setTime(QTime(5, 40))

        formulario.addRow("Hora:", self.hora)

        # ----------------------------------------------------
        # REPETICIONES
        # ----------------------------------------------------

        self.veces = QSpinBox()

        self.veces.setRange(1, 99999)

        self.veces.setValue(1)

        formulario.addRow("Veces por ejecución:", self.veces)

        # ----------------------------------------------------
        # INTERVALO
        # ----------------------------------------------------

        intervalo_widget = QWidget()

        intervalo_layout = QHBoxLayout(intervalo_widget)

        intervalo_layout.setContentsMargins(0, 0, 0, 0)

        self.intervalo_valor = QSpinBox()

        self.intervalo_valor.setRange(1, 99999)

        self.intervalo_valor.setValue(24)

        self.intervalo_unidad = QComboBox()

        self.intervalo_unidad.addItems(
            [
                "minutos",
                "horas",
                "días",
            ]
        )

        self.intervalo_unidad.setCurrentText("horas")

        intervalo_layout.addWidget(self.intervalo_valor)

        intervalo_layout.addWidget(self.intervalo_unidad)

        formulario.addRow("Cada:", intervalo_widget)

        # ----------------------------------------------------
        # DURACIÓN ESTIMADA
        # ----------------------------------------------------

        self.duracion = QTimeEdit()

        self.duracion.setDisplayFormat("HH:mm:ss")

        self.duracion.setTime(QTime(0, 0, 0))

        # La duración estimada la calcula BIN.
        # El usuario puede verla, pero no modificarla.
        self.duracion.setReadOnly(True)

        formulario.addRow("Duración estimada:", self.duracion)

        principal.addLayout(formulario)

        # ----------------------------------------------------
        # DÍAS
        # ----------------------------------------------------

        titulo_dias = QLabel("DÍAS DE EJECUCIÓN")

        titulo_dias.setObjectName("tituloPanel")

        principal.addWidget(titulo_dias)

        dias_layout = QHBoxLayout()

        self.check_dias = []

        for indice, nombre in enumerate(DIAS_NOMBRES):

            check = QCheckBox(nombre)

            check.setChecked(True)

            self.check_dias.append(check)

            dias_layout.addWidget(check)

        dias_layout.addStretch()

        principal.addLayout(dias_layout)

        # ----------------------------------------------------
        # AVISO
        # ----------------------------------------------------

        self.aviso = QLabel(
            "BIN comprobará automáticamente si este horario "
            "se solapa con otra tarea antes de guardarlo."
        )

        self.aviso.setWordWrap(True)

        self.aviso.setObjectName("aviso")

        principal.addWidget(self.aviso)

        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)

        boton_guardar = botones.button(QDialogButtonBox.Save)

        boton_guardar.setText("GUARDAR")

        boton_cancelar = botones.button(QDialogButtonBox.Cancel)

        boton_cancelar.setText("CANCELAR")

        botones.accepted.connect(self.validar)

        botones.rejected.connect(self.reject)

        principal.addWidget(botones)

    # ========================================================
    # CARGAR TAREA EXISTENTE
    # ========================================================

    def cargar_tarea(self, tarea):

        self.nombre.setText(tarea.get("nombre", ""))

        self.veces.setValue(tarea.get("veces", 1))

        self.intervalo_valor.setValue(tarea.get("intervalo_valor", 24))

        self.intervalo_unidad.setCurrentText(tarea.get("intervalo_unidad", "horas"))

        hora = QTime.fromString(tarea.get("hora", "05:40"), "HH:mm")

        if hora.isValid():

            self.hora.setTime(hora)

        duracion = QTime.fromString(tarea.get("duracion", "00:10:00"), "HH:mm:ss")

        if duracion.isValid():

            self.duracion.setTime(duracion)

        dias_tarea = tarea.get("dias", [])

        for indice, check in enumerate(self.check_dias):

            check.setChecked(indice in dias_tarea)

    # ========================================================
    # OBTENER DÍAS
    # ========================================================

    def obtener_dias(self):

        dias = []

        for indice, check in enumerate(self.check_dias):

            if check.isChecked():

                dias.append(indice)

        return dias

    # ========================================================
    # OBTENER DATOS
    # ========================================================

    def obtener_datos(self):

        hora = self.hora.time()

        duracion = self.duracion.time()

        return {
            "nombre": self.nombre.text().strip(),
            "hora": hora.toString("HH:mm"),
            "veces": self.veces.value(),
            "intervalo_valor": self.intervalo_valor.value(),
            "intervalo_unidad": self.intervalo_unidad.currentText(),
            "dias": self.obtener_dias(),
            "duracion": duracion.toString("HH:mm:ss"),
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
                self, "Nombre requerido", "La tarea necesita un nombre."
            )

            return

        # ----------------------------------------------------
        # DÍAS
        # ----------------------------------------------------

        dias = self.obtener_dias()

        if not dias:

            QMessageBox.warning(
                self, "Días requeridos", "Selecciona al menos un día de ejecución."
            )

            return

        # ----------------------------------------------------
        # COMPROBAR COLISIONES
        # ----------------------------------------------------

        if self.validador_conflictos:

            candidata = self.obtener_datos()

            conflictos = self.validador_conflictos(
                candidata, excluir_id=self.excluir_id
            )

            if conflictos:

                parent = self.parent()

                if parent is not None and hasattr(
                    parent, "formatear_mensaje_conflictos"
                ):
                    mensaje_conflictos = parent.formatear_mensaje_conflictos(
                        candidata,
                        conflictos,
                    )
                else:
                    nombres = "\n".join(
                        f"• {item.get('tarea', {}).get('nombre', 'Tarea')}"
                        for item in conflictos
                    )

                    mensaje_conflictos = (
                        "BIN detectó una colisión.\n\n"
                        f"{nombres}\n\n"
                        "Modifica la hora o los días y vuelve a pulsar "
                        "GUARDAR."
                    )

                ConflictDialog(
                    self,
                    "Conflicto de horario",
                    mensaje_conflictos,
                ).exec()

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

    def __init__(self, tarea):

        super().__init__()

        self.tarea = tarea

        self.setObjectName("tarjetaTarea")

        self.setMinimumWidth(0)

        self.crear_interfaz()

        self.actualizar_estado()

    # ========================================================
    # CREAR INTERFAZ
    # ========================================================

    def crear_interfaz(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(12, 10, 12, 10)

        layout.setSpacing(8)

        # ----------------------------------------------------
        # CABECERA
        # ----------------------------------------------------

        superior = QHBoxLayout()

        self.numero = QLabel(f"{self.tarea['id']:02}")

        self.numero.setObjectName("numeroTarea")

        self.titulo = QLabel(self.tarea["nombre"])

        self.titulo.setObjectName("tituloTarea")

        self.titulo.setWordWrap(True)

        self.estado = QLabel()

        self.estado.setAlignment(Qt.AlignRight)

        superior.addWidget(self.numero)

        superior.addWidget(self.titulo, 1)

        superior.addWidget(self.estado)

        layout.addLayout(superior)

        # ----------------------------------------------------
        # INFORMACIÓN
        # ----------------------------------------------------

        self.info = QLabel()

        self.info.setObjectName("textoSecundario")

        self.info.setWordWrap(True)

        layout.addWidget(self.info)

        # ----------------------------------------------------
        # ESTADO / PRÓXIMA EJECUCIÓN
        # ----------------------------------------------------

        self.proxima = QLabel()

        self.proxima.setObjectName("proximaTarea")

        self.proxima.setWordWrap(True)

        layout.addWidget(self.proxima)

        # ----------------------------------------------------
        # TIEMPOS
        # ----------------------------------------------------

        tiempos = QHBoxLayout()

        self.duracion = QLabel()

        self.duracion.setObjectName("textoSecundario")

        self.transcurrido = QLabel()

        self.transcurrido.setObjectName("textoSecundario")

        tiempos.addWidget(self.duracion)

        tiempos.addStretch()

        tiempos.addWidget(self.transcurrido)

        layout.addLayout(tiempos)

        # ----------------------------------------------------
        # PROGRESO
        # ----------------------------------------------------

        self.progreso = QProgressBar()

        self.progreso.setRange(0, 100)

        layout.addWidget(self.progreso)

        # ----------------------------------------------------
        # BOTONES PRINCIPALES
        # ----------------------------------------------------

        botones = QHBoxLayout()

        self.boton_ver = QPushButton("VER")

        self.boton_copiar = QPushButton("COPIAR")

        self.boton_pausa = QPushButton()

        botones.addWidget(self.boton_ver)

        botones.addWidget(self.boton_copiar)

        botones.addWidget(self.boton_pausa)

        layout.addLayout(botones)

        # ----------------------------------------------------
        # EJECUTAR AHORA
        # ----------------------------------------------------

        self.boton_ejecutar = QPushButton("▶ EJECUTAR AHORA")

        self.boton_ejecutar.setObjectName("botonEjecutar")

        layout.addWidget(self.boton_ejecutar)

        # ----------------------------------------------------
        # ELIMINAR
        # ----------------------------------------------------

        self.boton_eliminar = QPushButton("ELIMINAR")

        self.boton_eliminar.setObjectName("botonEliminar")

        layout.addWidget(self.boton_eliminar)

        # ----------------------------------------------------
        # EVENTOS
        # ----------------------------------------------------

        self.boton_ver.clicked.connect(
            lambda: self.ver_solicitado.emit(self.tarea["id"])
        )

        self.boton_copiar.clicked.connect(
            lambda: self.copiar_solicitado.emit(self.tarea["id"])
        )

        self.boton_eliminar.clicked.connect(
            lambda: self.eliminar_solicitado.emit(self.tarea["id"])
        )

        self.boton_pausa.clicked.connect(
            lambda: self.pausa_solicitada.emit(self.tarea["id"])
        )

        self.boton_ejecutar.clicked.connect(
            lambda: self.ejecutar_solicitado.emit(self.tarea["id"])
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
        self.estado.setStyleSheet(f"""
            color: {color};
            font-weight: 800;
            font-size: 10px;
            """)

        intervalo = (
            f"{self.tarea.get('intervalo_valor', 1)} "
            f"{self.tarea.get('intervalo_unidad', 'días')}"
        )

        acciones = self.tarea.get("acciones", [])
        texto_acciones = f"{len(acciones)} acción(es)" if acciones else "SIN ACCIONES"

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

        self.duracion.setText(f"Duración: {self.tarea.get('duracion', '00:00:00')}")

        self.transcurrido.setText(
            f"Transcurrido: {self.tarea.get('transcurrido', '00:00:00')}"
        )

        self.progreso.setValue(int(self.tarea.get("progreso", 0)))

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
            and not (estado == "EN PAUSA" and self.tarea.get("current_run_key"))
        )


# ============================================================
# VENTANA PRINCIPAL BIN
# ============================================================


class BIN(QMainWindow):

    evento_mouse_global = Signal(object)
    evento_teclado_global = Signal(object)
    solicitud_detener_grabacion = Signal()

    def __init__(self):

        super().__init__()

        # ====================================================
        # ESTADOS GENERALES
        # ====================================================

        self.grabando = False

        # ====================================================
        # GRABACIÓN GLOBAL DE ENTRADA
        # ====================================================

        self.listener_mouse_global = None
        self.listener_teclado_global = None

        self._mouse_botones_listener = set()
        self.mouse_global_presionados = {}

        self.click_global_pendiente = None

        self.teclas_modificadoras_global = set()
        self.teclas_abajo_global = set()
        self.acciones_teclado_en_curso = {}

        self.win_solo_pendiente = None

        self.timer_click_global = QTimer(self)
        self.timer_click_global.setSingleShot(True)
        self.timer_click_global.timeout.connect(self.confirmar_click_global_pendiente)

        self.evento_mouse_global.connect(self.procesar_evento_mouse_global)

        self.evento_teclado_global.connect(self.procesar_evento_teclado_global)

        # ====================================================
        # BARRA FLOTANTE DE GRABACIÓN
        # ====================================================

        self.barra_grabacion = None
        self.label_barra_grabacion = None
        self.boton_detener_barra = None

        self.solicitud_detener_grabacion.connect(self.detener_grabacion_desde_atajo)

        self.pantalla_completa = False

        # ====================================================
        # DIRECTORIOS
        # ====================================================

        self.directorio_bin = Path(__file__).resolve().parent

        self.directorio_datos = self.directorio_bin / "data"

        self.archivo_tareas = self.directorio_datos / "tareas.json"

        self.directorio_datos.mkdir(parents=True, exist_ok=True)

        # ====================================================
        # TAREAS DE DEMOSTRACIÓN
        # ====================================================

        self.tareas_demo = [
            {
                "id": 1,
                "nombre": "Crear contenido Alfora",
                "estado": "EN PAUSA",
                "hora": "05:00",
                "veces": 30,
                "intervalo_valor": 24,
                "intervalo_unidad": "horas",
                "dias": [0, 1, 2, 3, 4, 5, 6],
                "duracion": "00:18:42",
                "transcurrido": "00:06:31",
                "progreso": 35,
            },
            {
                "id": 2,
                "nombre": "Publicar en redes",
                "estado": "EN ESPERA",
                "hora": "05:40",
                "veces": 1,
                "intervalo_valor": 24,
                "intervalo_unidad": "horas",
                "dias": [0, 1, 2, 3, 4, 5, 6],
                "duracion": "00:10:00",
                "transcurrido": "00:00:00",
                "progreso": 0,
            },
            {
                "id": 3,
                "nombre": "Publicar segunda ronda",
                "estado": "PRÓXIMA",
                "hora": "07:30",
                "veces": 1,
                "intervalo_valor": 24,
                "intervalo_unidad": "horas",
                "dias": [0, 1, 2, 3, 4, 5, 6],
                "duracion": "00:10:00",
                "transcurrido": "00:00:00",
                "progreso": 0,
            },
        ]

        # ====================================================
        # CARGAR TAREAS GUARDADAS
        # ====================================================

        self.tareas = self.cargar_tareas()

        self.normalizar_tareas()

        self.tarjetas = {}

        # ====================================================
        # ESTADO DEL MOTOR / SCHEDULER / RUTINAS
        # ====================================================

        self.tarea_ejecutando_id = None
        self.tarea_seleccionada_id = None

        self.rutina_borrador = []
        self.rutina_borrador_semantica = []
        self.rutina_en_borrador = False
        self.inicio_grabacion = None
        self.duracion_rutina_borrador = 0

        self.ultimo_chat_sistema = ""

        # ====================================================
        # CAPTURA DEL ESCRITORIO
        # ====================================================

        self.frame_actual = None

        self.hilo_captura = None

        self.monitor_captura = 1

        self.fps_captura = 5

        self.geometria_monitor_captura = None

        self.bin_excluido_de_captura = False

        self.punto_estado_visor = None
        self.texto_estado_visor = None
        self.detalle_estado_visor = None

        # ====================================================
        # EJECUTOR FÍSICO SECUENCIAL
        # ====================================================

        self.timer_ejecucion_accion = QTimer(self)
        self.timer_ejecucion_accion.setSingleShot(True)
        self.timer_ejecucion_accion.timeout.connect(self.procesar_timer_ejecucion_real)

        self.plan_ejecucion_actual = []
        self.offsets_ejecucion_actual_ms = []
        self.plan_ejecucion_usa_semantica = False
        self.indice_ejecucion_real = 0
        self.repeticion_ejecucion_real = 1
        self.ejecucion_fisica_activa = False
        self.delay_ejecucion_restante_ms = 0
        self.fase_ejecucion_real = "inactiva"
        self.accion_real_actual = None
        self.resultado_accion_real_actual = None
        self.ejecuciones_reales_completadas = 0
        self.ejecuciones_reales_totales = 0
        self.inicio_repeticion_real_monotonic = None
        self.elapsed_repeticion_base_ms = 0
        self.tarjeta_accion_activa = None

        self.mouse_replay = None
        self.keyboard_replay = None

        # ====================================================
        # SUPERVISOR DE REPLAY / CONTEXTO TOLERANTE
        # ====================================================

        self.ultimo_contexto_replay_valido = None
        self.ultimo_hwnd_replay_valido = None
        self.ultimo_proceso_replay_valido = None
        self.ultimo_resultado_contexto_replay = None
        self.modo_fallback_contexto = False

        self.inicio_espera_supervisor_monotonic = None
        self.espera_supervisor_acumulada_ms = 0
        self.intentos_supervisor = 0
        self.timeout_supervisor_ms = 20_000
        self.intervalo_supervisor_ms = 500
        self.ultima_decision_supervisor = None
        self.ultimo_motivo_supervisor = ""
        self.supervisor_hubo_wait = False

        # Punto de extensión opcional. No requiere credenciales ni
        # dependencia adicional; puede conectarse más adelante.
        self.proveedor_ia_visual = None

        # ====================================================
        # VENTANA
        # ====================================================

        self.setWindowTitle("BIN — Automatizador Inteligente")

        self.resize(1550, 900)

        self.setMinimumSize(1200, 720)

        # ====================================================
        # INICIAR
        # ====================================================

        self.crear_interfaz()

        self.aplicar_estilos()

        # La ventana debe existir antes de que Windows
        # pueda excluirla de las capturas.
        self.excluir_bin_de_captura()

        self.iniciar_captura_pantalla()

        self.iniciar_temporizadores()

        self.actualizar_cabecera_operativa()

        self.actualizar_estado_cabecera_visor(
            "Listo",
            "",
            VERDE,
        )

    # ========================================================
    # CARGAR TAREAS DESDE DISCO
    # ========================================================
    def normalizar_tareas(self):
        for tarea in self.tareas:
            tarea.setdefault(
                "elapsed_seconds",
                duracion_a_segundos(tarea.get("transcurrido", "00:00:00")),
            )
            tarea.setdefault("runtime_started_at", None)
            tarea.setdefault("runtime_base_seconds", tarea.get("elapsed_seconds", 0))
            tarea.setdefault("current_run_key", None)
            tarea.setdefault("last_run_key", None)
            tarea.setdefault("queued_at", None)
            tarea.setdefault("completed_at", None)
            tarea.setdefault("ultima_ejecucion", tarea.get("completed_at"))
            tarea.setdefault("acciones", [])
            tarea.setdefault("acciones_semanticas", [])
            tarea.setdefault("accion_actual_indice", None)
            tarea.setdefault("duracion_origen", "legacy")
            tarea.setdefault("ejecucion_real_indice", 0)
            tarea.setdefault("ejecucion_real_repeticion", 1)
            tarea.setdefault("ejecuciones_reales_completadas", 0)
            tarea.setdefault("delay_ejecucion_restante_ms", 0)
            tarea.setdefault("ejecucion_real_fase", "inactiva")
            tarea.setdefault("elapsed_repeticion_real_ms", 0)
            tarea.setdefault("supervisor_espera_acumulada_ms", 0)
            tarea.setdefault("supervisor_intentos", 0)
            tarea.setdefault("supervisor_ultima_decision", None)
            tarea.setdefault("supervisor_ultimo_motivo", "")
            tarea.setdefault("ultimo_checkpoint", {})
            tarea.setdefault(
                "detalle_estado",
                f"Hora programada: {tarea.get('hora', '--:--')}",
            )

            repeticiones = self.obtener_repeticiones_tarea(tarea)
            tarea["repeticiones_totales"] = repeticiones

            try:
                repeticion_actual = int(
                    tarea.get(
                        "repeticion_actual",
                        0,
                    )
                )
            except Exception:
                repeticion_actual = 0

            tarea["repeticion_actual"] = min(
                repeticiones,
                max(
                    0,
                    repeticion_actual,
                ),
            )

            try:
                tarea["elapsed_seconds"] = max(
                    0,
                    int(
                        tarea.get(
                            "elapsed_seconds",
                            0,
                        )
                    ),
                )
            except Exception:
                tarea["elapsed_seconds"] = 0

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
                tarea["runtime_base_seconds"] = tarea.get("elapsed_seconds", 0)

                if tarea.get("ejecucion_real_fase") == "inactiva":
                    tarea["ejecucion_real_fase"] = "espera_accion"

            # Si existe una ejecución pausada recuperada, derivamos
            # la repetición desde el tiempo total ya guardado.
            if tarea.get("current_run_key"):
                estado_repeticion = self.calcular_estado_repeticiones(
                    tarea,
                    tarea.get("elapsed_seconds", 0),
                )

                if estado_repeticion["duracion_repeticion"] > 0:
                    tarea["repeticion_actual"] = estado_repeticion["repeticion_actual"]

    def cargar_tareas(self):

        if not self.archivo_tareas.exists():

            # Creamos copias independientes.
            tareas = [tarea.copy() for tarea in self.tareas_demo]

            return tareas

        try:

            with open(self.archivo_tareas, "r", encoding="utf-8") as archivo:

                datos = json.load(archivo)

            if isinstance(datos, list):

                return datos

        except Exception as error:

            print("Error cargando tareas:", error)

        return [tarea.copy() for tarea in self.tareas_demo]

    # ========================================================
    # GUARDAR TAREAS EN DISCO
    # ========================================================

    def guardar_tareas_en_disco(self):

        try:

            archivo_temporal = self.archivo_tareas.with_suffix(".tmp")

            with open(archivo_temporal, "w", encoding="utf-8") as archivo:

                json.dump(self.tareas, archivo, ensure_ascii=False, indent=4)

            archivo_temporal.replace(self.archivo_tareas)

        except Exception as error:

            QMessageBox.critical(
                self,
                "Error guardando tareas",
                "BIN no pudo guardar las tareas.\n\n" f"{error}",
            )

    # ========================================================
    # CREAR INTERFAZ PRINCIPAL
    # ========================================================

    def crear_interfaz(self):

        contenedor = QWidget()

        self.setCentralWidget(contenedor)

        principal = QVBoxLayout(contenedor)

        principal.setContentsMargins(10, 10, 10, 10)

        principal.setSpacing(8)

        # ====================================================
        # CABECERA
        # ====================================================

        cabecera = Panel()

        layout_cabecera = QHBoxLayout(cabecera)

        # ----------------------------------------------------
        # IDENTIDAD
        # ----------------------------------------------------

        identidad = QVBoxLayout()

        logo = QLabel("BIN")

        logo.setObjectName("logo")

        subtitulo = QLabel("AUTOMATIZADOR INTELIGENTE")

        subtitulo.setObjectName("textoSecundario")

        identidad.addWidget(logo)

        identidad.addWidget(subtitulo)

        layout_cabecera.addLayout(identidad)

        # ----------------------------------------------------
        # MOSTRAR RUTINA
        # ----------------------------------------------------

        self.boton_grabar = QPushButton("● MOSTRAR RUTINA")

        self.boton_grabar.setObjectName("botonGrabar")

        self.boton_grabar.clicked.connect(self.alternar_grabacion)

        layout_cabecera.addWidget(self.boton_grabar)

        # ----------------------------------------------------
        # PANTALLA COMPLETA
        # ----------------------------------------------------

        self.boton_pantalla_completa = QPushButton("⛶ PANTALLA COMPLETA")

        self.boton_pantalla_completa.setObjectName("botonPantallaCompleta")

        self.boton_pantalla_completa.clicked.connect(self.alternar_pantalla_completa)

        layout_cabecera.addWidget(self.boton_pantalla_completa)

        layout_cabecera.addStretch()

        # ----------------------------------------------------
        # TAREAS GUARDADAS
        # ----------------------------------------------------

        self.contador_tareas = QLabel()

        self.contador_tareas.setObjectName("infoCabecera")

        layout_cabecera.addWidget(self.contador_tareas)

        # ----------------------------------------------------
        # PRÓXIMA TAREA
        # ----------------------------------------------------

        self.proxima_cabecera = QLabel("PRÓXIMA TAREA\n--")

        self.proxima_cabecera.setObjectName("infoCabecera")

        layout_cabecera.addWidget(self.proxima_cabecera)

        # ----------------------------------------------------
        # ESTADO DE BIN
        # ----------------------------------------------------

        self.estado_bin = QLabel("● BIN OPERATIVO")

        self.estado_bin.setObjectName("estado")

        layout_cabecera.addWidget(self.estado_bin)

        # ----------------------------------------------------
        # RELOJ
        # ----------------------------------------------------

        self.hora = QLabel("00:00:00")

        self.hora.setObjectName("hora")

        layout_cabecera.addWidget(self.hora)

        principal.addWidget(cabecera)

        # ====================================================
        # CUERPO
        # ====================================================

        cuerpo = QHBoxLayout()

        cuerpo.setSpacing(8)

        # ====================================================
        # PANEL IZQUIERDO
        # ====================================================

        panel_tareas = self.crear_panel_tareas()

        panel_tareas.setMinimumWidth(360)

        cuerpo.addWidget(panel_tareas, 3)

        # ====================================================
        # CENTRO
        # ====================================================

        centro = QVBoxLayout()

        centro.setSpacing(8)

        # ====================================================
        # VISOR PRINCIPAL
        # ====================================================

        visor = QFrame()

        visor.setObjectName("visorPrincipal")

        visor_layout = QVBoxLayout(visor)

        cabecera_visor = QHBoxLayout()
        cabecera_visor.setContentsMargins(0, 0, 0, 0)
        cabecera_visor.setSpacing(10)

        titulo_visor = QLabel("Visor IA")

        titulo_visor.setObjectName("tituloVisor")

        cabecera_visor.addWidget(titulo_visor)

        cabecera_visor.addStretch()

        estado_visor_layout = QHBoxLayout()
        estado_visor_layout.setContentsMargins(0, 0, 0, 0)
        estado_visor_layout.setSpacing(6)

        self.punto_estado_visor = QLabel("●")
        self.punto_estado_visor.setStyleSheet(f"""
            color: {VERDE};
            font-size: 16px;
            font-weight: 900;
            border: none;
            background: transparent;
            """)

        self.texto_estado_visor = QLabel("Listo")
        self.texto_estado_visor.setStyleSheet(f"""
            color: {TEXTO};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
            """)

        self.detalle_estado_visor = QLabel("")
        self.detalle_estado_visor.setStyleSheet(f"""
            color: {TEXTO_SECUNDARIO};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            """)

        estado_visor_layout.addWidget(self.punto_estado_visor)
        estado_visor_layout.addWidget(self.texto_estado_visor)
        estado_visor_layout.addWidget(self.detalle_estado_visor)

        cabecera_visor.addLayout(estado_visor_layout)

        visor_layout.addLayout(cabecera_visor)

        pantalla = QFrame()

        pantalla.setObjectName("pantalla")

        pantalla_layout = QVBoxLayout(pantalla)

        pantalla_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        pantalla_layout.setSpacing(6)

        # ----------------------------------------------------
        # IMAGEN REAL DEL ESCRITORIO
        # ----------------------------------------------------
        self.visor_imagen = VisorInteractivo(self)

        self.visor_imagen.setText("INICIANDO CAPTURA DEL ESCRITORIO...")

        self.visor_imagen.setObjectName("visorImagen")

        self.visor_imagen.setAlignment(Qt.AlignCenter)

        self.visor_imagen.setMinimumSize(
            320,
            180,
        )

        self.visor_imagen.setScaledContents(False)

        self.visor_imagen.punto_solicitado.connect(self.mover_cursor_desde_visor)

        self.visor_imagen.doble_click_solicitado.connect(self.doble_click_desde_visor)

        self.visor_imagen.click_derecho_solicitado.connect(
            self.click_derecho_desde_visor
        )

        self.visor_imagen.scroll_solicitado.connect(self.scroll_desde_visor)

        pantalla_layout.addWidget(
            self.visor_imagen,
            1,
        )

        # ----------------------------------------------------
        # MENSAJE / ESTADO DEL VISOR
        # ----------------------------------------------------
        #
        # Conservamos self.mensaje_visor porque el motor
        # actual ya lo utiliza para informar qué está haciendo.
        #
        # La imagen y los mensajes quedan separados.
        # ----------------------------------------------------

        self.mensaje_visor = QLabel("BIN preparando visión...")

        self.mensaje_visor.setAlignment(Qt.AlignCenter)

        self.mensaje_visor.setWordWrap(True)

        self.mensaje_visor.setMaximumHeight(70)

        self.mensaje_visor.setObjectName("mensajeVisor")

        pantalla_layout.addWidget(self.mensaje_visor)
        self.mensaje_visor.hide()

        visor_layout.addWidget(pantalla, 1)

        centro.addWidget(visor, 8)

        # ====================================================
        # RENDIMIENTO DEL PC
        # ====================================================

        rendimiento = Panel()

        rendimiento_layout = QHBoxLayout(rendimiento)

        self.cpu_label = QLabel("CPU   0 %")

        self.ram_label = QLabel("RAM   0 %")

        self.gpu_label = QLabel("GPU   PENDIENTE")

        self.temp_label = QLabel("TEMP   PENDIENTE")

        for etiqueta in [
            self.cpu_label,
            self.ram_label,
            self.gpu_label,
            self.temp_label,
        ]:

            etiqueta.setObjectName("monitor")

            rendimiento_layout.addWidget(etiqueta)

        centro.addWidget(rendimiento, 1)

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
        self.entrada_chat.setPlaceholderText("Escribe una indicación para BIN...")

        self.boton_enviar_chat = QPushButton("ENVIAR")

        self.boton_enviar_chat.clicked.connect(self.procesar_chat)
        self.entrada_chat.returnPressed.connect(self.procesar_chat)

        entrada_chat_layout.addWidget(self.entrada_chat, 1)
        entrada_chat_layout.addWidget(self.boton_enviar_chat)

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

        self.titulo_tarea_acciones = QLabel("NINGUNA TAREA SELECCIONADA")
        self.titulo_tarea_acciones.setWordWrap(True)
        self.titulo_tarea_acciones.setObjectName("tituloTarea")
        acciones_layout.addWidget(self.titulo_tarea_acciones)

        self.scroll_acciones = QScrollArea()
        self.scroll_acciones.setWidgetResizable(True)
        self.scroll_acciones.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.contenedor_acciones = QWidget()
        self.layout_acciones = QVBoxLayout(self.contenedor_acciones)
        self.layout_acciones.setAlignment(Qt.AlignTop)
        self.layout_acciones.setSpacing(6)

        self.scroll_acciones.setWidget(self.contenedor_acciones)
        acciones_layout.addWidget(self.scroll_acciones, 1)

        self.boton_agregar_accion = QPushButton("+ AÑADIR ACCIÓN")
        self.boton_agregar_accion.clicked.connect(self.agregar_accion_manual)
        acciones_layout.addWidget(self.boton_agregar_accion)

        self.boton_guardar_rutina = QPushButton("GUARDAR TAREA")
        self.boton_guardar_rutina.setObjectName("botonPrincipal")
        self.boton_guardar_rutina.clicked.connect(self.guardar_rutina_como_tarea)
        self.boton_guardar_rutina.setEnabled(False)

        acciones_layout.addWidget(self.boton_guardar_rutina)

        cuerpo.addWidget(acciones)

        principal.addLayout(cuerpo, 1)

        self.refrescar_panel_acciones()

    # ========================================================
    # ESTADO COMPACTO DEL VISOR IA
    # ========================================================

    def actualizar_estado_cabecera_visor(
        self,
        texto="Listo",
        detalle="",
        color=None,
    ):
        if color is None:
            color = VERDE

        if self.punto_estado_visor is not None:
            self.punto_estado_visor.setStyleSheet(f"""
                color: {color};
                font-size: 16px;
                font-weight: 900;
                border: none;
                background: transparent;
                """)

        if self.texto_estado_visor is not None:
            self.texto_estado_visor.setText(texto)

        if self.detalle_estado_visor is not None:
            self.detalle_estado_visor.setText(detalle)

    # ========================================================
    # CREAR PANEL DE TAREAS
    # ========================================================

    def crear_panel_tareas(self):

        self.panel_tareas = Panel()

        layout = QVBoxLayout(self.panel_tareas)

        # ----------------------------------------------------
        # CABECERA
        # ----------------------------------------------------

        cabecera = QHBoxLayout()

        titulo = QLabel("LISTA DE TAREAS")

        titulo.setObjectName("tituloPanel")

        self.boton_nueva_tarea = QPushButton("+ NUEVA")

        self.boton_nueva_tarea.clicked.connect(self.crear_nueva_tarea)

        cabecera.addWidget(titulo)

        cabecera.addStretch()

        cabecera.addWidget(self.boton_nueva_tarea)

        layout.addLayout(cabecera)

        # ----------------------------------------------------
        # ÁREA DE SCROLL
        # ----------------------------------------------------

        self.scroll_tareas = QScrollArea()

        self.scroll_tareas.setWidgetResizable(True)

        self.scroll_tareas.setObjectName("scrollTareas")

        # ----------------------------------------------------
        # NUNCA SCROLL HORIZONTAL
        # ----------------------------------------------------

        self.scroll_tareas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ----------------------------------------------------
        # SCROLL VERTICAL SOLO SI HACE FALTA
        # ----------------------------------------------------

        self.scroll_tareas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.contenedor_tareas = QWidget()

        self.layout_tareas = QVBoxLayout(self.contenedor_tareas)

        self.layout_tareas.setAlignment(Qt.AlignTop)

        self.layout_tareas.setSpacing(10)

        self.layout_tareas.setContentsMargins(2, 2, 4, 2)

        self.scroll_tareas.setWidget(self.contenedor_tareas)

        layout.addWidget(self.scroll_tareas)

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

            tarjeta.ver_solicitado.connect(self.editar_tarea)
            tarjeta.copiar_solicitado.connect(self.copiar_tarea)
            tarjeta.eliminar_solicitado.connect(self.eliminar_tarea)
            tarjeta.pausa_solicitada.connect(self.alternar_pausa_tarea)
            tarjeta.ejecutar_solicitado.connect(self.ejecutar_ahora)
            tarjeta.seleccion_solicitada.connect(self.seleccionar_tarea)

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

    def obtener_tarea(self, tarea_id):

        for tarea in self.tareas:

            if tarea.get("id") == tarea_id:

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

        nuevo_id = (
            max(
                [tarea.get("id", 0) for tarea in self.tareas],
                default=0,
            )
            + 1
        )

        repeticiones = max(
            1,
            int(
                datos.get(
                    "veces",
                    1,
                )
            ),
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
            "acciones": [],
            "acciones_semanticas": [],
            "accion_actual_indice": None,
            "repeticion_actual": 0,
            "repeticiones_totales": repeticiones,
            "ejecucion_real_indice": 0,
            "ejecucion_real_repeticion": 1,
            "ejecuciones_reales_completadas": 0,
            "delay_ejecucion_restante_ms": 0,
            "ejecucion_real_fase": "inactiva",
            "elapsed_repeticion_real_ms": 0,
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

        repeticiones = self.obtener_repeticiones_tarea(tarea)

        tarea["repeticiones_totales"] = repeticiones
        tarea["repeticion_actual"] = min(
            repeticiones,
            max(
                0,
                int(
                    tarea.get(
                        "repeticion_actual",
                        0,
                    )
                ),
            ),
        )

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()

    # ========================================================
    # CREAR INTERVALOS SEMANALES
    # ========================================================

    def crear_intervalos_semanales(self, tarea):
        """
        Cada semana tiene:
        7 días * 86400 segundos.

        Esta función convierte una tarea en intervalos
        absolutos dentro de una semana.

        También permite detectar tareas que atraviesan
        la medianoche.

        La duración reservada corresponde al trabajo completo:
        duración individual × repeticiones.
        """

        segundos_dia = 24 * 60 * 60

        segundos_semana = 7 * segundos_dia

        inicio_dia = hora_a_segundos(tarea["hora"])

        duracion_total = self.obtener_duracion_total_tarea(tarea)

        intervalos = []

        for dia in tarea.get("dias", []):

            inicio = dia * segundos_dia + inicio_dia

            fin = inicio + duracion_total

            intervalos.append((inicio, fin))

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

            intervalos.append((inicio - segundos_semana, fin - segundos_semana))

            intervalos.append((inicio + segundos_semana, fin + segundos_semana))

        return intervalos

    # ========================================================
    # DETECTAR COLISIONES
    # ========================================================

    def formatear_segundo_semanal(
        self,
        segundo,
    ):
        segundos_dia = 24 * 60 * 60
        segundos_semana = 7 * segundos_dia

        try:
            segundo = int(segundo)
        except Exception:
            segundo = 0

        normalizado = segundo % segundos_semana
        dia = normalizado // segundos_dia
        segundos_del_dia = normalizado % segundos_dia
        hora = segundos_del_dia // 3600
        minuto = (segundos_del_dia % 3600) // 60

        nombres = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]

        return f"{nombres[dia]} {hora:02}:{minuto:02}"

    def formatear_intervalo_semanal(
        self,
        inicio,
        fin,
    ):
        segundos_dia = 24 * 60 * 60
        segundos_semana = 7 * segundos_dia

        try:
            inicio = int(inicio)
            fin = int(fin)
        except Exception:
            return "--"

        inicio_normalizado = inicio % segundos_semana
        fin_normalizado = fin % segundos_semana

        dia_inicio = inicio_normalizado // segundos_dia
        dia_fin = fin_normalizado // segundos_dia

        texto_inicio = self.formatear_segundo_semanal(inicio)

        segundos_fin_dia = fin_normalizado % segundos_dia
        hora_fin = segundos_fin_dia // 3600
        minuto_fin = (segundos_fin_dia % 3600) // 60

        if (
            dia_inicio == dia_fin
            and fin > inicio
            and fin - inicio < segundos_dia
            and fin_normalizado >= inicio_normalizado
        ):
            return f"{texto_inicio} - {hora_fin:02}:{minuto_fin:02}"

        texto_fin = self.formatear_segundo_semanal(fin)
        return f"{texto_inicio} - {texto_fin}"

    def formatear_mensaje_conflictos(
        self,
        candidata,
        conflictos,
    ):
        bloques = ["BIN detectó una colisión."]

        duracion_candidata = self.obtener_duracion_repeticion(candidata)
        repeticiones_candidata = self.obtener_repeticiones_tarea(candidata)

        for indice, conflicto in enumerate(conflictos, start=1):
            tarea_existente = conflicto.get("tarea", {})

            duracion_existente = self.obtener_duracion_repeticion(tarea_existente)
            repeticiones_existente = self.obtener_repeticiones_tarea(tarea_existente)

            horario_candidata = self.formatear_intervalo_semanal(
                conflicto.get("inicio_candidata", 0),
                conflicto.get("fin_candidata", 0),
            )
            horario_existente = self.formatear_intervalo_semanal(
                conflicto.get("inicio_existente", 0),
                conflicto.get("fin_existente", 0),
            )
            horario_solapamiento = self.formatear_intervalo_semanal(
                conflicto.get("inicio_solapamiento", 0),
                conflicto.get("fin_solapamiento", 0),
            )

            bloques.append(
                f"CONFLICTO {indice}\n"
                "\n"
                "Tarea solicitada:\n"
                f"{candidata.get('nombre', 'Tarea')}\n"
                "\n"
                "Horario:\n"
                f"{horario_candidata}\n"
                "\n"
                "Repeticiones:\n"
                f"{repeticiones_candidata} × "
                f"{segundos_a_hms(duracion_candidata)}\n"
                "\n"
                "Colisiona con:\n"
                f"{tarea_existente.get('nombre', 'Tarea')}\n"
                "\n"
                "Horario:\n"
                f"{horario_existente}\n"
                "\n"
                "Repeticiones:\n"
                f"{repeticiones_existente} × "
                f"{segundos_a_hms(duracion_existente)}\n"
                "\n"
                "Solapamiento:\n"
                f"{horario_solapamiento}"
            )

        bloques.append(
            "BIN solamente puede ejecutar una tarea a la vez.\n"
            "Modifica la hora o los días antes de continuar."
        )

        return "\n\n".join(bloques)

    def buscar_conflictos(self, candidata, excluir_id=None):

        conflictos = []

        segundos_semana = 7 * 24 * 60 * 60

        intervalos_candidata = self.crear_intervalos_semanales(candidata)

        claves_vistas = set()

        for tarea in self.tareas:

            # ------------------------------------------------
            # IGNORAR LA MISMA TAREA AL EDITARLA
            # ------------------------------------------------

            if excluir_id is not None:

                if tarea.get("id") == excluir_id:

                    continue

            # ------------------------------------------------
            # UNA TAREA DETENIDA NO RESERVA HORARIO
            # ------------------------------------------------

            if tarea.get("estado") == "DETENIDA":

                continue

            intervalos_existente = self.crear_intervalos_semanales(tarea)

            for inicio_candidata, fin_candidata in intervalos_candidata:

                for inicio_existente, fin_existente in intervalos_existente:

                    hay_solapamiento = (
                        inicio_candidata < fin_existente
                        and inicio_existente < fin_candidata
                    )

                    if not hay_solapamiento:
                        continue

                    inicio_solapamiento = max(
                        inicio_candidata,
                        inicio_existente,
                    )
                    fin_solapamiento = min(
                        fin_candidata,
                        fin_existente,
                    )

                    # Los intervalos ± semana son soporte técnico.
                    # Llevamos cada solapamiento a una semana canónica
                    # para no devolver el mismo conflicto varias veces.
                    desplazamiento = (
                        inicio_solapamiento // segundos_semana
                    ) * segundos_semana

                    inicio_canonico = inicio_solapamiento - desplazamiento
                    fin_canonico = fin_solapamiento - desplazamiento

                    clave = (
                        tarea.get("id"),
                        inicio_canonico,
                        fin_canonico,
                    )

                    if clave in claves_vistas:
                        continue

                    claves_vistas.add(clave)

                    conflictos.append(
                        {
                            "tarea": tarea,
                            "inicio_candidata": (inicio_candidata - desplazamiento),
                            "fin_candidata": (fin_candidata - desplazamiento),
                            "inicio_existente": (inicio_existente - desplazamiento),
                            "fin_existente": (fin_existente - desplazamiento),
                            "inicio_solapamiento": inicio_canonico,
                            "fin_solapamiento": fin_canonico,
                        }
                    )

        conflictos.sort(
            key=lambda item: (
                item.get("inicio_solapamiento", 0) % segundos_semana,
                str(item.get("tarea", {}).get("nombre", "")).lower(),
            )
        )

        return conflictos

    # ========================================================
    # COPIAR TAREA
    # ========================================================

    def copiar_tarea(self, tarea_id):
        original = self.obtener_tarea(tarea_id)

        if not original:
            return

        nuevo_id = (
            max(
                [tarea.get("id", 0) for tarea in self.tareas],
                default=0,
            )
            + 1
        )

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
        copia["repeticion_actual"] = 0
        copia["repeticiones_totales"] = self.obtener_repeticiones_tarea(copia)
        copia["ejecucion_real_indice"] = 0
        copia["ejecucion_real_repeticion"] = 1
        copia["ejecuciones_reales_completadas"] = 0
        copia["delay_ejecucion_restante_ms"] = 0
        copia["ejecucion_real_fase"] = "inactiva"
        copia["elapsed_repeticion_real_ms"] = 0
        copia.setdefault("acciones_semanticas", [])
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

        self.tareas = [item for item in self.tareas if item.get("id") != tarea_id]

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
            self.mensaje_chat.setText(f"BIN: {mensaje}")

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

        tarea = self.obtener_tarea(self.tarea_seleccionada_id)

        if not tarea:
            self.actualizar_chat_bin("La tarea seleccionada ya no existe.")
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

        tarea = self.obtener_tarea(self.tarea_seleccionada_id)

        if not tarea:
            return None

        return tarea.setdefault("acciones", [])

    def refrescar_panel_acciones(self):
        if not hasattr(self, "layout_acciones"):
            return

        self.tarjeta_accion_activa = None

        while self.layout_acciones.count():
            item = self.layout_acciones.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        acciones = self.obtener_acciones_panel_actual()

        tarea_panel = None

        if self.rutina_en_borrador:
            self.titulo_tarea_acciones.setText("RUTINA NUEVA")
            self.boton_agregar_accion.setEnabled(not self.grabando)
            self.boton_guardar_rutina.setText("GUARDAR TAREA")
            self.boton_guardar_rutina.setEnabled(
                not self.grabando
                and self.inicio_grabacion is None
                and self.duracion_rutina_borrador > 0
            )

            if self.grabando:
                aviso = QLabel(
                    "BIN está observando Windows.\n\n"
                    "Usa mouse y teclado normalmente.\n"
                    "Las acciones ocurrirán realmente "
                    "y BIN las registrará.\n\n"
                    "F12 = detener grabación."
                )
                aviso.setWordWrap(True)
                aviso.setObjectName("textoSecundario")
                self.layout_acciones.addWidget(aviso)

        elif self.tarea_seleccionada_id is not None:
            tarea_panel = self.obtener_tarea(self.tarea_seleccionada_id)

            if tarea_panel:
                self.titulo_tarea_acciones.setText(tarea_panel.get("nombre", "TAREA"))

            self.boton_agregar_accion.setEnabled(
                not bool(tarea_panel and tarea_panel.get("estado") == "EJECUTANDO")
            )
            self.boton_guardar_rutina.setText("CAMBIOS GUARDADOS")
            self.boton_guardar_rutina.setEnabled(False)

        else:
            self.titulo_tarea_acciones.setText("NINGUNA TAREA SELECCIONADA")
            self.boton_agregar_accion.setEnabled(False)
            self.boton_guardar_rutina.setText("GUARDAR TAREA")
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
                "Pulsa MOSTRAR RUTINA para enseñarle "
                "una demostración real a BIN "
                "o añade acciones manualmente."
            )
            aviso.setWordWrap(True)
            aviso.setAlignment(Qt.AlignCenter)
            aviso.setObjectName("textoSecundario")
            self.layout_acciones.addWidget(aviso)
            return

        indice_activo = None

        if tarea_panel and tarea_panel.get("estado") == "EJECUTANDO":
            indice_activo = tarea_panel.get("accion_actual_indice")

        for indice, accion in enumerate(acciones):
            tarjeta = QFrame()
            tarjeta.setObjectName("tarjetaTarea")

            activa = indice_activo is not None and indice == indice_activo

            tarjeta.setProperty(
                "accionActiva",
                "true" if activa else "false",
            )

            layout = QVBoxLayout(tarjeta)
            layout.setContentsMargins(7, 6, 7, 6)
            layout.setSpacing(5)

            descripcion = QLabel(
                f"{indice + 1:02}. " f"{accion.get('descripcion', 'Acción')}"
            )
            descripcion.setWordWrap(True)

            if activa:
                descripcion.setText("▶ " + descripcion.text())
                self.tarjeta_accion_activa = tarjeta

            botones = QHBoxLayout()

            subir = QPushButton("↑")
            bajar = QPushButton("↓")
            editar = QPushButton("EDITAR")
            eliminar = QPushButton("×")

            bloquear_edicion = bool(
                tarea_panel and tarea_panel.get("estado") == "EJECUTANDO"
            )

            subir.setEnabled(indice > 0 and not bloquear_edicion)
            bajar.setEnabled(indice < len(acciones) - 1 and not bloquear_edicion)
            editar.setEnabled(not bloquear_edicion)
            eliminar.setEnabled(not bloquear_edicion)

            subir.clicked.connect(
                lambda checked=False, i=indice: self.mover_accion(i, -1)
            )
            bajar.clicked.connect(
                lambda checked=False, i=indice: self.mover_accion(i, 1)
            )
            editar.clicked.connect(
                lambda checked=False, i=indice: self.editar_accion_manual(i)
            )
            eliminar.clicked.connect(
                lambda checked=False, i=indice: self.eliminar_accion_manual(i)
            )

            botones.addWidget(subir)
            botones.addWidget(bajar)
            botones.addWidget(editar)
            botones.addWidget(eliminar)

            layout.addWidget(descripcion)
            layout.addLayout(botones)

            self.layout_acciones.addWidget(tarjeta)

        if (
            tarea_panel
            and tarea_panel.get("estado") == "EJECUTANDO"
            and self.tarjeta_accion_activa is not None
            and hasattr(self, "scroll_acciones")
        ):
            tarjeta_activa = self.tarjeta_accion_activa

            QTimer.singleShot(
                0,
                lambda tarjeta=tarjeta_activa: self.scroll_acciones.ensureWidgetVisible(
                    tarjeta,
                    8,
                    24,
                ),
            )

    def agregar_accion_manual(self):
        acciones = self.obtener_acciones_panel_actual()

        if acciones is None:
            QMessageBox.information(
                self,
                "Selecciona una tarea",
                "Primero selecciona una tarea o inicia " "MOSTRAR RUTINA.",
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

        siguiente_id = (
            max(
                [accion.get("id", 0) for accion in acciones],
                default=0,
            )
            + 1
        )

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

        if acciones is None or indice < 0 or indice >= len(acciones):
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

        if acciones is None or indice < 0 or indice >= len(acciones):
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
            self.rutina_borrador_semantica = self.interpretar_acciones_semanticas(
                self.rutina_borrador
            )
            self.refrescar_panel_acciones()
            return

        if self.tarea_seleccionada_id is None:
            return

        tarea = self.obtener_tarea(self.tarea_seleccionada_id)

        if not tarea:
            return

        self.recalcular_duracion_desde_acciones(tarea)

        tarea["acciones_semanticas"] = self.interpretar_acciones_semanticas(
            tarea.get(
                "acciones",
                [],
            )
        )

        if tarea.get("acciones"):
            if tarea.get("estado") == "REQUIERE CONFIGURACIÓN":
                tarea["estado"] = "EN ESPERA"

            tarea["detalle_estado"] = (
                f"{len(tarea['acciones'])} acción(es) configurada(s)"
            )
        else:
            tarea["detalle_estado"] = "SIN ACCIONES · Duración sin calcular"

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

        tarea["duracion"] = segundos_a_hms(segundos)
        tarea["duracion_origen"] = "estimada_acciones"

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

        nuevo_id = (
            max(
                [tarea.get("id", 0) for tarea in self.tareas],
                default=0,
            )
            + 1
        )

        acciones = json.loads(json.dumps(self.rutina_borrador))

        acciones_semanticas = json.loads(
            json.dumps(
                self.rutina_borrador_semantica
                or self.interpretar_acciones_semanticas(acciones)
            )
        )

        repeticiones = max(
            1,
            int(
                datos.get(
                    "veces",
                    1,
                )
            ),
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
            "acciones_semanticas": acciones_semanticas,
            "accion_actual_indice": None,
            "repeticion_actual": 0,
            "repeticiones_totales": repeticiones,
            "ejecucion_real_indice": 0,
            "ejecucion_real_repeticion": 1,
            "ejecuciones_reales_completadas": 0,
            "delay_ejecucion_restante_ms": 0,
            "ejecucion_real_fase": "inactiva",
            "elapsed_repeticion_real_ms": 0,
            "duracion_origen": "grabacion",
            "detalle_estado": (
                f"{len(acciones)} acción(es) · "
                "Duración calculada desde la demostración"
            ),
        }

        self.tareas.append(nueva)

        self.rutina_borrador = []
        self.rutina_borrador_semantica = []
        self.rutina_en_borrador = False
        self.duracion_rutina_borrador = 0
        self.inicio_grabacion = None
        self.tarea_seleccionada_id = nuevo_id

        self.guardar_tareas_en_disco()
        self.refrescar_lista_tareas()

        self.actualizar_chat_bin(f"Guardé la rutina como '{nueva['nombre']}'.")

    # ========================================================
    # MOTOR DE EJECUCIÓN / COLA / SCHEDULER
    # ========================================================

    def obtener_tarea_ejecutando(self):
        if self.tarea_ejecutando_id is None:
            return None

        return self.obtener_tarea(self.tarea_ejecutando_id)

    def obtener_duracion_repeticion(self, tarea):
        """
        Devuelve la duración, en segundos, de UNA sola repetición.

        tarea["duracion"] conserva siempre este significado.
        """
        duracion = duracion_a_segundos(
            tarea.get(
                "duracion",
                "00:00:00",
            )
        )

        if duracion > 0:
            return duracion

        acciones = tarea.get(
            "acciones",
            [],
        )

        if acciones:
            # Conservamos la estimación actual, pero siempre como
            # duración individual de una sola repetición.
            duracion = max(
                5,
                len(acciones) * 5,
            )

            tarea["duracion"] = segundos_a_hms(duracion)
            tarea["duracion_origen"] = "estimada_acciones"

            return duracion

        return 0

    def obtener_repeticiones_tarea(self, tarea):
        try:
            repeticiones = int(
                tarea.get(
                    "veces",
                    1,
                )
            )
        except Exception:
            repeticiones = 1

        return max(
            1,
            repeticiones,
        )

    def obtener_duracion_total_tarea(self, tarea):
        duracion_repeticion = self.obtener_duracion_repeticion(tarea)

        if duracion_repeticion <= 0:
            return 0

        repeticiones = self.obtener_repeticiones_tarea(tarea)

        return duracion_repeticion * repeticiones

    def calcular_estado_repeticiones(
        self,
        tarea,
        transcurrido_total,
    ):
        duracion_repeticion = self.obtener_duracion_repeticion(tarea)

        repeticiones = self.obtener_repeticiones_tarea(tarea)

        duracion_total = duracion_repeticion * repeticiones

        if duracion_repeticion <= 0:
            return {
                "duracion_repeticion": 0,
                "repeticiones": repeticiones,
                "duracion_total": 0,
                "transcurrido_total": 0,
                "repeticion_actual": 0,
                "transcurrido_repeticion": 0,
            }

        try:
            transcurrido_total = int(transcurrido_total)
        except Exception:
            transcurrido_total = 0

        transcurrido_total = min(
            duracion_total,
            max(
                0,
                transcurrido_total,
            ),
        )

        if transcurrido_total >= duracion_total:
            repeticion_actual = repeticiones
            transcurrido_repeticion = duracion_repeticion
        else:
            indice_repeticion = transcurrido_total // duracion_repeticion

            repeticion_actual = min(
                repeticiones,
                indice_repeticion + 1,
            )

            transcurrido_repeticion = transcurrido_total % duracion_repeticion

        return {
            "duracion_repeticion": duracion_repeticion,
            "repeticiones": repeticiones,
            "duracion_total": duracion_total,
            "transcurrido_total": transcurrido_total,
            "repeticion_actual": repeticion_actual,
            "transcurrido_repeticion": transcurrido_repeticion,
        }

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
            hora, minuto = [int(valor) for valor in tarea.get("hora", "").split(":")]
        except Exception:
            return None

        if ahora.hour != hora or ahora.minute != minuto:
            return None

        return "sched-" + ahora.strftime("%Y%m%d-") + f"{hora:02}{minuto:02}"

    def ejecutar_ahora(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        tarea_actual = self.obtener_tarea_ejecutando()

        if tarea_actual:
            mensaje = f"La tarea '{tarea_actual['nombre']}' " "está en ejecución ahora."

            QMessageBox.information(
                self,
                "BIN está ocupado",
                mensaje,
            )

            self.actualizar_chat_bin(mensaje)
            return

        if tarea.get("estado") == "EN PAUSA" and tarea.get("current_run_key"):
            self.continuar_ejecucion(tarea)
            return

        duracion_total = self.obtener_duracion_total_tarea(tarea)

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
            tarea["estado"] = "REQUIERE CONFIGURACIÓN"
            tarea["detalle_estado"] = "Añade acciones antes de ejecutar"
            self.guardar_tareas_en_disco()
            self.actualizar_tarjeta_tarea(tarea["id"])
            return

        ahora = datetime.now()

        run_key = self.clave_programada_para_ahora(
            tarea,
            ahora,
        )

        if run_key is None:
            run_key = "manual-" + ahora.strftime("%Y%m%d-%H%M%S")

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
        tarea["queued_at"] = datetime.now().isoformat()
        tarea["runtime_started_at"] = None
        tarea["detalle_estado"] = "Esperando a que termine la tarea actual"

        self.guardar_tareas_en_disco()
        self.actualizar_tarjeta_tarea(tarea["id"])

        actual = self.obtener_tarea_ejecutando()

        if actual:
            self.actualizar_chat_bin(
                f"'{tarea['nombre']}' quedó en cola porque "
                f"'{actual['nombre']}' está en ejecución."
            )

    # ========================================================
    # EJECUTOR FÍSICO REAL
    # ========================================================

    def volver_panel_acciones_arriba(self):
        if not hasattr(self, "scroll_acciones"):
            return

        barra = self.scroll_acciones.verticalScrollBar()

        if barra is not None:
            barra.setValue(barra.minimum())

    def obtener_plan_ejecucion(
        self,
        tarea,
    ):
        semanticas = tarea.get("acciones_semanticas") or []

        if semanticas:
            return semanticas

        return (
            tarea.get(
                "acciones",
                [],
            )
            or []
        )

    def obtener_timestamp_accion_plan(
        self,
        tarea,
        accion,
        usa_semantica,
    ):
        candidatos = []

        if usa_semantica:
            ids_origen = accion.get("acciones_origen") or []

            for accion_origen in tarea.get(
                "acciones",
                [],
            ):
                if accion_origen.get("id") in ids_origen:
                    marca = accion_origen.get("capturado_en")

                    if marca:
                        candidatos.append(marca)
        else:
            marca = accion.get("capturado_en")

            if marca:
                candidatos.append(marca)

        fechas = []

        for marca in candidatos:
            try:
                fechas.append(datetime.fromisoformat(str(marca)))
            except Exception:
                continue

        if not fechas:
            return None

        return min(fechas)

    def calcular_offsets_plan_ejecucion(
        self,
        tarea,
        plan,
        usa_semantica,
    ):
        cantidad = len(plan)

        if cantidad <= 0:
            return []

        duracion_ms = max(
            1,
            self.obtener_duracion_repeticion(tarea) * 1000,
        )

        marcas = [
            self.obtener_timestamp_accion_plan(
                tarea,
                accion,
                usa_semantica,
            )
            for accion in plan
        ]

        if all(marca is not None for marca in marcas):
            inicio = marcas[0]
            offsets = []
            anterior = 0

            for marca in marcas:
                offset = int(
                    max(
                        0.0,
                        (marca - inicio).total_seconds() * 1000,
                    )
                )

                offset = min(
                    duracion_ms,
                    max(
                        anterior,
                        offset,
                    ),
                )

                offsets.append(offset)
                anterior = offset

            return offsets

        return [
            int(
                (indice * duracion_ms)
                / max(
                    1,
                    cantidad,
                )
            )
            for indice in range(cantidad)
        ]

    def indice_panel_para_accion_real(
        self,
        tarea,
        accion,
        usa_semantica,
    ):
        acciones_panel = tarea.get(
            "acciones",
            [],
        )

        if not acciones_panel:
            return None

        if not usa_semantica:
            identificador = accion.get("id")

            for indice, original in enumerate(acciones_panel):
                if original.get("id") == identificador:
                    return indice

            return None

        ids_origen = accion.get("acciones_origen") or []

        for identificador in ids_origen:
            for indice, original in enumerate(acciones_panel):
                if original.get("id") == identificador:
                    return indice

        return None

    def asegurar_controladores_replay(self):
        if pynput_mouse is None or pynput_keyboard is None:
            return False

        try:
            if self.mouse_replay is None:
                self.mouse_replay = pynput_mouse.Controller()

            if self.keyboard_replay is None:
                self.keyboard_replay = pynput_keyboard.Controller()

            return True

        except Exception as error:
            self.actualizar_chat_bin(
                "No pude preparar los controladores "
                "de reproducción física.\n\n"
                f"{error}"
            )

            return False

    def tecla_replay_desde_nombre(
        self,
        tecla,
        caracter=None,
    ):
        if pynput_keyboard is None:
            return None

        if caracter is not None:

            texto = str(caracter)

            if texto:
                return texto

        nombre = str(tecla or "").strip().lower()

        alias = {
            "return": "enter",
            "escape": "esc",
            "del": "delete",
            "pgup": "page_up",
            "pgdn": "page_down",
            "pageup": "page_up",
            "pagedown": "page_down",
            "arrowleft": "left",
            "arrowright": "right",
            "arrowup": "up",
            "arrowdown": "down",
            "windows": "cmd",
            "win": "cmd",
            "cmd_l": "cmd",
            "cmd_r": "cmd",
        }

        nombre = alias.get(
            nombre,
            nombre,
        )

        if len(nombre) == 1:
            return nombre

        mapa = {
            "enter": "enter",
            "tab": "tab",
            "esc": "esc",
            "space": "space",
            "backspace": "backspace",
            "delete": "delete",
            "insert": "insert",
            "home": "home",
            "end": "end",
            "page_up": "page_up",
            "page_down": "page_down",
            "left": "left",
            "right": "right",
            "up": "up",
            "down": "down",
            "caps_lock": "caps_lock",
            "num_lock": "num_lock",
            "print_screen": "print_screen",
            "pause": "pause",
            "menu": "menu",
            "cmd": "cmd",
        }

        atributo = mapa.get(nombre)

        if atributo:

            return getattr(
                pynput_keyboard.Key,
                atributo,
                None,
            )

        if nombre.startswith("f") and nombre[1:].isdigit():

            numero = int(nombre[1:])

            if 1 <= numero <= 20:

                return getattr(
                    pynput_keyboard.Key,
                    f"f{numero}",
                    None,
                )

        return None

    def modificador_replay(
        self,
        nombre,
    ):
        if pynput_keyboard is None:
            return None

        valor = str(nombre or "").strip().lower()

        mapa = {
            "ctrl": "ctrl",
            "control": "ctrl",
            "shift": "shift",
            "alt": "alt",
            "altgr": "alt_gr",
            "win": "cmd",
            "windows": "cmd",
            "cmd": "cmd",
        }

        atributo = mapa.get(valor)

        if not atributo:
            return None

        return getattr(
            pynput_keyboard.Key,
            atributo,
            None,
        )

    def ejecutar_atajo_replay(
        self,
        modificadores,
        tecla,
        caracter=None,
    ):
        if not self.asegurar_controladores_replay():
            return False

        tecla_objetivo = self.tecla_replay_desde_nombre(
            tecla,
            caracter,
        )

        if tecla_objetivo is None:
            return False

        teclas_modificadoras = []

        for nombre in modificadores or []:
            objeto = self.modificador_replay(nombre)

            if objeto is not None and objeto not in teclas_modificadoras:
                teclas_modificadoras.append(objeto)

        try:
            for modificador in teclas_modificadoras:
                self.keyboard_replay.press(modificador)

            self.keyboard_replay.press(tecla_objetivo)
            self.keyboard_replay.release(tecla_objetivo)

            for modificador in reversed(teclas_modificadoras):
                self.keyboard_replay.release(modificador)

            return True

        except Exception:
            for modificador in reversed(teclas_modificadoras):
                try:
                    self.keyboard_replay.release(modificador)
                except Exception:
                    pass

            return False

    def contexto_pertenece_a_bin(self, contexto):
        if not contexto:
            return False

        try:
            pid = int(contexto.get("pid", 0) or 0)
        except Exception:
            pid = 0

        if sys.platform == "win32":
            try:
                pid_bin = int(ctypes.windll.kernel32.GetCurrentProcessId())
                if pid and pid == pid_bin:
                    return True
            except Exception:
                pass

        proceso = str(contexto.get("proceso", "") or "").strip().lower()
        return (
            proceso in {"python.exe", "pythonw.exe"}
            and "bin" in str(contexto.get("titulo", "") or "").lower()
        )

    def contexto_externo_valido(self, contexto):
        if not contexto or self.contexto_pertenece_a_bin(contexto):
            return False

        if sys.platform != "win32":
            return True

        hwnd = contexto.get("hwnd")
        if not hwnd:
            return True

        try:
            return bool(
                ctypes.windll.user32.IsWindow(int(hwnd))
                and ctypes.windll.user32.IsWindowVisible(int(hwnd))
            )
        except Exception:
            return True

    def registrar_contexto_replay_valido(self, contexto, hwnd=None):
        if not self.contexto_externo_valido(contexto):
            return False

        copia = dict(contexto)
        hwnd_valor = hwnd if hwnd is not None else copia.get("hwnd")

        self.ultimo_contexto_replay_valido = copia
        self.ultimo_hwnd_replay_valido = hwnd_valor
        self.ultimo_proceso_replay_valido = (
            str(copia.get("proceso", "") or "").strip().lower() or None
        )
        return True

    def obtener_contexto_foreground_externo(self):
        actual = self.obtener_contexto_ventana_activa()
        if self.contexto_externo_valido(actual):
            return actual
        return None

    def buscar_ventana_contexto_replay(self, contexto, activar=False):
        if not contexto:
            return {
                "ok": False,
                "estado": "SIN_CONTEXTO",
                "recuperable": True,
                "metodo": "contexto_objetivo",
                "detalle": "La acción no contiene contexto objetivo.",
            }

        if sys.platform != "win32":
            return {
                "ok": False,
                "estado": "PLATAFORMA_NO_WINDOWS",
                "recuperable": False,
                "metodo": "contexto_objetivo",
                "detalle": "La activación de ventanas requiere Windows.",
            }

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd_bin = int(self.winId())
        pid_bin = int(kernel32.GetCurrentProcessId())

        esperado_proceso = str(contexto.get("proceso", "") or "").strip().lower()
        titulo_esperado = str(contexto.get("titulo", "") or "").strip().lower()
        clase_esperada = str(contexto.get("clase", "") or "").strip().lower()

        actual = self.obtener_contexto_ventana_activa()
        if (
            actual
            and self.contexto_externo_valido(actual)
            and (
                not esperado_proceso
                or str(actual.get("proceso", "") or "").strip().lower()
                == esperado_proceso
            )
        ):
            self.registrar_contexto_replay_valido(actual)
            return {
                "ok": True,
                "estado": "CONFIRMADO",
                "recuperable": False,
                "metodo": "foreground_compatible",
                "detalle": "El foreground actual ya pertenece al proceso esperado.",
                "contexto": actual,
                "hwnd": actual.get("hwnd"),
            }

        candidatos = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(hwnd, lparam):
            try:
                if not user32.IsWindowVisible(hwnd) or int(hwnd) == hwnd_bin:
                    return True

                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if int(pid.value) == pid_bin:
                    return True

                try:
                    proceso = psutil.Process(int(pid.value)).name().lower()
                except Exception:
                    return True

                if esperado_proceso and proceso != esperado_proceso:
                    return True

                longitud = user32.GetWindowTextLengthW(hwnd)
                buffer = ctypes.create_unicode_buffer(max(1, longitud + 1))
                user32.GetWindowTextW(hwnd, buffer, len(buffer))
                titulo = buffer.value.strip()

                clase_buffer = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, clase_buffer, len(clase_buffer))
                clase = clase_buffer.value.strip()

                puntuacion = 100 if esperado_proceso else 20
                titulo_l = titulo.lower()
                clase_l = clase.lower()

                if clase_esperada:
                    if clase_l == clase_esperada:
                        puntuacion += 20
                    elif clase_esperada in clase_l or clase_l in clase_esperada:
                        puntuacion += 8

                if titulo_esperado:
                    if titulo_l == titulo_esperado:
                        puntuacion += 16
                    elif titulo_esperado in titulo_l or titulo_l in titulo_esperado:
                        puntuacion += 8
                    else:
                        palabras = {
                            p
                            for p in titulo_esperado.replace("-", " ").split()
                            if len(p) >= 4
                        }
                        puntuacion += min(
                            6,
                            sum(2 for p in palabras if p in titulo_l),
                        )

                candidatos.append(
                    {
                        "puntuacion": puntuacion,
                        "hwnd": int(hwnd),
                        "contexto": {
                            "pid": int(pid.value),
                            "proceso": proceso,
                            "titulo": titulo,
                            "clase": clase,
                            "hwnd": int(hwnd),
                        },
                    }
                )
            except Exception:
                pass
            return True

        try:
            user32.EnumWindows(WNDENUMPROC(callback), 0)
        except Exception as error:
            return {
                "ok": False,
                "estado": "ERROR_ENUMWINDOWS",
                "recuperable": True,
                "metodo": "contexto_objetivo",
                "detalle": str(error),
            }

        if not candidatos:
            return {
                "ok": False,
                "estado": "NO_CONFIRMADO",
                "recuperable": True,
                "metodo": "contexto_objetivo",
                "detalle": "No hay una ventana visible compatible con el contexto esperado.",
            }

        candidatos.sort(key=lambda item: item["puntuacion"], reverse=True)
        elegido = candidatos[0]
        hwnd_destino = elegido["hwnd"]

        if activar:
            try:
                if user32.IsIconic(hwnd_destino):
                    user32.ShowWindow(hwnd_destino, 9)  # SW_RESTORE

                user32.SetForegroundWindow(hwnd_destino)
                QApplication.processEvents()
                kernel32.Sleep(60)

                actual = self.obtener_contexto_ventana_activa()
                if actual and self.contexto_externo_valido(actual):
                    proceso_actual = (
                        str(actual.get("proceso", "") or "").strip().lower()
                    )
                    if not esperado_proceso or proceso_actual == esperado_proceso:
                        elegido["contexto"] = actual
                        elegido["hwnd"] = actual.get("hwnd", hwnd_destino)
                    else:
                        return {
                            "ok": False,
                            "estado": "NO_CONFIRMADO",
                            "recuperable": True,
                            "metodo": "contexto_objetivo",
                            "detalle": "Windows no dejó el proceso esperado como foreground.",
                            "contexto": actual,
                        }
            except Exception as error:
                return {
                    "ok": False,
                    "estado": "NO_CONFIRMADO",
                    "recuperable": True,
                    "metodo": "contexto_objetivo",
                    "detalle": str(error),
                }

        return {
            "ok": True,
            "estado": "CONFIRMADO",
            "recuperable": False,
            "metodo": "contexto_objetivo",
            "detalle": "Ventana compatible localizada por proceso/clase/título tolerante.",
            "contexto": elegido["contexto"],
            "hwnd": elegido["hwnd"],
        }

    def resolver_contexto_teclado_replay(
        self,
        contexto,
        permitir_foreground_externo=False,
    ):
        # 1) Contexto objetivo grabado. El HWND histórico es solo una pista:
        # buscar_ventana_contexto_replay() vuelve a resolver una ventana actual
        # por proceso/clase/título y no depende del HWND viejo.
        if contexto:
            objetivo = self.buscar_ventana_contexto_replay(
                contexto,
                activar=True,
            )
            if objetivo.get("ok"):
                return objetivo

        # 2) Último contexto válido de replay. NO exigir que su HWND antiguo
        # siga siendo válido: Chrome/Explorer pueden recrear la ventana y
        # cambiar HWND mientras mantienen el mismo proceso.
        ultimo = self.ultimo_contexto_replay_valido
        if ultimo and not self.contexto_pertenece_a_bin(ultimo):
            compatible_ultimo = (
                self.contextos_compatibles(contexto, ultimo) if contexto else True
            )

            if compatible_ultimo is not False:
                resultado = self.buscar_ventana_contexto_replay(
                    ultimo,
                    activar=True,
                )
                if resultado.get("ok"):
                    resultado["metodo"] = "ultimo_contexto_valido"
                    resultado["detalle"] = (
                        "Se recuperó el último contexto de replay por "
                        "proceso/clase/título, sin depender del HWND grabado."
                    )
                    return resultado

        # 3) Foreground externo actual. Si coincide con el contexto esperado,
        # puede usarse directamente. En fallback se permite además como
        # destino provisional para no repetir la misma validación rígida.
        foreground = self.obtener_contexto_foreground_externo()
        if foreground:
            compatible = (
                self.contextos_compatibles(contexto, foreground) if contexto else True
            )

            if compatible is True or (compatible is None and not contexto):
                self.registrar_contexto_replay_valido(foreground)
                return {
                    "ok": True,
                    "estado": "CONFIRMADO",
                    "recuperable": False,
                    "metodo": "foreground_compatible",
                    "detalle": "Se reutilizó el foreground externo compatible.",
                    "contexto": foreground,
                    "hwnd": foreground.get("hwnd"),
                }

            if permitir_foreground_externo:
                self.registrar_contexto_replay_valido(foreground)
                return {
                    "ok": True,
                    "estado": "PROVISIONAL",
                    "recuperable": False,
                    "metodo": "foreground_externo",
                    "detalle": (
                        "Fallback: se usó el foreground externo visible "
                        "como destino provisional."
                    ),
                    "contexto": foreground,
                    "hwnd": foreground.get("hwnd"),
                }

        return {
            "ok": False,
            "estado": "CONTEXTO_NO_CONFIRMADO",
            "recuperable": True,
            "metodo": "contexto_no_confirmado",
            "detalle": "No se pudo confirmar todavía un destino externo válido.",
            "contexto": foreground,
        }

    def accion_requiere_contexto_activo(self, accion):
        if not accion:
            return False

        tipo = str(accion.get("tipo", "") or "").lower()
        contexto = accion.get("contexto_objetivo")

        # Alt+Tab cambia precisamente desde el foreground actual; activarle
        # antes otro contexto puede alterar la intención grabada.
        if tipo in {
            "cambiar_aplicacion",
            "abrir_inicio",
            "abrir_aplicacion",
        }:
            return False

        tipos_teclado = {
            "escribir_texto",
            "tecla",
            "texto_tecla",
            "atajo_teclado",
            "copiar",
            "pegar",
            "cortar",
            "deshacer",
            "rehacer",
            "seleccionar_todo",
            "guardar",
            "buscar",
            "imprimir",
            "cerrar_ventana",
            "navegar",
            "navegar_url",
            "buscar_o_navegar",
        }

        tipos_mouse = {
            "click",
            "doble_click",
            "abrir_elemento",
            "click_derecho",
            "abrir_menu_contextual",
            "click_central",
            "scroll",
            "scroll_agrupado",
            "desplazar",
            "arrastrar",
            "arrastre_central",
            "arrastre_derecho",
        }

        if tipo in tipos_teclado:
            # El teclado nunca debe caer dentro de BIN por falta de contexto.
            return True

        if tipo in tipos_mouse:
            # Con coordenadas absolutas solo podemos activar una ventana si
            # la demostración dejó contexto suficiente para identificarla.
            return bool(contexto)

        return bool(contexto)

    def preparar_contexto_accion_replay(
        self,
        accion,
        tarea=None,
        permitir_foreground_externo=False,
    ):
        if not accion:
            return {
                "ok": False,
                "estado": "ACCION_INVALIDA",
                "recuperable": False,
                "metodo": "preparacion_contexto",
                "detalle": "No existe una acción para preparar.",
            }

        if not self.accion_requiere_contexto_activo(accion):
            return {
                "ok": True,
                "estado": "NO_REQUERIDO",
                "recuperable": False,
                "metodo": "sin_contexto_requerido",
                "detalle": "La acción no requiere activar un contexto previo.",
            }

        contexto = accion.get("contexto_objetivo")
        resultado = self.resolver_contexto_teclado_replay(
            contexto,
            permitir_foreground_externo=permitir_foreground_externo,
        )

        self.ultimo_resultado_contexto_replay = resultado

        if resultado.get("ok"):
            contexto_confirmado = resultado.get("contexto")
            if contexto_confirmado:
                self.registrar_contexto_replay_valido(
                    contexto_confirmado,
                    resultado.get("hwnd"),
                )
            return resultado

        # Un contexto no confirmado es una transición recuperable. No debe
        # disparar fallback ni ERROR antes de que el supervisor pueda esperar.
        resultado = dict(resultado)
        resultado.setdefault("estado", "CONTEXTO_NO_CONFIRMADO")
        resultado.setdefault("recuperable", True)
        resultado.setdefault("metodo", "preparacion_contexto")
        return resultado

    def mantener_bin_visible_replay(
        self,
        activo=True,
    ):
        if sys.platform != "win32":
            return

        try:

            user32 = ctypes.windll.user32

            hwnd = int(self.winId())

            if activo:

                user32.ShowWindow(
                    hwnd,
                    4,
                )

            user32.SetWindowPos(
                hwnd,
                (HWND_TOPMOST if activo else HWND_NOTOPMOST),
                0,
                0,
                0,
                0,
                (
                    SWP_NOMOVE
                    | SWP_NOSIZE
                    | SWP_NOACTIVATE
                    | (SWP_SHOWWINDOW if activo else 0)
                ),
            )

        except Exception:

            pass

    def delay_minimo_supervision_accion(self, accion):
        tipo = str(accion.get("tipo", "") or "")
        if tipo in {"navegar", "navegar_url", "buscar_o_navegar"}:
            return 500
        if tipo in {
            "doble_click",
            "abrir_elemento",
            "cambiar_aplicacion",
            "cerrar_ventana",
        }:
            return 350
        if tipo in {"click", "click_derecho", "abrir_menu_contextual", "arrastrar"}:
            return 220
        return 170

    def tiempo_espera_supervisor_ms(self):
        total = int(self.espera_supervisor_acumulada_ms or 0)
        if self.inicio_espera_supervisor_monotonic is not None:
            total += int(
                max(0.0, time.monotonic() - self.inicio_espera_supervisor_monotonic)
                * 1000
            )
        return max(0, total)

    def iniciar_supervision_accion(
        self,
        tarea,
        accion,
        modo="postaccion",
        delay_inicial_ms=250,
    ):
        self.accion_real_actual = accion
        self.fase_ejecucion_real = (
            "supervisor_preaccion" if modo == "preaccion" else "supervisor"
        )
        self.espera_supervisor_acumulada_ms = 0
        self.inicio_espera_supervisor_monotonic = time.monotonic()
        self.intentos_supervisor = 0
        self.ultima_decision_supervisor = None
        self.ultimo_motivo_supervisor = ""
        self.supervisor_hubo_wait = False
        self.delay_ejecucion_restante_ms = max(0, int(delay_inicial_ms))
        self.guardar_estado_ejecutor_real_en_tarea(tarea)
        self.timer_ejecucion_accion.start(self.delay_ejecucion_restante_ms)

    def obtener_siguiente_accion_plan_real(self):
        siguiente = self.indice_ejecucion_real + 1
        if 0 <= siguiente < len(self.plan_ejecucion_actual):
            return self.plan_ejecucion_actual[siguiente]
        return None

    def evaluar_estado_con_ia(self, imagen, contexto):
        proveedor = getattr(self, "proveedor_ia_visual", None)
        if not callable(proveedor):
            return {
                "disponible": False,
                "decision": "AMBIGUOUS",
                "motivo": "Supervisor visual IA no configurado.",
            }

        try:
            respuesta = proveedor(imagen, contexto)
        except Exception as error:
            return {
                "disponible": True,
                "decision": "AMBIGUOUS",
                "motivo": f"El proveedor visual no pudo evaluar el estado: {error}",
            }

        if isinstance(respuesta, str):
            respuesta = {"decision": respuesta, "motivo": ""}

        if not isinstance(respuesta, dict):
            return {
                "disponible": True,
                "decision": "AMBIGUOUS",
                "motivo": "El proveedor visual devolvió un formato no reconocido.",
            }

        decision = str(respuesta.get("decision", "AMBIGUOUS") or "AMBIGUOUS").upper()
        if decision not in {"READY", "WAIT", "FAILED", "AMBIGUOUS"}:
            decision = "AMBIGUOUS"

        return {
            "disponible": True,
            "decision": decision,
            "motivo": str(respuesta.get("motivo", "") or ""),
        }

    def evaluar_preparacion_siguiente_accion(
        self,
        tarea,
        accion_ejecutada,
        siguiente_accion,
    ):
        actual = self.obtener_contexto_ventana_activa()

        if self.contexto_externo_valido(actual):
            self.registrar_contexto_replay_valido(actual)

        contexto_siguiente = (
            siguiente_accion.get("contexto_objetivo") if siguiente_accion else None
        )

        contexto_despues = (
            accion_ejecutada.get("contexto_despues") if accion_ejecutada else None
        )

        # ====================================================
        # SUPERVISAR APERTURA DIRECTA DE UNA APLICACIÓN
        # ====================================================

        if (
            accion_ejecutada
            and str(
                accion_ejecutada.get(
                    "tipo",
                    "",
                )
                or ""
            )
            .strip()
            .lower()
            == "abrir_aplicacion"
        ):

            datos_aplicacion = accion_ejecutada.get("datos") or {}

            proceso_aplicacion = self.normalizar_proceso_aplicacion(
                consulta=datos_aplicacion.get(
                    "consulta",
                    "",
                ),
                proceso=datos_aplicacion.get(
                    "proceso",
                    "",
                ),
            )

            if proceso_aplicacion:

                ventana_aplicacion = self.buscar_ventana_contexto_replay(
                    {
                        "proceso": proceso_aplicacion,
                        "titulo": "",
                        "clase": "",
                    },
                    activar=False,
                )

                if ventana_aplicacion.get("ok"):

                    contexto_aplicacion = ventana_aplicacion.get("contexto") or actual

                    if self.contexto_externo_valido(contexto_aplicacion):

                        self.registrar_contexto_replay_valido(
                            contexto_aplicacion,
                            ventana_aplicacion.get("hwnd"),
                        )

                    return {
                        "decision": "READY",
                        "motivo": (
                            f"{proceso_aplicacion} " "ya está visible y disponible."
                        ),
                        "fuente": "determinista",
                        "contexto_actual": contexto_aplicacion,
                    }

        # Primero, certeza determinista barata.
        if contexto_siguiente:
            compatible = self.contextos_compatibles(contexto_siguiente, actual)
            if compatible is True:
                return {
                    "decision": "READY",
                    "motivo": "El foreground actual ya es compatible con la próxima acción.",
                    "fuente": "determinista",
                    "contexto_actual": actual,
                }

            ventana = self.buscar_ventana_contexto_replay(
                contexto_siguiente,
                activar=False,
            )
            if ventana.get("ok"):
                return {
                    "decision": "READY",
                    "motivo": "La aplicación necesaria para la próxima acción está visible y disponible.",
                    "fuente": "determinista",
                    "contexto_actual": actual,
                }

        elif siguiente_accion is None:
            if contexto_despues:
                compatible = self.contextos_compatibles(contexto_despues, actual)
                if compatible is True:
                    return {
                        "decision": "READY",
                        "motivo": "El contexto posterior esperado está disponible.",
                        "fuente": "determinista",
                        "contexto_actual": actual,
                    }
                if compatible is False:
                    determinista = "WAIT"
                    motivo_determinista = (
                        "El contexto posterior todavía no coincide con el esperado."
                    )
                else:
                    determinista = "AMBIGUOUS"
                    motivo_determinista = "No hay evidencia suficiente para confirmar el contexto posterior."
            else:
                return {
                    "decision": "READY",
                    "motivo": "La acción no exige una transición de contexto antes de continuar.",
                    "fuente": "determinista",
                    "contexto_actual": actual,
                }
        else:
            # Si la próxima acción no declara contexto, contexto_despues de
            # la acción que acaba de ejecutarse sigue siendo evidencia útil.
            if contexto_despues:
                compatible_despues = self.contextos_compatibles(
                    contexto_despues,
                    actual,
                )
                if compatible_despues is True:
                    return {
                        "decision": "READY",
                        "motivo": "El contexto posterior esperado ya está disponible.",
                        "fuente": "determinista",
                        "contexto_actual": actual,
                    }
                if compatible_despues is False:
                    determinista = "WAIT"
                    motivo_determinista = (
                        "El contexto posterior todavía no coincide con el esperado."
                    )
                else:
                    determinista = "AMBIGUOUS"
                    motivo_determinista = (
                        "El contexto posterior aún no puede confirmarse."
                    )
            elif self.contexto_externo_valido(actual):
                return {
                    "decision": "READY",
                    "motivo": "Existe un foreground externo válido para la próxima acción.",
                    "fuente": "determinista",
                    "contexto_actual": actual,
                }
            else:
                determinista = "AMBIGUOUS"
                motivo_determinista = "No hay un foreground externo confirmado."

        if contexto_siguiente:
            determinista = "WAIT"
            motivo_determinista = (
                "La próxima aplicación o ventana aún no está confirmada."
            )

        frame = None
        if getattr(self, "frame_actual", None) is not None:
            try:
                frame = self.frame_actual.copy()
            except Exception:
                frame = self.frame_actual

        ia = self.evaluar_estado_con_ia(
            frame,
            {
                "accion_ejecutada": accion_ejecutada,
                "siguiente_accion": siguiente_accion,
                "contexto_esperado_despues": contexto_despues,
                "contexto_esperado_siguiente": contexto_siguiente,
                "contexto_actual": actual,
            },
        )

        if ia.get("disponible"):
            return {
                "decision": ia.get("decision", "AMBIGUOUS"),
                "motivo": ia.get("motivo", ""),
                "fuente": "ia",
                "contexto_actual": actual,
            }

        # Sin IA, AMBIGUOUS se comporta como WAIT hasta timeout.
        return {
            "decision": (
                "WAIT" if determinista in {"WAIT", "AMBIGUOUS"} else determinista
            ),
            "motivo": motivo_determinista,
            "fuente": "determinista",
            "contexto_actual": actual,
        }

    def registrar_checkpoint_supervisor(
        self,
        tarea,
        decision,
        motivo,
        contexto_actual,
    ):
        tarea["ultimo_checkpoint"] = {
            "decision": decision,
            "motivo": motivo,
            "timestamp": datetime.now().isoformat(),
            "accion_indice": self.indice_ejecucion_real,
            "repeticion": self.repeticion_ejecucion_real,
            "contexto_actual": (
                {
                    "pid": contexto_actual.get("pid"),
                    "proceso": contexto_actual.get("proceso"),
                    "titulo": contexto_actual.get("titulo"),
                    "clase": contexto_actual.get("clase"),
                    "hwnd": contexto_actual.get("hwnd"),
                }
                if contexto_actual
                else None
            ),
        }

    def completar_accion_real_supervisada(self, tarea):
        self.ejecuciones_reales_completadas += 1
        self.indice_ejecucion_real += 1

        total = max(1, self.ejecuciones_reales_totales)
        tarea["ejecuciones_reales_completadas"] = self.ejecuciones_reales_completadas
        tarea["progreso"] = min(
            100,
            int((self.ejecuciones_reales_completadas / total) * 100),
        )

        tarea["detalle_estado"] = (
            f"Repetición {self.repeticion_ejecucion_real}/"
            f"{tarea['repeticiones_totales']} · Acción "
            f"{min(self.indice_ejecucion_real, len(self.plan_ejecucion_actual))}/"
            f"{len(self.plan_ejecucion_actual)} · OK"
        )
        tarea["accion_actual_indice"] = None

        self.refrescar_panel_acciones()
        self.fase_ejecucion_real = "espera_accion"
        self.accion_real_actual = None
        self.resultado_accion_real_actual = None
        self.programar_siguiente_accion_real(tarea)

    def formatear_error_supervisor(
        self,
        tarea,
        accion,
        estado,
        motivo,
        contexto_actual,
        esperado_ms,
    ):
        esperado = (
            accion.get("contexto_objetivo") or accion.get("contexto_despues") or {}
        )
        proceso_esperado = str(esperado.get("proceso", "") or "--")
        proceso_actual = str((contexto_actual or {}).get("proceso", "") or "--")
        numero_accion = min(
            self.indice_ejecucion_real + 1,
            max(1, len(self.plan_ejecucion_actual)),
        )
        return (
            "ERROR DE EJECUCIÓN\n\n"
            f"Tarea: {tarea.get('nombre', '--')}\n"
            f"Repetición: {self.repeticion_ejecucion_real}/"
            f"{self.obtener_repeticiones_tarea(tarea)}\n"
            f"Acción: {numero_accion}/{len(self.plan_ejecucion_actual)}\n"
            f"Acción esperada: {accion.get('descripcion', 'Acción')}\n"
            f"Estado: {estado}\n"
            f"Esperó: {esperado_ms / 1000:.1f} s\n"
            f"Contexto esperado: {proceso_esperado}\n"
            f"Contexto actual: {proceso_actual}\n"
            f"Última decisión: {self.ultima_decision_supervisor or '--'}\n"
            f"Motivo: {motivo}"
        )

    def activar_contexto_objetivo(
        self,
        contexto,
    ):
        resultado = self.buscar_ventana_contexto_replay(
            contexto,
            activar=True,
        )

        self.ultimo_resultado_contexto_replay = resultado

        if resultado.get("ok"):
            actual = resultado.get("contexto") or self.obtener_contexto_ventana_activa()
            self.registrar_contexto_replay_valido(
                actual,
                resultado.get("hwnd"),
            )
            return True

        return False

    def contextos_compatibles(
        self,
        esperado,
        actual,
    ):
        if not esperado:
            return None

        if not actual:
            return False

        proceso_esperado = str(esperado.get("proceso", "") or "").strip().lower()
        proceso_actual = str(actual.get("proceso", "") or "").strip().lower()

        # El proceso es la señal principal. Cambios de título o HWND
        # dentro de la misma aplicación no invalidan el contexto.
        if proceso_esperado and proceso_actual:
            if proceso_esperado == proceso_actual:
                return True
            return False

        clase_esperada = str(esperado.get("clase", "") or "").strip().lower()
        clase_actual = str(actual.get("clase", "") or "").strip().lower()

        if clase_esperada and clase_actual:
            if clase_esperada == clase_actual:
                return True

        titulo_esperado = str(esperado.get("titulo", "") or "").strip().lower()
        titulo_actual = str(actual.get("titulo", "") or "").strip().lower()

        if titulo_esperado and titulo_actual:
            if (
                titulo_esperado == titulo_actual
                or titulo_esperado in titulo_actual
                or titulo_actual in titulo_esperado
            ):
                return True

        return None

    def preparar_contexto_teclado_replay(
        self,
        contexto,
    ):
        resultado = self.resolver_contexto_teclado_replay(
            contexto,
            permitir_foreground_externo=bool(
                getattr(self, "modo_fallback_contexto", False)
            ),
        )

        self.ultimo_resultado_contexto_replay = resultado
        return bool(resultado.get("ok"))

    def ejecutar_arrastre_fisico(
        self,
        datos,
    ):
        if not self.asegurar_controladores_replay():
            return False

        try:
            x_inicio = int(datos.get("x_inicio"))
            y_inicio = int(datos.get("y_inicio"))
            x_fin = int(datos.get("x_fin"))
            y_fin = int(datos.get("y_fin"))
        except Exception:
            return False

        boton_nombre = str(
            datos.get(
                "boton",
                "izquierdo",
            )
            or "izquierdo"
        ).lower()

        if "derech" in boton_nombre:
            boton = pynput_mouse.Button.right
        elif "central" in boton_nombre or "middle" in boton_nombre:
            boton = pynput_mouse.Button.middle
        else:
            boton = pynput_mouse.Button.left

        duracion_ms = max(
            0,
            int(
                datos.get(
                    "duracion_ms",
                    0,
                )
                or 0
            ),
        )

        pasos = max(
            2,
            min(
                8,
                int(duracion_ms / 60) + 2,
            ),
        )

        posicion_original = None
        bin_bajado = False

        if sys.platform == "win32":
            user32 = ctypes.windll.user32

            punto = wintypes.POINT()

            if user32.GetCursorPos(ctypes.byref(punto)):
                posicion_original = (
                    int(punto.x),
                    int(punto.y),
                )

            try:
                rect_bin = wintypes.RECT()

                if user32.GetWindowRect(
                    int(self.winId()),
                    ctypes.byref(rect_bin),
                ):
                    cubre_inicio = (
                        rect_bin.left <= x_inicio < rect_bin.right
                        and rect_bin.top <= y_inicio < rect_bin.bottom
                    )
                    cubre_fin = (
                        rect_bin.left <= x_fin < rect_bin.right
                        and rect_bin.top <= y_fin < rect_bin.bottom
                    )

                    if cubre_inicio or cubre_fin:
                        if user32.SetWindowPos(
                            int(self.winId()),
                            HWND_BOTTOM,
                            0,
                            0,
                            0,
                            0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                        ):
                            bin_bajado = True
                            QApplication.processEvents()
                            ctypes.windll.kernel32.Sleep(25)

            except Exception:
                bin_bajado = False

        try:
            self.mouse_replay.position = (
                x_inicio,
                y_inicio,
            )

            self.mouse_replay.press(boton)

            for paso in range(
                1,
                pasos + 1,
            ):
                x = round(x_inicio + (x_fin - x_inicio) * paso / pasos)

                y = round(y_inicio + (y_fin - y_inicio) * paso / pasos)

                self.mouse_replay.position = (
                    x,
                    y,
                )

                if sys.platform == "win32":
                    ctypes.windll.kernel32.Sleep(15)

            self.mouse_replay.release(boton)

            return True

        except Exception:
            try:
                self.mouse_replay.release(boton)
            except Exception:
                pass

            return False

        finally:
            if posicion_original is not None and self.mouse_replay is not None:
                try:
                    self.mouse_replay.position = posicion_original
                except Exception:
                    pass

            if bin_bajado and sys.platform == "win32":
                ctypes.windll.user32.SetWindowPos(
                    int(self.winId()),
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )

                QApplication.processEvents()

    def obtener_acciones_origen_semantica(
        self,
        tarea,
        accion,
    ):
        ids = accion.get("acciones_origen") or []

        por_id = {
            original.get("id"): original
            for original in tarea.get(
                "acciones",
                [],
            )
        }

        return [
            por_id[identificador] for identificador in ids if identificador in por_id
        ]

    def ejecutar_accion_original_real(
        self,
        accion,
        tarea,
    ):
        tipo = str(
            accion.get(
                "tipo",
                "",
            )
            or ""
        )

        contexto = accion.get("contexto_objetivo")

        if tipo in {
            "click",
            "doble_click",
            "click_derecho",
        }:
            try:
                x = int(accion.get("x"))
                y = int(accion.get("y"))
            except Exception:
                return {
                    "ok": False,
                    "metodo": "mouse",
                    "detalle": "Coordenadas inválidas",
                }

            mapa_tipo = {
                "click": "click",
                "doble_click": "doble_click",
                "click_derecho": "click_derecho",
            }

            ok = self.ejecutar_mouse_fisico(
                x,
                y,
                mapa_tipo[tipo],
            )

            return {
                "ok": bool(ok),
                "metodo": "SendInput",
                "detalle": tipo,
            }

        if tipo == "click_central":
            try:
                x = int(accion.get("x"))
                y = int(accion.get("y"))
            except Exception:
                return {
                    "ok": False,
                    "metodo": "mouse",
                    "detalle": "Coordenadas inválidas",
                }

            ok = self.ejecutar_mouse_fisico(
                x,
                y,
                "click_central",
            )

            return {
                "ok": bool(ok),
                "metodo": "SendInput",
                "detalle": "click_central",
            }

        if tipo in {
            "scroll",
            "scroll_agrupado",
        }:
            if accion.get("x") is None or accion.get("y") is None:
                return {
                    "ok": False,
                    "metodo": "mouse",
                    "detalle": "El scroll no tiene coordenadas grabadas",
                }

            try:
                x = int(accion.get("x"))
                y = int(accion.get("y"))
            except Exception:
                return {
                    "ok": False,
                    "metodo": "mouse",
                    "detalle": "Coordenadas de scroll inválidas",
                }

            dx = int(
                accion.get(
                    "dx",
                    0,
                )
                or 0
            )
            dy = int(
                accion.get(
                    "dy",
                    0,
                )
                or 0
            )

            if tipo == "scroll" and dy == 0:
                delta = int(
                    accion.get(
                        "delta",
                        0,
                    )
                    or 0
                )

                dy = int(delta / 120)

            pasos = max(
                1,
                int(
                    accion.get(
                        "pasos",
                        max(
                            abs(dx),
                            abs(dy),
                            1,
                        ),
                    )
                    or 1
                ),
            )

            if dy:
                delta = 120 * pasos * (1 if dy > 0 else -1)

                ok = self.ejecutar_mouse_fisico(
                    x,
                    y,
                    "scroll",
                    delta,
                )

                if not ok:
                    return {
                        "ok": False,
                        "metodo": "SendInput",
                        "detalle": "scroll vertical",
                    }

            if dx:
                if not self.asegurar_controladores_replay():
                    return {
                        "ok": False,
                        "metodo": "pynput",
                        "detalle": "scroll horizontal",
                    }

                try:
                    self.mouse_replay.position = (
                        x,
                        y,
                    )
                    self.mouse_replay.scroll(
                        (pasos if dx > 0 else -pasos),
                        0,
                    )
                except Exception as error:
                    return {
                        "ok": False,
                        "metodo": "pynput",
                        "detalle": str(error),
                    }

            return {
                "ok": True,
                "metodo": "mouse",
                "detalle": "scroll",
            }

        if tipo in {
            "arrastrar",
            "arrastre_central",
            "arrastre_derecho",
        }:
            datos = dict(accion)

            if tipo == "arrastre_central":
                datos["boton"] = "central"
            elif tipo == "arrastre_derecho":
                datos["boton"] = "derecho"

            ok = self.ejecutar_arrastre_fisico(datos)

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": tipo,
            }

        if tipo == "escribir_texto":
            if not self.preparar_contexto_teclado_replay(contexto):
                return {
                    "ok": False,
                    "metodo": "teclado",
                    "detalle": "No se pudo activar el contexto",
                }

            if not self.asegurar_controladores_replay():
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": "Controlador de teclado no disponible",
                }

            texto = str(
                accion.get(
                    "texto",
                    "",
                )
                or ""
            )

            try:
                self.keyboard_replay.type(texto)
                return {
                    "ok": True,
                    "metodo": "pynput",
                    "detalle": "escribir_texto",
                }
            except Exception as error:
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": str(error),
                }

        if tipo in {
            "tecla",
            "atajo_teclado",
            "texto_tecla",
        }:
            if not self.preparar_contexto_teclado_replay(contexto):
                return {
                    "ok": False,
                    "metodo": "teclado",
                    "detalle": "No se pudo activar el contexto",
                }

            modificadores = accion.get("modificadores") or []

            ok = self.ejecutar_atajo_replay(
                modificadores,
                accion.get("tecla"),
                accion.get("caracter"),
            )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": tipo,
            }

        return {
            "ok": False,
            "metodo": "no_soportado",
            "detalle": (f"Tipo original no soportado: {tipo}"),
        }

    def normalizar_proceso_aplicacion(
        self,
        consulta="",
        proceso="",
    ):
        proceso = str(proceso or "").strip().lower()

        if proceso:

            return proceso if proceso.endswith(".exe") else f"{proceso}.exe"

        consulta = str(consulta or "").strip().lower()

        alias = {
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "firefox": "firefox.exe",
            "brave": "brave.exe",
            "opera": "opera.exe",
            "explorer": "explorer.exe",
            "explorador": "explorer.exe",
            "explorador de archivos": "explorer.exe",
            "notepad": "notepad.exe",
            "bloc de notas": "notepad.exe",
            "calculadora": "calc.exe",
            "calculator": "calc.exe",
        }

        return alias.get(consulta)

    def resolver_ruta_aplicacion_windows(
        self,
        proceso,
        ejecutable="",
    ):
        ruta_guardada = str(ejecutable or "").strip()

        if ruta_guardada and Path(ruta_guardada).exists():
            return ruta_guardada

        proceso = self.normalizar_proceso_aplicacion(proceso=proceso)

        if not proceso:
            return None

        for proceso_objeto in psutil.process_iter(
            [
                "name",
                "exe",
            ]
        ):

            try:

                nombre = str(
                    proceso_objeto.info.get(
                        "name",
                        "",
                    )
                    or ""
                ).lower()

                if nombre != proceso:
                    continue

                ruta = proceso_objeto.info.get("exe")

                if ruta and Path(ruta).exists():
                    return ruta

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        ruta_path = shutil.which(proceso)

        if ruta_path:
            return ruta_path

        if sys.platform == "win32" and winreg is not None:

            subclave = (
                r"Software\Microsoft\Windows" r"\CurrentVersion\App Paths\\" + proceso
            )

            ubicaciones = [
                winreg.HKEY_CURRENT_USER,
                winreg.HKEY_LOCAL_MACHINE,
            ]

            for raiz in ubicaciones:

                for acceso in (
                    winreg.KEY_READ,
                    winreg.KEY_READ
                    | getattr(
                        winreg,
                        "KEY_WOW64_64KEY",
                        0,
                    ),
                    winreg.KEY_READ
                    | getattr(
                        winreg,
                        "KEY_WOW64_32KEY",
                        0,
                    ),
                ):

                    try:

                        with winreg.OpenKey(
                            raiz,
                            subclave,
                            0,
                            acceso,
                        ) as clave:

                            ruta, _ = winreg.QueryValueEx(
                                clave,
                                None,
                            )

                            if ruta and Path(ruta).exists():
                                return ruta

                    except OSError:
                        continue

        return None

    def ejecutar_abrir_aplicacion(
        self,
        datos,
    ):
        datos = datos or {}

        consulta = str(
            datos.get(
                "consulta",
                "",
            )
            or ""
        ).strip()

        proceso = self.normalizar_proceso_aplicacion(
            consulta=consulta,
            proceso=datos.get(
                "proceso",
                "",
            ),
        )

        ejecutable = str(
            datos.get(
                "ejecutable",
                "",
            )
            or ""
        ).strip()

        if proceso:

            existente = self.buscar_ventana_contexto_replay(
                {
                    "proceso": proceso,
                    "titulo": "",
                    "clase": "",
                },
                activar=False,
            )

            if existente.get("ok"):

                contexto = existente.get("contexto")

                if contexto:

                    self.registrar_contexto_replay_valido(
                        contexto,
                        existente.get("hwnd"),
                    )

                return {
                    "ok": True,
                    "estado": "DISPONIBLE",
                    "recuperable": False,
                    "metodo": "aplicacion_existente",
                    "detalle": (f"{proceso} ya estaba disponible."),
                }

        ruta = self.resolver_ruta_aplicacion_windows(
            proceso,
            ejecutable,
        )

        try:

            if ruta:

                subprocess.Popen(
                    [ruta],
                    close_fds=True,
                )

                return {
                    "ok": True,
                    "estado": "ENVIADO",
                    "recuperable": False,
                    "metodo": "subprocess",
                    "detalle": (f"Aplicación iniciada: {ruta}"),
                }

            if sys.platform == "win32" and proceso:

                resultado = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "open",
                    proceso,
                    None,
                    None,
                    1,
                )

                if int(resultado) > 32:

                    return {
                        "ok": True,
                        "estado": "ENVIADO",
                        "recuperable": False,
                        "metodo": "ShellExecuteW",
                        "detalle": ("Aplicación solicitada: " f"{proceso}"),
                    }

            return {
                "ok": False,
                "estado": "APLICACION_NO_RESUELTA",
                "recuperable": False,
                "metodo": "abrir_aplicacion",
                "detalle": (
                    "No pude resolver el ejecutable para "
                    f"'{consulta or proceso or 'aplicación'}'."
                ),
            }

        except Exception as error:

            return {
                "ok": False,
                "estado": "ERROR_APERTURA",
                "recuperable": False,
                "metodo": "abrir_aplicacion",
                "detalle": str(error),
            }

    def ejecutar_abrir_inicio(
        self,
    ):
        if not self.asegurar_controladores_replay():

            return {
                "ok": False,
                "estado": "SIN_TECLADO",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": ("Controlador de teclado no disponible."),
            }

        tecla_win = self.tecla_replay_desde_nombre("cmd")

        if tecla_win is None:

            return {
                "ok": False,
                "estado": "WIN_NO_DISPONIBLE",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": ("pynput no expuso la tecla Windows."),
            }

        try:

            self.keyboard_replay.press(tecla_win)

            self.keyboard_replay.release(tecla_win)

            return {
                "ok": True,
                "estado": "ENVIADO",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": ("Abrir menú Inicio"),
            }

        except Exception as error:

            return {
                "ok": False,
                "estado": "ERROR_TECLADO",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": str(error),
            }

    def ejecutar_accion_semantica_real(
        self,
        accion,
        tarea,
    ):
        tipo = str(
            accion.get(
                "tipo",
                "",
            )
            or ""
        )

        datos = accion.get("datos") or {}

        contexto = accion.get("contexto_objetivo")

        if tipo == "abrir_aplicacion":

            return self.ejecutar_abrir_aplicacion(datos)

        if tipo == "abrir_inicio":

            return self.ejecutar_abrir_inicio()

        if tipo in {
            "click",
            "doble_click",
            "abrir_elemento",
            "abrir_menu_contextual",
        }:
            tipo_mouse = {
                "click": "click",
                "doble_click": "doble_click",
                "abrir_elemento": "doble_click",
                "abrir_menu_contextual": "click_derecho",
            }[tipo]

            try:
                x = int(datos.get("x"))
                y = int(datos.get("y"))
            except Exception:
                return {
                    "ok": False,
                    "metodo": "mouse",
                    "detalle": "Coordenadas semánticas inválidas",
                }

            ok = self.ejecutar_mouse_fisico(
                x,
                y,
                tipo_mouse,
            )

            return {
                "ok": bool(ok),
                "metodo": "SendInput",
                "detalle": tipo,
            }

        if tipo == "click_central":
            origenes = self.obtener_acciones_origen_semantica(
                tarea,
                accion,
            )

            if origenes:
                return self.ejecutar_accion_original_real(
                    origenes[0],
                    tarea,
                )

            return {
                "ok": False,
                "metodo": "pynput",
                "detalle": "No hay coordenadas originales",
            }

        if tipo in {
            "desplazar",
            "scroll",
            "scroll_agrupado",
        }:
            accion_original = {
                "tipo": "scroll_agrupado",
                "x": datos.get("x"),
                "y": datos.get("y"),
                "dx": datos.get(
                    "dx",
                    0,
                ),
                "dy": datos.get(
                    "dy",
                    0,
                ),
                "pasos": datos.get(
                    "pasos",
                    1,
                ),
                "contexto_objetivo": contexto,
            }

            return self.ejecutar_accion_original_real(
                accion_original,
                tarea,
            )

        if tipo == "arrastrar":
            ok = self.ejecutar_arrastre_fisico(datos)

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": "arrastrar",
            }

        if tipo == "escribir_texto":

            if not self.asegurar_controladores_replay():
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": "Controlador de teclado no disponible",
                }

            texto = str(
                datos.get(
                    "texto",
                    "",
                )
                or ""
            )

            try:
                self.keyboard_replay.type(texto)

                return {
                    "ok": True,
                    "metodo": "pynput",
                    "detalle": "escribir_texto",
                }

            except Exception as error:
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": str(error),
                }

        mapa_atajos = {
            "copiar": (["Ctrl"], "c"),
            "pegar": (["Ctrl"], "v"),
            "cortar": (["Ctrl"], "x"),
            "deshacer": (["Ctrl"], "z"),
            "seleccionar_todo": (["Ctrl"], "a"),
            "guardar": (["Ctrl"], "s"),
            "buscar": (["Ctrl"], "f"),
            "imprimir": (["Ctrl"], "p"),
            "cambiar_aplicacion": (["Alt"], "tab"),
            "cerrar_ventana": (["Alt"], "f4"),
        }

        if tipo == "rehacer":
            modificadores = ["Ctrl"]
            tecla = "y"

            origenes = self.obtener_acciones_origen_semantica(
                tarea,
                accion,
            )

            if origenes:
                modificadores_origen = [
                    str(valor).lower()
                    for valor in (origenes[0].get("modificadores") or [])
                ]

                if "shift" in modificadores_origen:
                    modificadores = [
                        "Ctrl",
                        "Shift",
                    ]
                    tecla = "z"

            ok = self.ejecutar_atajo_replay(
                modificadores,
                tecla,
            )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": "rehacer",
            }

        if tipo in mapa_atajos:

            modificadores, tecla = mapa_atajos[tipo]

            ok = self.ejecutar_atajo_replay(
                modificadores,
                tecla,
            )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": tipo,
            }

        if tipo in {
            "navegar_url",
            "navegar",
            "buscar_o_navegar",
        }:
            navegador = str(
                datos.get(
                    "navegador",
                    "",
                )
                or ""
            ).lower()

            navegadores = {
                "chrome.exe",
                "msedge.exe",
                "firefox.exe",
                "brave.exe",
                "opera.exe",
            }

            if navegador not in navegadores:
                return {
                    "ok": False,
                    "metodo": "teclado",
                    "detalle": "Contexto de navegador no compatible",
                }

            if not self.asegurar_controladores_replay():
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": "Controlador de teclado no disponible",
                }

            destino = str(
                datos.get(
                    "destino",
                    "",
                )
                or ""
            )

            if not self.ejecutar_atajo_replay(
                ["Ctrl"],
                "l",
            ):
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": "Ctrl+L falló",
                }

            try:
                self.keyboard_replay.type(destino)
            except Exception as error:
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": str(error),
                }

            if not self.ejecutar_atajo_replay(
                [],
                "enter",
            ):
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": "Enter falló",
                }

            return {
                "ok": True,
                "metodo": "pynput",
                "detalle": tipo,
            }

        if tipo in {
            "tecla",
            "atajo_teclado",
        }:

            ok = self.ejecutar_atajo_replay(
                datos.get("modificadores") or [],
                datos.get("tecla"),
                datos.get("caracter"),
            )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": tipo,
            }

        return {
            "ok": False,
            "metodo": "no_soportado",
            "detalle": (f"Tipo semántico no soportado: {tipo}"),
        }

    def ejecutar_fallback_accion_real(
        self,
        accion,
        tarea,
    ):
        origenes = self.obtener_acciones_origen_semantica(
            tarea,
            accion,
        )

        if not origenes:
            return {
                "ok": False,
                "estado": "SIN_FALLBACK",
                "recuperable": False,
                "metodo": "fallback",
                "detalle": "Sin acciones originales asociadas",
            }

        # El fallback usa una política de contexto distinta: si no puede
        # recuperar el contexto grabado, puede usar el foreground externo
        # actual como destino provisional. Así no repite la misma validación
        # rígida que ya pudo fallar en la capa semántica.
        self.modo_fallback_contexto = True

        try:
            for original in origenes:
                self.ultimo_resultado_contexto_replay = None

                resultado = self.ejecutar_accion_original_real(
                    original,
                    tarea,
                )

                if not resultado.get("ok"):
                    contexto_resultado = self.ultimo_resultado_contexto_replay or {}
                    return {
                        "ok": False,
                        "estado": contexto_resultado.get(
                            "estado",
                            "FALLBACK_FALLIDO",
                        ),
                        "recuperable": bool(
                            contexto_resultado.get("recuperable", False)
                        ),
                        "metodo": contexto_resultado.get(
                            "metodo",
                            "fallback_original",
                        ),
                        "detalle": (
                            "Falló la acción original "
                            f"{original.get('id')}: "
                            f"{resultado.get('detalle', '')}"
                        ),
                    }

        finally:
            self.modo_fallback_contexto = False

        return {
            "ok": True,
            "estado": "ENVIADO",
            "recuperable": False,
            "metodo": "fallback_original",
            "detalle": f"{len(origenes)} acción(es) original(es)",
        }

    def iniciar_ejecutor_real(
        self,
        tarea,
        reanudar=False,
    ):
        plan = self.obtener_plan_ejecucion(tarea)

        if not plan:
            return False

        semanticas = tarea.get("acciones_semanticas") or []
        usa_semantica = bool(semanticas)

        self.plan_ejecucion_actual = plan
        self.plan_ejecucion_usa_semantica = usa_semantica
        self.offsets_ejecucion_actual_ms = self.calcular_offsets_plan_ejecucion(
            tarea,
            plan,
            usa_semantica,
        )

        repeticiones = self.obtener_repeticiones_tarea(tarea)
        self.ejecuciones_reales_totales = len(plan) * repeticiones

        if reanudar:
            self.indice_ejecucion_real = max(
                0,
                min(
                    len(plan),
                    int(tarea.get("ejecucion_real_indice", 0)),
                ),
            )
            self.repeticion_ejecucion_real = max(
                1,
                min(
                    repeticiones,
                    int(tarea.get("ejecucion_real_repeticion", 1)),
                ),
            )
            self.ejecuciones_reales_completadas = max(
                0,
                int(tarea.get("ejecuciones_reales_completadas", 0)),
            )
            self.delay_ejecucion_restante_ms = max(
                0,
                int(tarea.get("delay_ejecucion_restante_ms", 0)),
            )
            self.fase_ejecucion_real = str(
                tarea.get("ejecucion_real_fase", "espera_accion") or "espera_accion"
            )
            if self.fase_ejecucion_real == "checkpoint":
                self.fase_ejecucion_real = "supervisor"

            self.elapsed_repeticion_base_ms = max(
                0,
                int(tarea.get("elapsed_repeticion_real_ms", 0)),
            )
            self.espera_supervisor_acumulada_ms = max(
                0,
                int(tarea.get("supervisor_espera_acumulada_ms", 0)),
            )
            self.intentos_supervisor = max(
                0,
                int(tarea.get("supervisor_intentos", 0)),
            )
            self.ultima_decision_supervisor = tarea.get("supervisor_ultima_decision")
            self.ultimo_motivo_supervisor = str(
                tarea.get("supervisor_ultimo_motivo", "") or ""
            )
        else:
            self.indice_ejecucion_real = 0
            self.repeticion_ejecucion_real = 1
            self.ejecuciones_reales_completadas = 0
            self.delay_ejecucion_restante_ms = 0
            self.fase_ejecucion_real = "espera_accion"
            self.elapsed_repeticion_base_ms = 0
            self.espera_supervisor_acumulada_ms = 0
            self.intentos_supervisor = 0
            self.ultima_decision_supervisor = None
            self.ultimo_motivo_supervisor = ""

        self.ejecucion_fisica_activa = True
        self.accion_real_actual = None
        self.resultado_accion_real_actual = None
        self.supervisor_hubo_wait = False
        self.modo_fallback_contexto = False
        self.ultimo_resultado_contexto_replay = None

        if (
            reanudar
            and self.fase_ejecucion_real in {"supervisor", "supervisor_preaccion"}
            and 0 <= self.indice_ejecucion_real < len(plan)
        ):
            self.accion_real_actual = plan[self.indice_ejecucion_real]
            self.inicio_espera_supervisor_monotonic = time.monotonic()
        else:
            self.inicio_espera_supervisor_monotonic = None

        self.inicio_repeticion_real_monotonic = time.monotonic()

        tarea["ejecucion_real_indice"] = self.indice_ejecucion_real
        tarea["ejecucion_real_repeticion"] = self.repeticion_ejecucion_real
        tarea["ejecuciones_reales_completadas"] = self.ejecuciones_reales_completadas
        tarea["ejecucion_real_fase"] = self.fase_ejecucion_real
        tarea["repeticion_actual"] = self.repeticion_ejecucion_real

        if reanudar:
            delay = self.delay_ejecucion_restante_ms
        else:
            delay = (
                self.offsets_ejecucion_actual_ms[0]
                if self.offsets_ejecucion_actual_ms
                else 0
            )

        tarea["delay_ejecucion_restante_ms"] = delay

        self.grabando = False
        self.mantener_bin_visible_replay(True)

        self.timer_ejecucion_accion.start(max(0, int(delay)))
        return True

    def elapsed_repeticion_real_actual_ms(self):
        elapsed = int(self.elapsed_repeticion_base_ms)

        if (
            self.ejecucion_fisica_activa
            and self.inicio_repeticion_real_monotonic is not None
        ):
            elapsed += int(
                max(
                    0.0,
                    time.monotonic() - self.inicio_repeticion_real_monotonic,
                )
                * 1000
            )

        return max(
            0,
            elapsed,
        )

    def guardar_estado_ejecutor_real_en_tarea(
        self,
        tarea,
    ):
        tarea["ejecucion_real_indice"] = self.indice_ejecucion_real
        tarea["ejecucion_real_repeticion"] = self.repeticion_ejecucion_real
        tarea["ejecuciones_reales_completadas"] = self.ejecuciones_reales_completadas
        tarea["delay_ejecucion_restante_ms"] = self.delay_ejecucion_restante_ms
        tarea["ejecucion_real_fase"] = self.fase_ejecucion_real
        tarea["elapsed_repeticion_real_ms"] = self.elapsed_repeticion_real_actual_ms()
        tarea["supervisor_espera_acumulada_ms"] = self.tiempo_espera_supervisor_ms()
        tarea["supervisor_intentos"] = self.intentos_supervisor
        tarea["supervisor_ultima_decision"] = self.ultima_decision_supervisor
        tarea["supervisor_ultimo_motivo"] = self.ultimo_motivo_supervisor

    def procesar_timer_ejecucion_real(self):
        if not self.ejecucion_fisica_activa:
            return

        if self.fase_ejecucion_real in {
            "checkpoint",
            "supervisor",
            "supervisor_preaccion",
        }:
            self.procesar_checkpoint_accion_real()
            return

        if self.fase_ejecucion_real == "espera_fin_repeticion":
            self.finalizar_repeticion_real()
            return

        self.ejecutar_siguiente_accion_real()

    def ejecutar_siguiente_accion_real(self):
        tarea = self.obtener_tarea_ejecutando()

        if (
            not tarea
            or tarea.get("estado") != "EJECUTANDO"
            or not self.ejecucion_fisica_activa
        ):
            return

        plan = self.plan_ejecucion_actual

        if not plan:
            self.finalizar_ejecucion_con_error(
                tarea,
                "No existe un plan de ejecución real.",
            )
            return

        if self.indice_ejecucion_real >= len(plan):
            self.programar_fin_repeticion_real(tarea)
            return

        accion = plan[self.indice_ejecucion_real]
        self.accion_real_actual = accion
        self.ultimo_resultado_contexto_replay = None

        indice_panel = self.indice_panel_para_accion_real(
            tarea,
            accion,
            self.plan_ejecucion_usa_semantica,
        )

        tarea["accion_actual_indice"] = indice_panel
        tarea["repeticion_actual"] = self.repeticion_ejecucion_real
        tarea["repeticiones_totales"] = self.obtener_repeticiones_tarea(tarea)

        numero_accion = self.indice_ejecucion_real + 1
        cantidad_acciones = len(plan)
        descripcion = accion.get("descripcion", "Acción")

        tarea["detalle_estado"] = (
            f"Repetición {self.repeticion_ejecucion_real}/"
            f"{tarea['repeticiones_totales']} · "
            f"Acción {numero_accion}/{cantidad_acciones} · Preparando contexto..."
        )

        self.actualizar_estado_cabecera_visor(
            "Ejecutando",
            (
                f"· Repetición {self.repeticion_ejecucion_real}/"
                f"{tarea['repeticiones_totales']} "
                f"· Acción {numero_accion}/{cantidad_acciones}"
            ),
            AMARILLO,
        )

        self.actualizar_chat_bin(
            f"{tarea['nombre']} — repetición "
            f"{self.repeticion_ejecucion_real}/{tarea['repeticiones_totales']} · "
            f"acción {numero_accion}/{cantidad_acciones}: {descripcion}"
        )

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()

        # ====================================================
        # PREPARAR CONTEXTO ANTES DE ENVIAR NINGÚN EVENTO
        # ====================================================
        # Antes se intentaba la semántica y después el fallback aunque el
        # único problema fuera que la aplicación todavía estaba apareciendo.
        # Eso hacía que dos rutas fallaran por la misma causa. Ahora una
        # transición recuperable entra en WAIT ANTES de enviar/reintentar.
        preparacion = self.preparar_contexto_accion_replay(
            accion,
            tarea,
            permitir_foreground_externo=False,
        )

        if not preparacion.get("ok"):
            if preparacion.get("recuperable", False):
                self.resultado_accion_real_actual = preparacion
                self.iniciar_supervision_accion(
                    tarea,
                    accion,
                    modo="preaccion",
                    delay_inicial_ms=self.intervalo_supervisor_ms,
                )
                return

            self.finalizar_ejecucion_con_error(
                tarea,
                "No se pudo preparar el contexto de la acción: "
                f"{preparacion.get('detalle', '')}",
            )
            return

        tarea["detalle_estado"] = (
            f"Repetición {self.repeticion_ejecucion_real}/"
            f"{tarea['repeticiones_totales']} · "
            f"Acción {numero_accion}/{cantidad_acciones} · Ejecutando..."
        )

        # ====================================================
        # ENVIAR ACCIÓN FÍSICA
        # ====================================================
        if self.plan_ejecucion_usa_semantica:
            resultado = self.ejecutar_accion_semantica_real(accion, tarea)

            if not resultado.get("ok"):
                contexto_resultado = self.ultimo_resultado_contexto_replay or {}
                recuperable_semantica = bool(
                    resultado.get("recuperable", False)
                    or contexto_resultado.get("recuperable", False)
                )

                # Un fallo de CONTEXTO no ejecuta inmediatamente el fallback.
                # El supervisor espera y vuelve a intentar la MISMA acción
                # cuando el sistema esté listo.
                if recuperable_semantica:
                    self.resultado_accion_real_actual = {
                        "ok": False,
                        "estado": contexto_resultado.get(
                            "estado",
                            resultado.get("estado", "CONTEXTO_NO_CONFIRMADO"),
                        ),
                        "recuperable": True,
                        "metodo": contexto_resultado.get(
                            "metodo",
                            resultado.get("metodo", "supervisor_preaccion"),
                        ),
                        "detalle": resultado.get("detalle", ""),
                    }
                    self.iniciar_supervision_accion(
                        tarea,
                        accion,
                        modo="preaccion",
                        delay_inicial_ms=self.intervalo_supervisor_ms,
                    )
                    return

                # El fallback queda reservado para fallo físico/no soportado,
                # y usa su política propia de foreground externo provisional.
                resultado_fallback = self.ejecutar_fallback_accion_real(
                    accion,
                    tarea,
                )

                if resultado_fallback.get("ok"):
                    resultado = resultado_fallback
                elif resultado_fallback.get("recuperable", False):
                    self.resultado_accion_real_actual = resultado_fallback
                    self.iniciar_supervision_accion(
                        tarea,
                        accion,
                        modo="preaccion",
                        delay_inicial_ms=self.intervalo_supervisor_ms,
                    )
                    return
                else:
                    self.finalizar_ejecucion_con_error(
                        tarea,
                        (
                            "La acción real no pudo ejecutarse. "
                            f"Semántica: {resultado.get('detalle', '')}. "
                            f"Fallback: {resultado_fallback.get('detalle', '')}."
                        ),
                    )
                    return
        else:
            resultado = self.ejecutar_accion_original_real(accion, tarea)

            if not resultado.get("ok"):
                contexto_resultado = self.ultimo_resultado_contexto_replay or {}
                recuperable = bool(
                    resultado.get("recuperable", False)
                    or contexto_resultado.get("recuperable", False)
                )

                if recuperable:
                    self.resultado_accion_real_actual = {
                        **resultado,
                        "estado": contexto_resultado.get(
                            "estado",
                            resultado.get("estado", "CONTEXTO_NO_CONFIRMADO"),
                        ),
                        "recuperable": True,
                    }
                    self.iniciar_supervision_accion(
                        tarea,
                        accion,
                        modo="preaccion",
                        delay_inicial_ms=self.intervalo_supervisor_ms,
                    )
                    return

                self.finalizar_ejecucion_con_error(
                    tarea,
                    "La acción grabada no pudo ejecutarse: "
                    f"{resultado.get('detalle', '')}.",
                )
                return

        resultado = dict(resultado)
        resultado.setdefault("estado", "ENVIADO")
        resultado.setdefault("recuperable", False)

        self.resultado_accion_real_actual = resultado
        self.registrar_contexto_replay_valido(self.obtener_contexto_ventana_activa())

        tarea["detalle_estado"] = (
            f"Repetición {self.repeticion_ejecucion_real}/"
            f"{tarea['repeticiones_totales']} · "
            f"Acción {numero_accion}/{cantidad_acciones} · Enviada"
        )

        self.iniciar_supervision_accion(
            tarea,
            accion,
            modo="postaccion",
            delay_inicial_ms=self.delay_minimo_supervision_accion(accion),
        )

    def procesar_checkpoint_accion_real(self):
        tarea = self.obtener_tarea_ejecutando()

        if not tarea or not self.ejecucion_fisica_activa:
            return

        accion = self.accion_real_actual

        if accion is None:
            self.finalizar_ejecucion_con_error(
                tarea,
                "Se perdió la acción pendiente de supervisión.",
            )
            return

        modo = (
            "preaccion"
            if self.fase_ejecucion_real == "supervisor_preaccion"
            else "postaccion"
        )

        siguiente_accion = (
            accion if modo == "preaccion" else self.obtener_siguiente_accion_plan_real()
        )

        self.intentos_supervisor += 1

        # ====================================================
        # PRE-ACCIÓN: READY SOLO SI EL CONTEXTO SE PUEDE PREPARAR
        # ====================================================
        # No basta con que exista una ventana compatible en segundo plano.
        # Para teclado/mouse contextual, READY significa que BIN consiguió
        # recuperar/activar un destino válido sin depender del HWND histórico.
        if modo == "preaccion":
            preparacion = self.preparar_contexto_accion_replay(
                accion,
                tarea,
                permitir_foreground_externo=False,
            )

            if preparacion.get("ok"):
                resultado = {
                    "decision": "READY",
                    "motivo": preparacion.get(
                        "detalle",
                        "El contexto de la acción quedó preparado.",
                    ),
                    "fuente": "determinista",
                    "contexto_actual": (
                        preparacion.get("contexto")
                        or self.obtener_contexto_ventana_activa()
                    ),
                }
            elif not preparacion.get("recuperable", True):
                resultado = {
                    "decision": "FAILED",
                    "motivo": preparacion.get(
                        "detalle",
                        "El contexto de la acción no puede prepararse.",
                    ),
                    "fuente": "determinista",
                    "contexto_actual": self.obtener_contexto_ventana_activa(),
                }
            else:
                observacion = self.evaluar_preparacion_siguiente_accion(
                    tarea,
                    None,
                    accion,
                )

                # Aunque la observación/IA vea la aplicación, la acción no se
                # dispara hasta que la preparación de contexto se confirme.
                # Esto evita READY -> reintento -> mismo fallo -> bucle.
                if str(observacion.get("decision", "WAIT")).upper() == "FAILED":
                    resultado = observacion
                else:
                    resultado = {
                        "decision": "WAIT",
                        "motivo": (
                            preparacion.get("detalle")
                            or observacion.get("motivo")
                            or "El contexto todavía no puede activarse."
                        ),
                        "fuente": observacion.get("fuente", "determinista"),
                        "contexto_actual": observacion.get(
                            "contexto_actual",
                            self.obtener_contexto_ventana_activa(),
                        ),
                    }
        else:
            resultado = self.evaluar_preparacion_siguiente_accion(
                tarea,
                accion,
                siguiente_accion,
            )

        decision = str(resultado.get("decision", "AMBIGUOUS") or "AMBIGUOUS").upper()
        motivo = str(resultado.get("motivo", "") or "")
        contexto_actual = resultado.get("contexto_actual")

        self.ultima_decision_supervisor = decision
        self.ultimo_motivo_supervisor = motivo

        self.registrar_checkpoint_supervisor(
            tarea,
            decision,
            motivo,
            contexto_actual,
        )

        esperado_ms = self.tiempo_espera_supervisor_ms()

        if decision == "READY":
            if self.supervisor_hubo_wait:
                self.actualizar_chat_bin(
                    f"Sistema listo para continuar '{tarea['nombre']}'."
                )

            self.registrar_contexto_replay_valido(contexto_actual)
            self.supervisor_hubo_wait = False
            self.espera_supervisor_acumulada_ms = 0
            self.inicio_espera_supervisor_monotonic = None
            self.intentos_supervisor = 0

            if modo == "preaccion":
                self.fase_ejecucion_real = "espera_accion"
                self.delay_ejecucion_restante_ms = 0
                self.guardar_estado_ejecutor_real_en_tarea(tarea)
                self.timer_ejecucion_accion.start(0)
                return

            self.completar_accion_real_supervisada(tarea)
            return

        if esperado_ms >= self.timeout_supervisor_ms:
            self.finalizar_ejecucion_con_error(
                tarea,
                self.formatear_error_supervisor(
                    tarea,
                    accion,
                    estado="TIMEOUT",
                    motivo=(
                        motivo
                        or "El sistema no confirmó un estado listo antes del timeout."
                    ),
                    contexto_actual=contexto_actual,
                    esperado_ms=esperado_ms,
                ),
            )
            return

        if decision == "FAILED":
            self.finalizar_ejecucion_con_error(
                tarea,
                self.formatear_error_supervisor(
                    tarea,
                    accion,
                    estado="FAILED",
                    motivo=motivo or "El supervisor detectó un fallo no recuperable.",
                    contexto_actual=contexto_actual,
                    esperado_ms=esperado_ms,
                ),
            )
            return

        # WAIT y AMBIGUOUS son recuperables. Mantener la misma acción
        # resaltada y volver a observar sin avanzar el índice ni el progreso.
        if not self.supervisor_hubo_wait:
            self.supervisor_hubo_wait = True
            self.actualizar_chat_bin(
                f"'{tarea['nombre']}' está esperando que el sistema quede listo."
            )

        numero_accion = min(
            self.indice_ejecucion_real + 1,
            max(1, len(self.plan_ejecucion_actual)),
        )
        repeticiones = self.obtener_repeticiones_tarea(tarea)

        tarea["detalle_estado"] = (
            f"Repetición {self.repeticion_ejecucion_real}/{repeticiones} · "
            f"Acción {numero_accion}/{len(self.plan_ejecucion_actual)} · "
            "Esperando sistema..."
        )

        self.actualizar_estado_cabecera_visor(
            "Esperando",
            (
                f"· Repetición {self.repeticion_ejecucion_real}/{repeticiones} "
                f"· Acción {numero_accion}/{len(self.plan_ejecucion_actual)}"
            ),
            AMARILLO,
        )

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()

        self.delay_ejecucion_restante_ms = self.intervalo_supervisor_ms
        self.guardar_estado_ejecutor_real_en_tarea(tarea)
        self.timer_ejecucion_accion.start(self.intervalo_supervisor_ms)

    def programar_siguiente_accion_real(
        self,
        tarea,
    ):
        if self.indice_ejecucion_real >= len(self.plan_ejecucion_actual):
            self.programar_fin_repeticion_real(tarea)
            return

        elapsed_ms = self.elapsed_repeticion_real_actual_ms()

        objetivo_ms = (
            self.offsets_ejecucion_actual_ms[self.indice_ejecucion_real]
            if self.indice_ejecucion_real < len(self.offsets_ejecucion_actual_ms)
            else elapsed_ms
        )

        delay = max(
            0,
            int(objetivo_ms - elapsed_ms),
        )

        self.delay_ejecucion_restante_ms = delay
        self.fase_ejecucion_real = "espera_accion"

        self.guardar_estado_ejecutor_real_en_tarea(tarea)

        self.timer_ejecucion_accion.start(delay)

    def programar_fin_repeticion_real(
        self,
        tarea,
    ):
        duracion_ms = max(
            1,
            self.obtener_duracion_repeticion(tarea) * 1000,
        )

        elapsed_ms = self.elapsed_repeticion_real_actual_ms()

        delay = max(
            0,
            int(duracion_ms - elapsed_ms),
        )

        self.delay_ejecucion_restante_ms = delay
        self.fase_ejecucion_real = "espera_fin_repeticion"

        self.guardar_estado_ejecutor_real_en_tarea(tarea)

        self.timer_ejecucion_accion.start(delay)

    def finalizar_repeticion_real(self):
        tarea = self.obtener_tarea_ejecutando()

        if not tarea or not self.ejecucion_fisica_activa:
            return

        repeticiones = self.obtener_repeticiones_tarea(tarea)

        if self.repeticion_ejecucion_real >= repeticiones:
            self.finalizar_ejecucion(tarea)
            return

        self.repeticion_ejecucion_real += 1
        self.indice_ejecucion_real = 0
        self.elapsed_repeticion_base_ms = 0
        self.inicio_repeticion_real_monotonic = time.monotonic()
        self.fase_ejecucion_real = "espera_accion"
        self.inicio_espera_supervisor_monotonic = None
        self.espera_supervisor_acumulada_ms = 0
        self.intentos_supervisor = 0
        self.ultima_decision_supervisor = None
        self.ultimo_motivo_supervisor = ""
        self.supervisor_hubo_wait = False
        self.mantener_bin_visible_replay(True)
        self.delay_ejecucion_restante_ms = (
            self.offsets_ejecucion_actual_ms[0]
            if self.offsets_ejecucion_actual_ms
            else 0
        )

        tarea["repeticion_actual"] = self.repeticion_ejecucion_real
        tarea["accion_actual_indice"] = None

        tarea["detalle_estado"] = (
            f"Repetición "
            f"{self.repeticion_ejecucion_real}/"
            f"{repeticiones} · "
            "Preparando siguiente vuelta"
        )

        self.actualizar_estado_cabecera_visor(
            "Ejecutando",
            (f"· Repetición " f"{self.repeticion_ejecucion_real}/" f"{repeticiones}"),
            AMARILLO,
        )

        self.refrescar_panel_acciones()

        QTimer.singleShot(
            0,
            self.volver_panel_acciones_arriba,
        )

        self.guardar_estado_ejecutor_real_en_tarea(tarea)

        self.timer_ejecucion_accion.start(self.delay_ejecucion_restante_ms)

    def iniciar_ejecucion(
        self,
        tarea,
        run_key=None,
        origen="manual",
    ):
        if self.ejecucion_fisica_activa:
            return False

        plan = self.obtener_plan_ejecucion(tarea)

        if not plan:
            tarea["estado"] = "REQUIERE CONFIGURACIÓN"
            tarea["detalle_estado"] = "No hay acciones para ejecutar"
            self.guardar_tareas_en_disco()
            self.actualizar_tarjeta_tarea(tarea["id"])
            return False

        duracion_total = self.obtener_duracion_total_tarea(tarea)

        if duracion_total <= 0:
            tarea["estado"] = "REQUIERE CONFIGURACIÓN"
            tarea["detalle_estado"] = "La duración de la rutina no es válida"
            self.guardar_tareas_en_disco()
            self.actualizar_tarjeta_tarea(tarea["id"])
            return False

        ahora = datetime.now()

        if run_key is None:
            run_key = "manual-" + ahora.strftime("%Y%m%d-%H%M%S")

        # Grabación y replay son modos separados.
        self.grabando = False
        self.detener_grabadores_globales()
        self.ocultar_barra_grabacion()

        self.tarea_ejecutando_id = tarea["id"]
        self.tarea_seleccionada_id = tarea["id"]
        self.rutina_en_borrador = False

        repeticiones = self.obtener_repeticiones_tarea(tarea)

        tarea["estado"] = "EJECUTANDO"
        tarea["elapsed_seconds"] = 0
        tarea["runtime_base_seconds"] = 0
        tarea["transcurrido"] = "00:00:00"
        tarea["progreso"] = 0
        tarea["runtime_started_at"] = ahora.isoformat()
        tarea["current_run_key"] = run_key
        tarea["queued_at"] = None
        tarea["completed_at"] = None
        tarea["accion_actual_indice"] = None
        tarea["repeticion_actual"] = 1
        tarea["repeticiones_totales"] = repeticiones
        tarea["ejecucion_real_indice"] = 0
        tarea["ejecucion_real_repeticion"] = 1
        tarea["ejecuciones_reales_completadas"] = 0
        tarea["delay_ejecucion_restante_ms"] = 0
        tarea["ejecucion_real_fase"] = "espera_accion"
        tarea["elapsed_repeticion_real_ms"] = 0
        tarea["detalle_estado"] = (
            f"Repetición 1/{repeticiones} · " "Preparando ejecución física..."
        )

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText("● BIN OCUPADO")
            self.estado_bin.setStyleSheet(f"""
                color: {AMARILLO};
                font-weight: 800;
                """)

        self.actualizar_estado_cabecera_visor(
            "Ejecutando",
            f"· Repetición 1/{repeticiones}",
            AMARILLO,
        )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "BIN ESTÁ EJECUTANDO\n\n"
                f"{tarea['nombre']}\n\n"
                f"REPETICIÓN 1 DE {repeticiones}\n"
                "Preparando la primera acción física..."
            )

        if origen == "programada":
            self.actualizar_chat_bin(
                f"Inicié automáticamente "
                f"'{tarea['nombre']}' porque llegó "
                "su hora programada."
            )
        else:
            self.actualizar_chat_bin(
                f"Inicié '{tarea['nombre']}' " "con EJECUTAR AHORA."
            )

        if not self.iniciar_ejecutor_real(
            tarea,
            reanudar=False,
        ):
            self.finalizar_ejecucion_con_error(
                tarea,
                "No se pudo preparar el ejecutor físico.",
            )
            return False

        self.actualizar_tarjeta_tarea(tarea["id"])
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

        inicio_texto = tarea.get("runtime_started_at")

        if inicio_texto:
            try:
                inicio = datetime.fromisoformat(inicio_texto)

                adicional = int((datetime.now() - inicio).total_seconds())
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

        tarea["elapsed_seconds"] = transcurrido
        tarea["transcurrido"] = segundos_a_hms(transcurrido)

        total = max(
            1,
            int(
                self.ejecuciones_reales_totales
                or (
                    len(self.obtener_plan_ejecucion(tarea))
                    * self.obtener_repeticiones_tarea(tarea)
                )
            ),
        )

        completadas = max(
            0,
            int(
                tarea.get(
                    "ejecuciones_reales_completadas",
                    self.ejecuciones_reales_completadas,
                )
            ),
        )

        if self.ejecucion_fisica_activa:
            completadas = self.ejecuciones_reales_completadas
            tarea["ejecuciones_reales_completadas"] = completadas

        tarea["progreso"] = min(
            100,
            int((completadas / total) * 100),
        )

        tarea["repeticion_actual"] = max(
            1,
            int(
                self.repeticion_ejecucion_real
                if self.ejecucion_fisica_activa
                else tarea.get(
                    "ejecucion_real_repeticion",
                    1,
                )
            ),
        )

        tarea["repeticiones_totales"] = self.obtener_repeticiones_tarea(tarea)

        self.actualizar_tarjeta_tarea(tarea["id"])

    def pausar_ejecucion(self, tarea):
        inicio_texto = tarea.get("runtime_started_at")

        if inicio_texto:
            try:
                inicio = datetime.fromisoformat(inicio_texto)
                adicional = int((datetime.now() - inicio).total_seconds())
            except Exception:
                adicional = 0
        else:
            adicional = 0

        base = int(tarea.get("runtime_base_seconds", 0))
        transcurrido = max(0, base + adicional)

        tarea["elapsed_seconds"] = transcurrido
        tarea["runtime_base_seconds"] = transcurrido
        tarea["transcurrido"] = segundos_a_hms(transcurrido)
        tarea["runtime_started_at"] = None
        tarea["estado"] = "EN PAUSA"

        if (
            hasattr(self, "timer_ejecucion_accion")
            and self.timer_ejecucion_accion.isActive()
        ):
            restante = self.timer_ejecucion_accion.remainingTime()
            self.delay_ejecucion_restante_ms = max(0, int(restante))
            self.timer_ejecucion_accion.stop()

        if self.fase_ejecucion_real in {
            "supervisor",
            "supervisor_preaccion",
            "checkpoint",
        }:
            self.espera_supervisor_acumulada_ms = self.tiempo_espera_supervisor_ms()
            self.inicio_espera_supervisor_monotonic = None

        self.elapsed_repeticion_base_ms = self.elapsed_repeticion_real_actual_ms()
        self.inicio_repeticion_real_monotonic = None
        self.ejecucion_fisica_activa = False

        tarea["repeticion_actual"] = self.repeticion_ejecucion_real
        tarea["repeticiones_totales"] = self.obtener_repeticiones_tarea(tarea)
        tarea["detalle_estado"] = (
            f"Ejecución pausada · Repetición "
            f"{tarea['repeticion_actual']}/{tarea['repeticiones_totales']}"
        )

        self.guardar_estado_ejecutor_real_en_tarea(tarea)
        self.tarea_ejecutando_id = None
        self.mantener_bin_visible_replay(False)

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText("● BIN OPERATIVO")
            self.estado_bin.setStyleSheet(f"""
                color: {VERDE};
                font-weight: 800;
                """)

        self.actualizar_estado_cabecera_visor(
            "Ejecución pausada",
            (
                f"· Repetición {tarea['repeticion_actual']}/"
                f"{tarea['repeticiones_totales']}"
            ),
            AMARILLO,
        )

        self.actualizar_chat_bin(
            f"Pausé '{tarea['nombre']}' en {tarea['transcurrido']} · "
            f"repetición {tarea['repeticion_actual']}/{tarea['repeticiones_totales']}."
        )

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()
        self.guardar_tareas_en_disco()

        QTimer.singleShot(100, self.iniciar_siguiente_en_cola)

    def continuar_ejecucion(self, tarea):
        actual = self.obtener_tarea_ejecutando()

        if actual:
            mensaje = f"La tarea '{actual['nombre']}' " "está en ejecución ahora."
            QMessageBox.information(
                self,
                "BIN está ocupado",
                mensaje,
            )
            self.actualizar_chat_bin(mensaje)
            return

        if tarea.get("estado") != "EN PAUSA" or not tarea.get("current_run_key"):
            return

        self.grabando = False
        self.detener_grabadores_globales()
        self.ocultar_barra_grabacion()

        self.tarea_ejecutando_id = tarea["id"]
        self.tarea_seleccionada_id = tarea["id"]

        tarea["estado"] = "EJECUTANDO"
        tarea["runtime_base_seconds"] = int(
            tarea.get(
                "elapsed_seconds",
                0,
            )
        )
        tarea["runtime_started_at"] = datetime.now().isoformat()

        if not self.iniciar_ejecutor_real(
            tarea,
            reanudar=True,
        ):
            self.finalizar_ejecucion_con_error(
                tarea,
                "No se pudo restaurar el ejecutor físico.",
            )
            return

        repeticion_actual = self.repeticion_ejecucion_real
        repeticiones = self.obtener_repeticiones_tarea(tarea)

        tarea["repeticion_actual"] = repeticion_actual
        tarea["repeticiones_totales"] = repeticiones
        tarea["detalle_estado"] = (
            f"Continuando ejecución · " f"Repetición {repeticion_actual}/{repeticiones}"
        )

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText("● BIN OCUPADO")
            self.estado_bin.setStyleSheet(f"""
                color: {AMARILLO};
                font-weight: 800;
                """)

        self.actualizar_estado_cabecera_visor(
            "Ejecutando",
            (f"· Repetición " f"{repeticion_actual}/{repeticiones}"),
            AMARILLO,
        )

        self.actualizar_chat_bin(
            f"Continué '{tarea['nombre']}' "
            f"desde {tarea.get('transcurrido', '00:00:00')} · "
            f"repetición {repeticion_actual}/{repeticiones}."
        )

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()
        self.guardar_tareas_en_disco()

    def finalizar_ejecucion(self, tarea):
        duracion_total = self.obtener_duracion_total_tarea(tarea)
        repeticiones = self.obtener_repeticiones_tarea(tarea)

        if hasattr(self, "timer_ejecucion_accion"):
            self.timer_ejecucion_accion.stop()

        self.ejecucion_fisica_activa = False
        self.fase_ejecucion_real = "inactiva"
        self.delay_ejecucion_restante_ms = 0
        self.accion_real_actual = None
        self.resultado_accion_real_actual = None
        self.inicio_repeticion_real_monotonic = None
        self.elapsed_repeticion_base_ms = 0
        self.inicio_espera_supervisor_monotonic = None
        self.espera_supervisor_acumulada_ms = 0
        self.intentos_supervisor = 0
        self.supervisor_hubo_wait = False
        self.mantener_bin_visible_replay(False)

        ahora = datetime.now()

        tarea["estado"] = "FINALIZADA"
        tarea["elapsed_seconds"] = duracion_total
        tarea["runtime_base_seconds"] = 0
        tarea["transcurrido"] = segundos_a_hms(duracion_total)
        tarea["progreso"] = 100
        tarea["last_run_key"] = tarea.get("current_run_key")
        tarea["current_run_key"] = None
        tarea["runtime_started_at"] = None
        tarea["queued_at"] = None
        tarea["completed_at"] = ahora.isoformat()
        tarea["ultima_ejecucion"] = ahora.isoformat()
        tarea["accion_actual_indice"] = None
        tarea["repeticion_actual"] = repeticiones
        tarea["repeticiones_totales"] = repeticiones
        tarea["ejecucion_real_indice"] = 0
        tarea["ejecucion_real_repeticion"] = repeticiones
        tarea["ejecuciones_reales_completadas"] = max(
            tarea.get(
                "ejecuciones_reales_completadas",
                0,
            ),
            self.ejecuciones_reales_totales,
        )
        tarea["delay_ejecucion_restante_ms"] = 0
        tarea["ejecucion_real_fase"] = "inactiva"
        tarea["elapsed_repeticion_real_ms"] = 0

        proxima = self.calcular_proxima_ejecucion_tarea(
            tarea,
            desde=ahora + timedelta(seconds=1),
        )

        ultima_texto = ahora.strftime("%d/%m %H:%M")

        if proxima:
            tarea["detalle_estado"] = (
                "FINALIZADA\n"
                f"Repeticiones: {repeticiones}/{repeticiones}\n"
                f"Última ejecución: {ultima_texto}\n"
                "Próxima ejecución: " + self.formatear_proxima_ejecucion(proxima)
            )
        else:
            tarea["detalle_estado"] = (
                "FINALIZADA\n"
                f"Repeticiones: {repeticiones}/{repeticiones}\n"
                f"Última ejecución: {ultima_texto}\n"
                "Próxima ejecución: Sin programación"
            )

        self.tarea_ejecutando_id = None

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText("● BIN OPERATIVO")
            self.estado_bin.setStyleSheet(f"""
                color: {VERDE};
                font-weight: 800;
                """)

        self.actualizar_estado_cabecera_visor(
            "Ejecución finalizada",
            f"· Repeticiones {repeticiones}/{repeticiones}",
            VERDE,
        )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "EJECUCIÓN FINALIZADA\n\n"
                f"{tarea['nombre']}\n\n"
                f"REPETICIONES {repeticiones}/{repeticiones}\n\n"
                "BIN está disponible."
            )

        self.actualizar_chat_bin(
            f"Finalicé '{tarea['nombre']}' tras "
            f"{repeticiones} repetición(es). "
            + (
                "Próxima ejecución: " + self.formatear_proxima_ejecucion(proxima)
                if proxima
                else "No tiene una próxima ejecución."
            )
        )

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        QTimer.singleShot(
            0,
            self.volver_panel_acciones_arriba,
        )

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )

    def finalizar_ejecucion_con_error(
        self,
        tarea,
        mensaje,
    ):
        if hasattr(self, "timer_ejecucion_accion"):
            self.timer_ejecucion_accion.stop()

        self.ejecucion_fisica_activa = False
        self.fase_ejecucion_real = "inactiva"
        self.delay_ejecucion_restante_ms = 0
        self.accion_real_actual = None
        self.resultado_accion_real_actual = None
        self.inicio_repeticion_real_monotonic = None
        self.inicio_espera_supervisor_monotonic = None
        self.espera_supervisor_acumulada_ms = 0
        self.intentos_supervisor = 0
        self.supervisor_hubo_wait = False
        self.mantener_bin_visible_replay(False)

        tarea["estado"] = "ERROR"
        tarea["runtime_started_at"] = None
        tarea["detalle_estado"] = mensaje
        tarea["accion_actual_indice"] = None
        tarea["repeticiones_totales"] = self.obtener_repeticiones_tarea(tarea)
        tarea["ejecucion_real_indice"] = self.indice_ejecucion_real
        tarea["ejecucion_real_repeticion"] = self.repeticion_ejecucion_real
        tarea["ejecuciones_reales_completadas"] = self.ejecuciones_reales_completadas
        tarea["delay_ejecucion_restante_ms"] = 0
        tarea["ejecucion_real_fase"] = "inactiva"

        self.tarea_ejecutando_id = None

        if hasattr(self, "estado_bin"):
            self.estado_bin.setText("● BIN CON ERROR")
            self.estado_bin.setStyleSheet(f"""
                color: {ROJO};
                font-weight: 800;
                """)

        repeticion_actual = tarea.get(
            "repeticion_actual",
            0,
        )

        repeticiones = tarea.get(
            "repeticiones_totales",
            1,
        )

        detalle = ""

        if repeticion_actual:
            detalle = f"· Repetición " f"{repeticion_actual}/{repeticiones}"

        self.actualizar_estado_cabecera_visor(
            "Error de ejecución",
            detalle,
            ROJO,
        )

        if hasattr(self, "mensaje_visor"):
            self.mensaje_visor.setText(
                "ERROR DE EJECUCIÓN\n\n" f"{tarea['nombre']}\n\n" f"{mensaje}"
            )

        self.actualizar_chat_bin(f"Error en '{tarea['nombre']}': " f"{mensaje}")

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        QTimer.singleShot(
            0,
            self.volver_panel_acciones_arriba,
        )

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )

    def iniciar_siguiente_en_cola(self):
        if self.obtener_tarea_ejecutando():
            return

        en_cola = [tarea for tarea in self.tareas if tarea.get("estado") == "EN COLA"]

        if not en_cola:
            return

        en_cola.sort(
            key=lambda tarea: tarea.get(
                "queued_at",
                "",
            )
        )

        siguiente = en_cola[0]

        run_key = siguiente.get("current_run_key")

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
            hora, minuto = [int(valor) for valor in tarea.get("hora", "").split(":")]
        except Exception:
            return None

        dias = tarea.get("dias", [])

        if not dias:
            return None

        for desplazamiento in range(0, 8):
            fecha = desde + timedelta(days=desplazamiento)

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
        elif fecha == (hoy + timedelta(days=1)):
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
            dia_texto = nombres[momento.weekday()]

        segundos = max(
            0,
            int((momento - ahora).total_seconds()),
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

        proxima = self.calcular_proxima_ejecucion_tarea(tarea)

        if estado == "FINALIZADA":
            ultima_texto = "--"

            ultima = tarea.get("ultima_ejecucion")

            if ultima:
                try:
                    ultima_texto = datetime.fromisoformat(ultima).strftime(
                        "%d/%m %H:%M"
                    )
                except Exception:
                    ultima_texto = "--"

            if proxima:
                tarea["detalle_estado"] = (
                    "FINALIZADA\n"
                    f"Última ejecución: {ultima_texto}\n"
                    "Próxima ejecución: " + self.formatear_proxima_ejecucion(proxima)
                )
            else:
                tarea["detalle_estado"] = (
                    "FINALIZADA\n"
                    f"Última ejecución: {ultima_texto}\n"
                    "Próxima ejecución: Sin programación"
                )
            return

        if proxima:
            segundos = int((proxima - datetime.now()).total_seconds())

            if segundos <= UMBRAL_PROXIMA_SEGUNDOS:
                tarea["estado"] = "PRÓXIMA"
            else:
                tarea["estado"] = "EN ESPERA"

            tarea["detalle_estado"] = (
                "Próxima ejecución: " + self.formatear_proxima_ejecucion(proxima)
            )

    def actualizar_tarjeta_tarea(
        self,
        tarea_id,
    ):
        tarjeta = self.tarjetas.get(tarea_id)

        if tarjeta:
            tarjeta.actualizar_estado()

    def actualizar_tarjetas(self):
        for tarea in self.tareas:
            self.actualizar_estado_pasivo_tarea(tarea)

            tarjeta = self.tarjetas.get(tarea.get("id"))

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

            run_key = self.clave_programada_para_ahora(
                tarea,
                ahora,
            )

            if not run_key:
                continue

            if tarea.get("last_run_key") == run_key:
                continue

            if tarea.get("current_run_key") == run_key:
                continue

            if self.tarea_ejecutando_id == tarea.get("id"):
                continue

            duracion_total = self.obtener_duracion_total_tarea(tarea)

            if duracion_total <= 0:
                tarea["estado"] = "REQUIERE CONFIGURACIÓN"
                tarea["detalle_estado"] = (
                    "Llegó la hora, pero no hay acciones " "configuradas."
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

        if estado_actual == "EN PAUSA" and tarea.get("current_run_key"):
            self.continuar_ejecucion(tarea)
            return

        if estado_actual == "EN PAUSA":
            tarea["estado"] = "EN ESPERA"
            tarea["detalle_estado"] = "Programación reactivada"
            self.actualizar_chat_bin(
                f"Reactivé la programación de " f"'{tarea['nombre']}'."
            )

        elif estado_actual == "DETENIDA":
            candidata = tarea.copy()
            candidata["estado"] = "EN ESPERA"

            conflictos = self.buscar_conflictos(
                candidata,
                excluir_id=tarea_id,
            )

            if conflictos:
                ConflictDialog(
                    self,
                    "No se puede iniciar",
                    self.formatear_mensaje_conflictos(
                        candidata,
                        conflictos,
                    ),
                ).exec()
                return

            tarea["estado"] = "EN ESPERA"
            tarea["detalle_estado"] = "Programación activada"

            self.actualizar_chat_bin(
                f"Activé la programación de " f"'{tarea['nombre']}'."
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

            momento = self.calcular_proxima_ejecucion_tarea(
                tarea,
                desde=ahora,
            )

            if momento:
                candidatas.append((momento, tarea))

        if not candidatas:
            return None

        candidatas.sort(key=lambda item: item[0])

        return candidatas[0]

    # ========================================================
    # ACTUALIZAR CABECERA
    # ========================================================

    def actualizar_cabecera_operativa(self):
        # Esta función es deliberadamente segura durante el
        # arranque. Solo toca widgets de la cabecera.
        if hasattr(self, "contador_tareas"):
            self.contador_tareas.setText("TAREAS GUARDADAS\n" f"{len(self.tareas)}")

        if not hasattr(
            self,
            "proxima_cabecera",
        ):
            return

        proxima = self.calcular_proxima_tarea()

        if not proxima:
            self.proxima_cabecera.setText("PRÓXIMA TAREA\n--")
            return

        momento, tarea = proxima

        self.proxima_cabecera.setText(
            "PRÓXIMA TAREA\n"
            f"{tarea['nombre']} · "
            f"{self.formatear_proxima_ejecucion(momento)}"
        )

    # ========================================================
    # IDENTIFICAR BOTÓN DE MOUSE DE PYNPUT
    # ========================================================

    def nombre_boton_mouse_global(
        self,
        boton,
    ):
        if pynput_mouse is None:
            return "desconocido"

        if boton == pynput_mouse.Button.left:
            return "izquierdo"

        if boton == pynput_mouse.Button.right:
            return "derecho"

        if boton == pynput_mouse.Button.middle:
            return "central"

        return str(boton)

    # ========================================================
    # SERIALIZAR TECLA DE PYNPUT
    # ========================================================

    def serializar_tecla_global(
        self,
        tecla,
    ):
        if pynput_keyboard is None:
            return None

        if isinstance(
            tecla,
            pynput_keyboard.KeyCode,
        ):
            caracter = getattr(
                tecla,
                "char",
                None,
            )

            vk = getattr(
                tecla,
                "vk",
                None,
            )

            if caracter is not None:
                nombre = caracter
            elif vk is not None:
                nombre = f"VK_{vk}"
            else:
                nombre = str(tecla)

            identificador = f"vk:{vk}" if vk is not None else f"char:{repr(caracter)}"

            return {
                "id": identificador,
                "nombre": nombre,
                "caracter": caracter,
                "vk": vk,
                "especial": False,
            }

        nombre = str(tecla).replace(
            "Key.",
            "",
        )

        return {
            "id": f"key:{nombre}",
            "nombre": nombre,
            "caracter": None,
            "vk": None,
            "especial": True,
        }

    # ========================================================
    # ¿EL PUNTO PERTENECE A BIN?
    # ========================================================

    def punto_pertenece_a_bin(
        self,
        x,
        y,
    ):
        if sys.platform != "win32":
            return False

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            punto = wintypes.POINT(
                int(x),
                int(y),
            )

            user32.WindowFromPoint.argtypes = [wintypes.POINT]

            user32.WindowFromPoint.restype = wintypes.HWND

            hwnd = user32.WindowFromPoint(punto)

            if not hwnd:
                return False

            pid = wintypes.DWORD()

            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(pid),
            )

            pid_actual = int(kernel32.GetCurrentProcessId())

            return int(pid.value) == pid_actual

        except Exception:
            return False

    # ========================================================
    # INICIAR GRABADORES GLOBALES
    # ========================================================

    def iniciar_grabadores_globales(
        self,
    ):
        if pynput_mouse is None or pynput_keyboard is None:
            QMessageBox.warning(
                self,
                "Pynput no disponible",
                "BIN necesita pynput para observar "
                "mouse y teclado globalmente.\n\n"
                "Ejecuta:\n"
                "pip install pynput",
            )

            return False

        self._mouse_botones_listener = set()

        # ----------------------------------------------------
        # CALLBACK: MOVIMIENTO
        # ----------------------------------------------------

        def al_mover(
            x,
            y,
        ):
            if not self.grabando:
                return

            # Solo necesitamos movimiento mientras existe
            # algún botón presionado. Así evitamos registrar
            # miles de movimientos inútiles.
            if not self._mouse_botones_listener:
                return

            self.evento_mouse_global.emit(
                {
                    "evento": "move",
                    "x": int(x),
                    "y": int(y),
                    "botones": list(self._mouse_botones_listener),
                    "tiempo": time.monotonic(),
                }
            )

        # ----------------------------------------------------
        # CALLBACK: BOTONES
        # ----------------------------------------------------

        def al_click(
            x,
            y,
            boton,
            presionado,
        ):
            if not self.grabando:
                return

            nombre_boton = self.nombre_boton_mouse_global(boton)

            if presionado:
                self._mouse_botones_listener.add(nombre_boton)
            else:
                self._mouse_botones_listener.discard(nombre_boton)

            self.evento_mouse_global.emit(
                {
                    "evento": ("down" if presionado else "up"),
                    "x": int(x),
                    "y": int(y),
                    "boton": nombre_boton,
                    "tiempo": time.monotonic(),
                }
            )

        # ----------------------------------------------------
        # CALLBACK: SCROLL
        # ----------------------------------------------------

        def al_scroll(
            x,
            y,
            dx,
            dy,
        ):
            if not self.grabando:
                return

            self.evento_mouse_global.emit(
                {
                    "evento": "scroll",
                    "x": int(x),
                    "y": int(y),
                    "dx": int(dx),
                    "dy": int(dy),
                    "tiempo": time.monotonic(),
                }
            )

        # ----------------------------------------------------
        # CALLBACK: TECLA PRESIONADA
        # ----------------------------------------------------

        def al_presionar_tecla(
            tecla,
        ):
            if not self.grabando:
                return

            # F12 queda reservado para terminar
            # una demostración desde cualquier programa.
            if pynput_keyboard is not None and tecla == pynput_keyboard.Key.f12:
                self.solicitud_detener_grabacion.emit()
                return

            info = self.serializar_tecla_global(tecla)

            if info is None:
                return

            self.evento_teclado_global.emit(
                {
                    "evento": "down",
                    "tecla": info,
                    "tiempo": time.monotonic(),
                }
            )

        # ----------------------------------------------------
        # CALLBACK: TECLA LIBERADA
        # ----------------------------------------------------

        def al_soltar_tecla(
            tecla,
        ):
            if not self.grabando:
                return

            if pynput_keyboard is not None and tecla == pynput_keyboard.Key.f12:
                return

            info = self.serializar_tecla_global(tecla)

            if info is None:
                return

            self.evento_teclado_global.emit(
                {
                    "evento": "up",
                    "tecla": info,
                    "tiempo": time.monotonic(),
                }
            )

        try:
            self.listener_mouse_global = pynput_mouse.Listener(
                on_move=al_mover,
                on_click=al_click,
                on_scroll=al_scroll,
            )

            self.listener_teclado_global = pynput_keyboard.Listener(
                on_press=al_presionar_tecla,
                on_release=al_soltar_tecla,
                suppress=False,
            )

            self.listener_mouse_global.start()
            self.listener_teclado_global.start()

            return True

        except Exception as error:
            self.detener_grabadores_globales()

            QMessageBox.critical(
                self,
                "Error iniciando grabación",
                "BIN no pudo iniciar la captura " "global de entrada.\n\n" f"{error}",
            )

            return False

    # ========================================================
    # DETENER GRABADORES GLOBALES
    # ========================================================

    def detener_grabadores_globales(
        self,
    ):
        if self.listener_mouse_global is not None:
            try:
                self.listener_mouse_global.stop()
            except Exception:
                pass

            self.listener_mouse_global = None

        if self.listener_teclado_global is not None:
            try:
                self.listener_teclado_global.stop()
            except Exception:
                pass

            self.listener_teclado_global = None

        self._mouse_botones_listener.clear()
        self.mouse_global_presionados.clear()

        self.teclas_modificadoras_global.clear()
        self.teclas_abajo_global.clear()
        self.acciones_teclado_en_curso.clear()
        self.win_solo_pendiente = None

    # ========================================================
    # REGISTRAR ACCIÓN GLOBAL
    # ========================================================

    def registrar_accion_global(
        self,
        tipo,
        descripcion,
        contexto_objetivo=None,
        datos_extra=None,
    ):
        if not self.rutina_en_borrador:
            return None

        nuevo_id = (
            max(
                [
                    int(
                        accion.get(
                            "id",
                            0,
                        )
                    )
                    for accion in self.rutina_borrador
                ],
                default=0,
            )
            + 1
        )

        accion = {
            "id": nuevo_id,
            "tipo": tipo,
            "origen": "grabacion_global",
            "descripcion": descripcion,
            "contexto_objetivo": contexto_objetivo,
            "contexto_despues": None,
            "capturado_en": (datetime.now().isoformat()),
        }

        if datos_extra:
            accion.update(datos_extra)

        self.rutina_borrador.append(accion)

        return nuevo_id

    # ========================================================
    # COMPLETAR CONTEXTO DESPUÉS DE UNA ACCIÓN
    # ========================================================

    def completar_contexto_accion_global(
        self,
        accion_id,
    ):
        contexto_despues = self.obtener_contexto_ventana_activa()

        for accion in reversed(self.rutina_borrador):
            ids_origen = accion.get(
                "ids_origen",
                [],
            )

            if ids_origen:
                if accion_id not in ids_origen:
                    continue
            elif accion.get("id") != accion_id:
                continue

            accion["contexto_despues"] = contexto_despues

            return

    # ========================================================
    # FIRMA DE CONTEXTO PARA AGRUPACIÓN
    # ========================================================

    def firma_contexto_agrupacion(
        self,
        contexto,
    ):
        if not contexto:
            return None

        return (
            contexto.get("pid"),
            contexto.get("proceso"),
            contexto.get("titulo"),
            contexto.get("clase"),
        )

    # ========================================================
    # EXTRAER CARÁCTER AGRUPABLE
    # ========================================================

    def extraer_caracter_agrupable(
        self,
        accion,
    ):
        if accion.get("tipo") not in {
            "texto_tecla",
            "tecla",
        }:
            return None

        # En esta fase no agrupar caracteres que dependan
        # de modificadores para evitar interpretar mal símbolos.
        if accion.get("modificadores"):
            return None

        caracter = accion.get("caracter")

        if caracter is not None:
            return str(caracter)

        tecla = (
            accion.get(
                "tecla",
                "",
            )
            or ""
        ).lower()

        if tecla == "space":
            return " "

        return None

    def parece_url_o_dominio(
        self,
        texto,
    ):
        texto = str(texto or "").strip()

        if not texto:
            return False

        if any(caracter.isspace() for caracter in texto):
            return False

        minuscula = texto.lower()

        if (
            minuscula.startswith("http://")
            or minuscula.startswith("https://")
            or minuscula.startswith("www.")
        ):
            return True

        sin_ruta = minuscula.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]

        if sin_ruta in {
            "localhost",
            "127.0.0.1",
        }:
            return True

        if ":" in sin_ruta:
            host, _, puerto = sin_ruta.partition(":")

            if host in {
                "localhost",
                "127.0.0.1",
            } and (not puerto or puerto.isdigit()):
                return True

            sin_ruta = host

        partes_ip = sin_ruta.split(".")

        if len(partes_ip) == 4 and all(
            parte.isdigit() and 0 <= int(parte) <= 255 for parte in partes_ip
        ):
            return True

        if "." not in sin_ruta:
            return False

        etiquetas = sin_ruta.split(".")

        if any(not etiqueta for etiqueta in etiquetas):
            return False

        for etiqueta in etiquetas:
            limpia = etiqueta.replace(
                "-",
                "",
            )

            if not limpia.isalnum():
                return False

        extension = etiquetas[-1]

        return extension.isalpha() and 2 <= len(extension) <= 24

    def interpretar_acciones_semanticas(
        self,
        acciones,
    ):
        """
        Primera capa determinista y conservadora.

        Devuelve una lista nueva y nunca modifica destructivamente
        las acciones agrupadas originales.
        """

        if not acciones:
            return []

        navegadores = {
            "chrome.exe",
            "msedge.exe",
            "firefox.exe",
            "brave.exe",
            "opera.exe",
        }

        mapa_atajos = {
            ("ctrl", "c"): (
                "copiar",
                "Copiar",
            ),
            ("ctrl", "v"): (
                "pegar",
                "Pegar",
            ),
            ("ctrl", "x"): (
                "cortar",
                "Cortar",
            ),
            ("ctrl", "z"): (
                "deshacer",
                "Deshacer",
            ),
            ("ctrl", "y"): (
                "rehacer",
                "Rehacer",
            ),
            ("ctrl", "a"): (
                "seleccionar_todo",
                "Seleccionar todo",
            ),
            ("ctrl", "s"): (
                "guardar",
                "Guardar",
            ),
            ("ctrl", "f"): (
                "buscar",
                "Buscar",
            ),
            ("ctrl", "p"): (
                "imprimir",
                "Imprimir",
            ),
            ("alt", "tab"): (
                "cambiar_aplicacion",
                "Cambiar de aplicación",
            ),
            ("alt", "f4"): (
                "cerrar_ventana",
                "Cerrar ventana",
            ),
        }

        def copia_segura(
            valor,
        ):
            try:
                return json.loads(
                    json.dumps(
                        valor,
                        ensure_ascii=False,
                    )
                )
            except Exception:
                return valor

        def ids_acciones(
            elementos,
        ):
            ids = []

            for elemento in elementos:
                identificador = elemento.get("id")

                if identificador is not None and identificador not in ids:
                    ids.append(identificador)

            return ids

        def contexto_inicial(
            elementos,
        ):
            for elemento in elementos:
                contexto = elemento.get("contexto_objetivo")

                if contexto:
                    return copia_segura(contexto)

            return None

        def contexto_final(
            elementos,
        ):
            for elemento in reversed(elementos):
                contexto = elemento.get("contexto_despues")

                if contexto:
                    return copia_segura(contexto)

            for elemento in reversed(elementos):
                contexto = elemento.get("contexto_objetivo")

                if contexto:
                    return copia_segura(contexto)

            return None

        def agregar_cambio_contexto(
            datos,
            antes,
            despues,
        ):
            if not antes or not despues:
                return

            firma_antes = (
                antes.get("pid"),
                antes.get("proceso"),
                antes.get("titulo"),
                antes.get("clase"),
            )

            firma_despues = (
                despues.get("pid"),
                despues.get("proceso"),
                despues.get("titulo"),
                despues.get("clase"),
            )

            if firma_antes == firma_despues:
                return

            datos["cambio_contexto"] = True
            datos["proceso_antes"] = antes.get("proceso")
            datos["proceso_despues"] = despues.get("proceso")

        def crear_semantica(
            elementos,
            tipo,
            descripcion,
            confianza,
            datos=None,
        ):
            antes = contexto_inicial(elementos)

            despues = contexto_final(elementos)

            datos_semanticos = copia_segura(datos or {})

            agregar_cambio_contexto(
                datos_semanticos,
                antes,
                despues,
            )

            return {
                "id": 0,
                "tipo": tipo,
                "descripcion": descripcion,
                "acciones_origen": ids_acciones(elementos),
                "confianza": confianza,
                "datos": datos_semanticos,
                "contexto_objetivo": antes,
                "contexto_despues": despues,
            }

        def clave_atajo(
            accion,
        ):
            if accion.get("tipo") != "atajo_teclado":
                return None

            modificadores = [
                str(valor).strip().lower()
                for valor in (accion.get("modificadores") or [])
                if str(valor).strip()
            ]

            orden = {
                "ctrl": 0,
                "shift": 1,
                "alt": 2,
                "altgr": 3,
                "win": 4,
            }

            modificadores.sort(
                key=lambda valor: orden.get(
                    valor,
                    99,
                )
            )

            tecla = accion.get("caracter") or accion.get("tecla") or ""

            tecla = str(tecla).strip().lower()

            if tecla == "escape":
                tecla = "esc"

            return tuple(modificadores + [tecla])

        def es_enter(
            accion,
        ):
            if accion.get("tipo") != "tecla":
                return False

            tecla = (
                str(
                    accion.get(
                        "tecla",
                        "",
                    )
                    or ""
                )
                .strip()
                .lower()
            )

            if tecla in {
                "enter",
                "return",
            }:
                return True

            descripcion = str(
                accion.get(
                    "descripcion",
                    "",
                )
                or ""
            ).lower()

            return "enter" in descripcion

        def es_win_solo(
            accion,
        ):
            if accion.get("tipo") != "tecla":
                return False

            modificadores = [
                str(valor).strip().lower()
                for valor in (accion.get("modificadores") or [])
                if str(valor).strip()
            ]

            if modificadores:
                return False

            tecla = (
                str(
                    accion.get(
                        "tecla",
                        "",
                    )
                    or ""
                )
                .strip()
                .lower()
            )

            return tecla in {
                "cmd",
                "cmd_l",
                "cmd_r",
                "win",
                "windows",
            }

        def proceso_navegador_secuencia(
            elementos,
        ):
            procesos = set()

            for elemento in elementos:
                contexto = elemento.get("contexto_objetivo")

                if not contexto:
                    continue

                proceso = (
                    str(
                        contexto.get(
                            "proceso",
                            "",
                        )
                        or ""
                    )
                    .strip()
                    .lower()
                )

                if proceso:
                    procesos.add(proceso)

            if len(procesos) != 1:
                return None

            proceso = next(iter(procesos))

            if proceso not in navegadores:
                return None

            return proceso

        def descripcion_direccion_scroll(
            dx,
            dy,
        ):
            partes = []

            if dy > 0:
                partes.append("arriba")
            elif dy < 0:
                partes.append("abajo")

            if dx > 0:
                partes.append("derecha")
            elif dx < 0:
                partes.append("izquierda")

            return " y ".join(partes) or "sin dirección"

        resultado = []
        indice = 0

        while indice < len(acciones):
            accion = acciones[indice]

            # ------------------------------------------------
            # WINDOWS + TEXTO + ENTER
            # ------------------------------------------------

            if indice + 2 < len(acciones) and es_win_solo(accion):

                accion_texto = acciones[indice + 1]

                accion_enter = acciones[indice + 2]

                if accion_texto.get("tipo") == "escribir_texto" and es_enter(
                    accion_enter
                ):

                    secuencia = [
                        accion,
                        accion_texto,
                        accion_enter,
                    ]

                    consulta = str(
                        accion_texto.get(
                            "texto",
                            "",
                        )
                        or ""
                    ).strip()

                    despues = contexto_final(secuencia) or {}

                    proceso = str(
                        despues.get(
                            "proceso",
                            "",
                        )
                        or ""
                    ).strip()

                    ejecutable = str(
                        despues.get(
                            "ejecutable",
                            "",
                        )
                        or ""
                    ).strip()

                    resultado.append(
                        crear_semantica(
                            secuencia,
                            "abrir_aplicacion",
                            ("Abrir aplicación " f'"{consulta}"'),
                            "alta",
                            {
                                "consulta": consulta,
                                "proceso": proceso,
                                "ejecutable": ejecutable,
                            },
                        )
                    )

                    indice += 3

                    continue

            # ------------------------------------------------
            # NAVEGADOR: Ctrl+L + texto + Enter
            # ------------------------------------------------

            if indice + 2 < len(acciones) and clave_atajo(accion) == ("ctrl", "l"):
                accion_texto = acciones[indice + 1]

                accion_enter = acciones[indice + 2]

                if accion_texto.get("tipo") == "escribir_texto" and es_enter(
                    accion_enter
                ):
                    secuencia = [
                        accion,
                        accion_texto,
                        accion_enter,
                    ]

                    navegador = proceso_navegador_secuencia(secuencia)

                    if navegador:
                        destino = str(
                            accion_texto.get(
                                "texto",
                                "",
                            )
                            or ""
                        )

                        if self.parece_url_o_dominio(destino):
                            tipo = "navegar_url"
                            descripcion = f'Navegar a "{destino}"'
                        else:
                            tipo = "buscar_o_navegar"
                            descripcion = "Buscar o navegar a " f'"{destino}"'

                        resultado.append(
                            crear_semantica(
                                secuencia,
                                tipo,
                                descripcion,
                                "alta",
                                {
                                    "destino": destino,
                                    "navegador": navegador,
                                },
                            )
                        )

                        indice += 3
                        continue

            tipo_original = accion.get(
                "tipo",
                "",
            )

            # ------------------------------------------------
            # WINDOWS SOLA
            # ------------------------------------------------

            if es_win_solo(accion):

                resultado.append(
                    crear_semantica(
                        [accion],
                        "abrir_inicio",
                        "Abrir menú Inicio",
                        "alta",
                        {},
                    )
                )

                indice += 1

                continue

            # ------------------------------------------------
            # ESCRIBIR TEXTO
            # ------------------------------------------------

            if tipo_original == "escribir_texto":
                texto = str(
                    accion.get(
                        "texto",
                        "",
                    )
                    or ""
                )

                resultado.append(
                    crear_semantica(
                        [accion],
                        "escribir_texto",
                        f'Escribir "{texto}"',
                        "alta",
                        {
                            "texto": texto,
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # SCROLL AGRUPADO
            # ------------------------------------------------

            if tipo_original == "scroll_agrupado":
                dx = int(
                    accion.get(
                        "dx",
                        0,
                    )
                    or 0
                )

                dy = int(
                    accion.get(
                        "dy",
                        0,
                    )
                    or 0
                )

                pasos = max(
                    1,
                    int(
                        accion.get(
                            "pasos",
                            1,
                        )
                        or 1
                    ),
                )

                direccion = descripcion_direccion_scroll(
                    dx,
                    dy,
                )

                resultado.append(
                    crear_semantica(
                        [accion],
                        "desplazar",
                        ("Desplazar hacia " f"{direccion} · " f"{pasos} paso(s)"),
                        "alta",
                        {
                            "dx": dx,
                            "dy": dy,
                            "pasos": pasos,
                            "x": accion.get("x"),
                            "y": accion.get("y"),
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # ATAJOS CONOCIDOS
            # ------------------------------------------------

            if tipo_original == "atajo_teclado":
                clave = clave_atajo(accion)

                interpretacion = mapa_atajos.get(clave)

                if interpretacion:
                    tipo_semantico, descripcion = interpretacion

                    resultado.append(
                        crear_semantica(
                            [accion],
                            tipo_semantico,
                            descripcion,
                            "alta",
                            {
                                "atajo": list(clave),
                            },
                        )
                    )
                else:
                    resultado.append(
                        crear_semantica(
                            [accion],
                            "atajo_teclado",
                            accion.get(
                                "descripcion",
                                "Atajo de teclado",
                            ),
                            "alta",
                            {
                                "modificadores": copia_segura(
                                    accion.get(
                                        "modificadores",
                                        [],
                                    )
                                ),
                                "tecla": accion.get("tecla"),
                                "caracter": accion.get("caracter"),
                            },
                        )
                    )

                indice += 1
                continue

                # ------------------------------------------------
            # CLIC IZQUIERDO
            # ------------------------------------------------

            if tipo_original == "click":

                contexto = accion.get("contexto_objetivo") or {}

                despues = accion.get("contexto_despues") or {}

                proceso_antes = str(
                    contexto.get(
                        "proceso",
                        "",
                    )
                    or ""
                ).lower()

                proceso_despues = str(
                    despues.get(
                        "proceso",
                        "",
                    )
                    or ""
                ).lower()

                if proceso_despues and proceso_despues != proceso_antes:

                    resultado.append(
                        crear_semantica(
                            [accion],
                            "abrir_aplicacion",
                            ("Abrir aplicación " f"{proceso_despues}"),
                            "alta",
                            {
                                "consulta": (Path(proceso_despues).stem),
                                "proceso": proceso_despues,
                                "ejecutable": (
                                    despues.get(
                                        "ejecutable",
                                        "",
                                    )
                                ),
                                "x_fallback": accion.get("x"),
                                "y_fallback": accion.get("y"),
                            },
                        )
                    )

                else:

                    nombre = self.describir_contexto_ventana(
                        accion.get("contexto_objetivo")
                    )

                    resultado.append(
                        crear_semantica(
                            [accion],
                            "click",
                            (f"Clic izquierdo en {nombre}"),
                            "alta",
                            {
                                "x": accion.get("x"),
                                "y": accion.get("y"),
                                "boton": accion.get(
                                    "boton",
                                    "izquierdo",
                                ),
                            },
                        )
                    )

                indice += 1

                continue

                # ------------------------------------------------
            # DOBLE CLIC
            # ------------------------------------------------

            if tipo_original == "doble_click":

                contexto = accion.get("contexto_objetivo") or {}

                despues = accion.get("contexto_despues") or {}

                proceso = (
                    str(
                        contexto.get(
                            "proceso",
                            "",
                        )
                        or ""
                    )
                    .strip()
                    .lower()
                )

                proceso_despues = (
                    str(
                        despues.get(
                            "proceso",
                            "",
                        )
                        or ""
                    )
                    .strip()
                    .lower()
                )

                # ================================================
                # EL DOBLE CLIC ABRIÓ OTRA APLICACIÓN
                # ================================================

                if proceso and proceso_despues and proceso != proceso_despues:

                    tipo_semantico = "abrir_aplicacion"

                    descripcion = "Abrir aplicación " f"{proceso_despues}"

                    confianza = "alta"

                    datos = {
                        "consulta": (Path(proceso_despues).stem),
                        "proceso": proceso_despues,
                        "ejecutable": (
                            despues.get(
                                "ejecutable",
                                "",
                            )
                        ),
                        "x_fallback": accion.get("x"),
                        "y_fallback": accion.get("y"),
                    }

                # ================================================
                # DOBLE CLIC DENTRO DEL EXPLORADOR
                # SIN CAMBIO DE APLICACIÓN
                # ================================================

                elif proceso == "explorer.exe":

                    tipo_semantico = "abrir_elemento"

                    descripcion = "Abrir elemento con doble clic " "en Explorador"

                    confianza = "media"

                    datos = {
                        "x": accion.get("x"),
                        "y": accion.get("y"),
                        "boton": accion.get(
                            "boton",
                            "izquierdo",
                        ),
                    }

                # ================================================
                # DOBLE CLIC NORMAL
                # ================================================

                else:

                    tipo_semantico = "doble_click"

                    descripcion = "Doble clic en " + self.describir_contexto_ventana(
                        contexto
                    )

                    confianza = "alta"

                    datos = {
                        "x": accion.get("x"),
                        "y": accion.get("y"),
                        "boton": accion.get(
                            "boton",
                            "izquierdo",
                        ),
                    }

                resultado.append(
                    crear_semantica(
                        [accion],
                        tipo_semantico,
                        descripcion,
                        confianza,
                        datos,
                    )
                )

                indice += 1

                continue

            # ------------------------------------------------
            # CLIC DERECHO
            # ------------------------------------------------

            if tipo_original == "click_derecho":
                resultado.append(
                    crear_semantica(
                        [accion],
                        "abrir_menu_contextual",
                        "Abrir menú contextual",
                        "alta",
                        {
                            "x": accion.get("x"),
                            "y": accion.get("y"),
                            "boton": accion.get(
                                "boton",
                                "derecho",
                            ),
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # CLIC CENTRAL
            # ------------------------------------------------

            if tipo_original == "click_central":
                resultado.append(
                    crear_semantica(
                        [accion],
                        "click_central",
                        "Clic con botón central",
                        "alta",
                        {
                            "x": accion.get("x"),
                            "y": accion.get("y"),
                            "boton": accion.get(
                                "boton",
                                "central",
                            ),
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # ARRASTRES
            # ------------------------------------------------

            if tipo_original in {
                "arrastrar",
                "arrastre_central",
                "arrastre_derecho",
            }:
                resultado.append(
                    crear_semantica(
                        [accion],
                        "arrastrar",
                        (
                            "Arrastrar desde "
                            f"X={accion.get('x_inicio')} · "
                            f"Y={accion.get('y_inicio')} "
                            "hasta "
                            f"X={accion.get('x_fin')} · "
                            f"Y={accion.get('y_fin')}"
                        ),
                        "alta",
                        {
                            "x_inicio": accion.get("x_inicio"),
                            "y_inicio": accion.get("y_inicio"),
                            "x_fin": accion.get("x_fin"),
                            "y_fin": accion.get("y_fin"),
                            "duracion_ms": accion.get("duracion_ms"),
                            "boton": accion.get("boton"),
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # TECLAS ESPECIALES
            # ------------------------------------------------

            if tipo_original == "tecla":
                resultado.append(
                    crear_semantica(
                        [accion],
                        "tecla",
                        accion.get(
                            "descripcion",
                            "Tecla",
                        ),
                        "alta",
                        {
                            "tecla": accion.get("tecla"),
                            "caracter": accion.get("caracter"),
                            "vk": accion.get("vk"),
                            "modificadores": copia_segura(
                                accion.get(
                                    "modificadores",
                                    [],
                                )
                            ),
                        },
                    )
                )

                indice += 1
                continue

            # ------------------------------------------------
            # FALLBACK OBLIGATORIO
            # ------------------------------------------------

            datos_fallback = {}

            for clave, valor in accion.items():
                if clave in {
                    "id",
                    "tipo",
                    "descripcion",
                    "contexto_objetivo",
                    "contexto_despues",
                }:
                    continue

                datos_fallback[clave] = copia_segura(valor)

            resultado.append(
                crear_semantica(
                    [accion],
                    tipo_original or "accion",
                    accion.get(
                        "descripcion",
                        "Acción",
                    ),
                    "baja",
                    datos_fallback,
                )
            )

            indice += 1

        for nuevo_id, accion in enumerate(
            resultado,
            start=1,
        ):
            accion["id"] = nuevo_id

        return resultado

    # ========================================================
    # AGRUPAR ACCIONES GRABADAS
    # ========================================================

    def agrupar_acciones_grabadas(
        self,
    ):
        if not self.rutina_borrador:
            return

        originales = self.rutina_borrador
        limpias = []

        texto = None
        scroll = None

        def copiar(
            accion,
        ):
            copia = dict(accion)

            ids = list(
                copia.get(
                    "ids_origen",
                    [],
                )
            )

            id_original = copia.get("id")

            if id_original is not None and id_original not in ids:
                ids.append(id_original)

            copia["ids_origen"] = ids

            return copia

        # ----------------------------------------------------
        # CERRAR BLOQUE DE TEXTO
        # ----------------------------------------------------

        def vaciar_texto():
            nonlocal texto

            if texto is None:
                return

            contenido = texto["contenido"]

            if contenido:
                accion = copiar(texto["primera"])

                accion.update(
                    {
                        "tipo": "escribir_texto",
                        "origen": "grabacion_global_agrupada",
                        "texto": contenido,
                        "descripcion": (f'Escribir texto · "{contenido}"'),
                        "eventos_agrupados": len(texto["ids"]),
                        "ids_origen": list(texto["ids"]),
                        "contexto_despues": (texto["ultima"].get("contexto_despues")),
                    }
                )

                for clave in (
                    "tecla",
                    "caracter",
                    "vk",
                    "modificadores",
                    "duracion_ms",
                ):
                    accion.pop(
                        clave,
                        None,
                    )

                limpias.append(accion)

            texto = None

        # ----------------------------------------------------
        # CLAVE DE SCROLL
        # ----------------------------------------------------

        def clave_scroll(
            accion,
        ):
            dx = int(
                accion.get(
                    "dx",
                    0,
                )
            )

            dy = int(
                accion.get(
                    "dy",
                    0,
                )
            )

            return (
                1 if dx > 0 else -1 if dx < 0 else 0,
                1 if dy > 0 else -1 if dy < 0 else 0,
                self.firma_contexto_agrupacion(accion.get("contexto_objetivo")),
            )

        def descripcion_scroll(
            dx,
            dy,
        ):
            partes = []

            if dy > 0:
                partes.append("arriba")
            elif dy < 0:
                partes.append("abajo")

            if dx > 0:
                partes.append("derecha")
            elif dx < 0:
                partes.append("izquierda")

            return " + ".join(partes) or "sin dirección"

        # ----------------------------------------------------
        # CERRAR BLOQUE DE SCROLL
        # ----------------------------------------------------

        def vaciar_scroll():
            nonlocal scroll

            if scroll is None:
                return

            accion = copiar(scroll["primera"])

            dx_total = scroll["dx"]
            dy_total = scroll["dy"]

            pasos = max(
                1,
                abs(dx_total),
                abs(dy_total),
            )

            contexto = accion.get("contexto_objetivo")

            nombre = self.describir_contexto_ventana(contexto)

            accion.update(
                {
                    "tipo": "scroll_agrupado",
                    "origen": "grabacion_global_agrupada",
                    "dx": dx_total,
                    "dy": dy_total,
                    "pasos": pasos,
                    "eventos_agrupados": len(scroll["ids"]),
                    "ids_origen": list(scroll["ids"]),
                    "contexto_despues": (scroll["ultima"].get("contexto_despues")),
                    "x": scroll["ultima"].get(
                        "x",
                        accion.get("x"),
                    ),
                    "y": scroll["ultima"].get(
                        "y",
                        accion.get("y"),
                    ),
                    "descripcion": (
                        f"Scroll "
                        f"{descripcion_scroll(dx_total, dy_total)} "
                        f"· {pasos} paso(s) · "
                        f"{nombre}"
                    ),
                }
            )

            limpias.append(accion)

            scroll = None

        # ====================================================
        # RECORRER ACCIONES
        # ====================================================

        for original in originales:
            accion = copiar(original)

            caracter = self.extraer_caracter_agrupable(accion)

            # ------------------------------------------------
            # TEXTO
            # ------------------------------------------------

            if caracter is not None:
                vaciar_scroll()

                if texto is None:
                    texto = {
                        "contenido": "",
                        "primera": accion,
                        "ultima": accion,
                        "ids": [],
                    }

                texto["contenido"] += caracter
                texto["ultima"] = accion
                texto["ids"].extend(accion["ids_origen"])

                continue

            vaciar_texto()

            # ------------------------------------------------
            # SCROLL
            # ------------------------------------------------

            if accion.get("tipo") == "scroll":
                clave = clave_scroll(accion)

                if scroll is None or scroll["clave"] != clave:
                    vaciar_scroll()

                    scroll = {
                        "clave": clave,
                        "primera": accion,
                        "ultima": accion,
                        "dx": 0,
                        "dy": 0,
                        "ids": [],
                    }

                scroll["dx"] += int(
                    accion.get(
                        "dx",
                        0,
                    )
                )

                scroll["dy"] += int(
                    accion.get(
                        "dy",
                        0,
                    )
                )

                scroll["ultima"] = accion
                scroll["ids"].extend(accion["ids_origen"])

                continue

            vaciar_scroll()

            # ------------------------------------------------
            # ATAJOS
            # ------------------------------------------------

            if accion.get("tipo") == "atajo_teclado":
                modificadores = list(accion.get("modificadores") or [])

                tecla = accion.get("caracter") or accion.get(
                    "tecla",
                    "",
                )

                tecla = str(tecla)

                if len(tecla) == 1 and tecla.isalpha():
                    tecla = tecla.upper()

                accion["descripcion"] = "Atajo de teclado · " + " + ".join(
                    modificadores + [tecla]
                )

            limpias.append(accion)

        vaciar_texto()
        vaciar_scroll()

        # ----------------------------------------------------
        # RENUMERAR
        # ----------------------------------------------------

        for indice, accion in enumerate(
            limpias,
            start=1,
        ):
            accion["id"] = indice

        self.rutina_borrador = limpias

    # ========================================================
    # CONFIRMAR CLIC IZQUIERDO SIMPLE
    # ========================================================

    def confirmar_click_global_pendiente(
        self,
    ):
        pendiente = self.click_global_pendiente

        self.click_global_pendiente = None

        if pendiente is None:
            return

        contexto = pendiente.get("contexto")

        nombre_contexto = self.describir_contexto_ventana(contexto)

        x = pendiente["x"]
        y = pendiente["y"]

        accion_id = self.registrar_accion_global(
            "click",
            ("Clic izquierdo · " f"{nombre_contexto}\n" f"X={x} · Y={y}"),
            contexto,
            {
                "boton": "izquierdo",
                "x": x,
                "y": y,
            },
        )

        if accion_id is not None:
            QTimer.singleShot(
                450,
                lambda accion_id=accion_id: self.completar_contexto_accion_global(
                    accion_id
                ),
            )

    # ========================================================
    # PROCESAR CLIC IZQUIERDO / DOBLE CLIC
    # ========================================================

    def procesar_click_izquierdo_global(
        self,
        x,
        y,
        contexto,
        momento,
    ):
        try:
            intervalo_ms = int(ctypes.windll.user32.GetDoubleClickTime())
        except Exception:
            intervalo_ms = 500

        pendiente = self.click_global_pendiente

        if pendiente is not None:
            diferencia = momento - pendiente["tiempo"]

            dx = x - pendiente["x"]

            dy = y - pendiente["y"]

            distancia_cuadrada = dx * dx + dy * dy

            if diferencia <= intervalo_ms / 1000 and distancia_cuadrada <= 64:
                self.timer_click_global.stop()

                self.click_global_pendiente = None

                nombre_contexto = self.describir_contexto_ventana(contexto)

                accion_id = self.registrar_accion_global(
                    "doble_click",
                    ("Doble clic izquierdo · " f"{nombre_contexto}\n" f"X={x} · Y={y}"),
                    contexto,
                    {
                        "boton": "izquierdo",
                        "x": x,
                        "y": y,
                    },
                )

                if accion_id is not None:
                    QTimer.singleShot(
                        600,
                        lambda accion_id=accion_id: self.completar_contexto_accion_global(
                            accion_id
                        ),
                    )

                return

            # Segundo clic diferente:
            # confirmar inmediatamente el primero.
            self.timer_click_global.stop()

            self.confirmar_click_global_pendiente()

        self.click_global_pendiente = {
            "x": int(x),
            "y": int(y),
            "tiempo": momento,
            "contexto": contexto,
        }

        self.timer_click_global.start(intervalo_ms + 60)

    # ========================================================
    # PROCESAR EVENTO GLOBAL DE MOUSE
    # ========================================================

    def procesar_evento_mouse_global(
        self,
        evento,
    ):
        if not self.grabando:
            return

        tipo_evento = evento.get("evento")

        x = int(
            evento.get(
                "x",
                0,
            )
        )

        y = int(
            evento.get(
                "y",
                0,
            )
        )

        momento = float(
            evento.get(
                "tiempo",
                time.monotonic(),
            )
        )

        # ----------------------------------------------------
        # BOTÓN PRESIONADO
        # ----------------------------------------------------

        if tipo_evento == "down":
            boton = evento.get("boton")

            ignorar = self.punto_pertenece_a_bin(
                x,
                y,
            )

            contexto = None

            if not ignorar:
                contexto = self.obtener_contexto_ventana_en_punto(
                    x,
                    y,
                )

            self.mouse_global_presionados[boton] = {
                "x_inicio": x,
                "y_inicio": y,
                "x_ultimo": x,
                "y_ultimo": y,
                "inicio": momento,
                "movido": False,
                "ignorar": ignorar,
                "contexto": contexto,
            }

            return

        # ----------------------------------------------------
        # MOVIMIENTO MIENTRAS SE MANTIENE UN BOTÓN
        # ----------------------------------------------------

        if tipo_evento == "move":
            for boton in evento.get(
                "botones",
                [],
            ):
                estado = self.mouse_global_presionados.get(boton)

                if not estado:
                    continue

                estado["x_ultimo"] = x
                estado["y_ultimo"] = y

                dx = x - estado["x_inicio"]

                dy = y - estado["y_inicio"]

                if dx * dx + dy * dy >= 25:
                    estado["movido"] = True

            return

        # ----------------------------------------------------
        # BOTÓN LIBERADO
        # ----------------------------------------------------

        if tipo_evento == "up":
            boton = evento.get("boton")

            estado = self.mouse_global_presionados.pop(
                boton,
                None,
            )

            if not estado:
                return

            if estado.get("ignorar"):
                return

            contexto = estado.get("contexto")

            duracion_ms = int(
                max(
                    0,
                    momento - estado["inicio"],
                )
                * 1000
            )

            # ------------------------------------------------
            # ARRASTRE
            # ------------------------------------------------

            if estado.get("movido"):
                if boton == "central":
                    descripcion_boton = "Arrastre con botón central"
                    tipo_accion = "arrastre_central"

                elif boton == "derecho":
                    descripcion_boton = "Arrastre con botón derecho"
                    tipo_accion = "arrastre_derecho"

                else:
                    descripcion_boton = "Arrastrar y soltar"
                    tipo_accion = "arrastrar"

                accion_id = self.registrar_accion_global(
                    tipo_accion,
                    (
                        f"{descripcion_boton}\n"
                        f"Desde "
                        f"X={estado['x_inicio']} · "
                        f"Y={estado['y_inicio']}\n"
                        f"Hasta X={x} · Y={y}"
                    ),
                    contexto,
                    {
                        "boton": boton,
                        "x_inicio": int(estado["x_inicio"]),
                        "y_inicio": int(estado["y_inicio"]),
                        "x_fin": x,
                        "y_fin": y,
                        "duracion_ms": duracion_ms,
                    },
                )

                if accion_id is not None:
                    QTimer.singleShot(
                        500,
                        lambda accion_id=accion_id: self.completar_contexto_accion_global(
                            accion_id
                        ),
                    )

                return

            # ------------------------------------------------
            # CLIC IZQUIERDO
            # ------------------------------------------------

            if boton == "izquierdo":
                self.procesar_click_izquierdo_global(
                    x,
                    y,
                    contexto,
                    momento,
                )

                return

            # ------------------------------------------------
            # CLIC DERECHO
            # ------------------------------------------------

            if boton == "derecho":
                nombre_contexto = self.describir_contexto_ventana(contexto)

                accion_id = self.registrar_accion_global(
                    "click_derecho",
                    ("Clic derecho · " f"{nombre_contexto}\n" f"X={x} · Y={y}"),
                    contexto,
                    {
                        "boton": "derecho",
                        "x": x,
                        "y": y,
                    },
                )

                if accion_id is not None:
                    QTimer.singleShot(
                        400,
                        lambda accion_id=accion_id: self.completar_contexto_accion_global(
                            accion_id
                        ),
                    )

                return

            # ------------------------------------------------
            # BOTÓN CENTRAL / RUEDA PRESIONADA
            # ------------------------------------------------

            if boton == "central":
                nombre_contexto = self.describir_contexto_ventana(contexto)

                accion_id = self.registrar_accion_global(
                    "click_central",
                    (
                        "Clic botón central / rueda · "
                        f"{nombre_contexto}\n"
                        f"X={x} · Y={y}"
                    ),
                    contexto,
                    {
                        "boton": "central",
                        "x": x,
                        "y": y,
                    },
                )

                if accion_id is not None:
                    QTimer.singleShot(
                        400,
                        lambda accion_id=accion_id: self.completar_contexto_accion_global(
                            accion_id
                        ),
                    )

                return

        # ----------------------------------------------------
        # SCROLL REAL
        # ----------------------------------------------------

        if tipo_evento == "scroll":
            if self.punto_pertenece_a_bin(
                x,
                y,
            ):
                return

            dx = int(
                evento.get(
                    "dx",
                    0,
                )
            )

            dy = int(
                evento.get(
                    "dy",
                    0,
                )
            )

            contexto = self.obtener_contexto_ventana_en_punto(
                x,
                y,
            )

            nombre_contexto = self.describir_contexto_ventana(contexto)

            if dy > 0:
                direccion_vertical = "arriba"
            elif dy < 0:
                direccion_vertical = "abajo"
            else:
                direccion_vertical = ""

            if dx > 0:
                direccion_horizontal = "derecha"
            elif dx < 0:
                direccion_horizontal = "izquierda"
            else:
                direccion_horizontal = ""

            direcciones = [
                valor
                for valor in [
                    direccion_vertical,
                    direccion_horizontal,
                ]
                if valor
            ]

            texto_direccion = " + ".join(direcciones) or "sin dirección"

            self.registrar_accion_global(
                "scroll",
                (
                    f"Scroll {texto_direccion} · "
                    f"{nombre_contexto}\n"
                    f"ΔX={dx} · ΔY={dy}"
                ),
                contexto,
                {
                    "x": x,
                    "y": y,
                    "dx": dx,
                    "dy": dy,
                },
            )

    # ========================================================
    # MODIFICADOR DE TECLADO
    # ========================================================

    def modificador_teclado_global(
        self,
        nombre,
    ):
        mapa = {
            "ctrl": "Ctrl",
            "ctrl_l": "Ctrl",
            "ctrl_r": "Ctrl",
            "shift": "Shift",
            "shift_l": "Shift",
            "shift_r": "Shift",
            "alt": "Alt",
            "alt_l": "Alt",
            "alt_r": "Alt",
            "alt_gr": "AltGr",
            "cmd": "Win",
            "cmd_l": "Win",
            "cmd_r": "Win",
        }

        return mapa.get(nombre)

    # ========================================================
    # NOMBRE LEGIBLE DE TECLA
    # ========================================================

    def nombre_tecla_global(
        self,
        info,
    ):
        caracter = info.get("caracter")

        if caracter:
            return caracter

        nombre = info.get(
            "nombre",
            "",
        )

        mapa = {
            "enter": "Enter",
            "tab": "Tab",
            "esc": "Esc",
            "space": "Espacio",
            "backspace": "Backspace",
            "delete": "Delete",
            "insert": "Insert",
            "home": "Home",
            "end": "End",
            "page_up": "Page Up",
            "page_down": "Page Down",
            "left": "Flecha izquierda",
            "right": "Flecha derecha",
            "up": "Flecha arriba",
            "down": "Flecha abajo",
            "caps_lock": "Caps Lock",
            "num_lock": "Num Lock",
            "print_screen": "Print Screen",
            "pause": "Pause",
            "menu": "Menú",
        }

        if nombre in mapa:
            return mapa[nombre]

        if len(nombre) >= 2 and nombre.startswith("f") and nombre[1:].isdigit():
            return nombre.upper()

        return nombre

    # ========================================================
    # ACTUALIZAR DURACIÓN DE UNA TECLA
    # ========================================================

    def actualizar_duracion_tecla_global(
        self,
        accion_id,
        duracion_ms,
    ):
        for accion in reversed(self.rutina_borrador):
            if accion.get("id") == accion_id:
                accion["duracion_ms"] = int(duracion_ms)

                return

    # ========================================================
    # PROCESAR EVENTO GLOBAL DE TECLADO
    # ========================================================

    def procesar_evento_teclado_global(
        self,
        evento,
    ):
        if not self.grabando:
            return

        info = evento.get("tecla")

        if not info:
            return

        nombre = info.get(
            "nombre",
            "",
        )

        identificador = info.get(
            "id",
            nombre,
        )

        modificador = self.modificador_teclado_global(nombre)

        tipo_evento = evento.get("evento")

        momento = float(
            evento.get(
                "tiempo",
                time.monotonic(),
            )
        )

        # ====================================================
        # DOWN
        # ====================================================

        if tipo_evento == "down":

            if modificador:

                if (
                    modificador == "Win"
                    and "Win" not in self.teclas_modificadoras_global
                ):

                    self.win_solo_pendiente = {
                        "inicio": momento,
                        "nombre": nombre,
                        "info": dict(info),
                        "contexto": (self.obtener_contexto_ventana_activa()),
                        "usado_como_modificador": False,
                    }

                self.teclas_modificadoras_global.add(modificador)

                return

            if (
                "Win" in self.teclas_modificadoras_global
                and self.win_solo_pendiente is not None
            ):

                self.win_solo_pendiente["usado_como_modificador"] = True

            if identificador in self.teclas_abajo_global:
                return

            self.teclas_abajo_global.add(identificador)

            contexto = self.obtener_contexto_ventana_activa()

            modificadores = sorted(
                self.teclas_modificadoras_global,
                key=lambda valor: {
                    "Ctrl": 0,
                    "Shift": 1,
                    "Alt": 2,
                    "AltGr": 3,
                    "Win": 4,
                }.get(
                    valor,
                    99,
                ),
            )

            tecla_legible = self.nombre_tecla_global(info)

            combinacion = modificadores + [tecla_legible]

            texto_combinacion = " + ".join(combinacion)

            if any(
                modificador_actual
                in {
                    "Ctrl",
                    "Alt",
                    "AltGr",
                    "Win",
                }
                for modificador_actual in modificadores
            ):

                tipo_accion = "atajo_teclado"

                descripcion = "Atajo de teclado · " f"{texto_combinacion}"

            elif "Shift" in modificadores:

                tipo_accion = "tecla"

                descripcion = "Tecla · " f"{texto_combinacion}"

            elif info.get("caracter") is not None:

                tipo_accion = "texto_tecla"

                descripcion = "Escribir tecla · " f"{tecla_legible}"

            else:

                tipo_accion = "tecla"

                descripcion = "Tecla · " f"{tecla_legible}"

            accion_id = self.registrar_accion_global(
                tipo_accion,
                descripcion,
                contexto,
                {
                    "tecla": nombre,
                    "caracter": info.get("caracter"),
                    "vk": info.get("vk"),
                    "modificadores": modificadores,
                },
            )

            if accion_id is not None:

                self.acciones_teclado_en_curso[identificador] = {
                    "accion_id": accion_id,
                    "inicio": momento,
                }

                QTimer.singleShot(
                    300,
                    lambda accion_id=accion_id: self.completar_contexto_accion_global(
                        accion_id
                    ),
                )

            return

        # ====================================================
        # UP
        # ====================================================

        if tipo_evento == "up":

            if modificador:

                self.teclas_modificadoras_global.discard(modificador)

                if modificador == "Win":

                    pendiente = self.win_solo_pendiente

                    self.win_solo_pendiente = None

                    if pendiente and not pendiente.get(
                        "usado_como_modificador",
                        False,
                    ):

                        duracion_ms = int(
                            max(
                                0.0,
                                momento
                                - float(
                                    pendiente.get(
                                        "inicio",
                                        momento,
                                    )
                                ),
                            )
                            * 1000
                        )

                        accion_id = self.registrar_accion_global(
                            "tecla",
                            "Tecla · Win",
                            pendiente.get("contexto"),
                            {
                                "tecla": pendiente.get(
                                    "nombre",
                                    nombre,
                                ),
                                "caracter": None,
                                "vk": pendiente.get(
                                    "info",
                                    {},
                                ).get("vk"),
                                "modificadores": [],
                                "duracion_ms": duracion_ms,
                            },
                        )

                        if accion_id is not None:

                            QTimer.singleShot(
                                350,
                                lambda accion_id=accion_id: self.completar_contexto_accion_global(
                                    accion_id
                                ),
                            )

                return

            self.teclas_abajo_global.discard(identificador)

            datos_inicio = self.acciones_teclado_en_curso.pop(
                identificador,
                None,
            )

            if not datos_inicio:
                return

            duracion_ms = int(
                max(
                    0,
                    momento - datos_inicio["inicio"],
                )
                * 1000
            )

            self.actualizar_duracion_tecla_global(
                datos_inicio["accion_id"],
                duracion_ms,
            )

    # ========================================================
    # DETENER GRABACIÓN CON F12
    # ========================================================

    def detener_grabacion_desde_atajo(
        self,
    ):
        if not self.grabando:
            return

        self.alternar_grabacion()

    # ========================================================
    # CREAR BARRA FLOTANTE DE GRABACIÓN
    # ========================================================

    # ========================================================
    # CREAR BARRA FLOTANTE DE GRABACIÓN
    # ========================================================

    def crear_barra_grabacion(
        self,
    ):
        if self.barra_grabacion is not None:
            return

        self.barra_grabacion = QWidget(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )

        self.barra_grabacion.setObjectName("barra_grabacion")

        self.barra_grabacion.setAttribute(
            Qt.WA_DeleteOnClose,
            False,
        )

        self.barra_grabacion.setStyleSheet(f"""
            QWidget#barra_grabacion {{
                background-color: rgba(7, 10, 18, 235);
                border: 1px solid {BORGONA};
                border-radius: 14px;
            }}

            QLabel {{
                color: {TEXTO};
                font-size: 12px;
                font-weight: 700;
            }}

            QPushButton {{
                background-color: {ROJO};
                color: white;
                border: 1px solid {BORGONA};
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 800;
            }}

            QPushButton:hover {{
                background-color: {BORGONA_CLARO};
            }}
        """)

        layout = QHBoxLayout(self.barra_grabacion)

        layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        layout.setSpacing(10)

        self.label_barra_grabacion = QLabel("● BIN grabando demostración")

        self.boton_detener_barra = QPushButton("DETENER DEMOSTRACIÓN")

        self.boton_detener_barra.clicked.connect(
            self.detener_grabacion_desde_boton_flotante
        )

        layout.addWidget(self.label_barra_grabacion)

        layout.addWidget(self.boton_detener_barra)

        self.barra_grabacion.adjustSize()

    # ========================================================
    # MOSTRAR BARRA FLOTANTE
    # ========================================================

    def mostrar_barra_grabacion(
        self,
    ):
        self.crear_barra_grabacion()

        if self.barra_grabacion is None:
            return

        pantalla = QApplication.primaryScreen()

        if pantalla is None:
            self.barra_grabacion.show()
            return

        area = pantalla.availableGeometry()

        self.barra_grabacion.adjustSize()

        ancho = self.barra_grabacion.width()
        alto = self.barra_grabacion.height()

        margen = 18

        x = area.right() - ancho - margen
        y = area.top() + margen

        self.barra_grabacion.move(
            x,
            y,
        )

        self.barra_grabacion.show()
        self.barra_grabacion.raise_()

    # ========================================================
    # OCULTAR BARRA FLOTANTE
    # ========================================================

    def ocultar_barra_grabacion(
        self,
    ):
        if self.barra_grabacion is not None:
            self.barra_grabacion.hide()

    # ========================================================
    # DETENER GRABACIÓN DESDE BOTÓN FLOTANTE
    # ========================================================

    def detener_grabacion_desde_boton_flotante(
        self,
    ):
        if not self.grabando:
            return

        self.alternar_grabacion()

    # ========================================================
    # MOSTRAR / DETENER RUTINA
    # GRABACIÓN GLOBAL REAL
    # ========================================================

    def alternar_grabacion(
        self,
    ):
        # ====================================================
        # INICIAR
        # ====================================================

        if not self.grabando:
            if pynput_mouse is None or pynput_keyboard is None:
                QMessageBox.warning(
                    self,
                    "Pynput no instalado",
                    "BIN necesita pynput para observar "
                    "las acciones reales del sistema.\n\n"
                    "Ejecuta:\n"
                    "pip install pynput",
                )

                return

            self.grabando = True

            self.rutina_en_borrador = True
            self.rutina_borrador = []
            self.rutina_borrador_semantica = []

            self.duracion_rutina_borrador = 0
            self.inicio_grabacion = datetime.now()

            self.click_global_pendiente = None

            self.mouse_global_presionados.clear()
            self.teclas_modificadoras_global.clear()
            self.teclas_abajo_global.clear()
            self.acciones_teclado_en_curso.clear()
            self.win_solo_pendiente = None

            # BIN ya no debe tapar el escritorio.
            self.establecer_bin_siempre_visible(False)

            # Mientras grabamos deshabilitamos la interacción
            # artificial del Visor IA.
            if hasattr(
                self,
                "visor_imagen",
            ):
                self.visor_imagen.setEnabled(False)

            iniciado = self.iniciar_grabadores_globales()

            if not iniciado:
                self.grabando = False
                self.rutina_en_borrador = False
                self.inicio_grabacion = None

                if hasattr(
                    self,
                    "visor_imagen",
                ):
                    self.visor_imagen.setEnabled(True)

                return

            self.boton_grabar.setText("■ DETENER GRABACIÓN")

            self.estado_bin.setText("● BIN OBSERVANDO WINDOWS")

            self.estado_bin.setStyleSheet(f"""
                color: {AMARILLO};
                font-weight: 800;
                """)

            self.actualizar_estado_cabecera_visor(
                "Grabando demostración",
                "",
                AMARILLO,
            )

            self.actualizar_chat_bin(
                "Grabación global iniciada.\n\n"
                "Usa Windows normalmente. "
                "BIN observará mouse y teclado "
                "sin bloquear las acciones.\n\n"
                "Puedes detenerla con F12 "
                "o con el botón flotante."
            )

            self.mostrar_barra_grabacion()

            if hasattr(
                self,
                "mensaje_visor",
            ):
                self.mensaje_visor.setText(
                    "GRABACIÓN GLOBAL ACTIVA\n\n"
                    "Usa Windows normalmente.\n"
                    "F12 o botón flotante = detener."
                )

            self.refrescar_panel_acciones()

            # Dejamos unos milisegundos para que se actualice
            # la interfaz y luego apartamos BIN.
            QTimer.singleShot(
                450,
                self.showMinimized,
            )

            return

        # ====================================================
        # DETENER
        # ====================================================

        # Si existe un clic simple esperando a comprobar
        # si era doble clic, lo guardamos antes de detener.
        if self.click_global_pendiente is not None:
            self.timer_click_global.stop()

            self.confirmar_click_global_pendiente()

        self.grabando = False

        self.detener_grabadores_globales()
        self.ocultar_barra_grabacion()

        # Limpiar y compactar la demostración
        # antes de interpretarla y mostrarla en el panel.
        self.agrupar_acciones_grabadas()

        self.rutina_borrador_semantica = self.interpretar_acciones_semanticas(
            self.rutina_borrador
        )

        ahora = datetime.now()

        if self.inicio_grabacion:
            segundos = max(
                1,
                int((ahora - self.inicio_grabacion).total_seconds()),
            )
        else:
            segundos = 1

        self.duracion_rutina_borrador = segundos

        self.inicio_grabacion = None

        self.actualizar_estado_cabecera_visor(
            "Rutina capturada",
            f"· Duración: {segundos_a_hms(segundos)}",
            VERDE,
        )

        if hasattr(
            self,
            "visor_imagen",
        ):
            self.visor_imagen.setEnabled(True)

        self.boton_grabar.setText("● MOSTRAR RUTINA")

        self.estado_bin.setText("● BIN OPERATIVO")

        self.estado_bin.setStyleSheet(f"""
            color: {VERDE};
            font-weight: 800;
            """)

        # Recuperar la interfaz de BIN.
        self.showNormal()
        self.raise_()
        self.activateWindow()

        self.actualizar_chat_bin(
            "Detuve la grabación global.\n\n"
            f"Duración: "
            f"{segundos_a_hms(segundos)}\n"
            f"Eventos capturados: "
            f"{len(self.rutina_borrador)}.\n"
            f"Acciones semánticas: "
            f"{len(self.rutina_borrador_semantica)}.\n\n"
            "Revisa el Panel de acciones."
        )

        if hasattr(
            self,
            "mensaje_visor",
        ):
            self.mensaje_visor.setText(
                "RUTINA CAPTURADA\n\n"
                f"Duración: "
                f"{segundos_a_hms(segundos)}\n"
                f"Acciones: "
                f"{len(self.rutina_borrador)}"
            )

        self.refrescar_panel_acciones()

    # ========================================================
    # PANTALLA COMPLETA
    # ========================================================

    def alternar_pantalla_completa(self):

        self.pantalla_completa = not self.pantalla_completa

        if self.pantalla_completa:

            self.showFullScreen()

            self.boton_pantalla_completa.setText("⛶ SALIR DE PANTALLA COMPLETA")

        else:

            self.showNormal()

            self.boton_pantalla_completa.setText("⛶ PANTALLA COMPLETA")

    # ========================================================
    # RELOJ
    # ========================================================

    def actualizar_reloj(self):

        self.hora.setText(datetime.now().strftime("%H:%M:%S"))

        self.actualizar_cabecera_operativa()

    # ========================================================
    # MONITOREO DEL SISTEMA
    # ========================================================

    def actualizar_sistema(self):

        cpu = psutil.cpu_percent()

        memoria = psutil.virtual_memory()

        self.cpu_label.setText(f"CPU   " f"{cpu:.0f} %")

        self.ram_label.setText(f"RAM   " f"{memoria.percent:.0f} %")

    # ========================================================
    # EXCLUIR BIN DE LA CAPTURA DE WINDOWS
    # ========================================================

    def excluir_bin_de_captura(self):

        if sys.platform != "win32":
            return False

        try:

            hwnd = int(self.winId())

            resultado = ctypes.windll.user32.SetWindowDisplayAffinity(
                hwnd,
                WDA_EXCLUDEFROMCAPTURE,
            )

            if resultado:

                self.bin_excluido_de_captura = True

                if hasattr(
                    self,
                    "mensaje_chat",
                ):

                    self.mensaje_chat.setText(
                        "BIN: Mi ventana fue excluida " "de la captura del escritorio."
                    )

                return True

            self.bin_excluido_de_captura = False

            if hasattr(
                self,
                "mensaje_chat",
            ):

                self.mensaje_chat.setText(
                    "BIN: Windows no permitió excluir " "mi ventana de la captura."
                )

            return False

        except Exception as error:

            self.bin_excluido_de_captura = False

            if hasattr(
                self,
                "mensaje_chat",
            ):

                self.mensaje_chat.setText(
                    "BIN: No pude excluir mi ventana " "de la captura.\n\n" f"{error}"
                )

            return False

    # ========================================================
    # OBTENER GEOMETRÍA DEL MONITOR CAPTURADO
    # ========================================================

    def actualizar_geometria_monitor_captura(self):

        if mss is None:
            return False

        try:

            with mss.mss() as capturador:

                monitores = capturador.monitors

                if len(monitores) <= 1:

                    self.geometria_monitor_captura = None

                    return False

                indice = self.monitor_captura

                if indice <= 0 or indice >= len(monitores):

                    indice = 1

                monitor = monitores[indice]

                self.geometria_monitor_captura = {
                    "left": int(monitor["left"]),
                    "top": int(monitor["top"]),
                    "width": int(monitor["width"]),
                    "height": int(monitor["height"]),
                }

                return True

        except Exception as error:

            self.geometria_monitor_captura = None

            self.actualizar_chat_bin(
                "No pude obtener la geometría " "del monitor.\n\n" f"{error}"
            )

            return False

            # ========================================================

    # MANTENER BIN ENCIMA DURANTE UNA DEMOSTRACIÓN
    # ========================================================

    def establecer_bin_siempre_visible(
        self,
        activo,
    ):

        if sys.platform != "win32":
            return

        try:

            hwnd = int(self.winId())

            destino = HWND_TOPMOST if activo else HWND_NOTOPMOST

            ctypes.windll.user32.SetWindowPos(
                hwnd,
                destino,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

        except Exception as error:

            self.actualizar_chat_bin(
                "No pude cambiar temporalmente "
                "la prioridad visual de BIN.\n\n"
                f"{error}"
            )

    # ========================================================
    # ENVIAR CLIC IZQUIERDO AL ESCRITORIO REAL
    # ========================================================
    # ========================================================
    # PUENTE FÍSICO DE MOUSE
    # ========================================================

    def ejecutar_mouse_fisico(
        self,
        x_real,
        y_real,
        tipo,
        delta=0,
    ):
        if sys.platform != "win32" or BIN_SEND_INPUT is None:
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = int(self.winId())

        def crear_entrada_mouse(
            flags,
            mouse_data=0,
        ):
            entrada = BINInput()

            entrada.type = 0

            entrada.mi = BINMouseInput(
                0,
                0,
                ctypes.c_uint32(int(mouse_data) & 0xFFFFFFFF).value,
                int(flags),
                0,
                0,
            )

            return entrada

        if tipo == "click":

            entradas = [
                crear_entrada_mouse(MOUSEEVENTF_LEFTDOWN),
                crear_entrada_mouse(MOUSEEVENTF_LEFTUP),
            ]

        elif tipo == "doble_click":

            entradas = [
                crear_entrada_mouse(MOUSEEVENTF_LEFTDOWN),
                crear_entrada_mouse(MOUSEEVENTF_LEFTUP),
                crear_entrada_mouse(MOUSEEVENTF_LEFTDOWN),
                crear_entrada_mouse(MOUSEEVENTF_LEFTUP),
            ]

        elif tipo == "click_derecho":

            entradas = [
                crear_entrada_mouse(MOUSEEVENTF_RIGHTDOWN),
                crear_entrada_mouse(MOUSEEVENTF_RIGHTUP),
            ]

        elif tipo == "click_central":

            entradas = [
                crear_entrada_mouse(MOUSEEVENTF_MIDDLEDOWN),
                crear_entrada_mouse(MOUSEEVENTF_MIDDLEUP),
            ]

        elif tipo == "scroll":

            entradas = [
                crear_entrada_mouse(
                    MOUSEEVENTF_WHEEL,
                    delta,
                )
            ]

        else:

            return False

        cantidad = len(entradas)

        arreglo_entradas = (BINInput * cantidad)(*entradas)

        posicion_original = wintypes.POINT()

        posicion_guardada = bool(user32.GetCursorPos(ctypes.byref(posicion_original)))

        bin_bajado = False

        try:

            rect_bin = wintypes.RECT()

            if user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect_bin),
            ):

                punto_cubierto_por_bin = (
                    rect_bin.left <= int(x_real) < rect_bin.right
                    and rect_bin.top <= int(y_real) < rect_bin.bottom
                )

                if punto_cubierto_por_bin:

                    resultado_z = user32.SetWindowPos(
                        hwnd,
                        HWND_BOTTOM,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                    )

                    if resultado_z:

                        bin_bajado = True

                        QApplication.processEvents()

                        kernel32.Sleep(25)

            resultado_cursor = user32.SetCursorPos(
                int(x_real),
                int(y_real),
            )

            if not resultado_cursor:
                raise ctypes.WinError()

            enviados = BIN_SEND_INPUT(
                cantidad,
                arreglo_entradas,
                ctypes.sizeof(BINInput),
            )

            if enviados != cantidad:

                codigo = ctypes.get_last_error()

                if codigo:
                    raise ctypes.WinError(codigo)

                raise RuntimeError("SendInput no envió todos los eventos.")

            kernel32.Sleep(45)

            return True

        except Exception as error:

            self.actualizar_chat_bin(
                "No pude ejecutar la acción " "del mouse en Windows.\n\n" f"{error}"
            )

            return False

        finally:

            if posicion_guardada:

                user32.SetCursorPos(
                    int(posicion_original.x),
                    int(posicion_original.y),
                )

            if bin_bajado:
                QApplication.processEvents()

            self.mantener_bin_visible_replay(True)

    # ========================================================
    # CLIC IZQUIERDO
    # ========================================================

    def enviar_click_real(
        self,
        x_real,
        y_real,
    ):
        return self.ejecutar_mouse_fisico(
            x_real,
            y_real,
            "click",
        )

    # ========================================================
    # EVENTOS ADICIONALES DEL MOUSE
    # ========================================================

    def enviar_evento_mouse_adicional(
        self,
        x_real,
        y_real,
        tipo,
        delta=0,
    ):
        return self.ejecutar_mouse_fisico(
            x_real,
            y_real,
            tipo,
            delta,
        )

    # ========================================================
    # REGISTRAR CLIC DENTRO DE LA RUTINA
    # ========================================================
    # ========================================================
    # LEER CONTEXTO DE UNA VENTANA DE WINDOWS
    # ========================================================

    def obtener_contexto_hwnd(self, hwnd):
        if sys.platform != "win32" or not hwnd:
            return None

        user32 = ctypes.windll.user32

        try:
            user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            user32.GetWindowTextLengthW.restype = ctypes.c_int

            user32.GetWindowTextW.argtypes = [
                wintypes.HWND,
                wintypes.LPWSTR,
                ctypes.c_int,
            ]
            user32.GetWindowTextW.restype = ctypes.c_int

            user32.GetClassNameW.argtypes = [
                wintypes.HWND,
                wintypes.LPWSTR,
                ctypes.c_int,
            ]
            user32.GetClassNameW.restype = ctypes.c_int

            user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.DWORD),
            ]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD

            hwnd = int(hwnd)

            longitud = user32.GetWindowTextLengthW(hwnd)

            buffer_titulo = ctypes.create_unicode_buffer(max(1, longitud + 1))

            user32.GetWindowTextW(
                hwnd,
                buffer_titulo,
                len(buffer_titulo),
            )

            buffer_clase = ctypes.create_unicode_buffer(256)

            user32.GetClassNameW(
                hwnd,
                buffer_clase,
                len(buffer_clase),
            )

            pid = wintypes.DWORD()

            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(pid),
            )

            proceso = ""
            ejecutable = ""

            if pid.value:

                try:

                    proceso_objeto = psutil.Process(pid.value)

                    proceso = proceso_objeto.name()

                    try:

                        ejecutable = proceso_objeto.exe()

                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                    ):

                        ejecutable = ""

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):

                    proceso = ""
                    ejecutable = ""

                try:
                    proceso = psutil.Process(pid.value).name()

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    proceso = ""

            return {
                "hwnd": hwnd,
                "pid": int(pid.value),
                "proceso": proceso,
                "ejecutable": ejecutable,
                "titulo": buffer_titulo.value.strip(),
                "clase": buffer_clase.value.strip(),
            }

        except Exception:
            return None

    # ========================================================
    # VENTANA REAL DEBAJO DEL PUNTO DEL VISOR
    # ========================================================

    def obtener_contexto_ventana_en_punto(
        self,
        x_real,
        y_real,
    ):
        if sys.platform != "win32":
            return None

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CALLBACK = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        user32.EnumWindows.argtypes = [
            CALLBACK,
            wintypes.LPARAM,
        ]

        user32.EnumWindows.restype = wintypes.BOOL

        user32.IsWindowVisible.argtypes = [wintypes.HWND]

        user32.IsWindowVisible.restype = wintypes.BOOL

        user32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]

        user32.GetWindowRect.restype = wintypes.BOOL

        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]

        kernel32.GetCurrentProcessId.restype = wintypes.DWORD

        hwnd_bin = int(self.winId())

        pid_bin = int(kernel32.GetCurrentProcessId())

        encontrado = {"hwnd": None}

        def revisar_ventana(
            hwnd,
            lparam,
        ):
            hwnd = int(hwnd)

            if hwnd == hwnd_bin:
                return True

            if not user32.IsWindowVisible(hwnd):
                return True

            pid = wintypes.DWORD()

            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(pid),
            )

            if int(pid.value) == pid_bin:
                return True

            rect = wintypes.RECT()

            if not user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect),
            ):
                return True

            if rect.left <= x_real < rect.right and rect.top <= y_real < rect.bottom:
                encontrado["hwnd"] = hwnd

                return False

            return True

        callback = CALLBACK(revisar_ventana)

        try:
            user32.EnumWindows(
                callback,
                0,
            )

        except Exception:
            return None

        if not encontrado["hwnd"]:
            return None

        return self.obtener_contexto_hwnd(encontrado["hwnd"])

    # ========================================================
    # OBTENER HWND REAL DEL CONTROL BAJO EL PUNTO
    # ========================================================

    def obtener_objetivo_virtual_en_punto(
        self,
        x_real,
        y_real,
    ):
        if sys.platform != "win32":
            return None

        contexto_superior = self.obtener_contexto_ventana_en_punto(
            x_real,
            y_real,
        )

        if not contexto_superior:
            return None

        hwnd_superior = contexto_superior.get("hwnd")

        if not hwnd_superior:
            return None

        user32 = ctypes.windll.user32

        try:
            user32.ScreenToClient.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.POINT),
            ]

            user32.ScreenToClient.restype = wintypes.BOOL

            user32.ChildWindowFromPointEx.argtypes = [
                wintypes.HWND,
                wintypes.POINT,
                wintypes.UINT,
            ]

            user32.ChildWindowFromPointEx.restype = wintypes.HWND

            hwnd_actual = int(hwnd_superior)

            flags = CWP_SKIPINVISIBLE | CWP_SKIPDISABLED | CWP_SKIPTRANSPARENT

            # ------------------------------------------------
            # DESCENDER POR LA JERARQUÍA DE CONTROLES
            #
            # Ejemplo:
            #
            # Chrome
            #   ↓
            # ventana interna
            #   ↓
            # superficie donde realmente ocurrió el clic
            # ------------------------------------------------

            for _ in range(12):

                punto = wintypes.POINT(
                    int(x_real),
                    int(y_real),
                )

                convertido = user32.ScreenToClient(
                    hwnd_actual,
                    ctypes.byref(punto),
                )

                if not convertido:
                    break

                hwnd_hijo = user32.ChildWindowFromPointEx(
                    hwnd_actual,
                    punto,
                    flags,
                )

                if not hwnd_hijo:
                    break

                hwnd_hijo = int(hwnd_hijo)

                if not hwnd_hijo or hwnd_hijo == hwnd_actual:
                    break

                hwnd_actual = hwnd_hijo

            contexto_objetivo = self.obtener_contexto_hwnd(hwnd_actual)

            return {
                "hwnd_superior": int(hwnd_superior),
                "hwnd_objetivo": int(hwnd_actual),
                "contexto_superior": (contexto_superior),
                "contexto_objetivo": (contexto_objetivo or contexto_superior),
            }

        except Exception as error:

            self.actualizar_chat_bin(
                "No pude identificar el control "
                "interno bajo el punto.\n\n"
                f"{error}"
            )

            return None

    # ========================================================
    # ENVIAR MOUSE VIRTUAL SIN MOVER EL CURSOR FÍSICO
    # ========================================================

    def enviar_evento_mouse_virtual(
        self,
        x_real,
        y_real,
        tipo,
        delta=0,
    ):
        if sys.platform != "win32":
            return False

        objetivo = self.obtener_objetivo_virtual_en_punto(
            x_real,
            y_real,
        )

        if not objetivo:

            self.actualizar_chat_bin(
                "No pude encontrar una ventana " "destino para la acción virtual."
            )

            return False

        hwnd_objetivo = int(objetivo["hwnd_objetivo"])

        user32 = ctypes.windll.user32

        try:
            user32.ScreenToClient.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.POINT),
            ]

            user32.ScreenToClient.restype = wintypes.BOOL

            user32.PostMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]

            user32.PostMessageW.restype = wintypes.BOOL

            # ------------------------------------------------
            # COORDENADA RELATIVA AL CONTROL DESTINO
            # ------------------------------------------------

            punto_cliente = wintypes.POINT(
                int(x_real),
                int(y_real),
            )

            convertido = user32.ScreenToClient(
                hwnd_objetivo,
                ctypes.byref(punto_cliente),
            )

            if not convertido:

                self.actualizar_chat_bin(
                    "No pude convertir la coordenada " "del visor al control destino."
                )

                return False

            x_cliente = int(punto_cliente.x)

            y_cliente = int(punto_cliente.y)

            # ------------------------------------------------
            # EMPAQUETAR X / Y PARA LPARAM
            # ------------------------------------------------

            lparam_cliente = ((y_cliente & 0xFFFF) << 16) | (x_cliente & 0xFFFF)

            # WM_MOUSEWHEEL usa coordenadas de pantalla.
            lparam_pantalla = ((int(y_real) & 0xFFFF) << 16) | (int(x_real) & 0xFFFF)

            def enviar(
                mensaje,
                wparam,
                lparam,
            ):
                return bool(
                    user32.PostMessageW(
                        hwnd_objetivo,
                        mensaje,
                        wparam,
                        lparam,
                    )
                )

            # ------------------------------------------------
            # CLIC IZQUIERDO
            # ------------------------------------------------

            if tipo == "click":

                correcto = (
                    enviar(
                        WM_MOUSEMOVE,
                        0,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONDOWN,
                        MK_LBUTTON,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONUP,
                        0,
                        lparam_cliente,
                    )
                )

            # ------------------------------------------------
            # DOBLE CLIC
            # ------------------------------------------------

            elif tipo == "doble_click":

                correcto = (
                    enviar(
                        WM_MOUSEMOVE,
                        0,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONDOWN,
                        MK_LBUTTON,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONUP,
                        0,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONDBLCLK,
                        MK_LBUTTON,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_LBUTTONUP,
                        0,
                        lparam_cliente,
                    )
                )

            # ------------------------------------------------
            # CLIC DERECHO
            # ------------------------------------------------

            elif tipo == "click_derecho":

                correcto = (
                    enviar(
                        WM_MOUSEMOVE,
                        0,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_RBUTTONDOWN,
                        MK_RBUTTON,
                        lparam_cliente,
                    )
                    and enviar(
                        WM_RBUTTONUP,
                        0,
                        lparam_cliente,
                    )
                )

            # ------------------------------------------------
            # SCROLL
            # ------------------------------------------------

            elif tipo == "scroll":

                wparam_scroll = (int(delta) & 0xFFFF) << 16

                correcto = enviar(
                    WM_MOUSEWHEEL,
                    wparam_scroll,
                    lparam_pantalla,
                )

            else:

                return False

            if not correcto:

                self.actualizar_chat_bin(
                    "Windows rechazó el mensaje " "virtual de mouse."
                )

                return False

            return True

        except Exception as error:

            self.actualizar_chat_bin(
                "No pude ejecutar la acción " "virtual del mouse.\n\n" f"{error}"
            )

            return False

    # ========================================================
    # VENTANA ACTIVA DESPUÉS DE UNA ACCIÓN
    # ========================================================

    def obtener_contexto_ventana_activa(self):
        if sys.platform != "win32":
            return None

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.GetForegroundWindow.restype = wintypes.HWND

            kernel32.GetCurrentProcessId.restype = wintypes.DWORD

            hwnd = user32.GetForegroundWindow()

            if not hwnd:
                return None

            contexto = self.obtener_contexto_hwnd(hwnd)

            if not contexto:
                return None

            if contexto.get("pid") == int(kernel32.GetCurrentProcessId()):
                return None

            return contexto

        except Exception:
            return None

    # ========================================================
    # NOMBRE AMIGABLE DE UNA VENTANA
    # ========================================================

    def describir_contexto_ventana(
        self,
        contexto,
    ):
        if not contexto:
            return "Ventana no identificada"

        proceso = (
            contexto.get(
                "proceso",
                "",
            )
            or ""
        ).strip()

        titulo = (
            contexto.get(
                "titulo",
                "",
            )
            or ""
        ).strip()

        clase = (
            contexto.get(
                "clase",
                "",
            )
            or ""
        ).strip()

        proceso_minuscula = proceso.lower()
        titulo_minuscula = titulo.lower()

        if len(titulo) > 70:
            titulo = titulo[:67] + "..."

        if proceso_minuscula == "startmenuexperiencehost.exe":
            return "Menú Inicio"

        if proceso_minuscula in {
            "searchhost.exe",
            "searchapp.exe",
        }:
            return "Búsqueda de Windows"

        if proceso_minuscula == "explorer.exe":

            if clase in {
                "Shell_TrayWnd",
                "Shell_SecondaryTrayWnd",
            }:
                return "Barra de tareas"

            if clase in {
                "Progman",
                "WorkerW",
            }:
                return "Escritorio"

            if titulo:
                return "Explorador de Windows · " f"{titulo}"

            return "Explorador de Windows"

        nombres = {
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "firefox.exe": "Mozilla Firefox",
            "chatgpt.exe": "ChatGPT",
            "code.exe": "Visual Studio Code",
            "notepad.exe": "Bloc de notas",
            "excel.exe": "Microsoft Excel",
            "winword.exe": "Microsoft Word",
            "powerpnt.exe": "Microsoft PowerPoint",
        }

        nombre = nombres.get(
            proceso_minuscula,
            proceso or "Ventana",
        )

        if "chatgpt" in titulo_minuscula:

            if proceso_minuscula == "chrome.exe":
                return "ChatGPT · Google Chrome"

            if proceso_minuscula == "msedge.exe":
                return "ChatGPT · Microsoft Edge"

            return "ChatGPT"

        if titulo and titulo.lower() not in nombre.lower():
            return f"{nombre} · " f"{titulo}"

        return nombre

    # ========================================================
    # REGISTRAR CLIC DENTRO DE LA RUTINA
    # ========================================================

    def registrar_click_rutina(
        self,
        x_normalizado,
        y_normalizado,
        x_real,
        y_real,
        contexto_objetivo=None,
    ):
        if not self.grabando:
            return None

        acciones = self.rutina_borrador

        nuevo_id = (
            max(
                [
                    int(
                        accion.get(
                            "id",
                            0,
                        )
                    )
                    for accion in acciones
                ],
                default=0,
            )
            + 1
        )

        nombre_objetivo = self.describir_contexto_ventana(contexto_objetivo)

        accion = {
            "id": nuevo_id,
            "tipo": "click",
            "origen": "rutina",
            "descripcion": (
                "Clic izquierdo · " f"{nombre_objetivo}\n" f"X={x_real} · Y={y_real}"
            ),
            "x": int(x_real),
            "y": int(y_real),
            "x_normalizado": float(x_normalizado),
            "y_normalizado": float(y_normalizado),
            "monitor": int(self.monitor_captura),
            "contexto_objetivo": (contexto_objetivo),
            "contexto_despues": None,
            "capturado_en": (datetime.now().isoformat()),
        }

        acciones.append(accion)

        self.refrescar_panel_acciones()

        return nuevo_id

    # ========================================================
    # COMPLETAR CONTEXTO DESPUÉS DEL CLIC
    # ========================================================

    def completar_contexto_click_rutina(
        self,
        accion_id,
    ):
        contexto_despues = self.obtener_contexto_ventana_activa()

        for accion in reversed(self.rutina_borrador):

            if accion.get("id") != accion_id:
                continue

            accion["contexto_despues"] = contexto_despues

            nombre_objetivo = self.describir_contexto_ventana(
                accion.get("contexto_objetivo")
            )

            nombre_despues = self.describir_contexto_ventana(contexto_despues)

            if contexto_despues and nombre_despues != nombre_objetivo:

                accion["descripcion"] = (
                    "Clic izquierdo · "
                    f"{nombre_objetivo}"
                    " → "
                    f"{nombre_despues}\n"
                    f"X={accion.get('x')} · "
                    f"Y={accion.get('y')}"
                )

            else:

                accion["descripcion"] = (
                    "Clic izquierdo · "
                    f"{nombre_objetivo}\n"
                    f"X={accion.get('x')} · "
                    f"Y={accion.get('y')}"
                )

            self.refrescar_panel_acciones()

            return

    # ========================================================
    # CLIC IZQUIERDO VIRTUAL DESDE EL VISOR IA
    # ========================================================

    def mover_cursor_desde_visor(
        self,
        x_normalizado,
        y_normalizado,
    ):
        if not self.grabando:

            self.actualizar_chat_bin(
                "El visor está en modo observación. "
                "Pulsa MOSTRAR RUTINA para habilitar "
                "la interacción."
            )

            return

        if sys.platform != "win32":

            self.actualizar_chat_bin(
                "El control interactivo del visor "
                "está preparado actualmente para Windows."
            )

            return

        punto = self.convertir_punto_visor_a_windows(
            x_normalizado,
            y_normalizado,
        )

        if punto is None:

            self.actualizar_chat_bin(
                "No pude determinar las dimensiones " "del monitor capturado."
            )

            return

        (
            x_real,
            y_real,
        ) = punto

        contexto_objetivo = self.obtener_contexto_ventana_en_punto(
            x_real,
            y_real,
        )

        # ----------------------------------------------------
        # IMPORTANTE:
        # NO usamos enviar_click_real().
        #
        # Eso movería el mouse físico.
        # ----------------------------------------------------

        ejecutado = self.enviar_evento_mouse_virtual(
            x_real,
            y_real,
            "click",
        )

        if not ejecutado:

            self.actualizar_chat_bin(
                "El destino no aceptó el clic virtual.\n\n"
                "No ejecutaré el respaldo físico "
                "para evitar sacar el cursor del Visor IA."
            )

            return

        accion_id = self.registrar_click_rutina(
            x_normalizado,
            y_normalizado,
            x_real,
            y_real,
            contexto_objetivo,
        )

        if accion_id is None:
            return

        QTimer.singleShot(
            500,
            lambda accion_id=accion_id: self.completar_contexto_click_rutina(accion_id),
        )

        numero_accion = len(self.rutina_borrador)

        nombre_objetivo = self.describir_contexto_ventana(contexto_objetivo)

        self.actualizar_chat_bin(
            "Acción virtual capturada.\n\n"
            f"{numero_accion:02}. "
            "Clic izquierdo\n"
            f"Objetivo: {nombre_objetivo}\n"
            f"X={x_real} · Y={y_real}\n\n"
            "El cursor físico permaneció "
            "dentro de BIN."
        )

    # ========================================================
    # CONVERTIR VISOR → WINDOWS
    # PARA LOS NUEVOS EVENTOS DEL MOUSE
    # ========================================================

    def convertir_punto_visor_a_windows(
        self,
        x_normalizado,
        y_normalizado,
    ):
        if not self.geometria_monitor_captura:

            if not self.actualizar_geometria_monitor_captura():

                return None

        geometria = self.geometria_monitor_captura

        x_real = geometria["left"] + int(
            round(
                x_normalizado
                * max(
                    0,
                    geometria["width"] - 1,
                )
            )
        )

        y_real = geometria["top"] + int(
            round(
                y_normalizado
                * max(
                    0,
                    geometria["height"] - 1,
                )
            )
        )

        return (
            x_real,
            y_real,
        )

    # ========================================================
    # REGISTRAR ACCIÓN ADICIONAL DE MOUSE
    # ========================================================

    def registrar_accion_mouse_extra(
        self,
        tipo,
        etiqueta,
        x_normalizado,
        y_normalizado,
        x_real,
        y_real,
        contexto_objetivo=None,
        datos_extra=None,
    ):
        if not self.grabando:
            return None

        acciones = self.rutina_borrador

        nuevo_id = (
            max(
                [
                    int(
                        accion.get(
                            "id",
                            0,
                        )
                    )
                    for accion in acciones
                ],
                default=0,
            )
            + 1
        )

        nombre_objetivo = self.describir_contexto_ventana(contexto_objetivo)

        accion = {
            "id": nuevo_id,
            "tipo": tipo,
            "origen": "rutina",
            "etiqueta": etiqueta,
            "descripcion": (
                f"{etiqueta} · " f"{nombre_objetivo}\n" f"X={x_real} · " f"Y={y_real}"
            ),
            "x": int(x_real),
            "y": int(y_real),
            "x_normalizado": float(x_normalizado),
            "y_normalizado": float(y_normalizado),
            "monitor": int(self.monitor_captura),
            "contexto_objetivo": (contexto_objetivo),
            "contexto_despues": None,
            "capturado_en": (datetime.now().isoformat()),
        }

        if datos_extra:

            accion.update(datos_extra)

        acciones.append(accion)

        self.refrescar_panel_acciones()

        return nuevo_id

    # ========================================================
    # COMPLETAR CONTEXTO DESPUÉS DEL EVENTO
    # ========================================================

    def completar_contexto_accion_mouse_extra(
        self,
        accion_id,
    ):
        contexto_despues = self.obtener_contexto_ventana_activa()

        for accion in reversed(self.rutina_borrador):

            if accion.get("id") != accion_id:
                continue

            accion["contexto_despues"] = contexto_despues

            etiqueta = accion.get(
                "etiqueta",
                "Acción",
            )

            nombre_objetivo = self.describir_contexto_ventana(
                accion.get("contexto_objetivo")
            )

            nombre_despues = self.describir_contexto_ventana(contexto_despues)

            if contexto_despues and nombre_despues != nombre_objetivo:

                contexto_texto = f"{nombre_objetivo}" " → " f"{nombre_despues}"

            else:

                contexto_texto = nombre_objetivo

            extra = ""

            if accion.get("tipo") == "scroll":

                direccion = accion.get(
                    "direccion",
                    "",
                )

                pasos = accion.get(
                    "pasos",
                    1,
                )

                extra = f" · {direccion}" f" · {pasos} paso(s)"

            accion["descripcion"] = (
                f"{etiqueta}"
                f"{extra}"
                f" · {contexto_texto}\n"
                f"X={accion.get('x')} · "
                f"Y={accion.get('y')}"
            )

            self.refrescar_panel_acciones()

            return

    # ========================================================
    # DOBLE CLIC DESDE EL VISOR IA
    # ========================================================

    def doble_click_desde_visor(
        self,
        x_normalizado,
        y_normalizado,
    ):
        if not self.grabando:
            return

        punto = self.convertir_punto_visor_a_windows(
            x_normalizado,
            y_normalizado,
        )

        if punto is None:

            self.actualizar_chat_bin(
                "No pude determinar las " "coordenadas del monitor."
            )

            return

        (
            x_real,
            y_real,
        ) = punto

        contexto_objetivo = self.obtener_contexto_ventana_en_punto(
            x_real,
            y_real,
        )

        ejecutado = self.enviar_evento_mouse_adicional(
            x_real,
            y_real,
            "doble_click",
        )

        if not ejecutado:
            return

        accion_id = self.registrar_accion_mouse_extra(
            "doble_click",
            "Doble clic",
            x_normalizado,
            y_normalizado,
            x_real,
            y_real,
            contexto_objetivo,
        )

        if accion_id is not None:

            QTimer.singleShot(
                1200,
                lambda accion_id=accion_id: self.completar_contexto_accion_mouse_extra(
                    accion_id
                ),
            )

        self.actualizar_chat_bin(
            "Acción capturada.\n\n"
            "Doble clic izquierdo\n"
            f"X={x_real} · "
            f"Y={y_real}"
        )

    # ========================================================
    # CLIC DERECHO VIRTUAL DESDE EL VISOR IA
    # ========================================================

    def click_derecho_desde_visor(
        self,
        x_normalizado,
        y_normalizado,
    ):
        if not self.grabando:
            return

        punto = self.convertir_punto_visor_a_windows(
            x_normalizado,
            y_normalizado,
        )

        if punto is None:

            self.actualizar_chat_bin(
                "No pude determinar las " "coordenadas del monitor."
            )

            return

        (
            x_real,
            y_real,
        ) = punto

        contexto_objetivo = self.obtener_contexto_ventana_en_punto(
            x_real,
            y_real,
        )

        ejecutado = self.enviar_evento_mouse_virtual(
            x_real,
            y_real,
            "click_derecho",
        )

        if not ejecutado:

            self.actualizar_chat_bin("El destino no aceptó " "el clic derecho virtual.")

            return

        accion_id = self.registrar_accion_mouse_extra(
            "click_derecho",
            "Clic derecho",
            x_normalizado,
            y_normalizado,
            x_real,
            y_real,
            contexto_objetivo,
        )

        if accion_id is not None:

            QTimer.singleShot(
                500,
                lambda accion_id=accion_id: self.completar_contexto_accion_mouse_extra(
                    accion_id
                ),
            )

        self.actualizar_chat_bin(
            "Acción virtual capturada.\n\n" "Clic derecho\n" f"X={x_real} · Y={y_real}"
        )

    # ========================================================
    # SCROLL VIRTUAL DESDE EL VISOR IA
    # ========================================================

    def scroll_desde_visor(
        self,
        x_normalizado,
        y_normalizado,
        delta,
    ):
        if not self.grabando or delta == 0:
            return

        punto = self.convertir_punto_visor_a_windows(
            x_normalizado,
            y_normalizado,
        )

        if punto is None:

            self.actualizar_chat_bin(
                "No pude determinar las " "coordenadas del monitor."
            )

            return

        (
            x_real,
            y_real,
        ) = punto

        contexto_objetivo = self.obtener_contexto_ventana_en_punto(
            x_real,
            y_real,
        )

        direccion = "Arriba" if delta > 0 else "Abajo"

        pasos = max(
            1,
            round(abs(delta) / 120),
        )

        ejecutado = self.enviar_evento_mouse_virtual(
            x_real,
            y_real,
            "scroll",
            delta,
        )

        if not ejecutado:

            self.actualizar_chat_bin("El destino no aceptó " "el scroll virtual.")

            return

        accion_id = self.registrar_accion_mouse_extra(
            "scroll",
            "Scroll",
            x_normalizado,
            y_normalizado,
            x_real,
            y_real,
            contexto_objetivo,
            {
                "delta": int(delta),
                "direccion": (direccion),
                "pasos": int(pasos),
            },
        )

        if accion_id is not None:

            QTimer.singleShot(
                350,
                lambda accion_id=accion_id: self.completar_contexto_accion_mouse_extra(
                    accion_id
                ),
            )

        self.actualizar_chat_bin(
            "Acción virtual capturada.\n\n"
            f"Scroll "
            f"{direccion.lower()} · "
            f"{pasos} paso(s)"
        )

    # ========================================================
    # INICIAR CAPTURA DEL ESCRITORIO
    # ========================================================

    def iniciar_captura_pantalla(self):

        if mss is None:

            if hasattr(
                self,
                "visor_imagen",
            ):

                self.visor_imagen.setText(
                    "NO SE PUDO INICIAR LA CAPTURA\n\n"
                    "Falta instalar MSS.\n\n"
                    "Ejecuta:\n"
                    "pip install mss"
                )

            self.actualizar_estado_cabecera_visor(
                "Error de captura",
                "",
                ROJO,
            )

            return

        self.actualizar_geometria_monitor_captura()

        if self.hilo_captura and self.hilo_captura.isRunning():

            return

        self.hilo_captura = ScreenCaptureThread(
            monitor_index=self.monitor_captura,
            fps=self.fps_captura,
            parent=self,
        )

        self.hilo_captura.frame_ready.connect(self.recibir_frame_pantalla)

        self.hilo_captura.error_captura.connect(self.mostrar_error_captura)

        self.hilo_captura.start()

        self.actualizar_estado_cabecera_visor(
            "Listo",
            "",
            VERDE,
        )

        if hasattr(
            self,
            "mensaje_visor",
        ):

            self.mensaje_visor.setText("")

    # ========================================================
    # RECIBIR FRAME DEL ESCRITORIO
    # ========================================================

    def recibir_frame_pantalla(
        self,
        imagen,
    ):

        if imagen.isNull():

            return

        # Guardamos una copia completa del último frame.
        #
        # Este será posteriormente el mismo frame que podrán
        # usar:
        #
        # - el visor
        # - la IA visual
        # - checkpoints
        # - Mostrar rutina
        # - recuperación
        #
        self.frame_actual = imagen.copy()

        if not hasattr(
            self,
            "visor_imagen",
        ):

            return

        ancho = self.visor_imagen.width()

        alto = self.visor_imagen.height()

        if ancho <= 1 or alto <= 1:

            return

        pixmap = QPixmap.fromImage(self.frame_actual)

        pixmap_escalado = pixmap.scaled(
            ancho,
            alto,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.visor_imagen.setPixmap(pixmap_escalado)

    # ========================================================
    # ERROR EN CAPTURA
    # ========================================================

    def mostrar_error_captura(
        self,
        mensaje,
    ):
        self.actualizar_estado_cabecera_visor(
            "Error de captura",
            "",
            ROJO,
        )

        if hasattr(
            self,
            "visor_imagen",
        ):

            self.visor_imagen.clear()

            self.visor_imagen.setText(
                "ERROR EN LA CAPTURA DEL ESCRITORIO\n\n" f"{mensaje}"
            )

        if hasattr(
            self,
            "mensaje_chat",
        ):

            self.mensaje_chat.setText(
                "BIN: No pude iniciar correctamente "
                "la captura del escritorio.\n\n"
                f"{mensaje}"
            )

    # ========================================================
    # DETENER CAPTURA
    # ========================================================

    def detener_captura_pantalla(self):

        if not self.hilo_captura:

            return

        if self.hilo_captura.isRunning():

            self.hilo_captura.detener()

            self.hilo_captura.wait(2000)

        self.actualizar_estado_cabecera_visor(
            "Captura detenida",
            "",
            GRIS,
        )

        self.hilo_captura = None

    # ========================================================
    # TEMPORIZADORES
    # ========================================================

    def iniciar_temporizadores(self):
        # RELOJ
        self.timer_reloj = QTimer(self)
        self.timer_reloj.timeout.connect(self.actualizar_reloj)
        self.timer_reloj.start(1000)

        # SISTEMA
        self.timer_sistema = QTimer(self)
        self.timer_sistema.timeout.connect(self.actualizar_sistema)
        self.timer_sistema.start(1500)

        # MOTOR DE EJECUCIÓN
        self.timer_motor = QTimer(self)
        self.timer_motor.timeout.connect(self.actualizar_motor_ejecucion)
        self.timer_motor.start(250)

        # SCHEDULER AUTOMÁTICO
        self.timer_scheduler = QTimer(self)
        self.timer_scheduler.timeout.connect(self.scheduler_tick)
        self.timer_scheduler.start(1000)

        # GUARDADO PERIÓDICO DEL ESTADO
        self.timer_guardado_runtime = QTimer(self)
        self.timer_guardado_runtime.timeout.connect(self.guardar_estado_runtime)
        self.timer_guardado_runtime.start(5000)

        self.actualizar_reloj()
        self.actualizar_sistema()
        self.scheduler_tick()

    # ========================================================
    # ESTILOS
    # ========================================================

    def closeEvent(
        self,
        event,
    ):
        # ----------------------------------------------------
        # DETENER GRABACIÓN GLOBAL
        # ----------------------------------------------------

        self.grabando = False

        if hasattr(
            self,
            "timer_click_global",
        ):
            self.timer_click_global.stop()

        self.detener_grabadores_globales()
        self.ocultar_barra_grabacion()

        # ----------------------------------------------------
        # DETENER EJECUTOR FÍSICO
        # ----------------------------------------------------

        tarea_replay = self.obtener_tarea_ejecutando()

        if tarea_replay and self.ejecucion_fisica_activa:
            if (
                hasattr(self, "timer_ejecucion_accion")
                and self.timer_ejecucion_accion.isActive()
            ):
                self.delay_ejecucion_restante_ms = max(
                    0,
                    int(self.timer_ejecucion_accion.remainingTime()),
                )

            self.elapsed_repeticion_base_ms = self.elapsed_repeticion_real_actual_ms()
            self.inicio_repeticion_real_monotonic = None

            self.guardar_estado_ejecutor_real_en_tarea(tarea_replay)

        if hasattr(self, "timer_ejecucion_accion"):
            self.timer_ejecucion_accion.stop()

        self.ejecucion_fisica_activa = False

        # ----------------------------------------------------
        # DETENER CAPTURA DEL ESCRITORIO
        # ----------------------------------------------------

        self.detener_captura_pantalla()

        # ----------------------------------------------------
        # GUARDADO SEGURO DE UNA EJECUCIÓN
        # ----------------------------------------------------

        tarea = self.obtener_tarea_ejecutando()

        if tarea and tarea.get("estado") == "EJECUTANDO":

            inicio_texto = tarea.get("runtime_started_at")

            adicional = 0

            if inicio_texto:

                try:

                    inicio = datetime.fromisoformat(inicio_texto)

                    adicional = int((datetime.now() - inicio).total_seconds())

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

            tarea["runtime_base_seconds"] = tarea["elapsed_seconds"]

            tarea["transcurrido"] = segundos_a_hms(tarea["elapsed_seconds"])

            tarea["runtime_started_at"] = None

            tarea["estado"] = "EN PAUSA"

            tarea["detalle_estado"] = "Pausada al cerrar BIN"

        # ----------------------------------------------------
        # TAREAS QUE ESTABAN EN COLA
        # ----------------------------------------------------

        for item in self.tareas:

            if item.get("estado") == "EN COLA":

                item["estado"] = "EN PAUSA"

                item["runtime_started_at"] = None

                item["detalle_estado"] = "Pausada al cerrar BIN"

        self.guardar_tareas_en_disco()

        event.accept()

    def aplicar_estilos(self):

        self.setStyleSheet(f"""

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


            QFrame#tarjetaTarea[accionActiva="true"] {{

                border:
                    2px solid
                    {AZUL};

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

            QLabel#visorImagen {{

                background-color:
                    #020306;

                color:
                    #454c57;

                border:
                    none;

                font-size:
                    16px;

                font-weight:
                    700;

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

            """)


# ============================================================
# INICIAR APLICACIÓN
# ============================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    bin_app = BIN()

    bin_app.show()

    sys.exit(app.exec())
