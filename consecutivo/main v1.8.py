import sys
import json
import base64
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

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    QTime,
    QThread,
    QBuffer,
    QIODevice,
    QUrl,
    QByteArray,
)

from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply,
)
from PySide6.QtGui import QImage, QPixmap, QIcon
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
    QTextEdit,
    QButtonGroup,
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

# Si una tarea programada comenzará dentro de este margen,
# BIN no iniciará una tarea retrasada antes de ella.
UMBRAL_PROTEGER_TAREA_PROGRAMADA_SEGUNDOS = 5 * 60

# Margen adicional para evitar que una tarea retrasada
# termine demasiado pegada a la siguiente tarea programada.
MARGEN_SEGURIDAD_ENTRE_TAREAS_SEGUNDOS = 30

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

            with mss.MSS() as capturador:

                monitores = capturador.monitors

                if len(monitores) <= 1:

                    self.error_captura.emit(
                        "BIN no encontró ningún monitor disponible."
                    )

                    return

                while self._capturando:

                    indice = self.monitor_index

                    try:
                        indice = int(indice)
                    except Exception:
                        indice = 1

                    if indice <= 0 or indice >= len(monitores):
                        indice = 1

                    monitor = monitores[indice]

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

    def cambiar_monitor(
        self,
        monitor_index,
    ):

        try:

            monitor_index = int(monitor_index)

        except Exception:
            return False

        if monitor_index < 1:
            return False

        self.monitor_index = monitor_index

        return True

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

    reset_solicitado = Signal(int)

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
        # RESET DE EJECUCIÓN PAUSADA
        # ----------------------------------------------------

        self.boton_reset = QPushButton("RESET TAREA")

        self.boton_reset.setEnabled(False)

        layout.addWidget(self.boton_reset)

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

        self.boton_reset.clicked.connect(
            lambda: self.reset_solicitado.emit(self.tarea["id"])
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

        self.boton_reset.setEnabled(
            estado == "EN PAUSA"
            and bool(self.tarea.get("current_run_key"))
        )

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

        # ====================================================
        # BARRA FLOTANTE DE EJECUCIÓN
        # ====================================================

        self.barra_ejecucion = None
        self.label_barra_ejecucion = None
        self.boton_pausa_barra_ejecucion = None

        # Tarea que fue pausada mediante el control de ejecución.
        # Permite saber exactamente qué ejecución debe continuar.
        self.tarea_pausada_flotante_id = None

        # Mientras sea True, BIN no debe iniciar ninguna otra
        # tarea programada o en cola.
        self.pausa_ejecucion_global = False

        # ====================================================
        # TAREAS RETRASADAS
        # ====================================================

        # Evita abrir más de un diálogo de retrasos a la vez.
        self.dialogo_tareas_retrasadas_abierto = False

        # Si el usuario cierra el diálogo sin decidir, BIN espera
        # unos segundos antes de volver a mostrarlo.
        self.proximo_aviso_tareas_retrasadas = None

        # Ejecuciones retrasadas que el usuario aprobó durante
        # esta sesión. La clave es (id_tarea, run_key).
        self.runs_retrasados_aceptados = set()

        self.solicitud_detener_grabacion.connect(self.detener_grabacion_desde_atajo)

        self.pantalla_completa = False

        # ====================================================
        # DIRECTORIOS
        # ====================================================

        self.directorio_bin = Path(__file__).resolve().parent

        self.directorio_datos = self.directorio_bin / "data"

        self.archivo_tareas = self.directorio_datos / "tareas.json"

        self.directorio_assets = self.directorio_bin / "assets"
        self.archivo_logo_bin = self.directorio_assets / "bin_face.png"
        self.archivo_icono_bin = self.directorio_assets / "bin_face.ico"

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

        self.geometrias_monitores_captura = []

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
        self.timeout_supervisor_ms = 60_000
        self.intervalo_supervisor_ms = 500
        self.ultima_decision_supervisor = None
        self.ultimo_motivo_supervisor = ""
        self.supervisor_hubo_wait = False

        # ====================================================
        # IA VISUAL LOCAL — OLLAMA / QWEN3-VL
        # ====================================================

        self.modelo_ia_visual = "qwen3-vl:4b-instruct"

        # ====================================================
        # CONTEXTO GLOBAL DE QWEN
        # ====================================================

        # 4096 ya es insuficiente para algunas consultas
        # multimodales que contienen:
        # - captura actual
        # - demostración de la tarea
        # - instrucciones del agente
        # - resultados anteriores
        #
        # 8192 nos deja margen para el nuevo ciclo
        # observar → actuar → verificar.
        self.num_ctx_qwen = 8192

        self.url_ia_visual = QUrl("http://127.0.0.1:11434/api/chat")

        self.gestor_red_ia_visual = QNetworkAccessManager(self)

        self.respuesta_red_ia_visual = None

        self.clave_ia_visual_en_curso = None
        self.clave_resultado_ia_visual = None
        self.resultado_ia_visual = None

        self.proveedor_ia_visual = self.proveedor_ia_visual_ollama

        # ====================================================
        # DIAGNÓSTICO / CHAT DIRECTO CON QWEN
        # ====================================================

        self.modo_diagnostico_ia = True

        self.inicio_consulta_ia_visual_monotonic = None

        self.ultimo_aviso_espera_ia_bloque = -1

        self.respuesta_red_chat_qwen = None

        self.inicio_chat_qwen_monotonic = None

        self.mensaje_chat_qwen_pendiente = None

        self.historial_chat_qwen = []

        # ====================================================
        # VERIFICACIÓN VISUAL DE ACCIONES DEL CHAT QWEN
        # ====================================================

        self.respuesta_red_verificacion_chat_qwen = None

        self.inicio_verificacion_chat_qwen_monotonic = None

        self.verificacion_chat_pendiente = None

        # Objetivo completo solicitado por el usuario.
        self.objetivo_chat_qwen_activo = None

        # Cantidad de acciones físicas realizadas
        # intentando completar el objetivo actual.
        self.pasos_objetivo_chat_qwen = 0

        self.max_pasos_objetivo_chat_qwen = 8

        # Intentos visuales durante una verificación.
        self.intentos_verificacion_chat_qwen = 0

        # ====================================================
        # STOP MANUAL DEL AGENTE DE CHAT
        # ====================================================

        self.detener_chat_qwen_solicitado = False

        # Identificador incremental del objetivo actual.
        # Un STOP invalida respuestas y QTimers anteriores.
        self.chat_qwen_ciclo_id = 0

        # ====================================================
        # AGENTE IA POR LOTES
        # ====================================================

        # Nuevo motor:
        # Qwen comprende la demostración completa,
        # crea su propio plan y BIN únicamente ejecuta
        # las herramientas solicitadas.
        self.modo_agente_ia_activo = True

        self.respuesta_red_agente_ia = None
        self.inicio_consulta_agente_ia_monotonic = None

        # Lote actual generado por Qwen.
        self.plan_agente_ia_actual = []
        self.indice_plan_agente_ia = 0

        # Reanálisis permitidos solamente cuando
        # realmente hacen falta.
        self.reanalisis_agente_ia = 0
        self.max_reanalisis_agente_ia = 6

        # Historial físico de lo que Qwen ordenó
        # y BIN consiguió ejecutar.
        self.historial_agente_ia = []

        # ====================================================
        # ANTIBUCLE DEL AGENTE DE TAREAS
        # ====================================================

        # Durante calibración no permitiremos que una
        # repetición se convierta en decenas de minutos
        # de acciones sin progreso.
        self.pasos_agente_ia_actual = 0
        self.max_pasos_agente_ia = 8

        # Detecta propuestas prácticamente iguales.
        self.ultima_firma_plan_agente_ia = None
        self.repeticiones_plan_agente_ia = 0

        # Cantidad de veces que BIN detectó
        # estancamiento consecutivo.
        self.estancamientos_agente_ia = 0
        self.max_estancamientos_agente_ia = 3

        # ====================================================
        # CONTROL DE TRAYECTORIA IA
        # ====================================================

        # Qwen supervisará cada acción antes de que BIN
        # permita que Python continúe con la rutina.
        self.control_trayectoria_ia_activo = False

        # Pausa interna automática. No es la pausa del usuario.
        self.pausa_ia_activa = False

        # Una acción solo se ejecuta cuando Qwen la autoriza.
        self.clave_accion_autorizada_ia = None

        # Control de tiempo de una corrección.
        self.inicio_control_trayectoria_ia_monotonic = None
        self.intervalo_control_trayectoria_ia_ms = 900
        self.timeout_control_trayectoria_ia_ms = 300_000

        # Evita bucles infinitos de corrección.
        self.correcciones_ia_consecutivas = 0
        self.max_correcciones_ia_consecutivas = 8

        # Última corrección ejecutada por Qwen.
        self.ultima_correccion_ia = None

        # ====================================================
        # VENTANA
        # ====================================================

        self.setWindowTitle("BIN IA Asistem")

        self.aplicar_identidad_visual_bin()

        self.resize(1550, 900)

        self.setMinimumSize(1200, 720)

        # ====================================================
        # INICIAR
        # ====================================================

        self.crear_interfaz()

        self.aplicar_estilos()

        # La ventana debe existir antes de configurar
        # su comportamiento frente a capturas.
        self.permitir_bin_en_capturas()

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
            tarea.setdefault("last_skipped_run_key", None)
            tarea.setdefault("queued_at", None)
            tarea.setdefault("completed_at", None)
            tarea.setdefault("ultima_ejecucion", tarea.get("completed_at"))
            tarea.setdefault("acciones", [])
            tarea.setdefault("acciones_semanticas", [])

            # --------------------------------------------
            # MEMORIA INTELIGENTE DE LA TAREA
            # --------------------------------------------

            # Objetivo que Qwen irá deduciendo de la
            # demostración completa.
            tarea.setdefault("objetivo_ia", None)

            # Futuro plan optimizado. La demostración
            # original permanecerá intacta.
            tarea.setdefault("plan_ia", [])

            memoria_ia = tarea.get("memoria_ia")

            if not isinstance(memoria_ia, dict):
                memoria_ia = {}

            memoria_ia.setdefault(
                "correcciones_exitosas",
                [],
            )

            memoria_ia.setdefault(
                "correcciones_fallidas",
                [],
            )

            tarea["memoria_ia"] = memoria_ia

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

            # Recuperación segura: una tarea que estaba ejecutándose
            # sigue quedando pausada para no reanudarla a ciegas.
            if tarea.get("estado") == "EJECUTANDO":
                if tarea.get("current_run_key"):
                    tarea["estado"] = "EN PAUSA"
                else:
                    tarea["estado"] = "EN ESPERA"

                tarea["runtime_started_at"] = None
                tarea["runtime_base_seconds"] = tarea.get("elapsed_seconds", 0)

                if tarea.get("ejecucion_real_fase") == "inactiva":
                    tarea["ejecucion_real_fase"] = "espera_accion"

            # Una tarea que solo estaba en cola se devuelve a espera.
            # Al iniciar BIN nuevamente, el scheduler comprobará si
            # quedó retrasada y volverá a pedir una decisión al usuario.
            elif tarea.get("estado") == "EN COLA":
                tarea["estado"] = "EN ESPERA"
                tarea["current_run_key"] = None
                tarea["queued_at"] = None
                tarea["runtime_started_at"] = None
                tarea["runtime_base_seconds"] = tarea.get("elapsed_seconds", 0)
                tarea["detalle_estado"] = "Pendiente de reevaluar programación"

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

    def aplicar_identidad_visual_bin(self):

        ruta_icono = None

        if self.archivo_icono_bin.exists():
            ruta_icono = self.archivo_icono_bin
        elif self.archivo_logo_bin.exists():
            ruta_icono = self.archivo_logo_bin

        if ruta_icono is None:
            return

        icono = QIcon(str(ruta_icono))

        self.setWindowIcon(icono)

        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(icono)

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

        cabecera.setFixedHeight(82)

        layout_cabecera = QHBoxLayout(cabecera)

        layout_cabecera.setContentsMargins(
            12,
            5,
            12,
            5,
        )

        layout_cabecera.setSpacing(10)

        # ----------------------------------------------------
        # IDENTIDAD
        # ----------------------------------------------------

        identidad = QVBoxLayout()

        identidad.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        identidad.setSpacing(1)

        self.logo_imagen = QLabel()

        self.logo_imagen.setObjectName("logoImagen")

        self.logo_imagen.setAlignment(
            Qt.AlignCenter
        )

        self.logo_imagen.setFixedSize(
            58,
            52,
        )

        if self.archivo_logo_bin.exists():

            pixmap_logo = QPixmap(
                str(self.archivo_logo_bin)
            )

            if not pixmap_logo.isNull():

                self.logo_imagen.setPixmap(
                    pixmap_logo.scaled(
                        50,
                        50,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

            else:

                self.logo_imagen.setText("BIN")

                self.logo_imagen.setObjectName(
                    "logo"
                )

        else:

            self.logo_imagen.setText("BIN")

            self.logo_imagen.setObjectName(
                "logo"
            )

        subtitulo = QLabel(
            "BIN IA Asistem"
        )

        subtitulo.setObjectName(
            "logoNombre"
        )

        subtitulo.setAlignment(
            Qt.AlignCenter
        )

        identidad.addWidget(
            self.logo_imagen,
            0,
            Qt.AlignCenter,
        )

        identidad.addWidget(
            subtitulo,
            0,
            Qt.AlignCenter,
        )

        layout_cabecera.addLayout(
            identidad
        )

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

        self.mensaje_chat = QTextEdit()

        self.mensaje_chat.setReadOnly(True)

        self.mensaje_chat.setMinimumHeight(150)

        self.mensaje_chat.setPlainText(
            "BIN: Hola. Estoy operativo."
        )

        entrada_chat_layout = QHBoxLayout()

        self.entrada_chat = QLineEdit()
        self.entrada_chat.setPlaceholderText("Escribe una indicación para BIN...")

        self.boton_enviar_chat = QPushButton(
            "ENVIAR"
        )

        self.boton_detener_chat_qwen = QPushButton(
            "■ PARAR ACCIÓN"
        )

        self.boton_detener_chat_qwen.setObjectName(
            "botonEliminar"
        )

        self.boton_detener_chat_qwen.setEnabled(
            False
        )

        self.boton_enviar_chat.clicked.connect(
            self.procesar_chat
        )

        self.entrada_chat.returnPressed.connect(
            self.procesar_chat
        )

        self.boton_detener_chat_qwen.clicked.connect(
            self.detener_accion_chat_qwen
        )

        entrada_chat_layout.addWidget(
            self.entrada_chat,
            1,
        )

        entrada_chat_layout.addWidget(
            self.boton_enviar_chat
        )

        entrada_chat_layout.addWidget(
            self.boton_detener_chat_qwen
        )

        chat_layout.addWidget(titulo_chat)
        chat_layout.addWidget(self.mensaje_chat)
        chat_layout.addLayout(entrada_chat_layout)

        centro.addWidget(chat, 3)

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

        self.boton_limpiar_panel_acciones = QPushButton(
            "LIMPIAR PANEL DE ACCIÓN"
        )

        self.boton_limpiar_panel_acciones.clicked.connect(
            self.limpiar_panel_acciones
        )

        acciones_layout.addWidget(
            self.boton_limpiar_panel_acciones
        )

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
            tarjeta.reset_solicitado.connect(self.resetear_tarea_pausada)
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

    def agregar_mensaje_chat(
        self,
        autor,
        mensaje,
    ):
        mensaje = str(
            mensaje
            or ""
        ).strip()

        if not mensaje:
            return

        hora = datetime.now().strftime(
            "%H:%M:%S"
        )

        bloque = (
            f"[{hora}] {autor}:\n"
            f"{mensaje}"
        )

        self.ultimo_chat_sistema = mensaje

        if not hasattr(
            self,
            "mensaje_chat",
        ):
            return

        actual = (
            self.mensaje_chat.toPlainText()
            .strip()
        )

        if actual:
            nuevo = (
                actual
                + "\n\n"
                + bloque
            )
        else:
            nuevo = bloque

        self.mensaje_chat.setPlainText(
            nuevo
        )

        barra = (
            self.mensaje_chat.verticalScrollBar()
        )

        if barra is not None:
            barra.setValue(
                barra.maximum()
            )

    def actualizar_chat_bin(
        self,
        mensaje,
    ):
        self.agregar_mensaje_chat(
            "BIN",
            mensaje,
        )

    def actualizar_chat_qwen(
        self,
        mensaje,
    ):
        self.agregar_mensaje_chat(
            "QWEN",
            mensaje,
        )

    def actualizar_chat_usuario(
        self,
        mensaje,
    ):
        self.agregar_mensaje_chat(
            "TÚ",
            mensaje,
        )

    # ========================================================
    # DESCRIBIR HERRAMIENTA QWEN PARA EL PANEL
    # ========================================================

    def describir_herramienta_qwen_panel(
        self,
        herramienta,
    ):
        if not isinstance(
            herramienta,
            dict,
        ):
            return "Acción Qwen"

        tipo = str(
            herramienta.get(
                "type",
                "",
            )
            or ""
        ).strip().lower()

        datos = dict(
            herramienta.get(
                "data"
            )
            or {}
        )

        nombres = {
            "abrir_inicio": "Abrir menú Inicio",
            "click": "Clic",
            "doble_click": "Doble clic",
            "abrir_elemento": "Abrir elemento",
            "abrir_menu_contextual": (
                "Abrir menú contextual"
            ),
            "desplazar": "Desplazar",
            "scroll": "Scroll",
            "scroll_agrupado": "Scroll",
            "arrastrar": "Arrastrar",
            "escribir_texto": "Escribir texto",
            "copiar": "Copiar",
            "pegar": "Pegar",
            "cortar": "Cortar",
            "deshacer": "Deshacer",
            "rehacer": "Rehacer",
            "seleccionar_todo": (
                "Seleccionar todo"
            ),
            "guardar": "Guardar",
            "buscar": "Buscar",
            "imprimir": "Imprimir",
            "cambiar_aplicacion": (
                "Cambiar aplicación"
            ),
            "cerrar_ventana": (
                "Cerrar ventana"
            ),
            "navegar_url": "Navegar",
            "navegar": "Navegar",
            "buscar_o_navegar": (
                "Buscar o navegar"
            ),
            "tecla": "Presionar tecla",
            "atajo_teclado": (
                "Atajo de teclado"
            ),
        }

        if tipo == "abrir_aplicacion":
            objetivo = str(
                datos.get(
                    "consulta"
                )
                or datos.get(
                    "app_name"
                )
                or datos.get(
                    "application"
                )
                or datos.get(
                    "proceso"
                )
                or "aplicación"
            )

            return (
                f"Abrir {objetivo}"
            )

        if tipo == "escribir_texto":
            texto = str(
                datos.get(
                    "texto"
                )
                or datos.get(
                    "text"
                )
                or ""
            )

            if len(texto) > 55:
                texto = (
                    texto[:52]
                    + "..."
                )

            if texto:
                return (
                    f'Escribir "{texto}"'
                )

        if tipo in {
            "navegar_url",
            "navegar",
            "buscar_o_navegar",
        }:
            destino = str(
                datos.get(
                    "destino"
                )
                or datos.get(
                    "url"
                )
                or ""
            )

            if destino:
                return (
                    f"Navegar a {destino}"
                )

        if tipo == "tecla":
            tecla = str(
                datos.get(
                    "tecla"
                )
                or datos.get(
                    "key"
                )
                or ""
            )

            if tecla:
                return (
                    f"Presionar {tecla}"
                )

        nombre = nombres.get(
            tipo
        )

        if nombre:
            return nombre

        if tipo:
            return (
                "Qwen · "
                + tipo.replace(
                    "_",
                    " ",
                )
            )

        return "Acción Qwen"

    # ========================================================
    # REGISTRAR ACCIÓN DE QWEN EN PANEL
    # ========================================================

    def registrar_herramienta_qwen_panel(
        self,
        herramienta,
    ):
        if not isinstance(
            herramienta,
            dict,
        ):
            return None

        tipo = str(
            herramienta.get(
                "type",
                "",
            )
            or ""
        ).strip().lower()

        if not tipo:
            return None

        # --------------------------------------------
        # EL CHAT DE QWEN CREA UNA RUTINA BORRADOR
        # --------------------------------------------

        if not self.rutina_en_borrador:
            self.rutina_en_borrador = True

            self.rutina_borrador = []

            self.rutina_borrador_semantica = []

            self.duracion_rutina_borrador = 0

        siguiente_id = (
            max(
                [
                    accion.get(
                        "id",
                        0,
                    )
                    for accion
                    in self.rutina_borrador
                ],
                default=0,
            )
            + 1
        )

        datos = json.loads(
            json.dumps(
                herramienta.get(
                    "data"
                )
                or {}
            )
        )

        accion_panel = {
            "id": siguiente_id,
            "tipo": tipo,
            "descripcion": (
                self.describir_herramienta_qwen_panel(
                    herramienta
                )
            ),
            "origen": "qwen",
            "datos": datos,
            "capturado_en": (
                datetime.now()
                .isoformat()
            ),
            "estado_ia": "PENDIENTE",
            "detalle_ia": "",
        }

        self.rutina_borrador.append(
            accion_panel
        )

        # Estimación provisional para permitir
        # guardar posteriormente la rutina.
        self.duracion_rutina_borrador = max(
            1,
            len(
                self.rutina_borrador
            )
            * 5,
        )

        indice = (
            len(
                self.rutina_borrador
            )
            - 1
        )

        self.refrescar_panel_acciones()

        return indice

    # ========================================================
    # ACTUALIZAR ESTADO DE ACCIÓN QWEN
    # ========================================================

    def actualizar_estado_herramienta_qwen_panel(
        self,
        indice,
        estado,
        detalle="",
    ):
        if (
            indice is None
            or indice < 0
            or indice
            >= len(
                self.rutina_borrador
            )
        ):
            return

        accion = (
            self.rutina_borrador[
                indice
            ]
        )

        if (
            accion.get(
                "origen"
            )
            != "qwen"
        ):
            return

        accion["estado_ia"] = str(
            estado
            or ""
        ).strip().upper()

        accion["detalle_ia"] = str(
            detalle
            or ""
        ).strip()

        self.refrescar_panel_acciones()

    # ========================================================
    # DETENER OBJETIVO QWEN INICIADO DESDE EL CHAT
    # ========================================================

    def detener_accion_chat_qwen(
        self,
    ):
        self.detener_chat_qwen_solicitado = True

        # Invalida cualquier callback pendiente
        # perteneciente al ciclo anterior.
        self.chat_qwen_ciclo_id += 1

        for atributo in (
            "respuesta_red_chat_qwen",
            "respuesta_red_verificacion_chat_qwen",
        ):
            respuesta = getattr(
                self,
                atributo,
                None,
            )

            if respuesta is not None:
                try:
                    if not respuesta.isFinished():
                        respuesta.abort()
                except Exception:
                    pass

            setattr(
                self,
                atributo,
                None,
            )

        self.objetivo_chat_qwen_activo = None

        self.pasos_objetivo_chat_qwen = 0

        self.intentos_verificacion_chat_qwen = 0

        self.verificacion_chat_pendiente = None

        self.inicio_chat_qwen_monotonic = None

        self.inicio_verificacion_chat_qwen_monotonic = (
            None
        )

        self.mensaje_chat_qwen_pendiente = None

        if hasattr(
            self,
            "boton_detener_chat_qwen",
        ):
            self.boton_detener_chat_qwen.setEnabled(
                False
            )

        self.actualizar_chat_bin(
            "Detuve la acción iniciada "
            "desde el chat de Qwen."
        )

    def procesar_chat(self):
        if not hasattr(
            self,
            "entrada_chat",
        ):
            return

        texto = (
            self.entrada_chat.text()
            .strip()
        )

        if not texto:
            return

        self.entrada_chat.clear()

        self.actualizar_chat_usuario(
            texto
        )

        # ====================================================
        # ACTUALIZAR VISIÓN ANTES DE ENVIAR A QWEN
        # ====================================================
        #
        # No dependemos del último frame del hilo.
        # Tomamos una fotografía física ahora mismo
        # y la mostramos inmediatamente en el Visor IA.
        # ====================================================

        frame = (
            self.capturar_frame_fresco_ia()
        )

        if frame is None:
            self.actualizar_chat_bin(
                "No pude actualizar la pantalla "
                "antes de consultar a Qwen."
            )

            return

        QApplication.processEvents()

        self.enviar_chat_qwen(
            texto,
            frame_preparado=frame,
        )

    def enviar_chat_qwen(
        self,
        texto,
        continuacion=False,
        nota_continuacion="",
        ciclo_id=None,
        frame_preparado=None,
    ):
        # ====================================================
        # V1 ESTABLE:
        # UNA CONSULTA QWEN → HASTA 5 HERRAMIENTAS
        # ====================================================

        # El ciclo autónomo de continuación queda
        # desactivado de momento para la V1.
        if continuacion:
            return

        if (
            self.respuesta_red_chat_qwen
            is not None
        ):
            try:
                if not (
                    self.respuesta_red_chat_qwen
                    .isFinished()
                ):
                    self.actualizar_chat_bin(
                        "Qwen ya está respondiendo "
                        "otro mensaje."
                    )
                    return

            except Exception:
                pass

        if (
            self.respuesta_red_agente_ia
            is not None
        ):
            try:
                if not (
                    self.respuesta_red_agente_ia
                    .isFinished()
                ):
                    self.actualizar_chat_bin(
                        "Qwen está ocupado con "
                        "la tarea actual."
                    )
                    return

            except Exception:
                pass

        if (
            self.respuesta_red_ia_visual
            is not None
        ):
            try:
                if not (
                    self.respuesta_red_ia_visual
                    .isFinished()
                ):
                    self.actualizar_chat_bin(
                        "Qwen está ocupado "
                        "supervisando una tarea."
                    )
                    return

            except Exception:
                pass

        texto = str(
            texto
            or ""
        ).strip()

        if not texto:
            return

        # ====================================================
        # NUEVO CICLO DE CHAT
        # ====================================================

        self.chat_qwen_ciclo_id += 1

        ciclo_id = (
            self.chat_qwen_ciclo_id
        )

        self.detener_chat_qwen_solicitado = (
            False
        )

        if hasattr(
            self,
            "boton_detener_chat_qwen",
        ):
            self.boton_detener_chat_qwen.setEnabled(
                True
            )

        # ====================================================
        # CONTEXTO DE TAREA SOLO COMO INFORMACIÓN
        # ====================================================

        tarea = (
            self.obtener_tarea_ejecutando()
        )

        if (
            tarea is None
            and self.tarea_seleccionada_id
            is not None
        ):
            tarea = self.obtener_tarea(
                self.tarea_seleccionada_id
            )

        contexto_tarea = None

        if tarea:
            contexto_tarea = {
                "nombre": tarea.get(
                    "nombre"
                ),
                "objetivo_ia": tarea.get(
                    "objetivo_ia"
                ),
                "rutina": (
                    self.resumir_rutina_para_ia(
                        tarea
                    )[:20]
                ),
            }

        # ====================================================
        # CAPTURA FRESCA
        # ====================================================

        frame = frame_preparado

        if frame is None:
            frame = (
                self.capturar_frame_fresco_ia()
            )

        else:
            try:
                frame = frame.copy()
            except Exception:
                pass

        imagen_base64 = (
            self.convertir_frame_ia_a_base64(
                frame
            )
        )

        if not imagen_base64:
            self.actualizar_chat_bin(
                "No envié la instrucción a Qwen "
                "porque no pude preparar "
                "la captura actual."
            )

            if hasattr(
                self,
                "boton_detener_chat_qwen",
            ):
                self.boton_detener_chat_qwen.setEnabled(
                    False
                )

            return

        # ====================================================
        # PROMPT ESTABLE DEL AGENTE DE CHAT
        # ====================================================

        instrucciones = (
            "You are Qwen3-VL Instruct integrated inside "
            "BIN, a Windows automation application.\n\n"

            "You can either ANSWER the user or ACT on "
            "the Windows computer using BIN tools.\n\n"

            "MODE RULES:\n"

            "ANSWER = the user asked a question or did not "
            "request a physical computer action. "
            "When mode is ANSWER, actions MUST be empty.\n\n"

            "ACT = the user explicitly asked you to perform "
            "something on the computer.\n\n"

            "IMPORTANT ACTION STRATEGY:\n"

            "When the user names an application, prefer "
            "abrir_aplicacion instead of visually clicking "
            "its icon.\n"

            "When the user asks to open a website, prefer "
            "navegar_url instead of manually clicking the "
            "browser address bar.\n"

            "Use visual click or doble_click when the target "
            "must actually be located from the screenshot.\n\n"

            "A named application does NOT need to be visible "
            "on the screenshot before you may use "
            "abrir_aplicacion.\n\n"

            "If the user asks for a short sequence such as "
            "'open Notepad and write hello', you may return "
            "the necessary tools in order.\n\n"

            "MOUSE RULES:\n"

            "Use click for buttons, tabs and taskbar items.\n"

            "Use doble_click for desktop icons, files and "
            "folders that normally require double click.\n"

            "For click and doble_click use x_norm/y_norm "
            "between 0.0 and 1.0.\n"

            "Never invent coordinates for an object that "
            "you cannot see.\n\n"

            "Never use click_central from chat.\n\n"

            "AVAILABLE BIN TOOLS:\n"

            "abrir_aplicacion, abrir_inicio, "
            "click, doble_click, abrir_elemento, "
            "abrir_menu_contextual, "
            "desplazar, scroll, scroll_agrupado, "
            "arrastrar, escribir_texto, copiar, pegar, "
            "cortar, deshacer, rehacer, seleccionar_todo, "
            "guardar, buscar, imprimir, cambiar_aplicacion, "
            "cerrar_ventana, navegar_url, navegar, "
            "buscar_o_navegar, tecla, atajo_teclado.\n\n"

            "KEYBOARD SAFETY RULES:\n"
            "escribir_texto and normal tecla actions MUST "
            "have an explicit target window.\n"
            "Use proceso_objetivo when the target application "
            "is known.\n"
            "Use usar_foreground=true only when the CURRENT "
            "screen clearly proves that the intended external "
            "window or input is already focused.\n"
            "Never type into an unspecified window.\n\n"

            "GLOBAL SHORTCUT RULES:\n"
            "Use atajo_teclado for Windows shortcuts and "
            "keyboard combinations such as Windows+R, "
            "Windows+S, Ctrl+Shift+S, Alt+F4, etc.\n"
            "Global shortcuts do NOT require proceso_objetivo.\n"
            "For an arbitrary simultaneous combination, "
            "use the teclas array.\n\n"

            "IMPORTANT NAVIGATION RULE:\n"
            "buscar_o_navegar is ONLY for web browsers.\n"
            "Do NOT use buscar_o_navegar to search Windows "
            "files, folders or applications.\n"
            "For Windows Search use Windows+S with "
            "atajo_teclado, verify the screen, then continue.\n\n"

            "APPLICATION RULE:\n"
            "When opening a known application, include its "
            "real Windows process whenever possible, even "
            "if the user misspelled the application name.\n\n"

            "EXACT TOOL ARGUMENTS:\n"

            'escribir_texto: '
            '{"texto":"...","proceso_objetivo":"notepad.exe"}\n'

            'escribir_texto foreground: '
            '{"texto":"...","usar_foreground":true}\n'

            'tecla: '
            '{"tecla":"enter","proceso_objetivo":"notepad.exe"}\n'

            'atajo_teclado: '
            '{"modificadores":["win"],"tecla":"r"}\n'

            'atajo_teclado arbitrary combination: '
            '{"teclas":["ctrl","shift","s"]}\n'

            'abrir_aplicacion: '
            '{"consulta":"bloc de notas",'
            '"proceso":"notepad.exe"}\n'

            'click: '
            '{"x_norm":0.0,"y_norm":0.0}\n'

            'doble_click: '
            '{"x_norm":0.0,"y_norm":0.0}\n'

            'navegar_url: '
            '{"destino":"https://example.com",'
            '"navegador":"chrome.exe"}\n\n'

            "Do not claim that an action was executed "
            "unless you return it inside actions.\n\n"

            "Return ONLY one valid JSON object:\n"

            "{\n"
            '  "mode": "ANSWER|ACT",\n'
            '  "response": "short Spanish response",\n'
            '  "screen_summary": "short visible state",\n'
            '  "actions": [\n'
            "    {\n"
            '      "type": "tool_name",\n'
            '      "data": {}\n'
            "    }\n"
            "  ]\n"
            "}\n\n"

            "Use at most 5 actions."
        )

        contenido = (
            "TASK CONTEXT:\n"
            + json.dumps(
                contexto_tarea,
                ensure_ascii=False,
                default=str,
            )
            + "\n\nUSER MESSAGE:\n"
            + texto
        )

        mensajes = [
            {
                "role": "system",
                "content": instrucciones,
            }
        ]

        # Historial corto para reducir contexto.
        for item in (
            self.historial_chat_qwen[-4:]
        ):
            mensajes.append(
                dict(item)
            )

        mensaje_usuario = {
            "role": "user",
            "content": contenido,
            "images": [
                imagen_base64
            ],
        }

        mensajes.append(
            mensaje_usuario
        )

        payload = {
            "model": self.modelo_ia_visual,
            "messages": mensajes,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx_qwen,
                "num_predict": 300,
            },
        }

        solicitud = QNetworkRequest(
            self.url_ia_visual
        )

        solicitud.setHeader(
            QNetworkRequest.KnownHeaders
            .ContentTypeHeader,
            "application/json",
        )

        cuerpo = QByteArray(
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode(
                "utf-8"
            )
        )

        respuesta = (
            self.gestor_red_ia_visual.post(
                solicitud,
                cuerpo,
            )
        )

        self.respuesta_red_chat_qwen = (
            respuesta
        )

        self.inicio_chat_qwen_monotonic = (
            time.monotonic()
        )

        self.mensaje_chat_qwen_pendiente = (
            texto
        )

        self.actualizar_chat_qwen(
            "Analizando tu mensaje "
            "y la captura actual..."
        )

        respuesta.finished.connect(
            lambda respuesta=respuesta,
            ciclo_id=ciclo_id: (
                self.recibir_chat_qwen(
                    respuesta,
                    ciclo_id,
                )
            )
        )
    def recibir_chat_qwen(
        self,
        respuesta,
        ciclo_id=None,
    ):
        if (
            self.detener_chat_qwen_solicitado
            or ciclo_id
            != self.chat_qwen_ciclo_id
        ):
            try:
                respuesta.deleteLater()
            except Exception:
                pass

            return

        texto_usuario = (
            self.mensaje_chat_qwen_pendiente
            or ""
        )

        try:
            # ====================================================
            # ERROR DE RED
            # ====================================================

            if (
                respuesta.error()
                != QNetworkReply
                .NetworkError
                .NoError
            ):
                cuerpo_error = bytes(
                    respuesta.readAll()
                ).decode(
                    "utf-8",
                    errors="replace",
                )

                self.actualizar_chat_qwen(
                    "No pude responder.\n"
                    + (
                        cuerpo_error.strip()
                        or respuesta.errorString()
                    )
                )

                return

            # ====================================================
            # RESPUESTA OLLAMA
            # ====================================================

            bruto = bytes(
                respuesta.readAll()
            ).decode(
                "utf-8",
                errors="replace",
            ).strip()

            if not bruto:
                raise ValueError(
                    "Ollama devolvió una respuesta vacía."
                )

            envoltura = json.loads(
                bruto
            )

            error_ollama = str(
                envoltura.get(
                    "error",
                    "",
                )
                or ""
            ).strip()

            if error_ollama:
                raise ValueError(
                    error_ollama
                )

            contenido_original = (
                envoltura.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            )

            if isinstance(
                contenido_original,
                dict,
            ):
                datos = contenido_original

            else:
                contenido = str(
                    contenido_original
                    or ""
                ).strip()

                if contenido.startswith(
                    "```"
                ):
                    lineas = (
                        contenido.splitlines()
                    )

                    if (
                        lineas
                        and lineas[0]
                        .strip()
                        .startswith("```")
                    ):
                        lineas = lineas[1:]

                    if (
                        lineas
                        and lineas[-1]
                        .strip()
                        == "```"
                    ):
                        lineas = lineas[:-1]

                    contenido = "\n".join(
                        lineas
                    ).strip()

                try:
                    datos = json.loads(
                        contenido
                    )

                except json.JSONDecodeError:
                    inicio = contenido.find(
                        "{"
                    )

                    fin = contenido.rfind(
                        "}"
                    )

                    if (
                        inicio >= 0
                        and fin > inicio
                    ):
                        datos = json.loads(
                            contenido[
                                inicio:
                                fin + 1
                            ]
                        )

                    else:
                        # Respuesta textual normal:
                        # nunca ejecutar herramientas.
                        datos = {
                            "mode": "ANSWER",
                            "response": contenido,
                            "screen_summary": "",
                            "actions": [],
                        }

            if not isinstance(
                datos,
                dict,
            ):
                raise ValueError(
                    "Qwen no devolvió "
                    "un objeto JSON válido."
                )

            # ====================================================
            # DATOS DE QWEN
            # ====================================================

            modo = str(
                datos.get(
                    "mode",
                    "ANSWER",
                )
                or "ANSWER"
            ).strip().upper()

            if modo not in {
                "ANSWER",
                "ACT",
            }:
                modo = "ANSWER"

            respuesta_texto = str(
                datos.get(
                    "response",
                    "",
                )
                or ""
            ).strip()

            resumen_pantalla = str(
                datos.get(
                    "screen_summary",
                    "",
                )
                or ""
            ).strip()

            acciones = datos.get(
                "actions"
            )

            if not isinstance(
                acciones,
                list,
            ):
                acciones = []

            # ====================================================
            # MÉTRICAS
            # ====================================================

            segundos = 0.0

            if (
                self.inicio_chat_qwen_monotonic
                is not None
            ):
                segundos = (
                    time.monotonic()
                    - self.inicio_chat_qwen_monotonic
                )

            prompt_tokens = int(
                envoltura.get(
                    "prompt_eval_count",
                    0,
                )
                or 0
            )

            salida_tokens = int(
                envoltura.get(
                    "eval_count",
                    0,
                )
                or 0
            )

            resultados = []

            # ====================================================
            # EJECUTAR ACCIONES GENERADAS POR QWEN
            # ====================================================

            if modo == "ACT":
                # El chat usa un contexto temporal propio.
                # No modifica ni controla una tarea guardada.
                tarea_chat = {
                    "nombre": "Chat Qwen",
                    "acciones": [],
                    "acciones_semanticas": [],
                }

                for accion in acciones[:5]:
                    if not isinstance(
                        accion,
                        dict,
                    ):
                        continue

                    # --------------------------------------------
                    # MOSTRAR PRIMERO EN EL PANEL
                    # --------------------------------------------

                    indice_panel = (
                        self.registrar_herramienta_qwen_panel(
                            accion
                        )
                    )

                    self.actualizar_estado_herramienta_qwen_panel(
                        indice_panel,
                        "EJECUTANDO",
                    )

                    QApplication.processEvents()

                    # --------------------------------------------
                    # EJECUTAR
                    # --------------------------------------------

                    resultado = (
                        self.ejecutar_herramienta_ia(
                            tarea_chat,
                            accion,
                        )
                    )

                    ok = bool(
                        resultado.get(
                            "ok"
                        )
                    )

                    detalle = str(
                        resultado.get(
                            "detalle",
                            "",
                        )
                        or ""
                    )

                    self.actualizar_estado_herramienta_qwen_panel(
                        indice_panel,
                        (
                            "EJECUTADA"
                            if ok
                            else "ERROR"
                        ),
                        detalle,
                    )

                    QApplication.processEvents()

                    resultados.append(
                        {
                            "type": accion.get(
                                "type",
                                "",
                            ),
                            "ok": ok,
                            "detalle": detalle,
                        }
                    )

                    # Si una acción falla,
                    # no ejecutar las siguientes.
                    if not ok:
                        break

            # ====================================================
            # MOSTRAR RESULTADO
            # ====================================================

            partes = []

            if respuesta_texto:
                partes.append(
                    respuesta_texto
                )

            if resumen_pantalla:
                partes.append(
                    "Pantalla: "
                    + resumen_pantalla
                )

            if modo == "ACT":
                partes.append(
                    "ACCIONES DE QWEN:"
                )

                if resultados:
                    for resultado in resultados:
                        estado = (
                            "OK"
                            if resultado.get(
                                "ok"
                            )
                            else "ERROR"
                        )

                        partes.append(
                            "• "
                            f"{resultado.get('type')} "
                            f"→ {estado}"
                        )

                        if resultado.get(
                            "detalle"
                        ):
                            partes.append(
                                "  "
                                + resultado.get(
                                    "detalle"
                                )
                            )

                else:
                    partes.append(
                        "• Qwen pidió actuar, "
                        "pero no entregó "
                        "herramientas válidas."
                    )

            partes.append(
                "────────────────────\n"
                f"Modo: {modo}\n"
                f"Tiempo: {segundos:.1f} s\n"
                f"Entrada: {prompt_tokens} tokens\n"
                f"Salida: {salida_tokens} tokens"
            )

            self.actualizar_chat_qwen(
                "\n".join(
                    partes
                )
            )

            # ====================================================
            # HISTORIAL
            # ====================================================

            if texto_usuario:
                self.historial_chat_qwen.append(
                    {
                        "role": "user",
                        "content": texto_usuario,
                    }
                )

            if respuesta_texto:
                self.historial_chat_qwen.append(
                    {
                        "role": "assistant",
                        "content": respuesta_texto,
                    }
                )

            if len(
                self.historial_chat_qwen
            ) > 8:
                self.historial_chat_qwen = (
                    self.historial_chat_qwen[
                        -8:
                    ]
                )

        except Exception as error:
            self.actualizar_chat_qwen(
                "Error interpretando la "
                f"respuesta: {error}"
            )

        finally:
            if (
                self.respuesta_red_chat_qwen
                is respuesta
            ):
                self.respuesta_red_chat_qwen = (
                    None
                )

            self.inicio_chat_qwen_monotonic = (
                None
            )

            self.mensaje_chat_qwen_pendiente = (
                None
            )

            self.objetivo_chat_qwen_activo = (
                None
            )

            self.pasos_objetivo_chat_qwen = 0

            self.intentos_verificacion_chat_qwen = 0

            if hasattr(
                self,
                "boton_detener_chat_qwen",
            ):
                self.boton_detener_chat_qwen.setEnabled(
                    False
                )

            respuesta.deleteLater()
    # ========================================================
    # INICIAR VERIFICACIÓN VISUAL DE UNA ACCIÓN DEL CHAT
    # ========================================================

    def iniciar_verificacion_chat_qwen(
        self,
        indice_panel,
        accion,
        objetivo,
        frame_antes=None,
        ciclo_id=None,
    ):
        if not isinstance(
            accion,
            dict,
        ):
            return

        if (
            self.pasos_objetivo_chat_qwen
            >= self.max_pasos_objetivo_chat_qwen
        ):
            self.actualizar_estado_herramienta_qwen_panel(
                indice_panel,
                "ERROR",
                "Máximo de pasos alcanzado.",
            )

            self.actualizar_chat_qwen(
                "Detuve el objetivo porque Qwen "
                "alcanzó el máximo de pasos permitidos."
            )

            self.objetivo_chat_qwen_activo = None

            return

        self.actualizar_estado_herramienta_qwen_panel(
            indice_panel,
            "VERIFICANDO",
        )

        QApplication.processEvents()

        self.intentos_verificacion_chat_qwen = 0

        self.enviar_verificacion_chat_qwen(
            indice_panel,
            accion,
            objetivo,
            frame_antes,
            ciclo_id,
        )

    # ========================================================
    # ENVIAR CAPTURA POST-ACCIÓN A QWEN
    # ========================================================

    def enviar_verificacion_chat_qwen(
        self,
        indice_panel,
        accion,
        objetivo,
        frame_antes=None,
        ciclo_id=None,
    ):
        if (
            self.respuesta_red_verificacion_chat_qwen
            is not None
        ):
            try:
                if not (
                    self.respuesta_red_verificacion_chat_qwen
                    .isFinished()
                ):
                    return

            except Exception:
                pass

        # --------------------------------------------
        # FOTO NUEVA DESPUÉS DE LA ACCIÓN
        # --------------------------------------------

        # --------------------------------------------
        # IMAGEN ANTES
        # --------------------------------------------

        imagen_antes_base64 = (
            self.convertir_frame_ia_a_base64(
                frame_antes
            )
        )

        # --------------------------------------------
        # IMAGEN DESPUÉS
        # --------------------------------------------

        frame_despues = (
            self.capturar_frame_fresco_ia()
        )

        imagen_despues_base64 = (
            self.convertir_frame_ia_a_base64(
                frame_despues
            )
        )

        if not imagen_antes_base64:
            self.actualizar_estado_herramienta_qwen_panel(
                indice_panel,
                "ERROR",
                "Falta la captura anterior.",
            )

            self.actualizar_chat_qwen(
                "No puedo verificar causalmente "
                "la acción porque falta la "
                "captura anterior."
            )

            self.objetivo_chat_qwen_activo = None

            return

        if not imagen_despues_base64:
            self.actualizar_estado_herramienta_qwen_panel(
                indice_panel,
                "ERROR",
                "Falta la captura posterior.",
            )

            self.actualizar_chat_qwen(
                "No pude capturar la pantalla "
                "después de la acción."
            )

            self.objetivo_chat_qwen_activo = None

            return

        datos_accion = json.dumps(
            accion,
            ensure_ascii=False,
            default=str,
        )

        prompt = (
            "You are Qwen3-VL Instruct acting as the "
            "visual verifier of BIN on Windows.\n\n"

            "You receive TWO screenshots from the SAME "
            "desktop workflow.\n\n"

            "IMAGE 1 = BEFORE BIN executed the action.\n"
            "IMAGE 2 = AFTER BIN executed the action.\n\n"

            "USER'S COMPLETE GOAL:\n"
            f"{objetivo}\n\n"

            "ACTION JUST EXECUTED:\n"
            f"{datos_accion}\n\n"

            "YOUR FIRST MANDATORY QUESTION IS:\n"
            "Did the visible screen change as a consequence "
            "of the executed action?\n\n"

            "Then evaluate whether that visible change "
            "actually corresponds to the action BIN "
            "executed.\n\n"

            "IMPORTANT CAUSAL RULES:\n"
            "- Compare IMAGE 1 against IMAGE 2.\n"
            "- screen_changed=true only if IMAGE 2 contains "
            "a meaningful visible change from IMAGE 1.\n"
            "- change_matches_action=true only if that "
            "change is consistent with the executed action.\n"
            "- A change in the wrong application, wrong "
            "window, wrong input field, or wrong page does "
            "NOT match the action.\n"
            "- Never credit something that was already "
            "present in IMAGE 1.\n"
            "- Never assume success just because BIN says "
            "the command was sent.\n\n"

            "SPECIAL NAVIGATION RULE:\n"
            "For navegar_url, navegar, or buscar_o_navegar, "
            "the intended website/domain or clearly matching "
            "page content must be visible in IMAGE 2.\n"
            "Merely opening a browser, selecting an address "
            "bar, or typing text into another application "
            "is NOT success.\n\n"

            "UNCERTAINTY RULE:\n"
            "If the expected target is not unambiguously "
            "visible in IMAGE 2, prefer NOT_CONFIRMED.\n"

            "If you are uncertain whether the visible change "
            "really belongs to the requested action, prefer "
            "NOT_CONFIRMED and let BIN inspect again.\n"

            "DONE is valid only when status is CONFIRMED "
            "and the user's COMPLETE goal is visibly "
            "satisfied in IMAGE 2.\n\n"

            "VERIFICATION STATUS:\n"
            "CONFIRMED = the expected visible effect occurred "
            "and change_matches_action is true.\n"
            "NOT_CONFIRMED = the expected visible effect did "
            "not occur, the wrong place changed, or the "
            "change does not correspond to the action.\n"
            "WAIT = IMAGE 2 is visibly still loading or "
            "transitioning and cannot yet be judged.\n\n"

            "GOAL STATUS:\n"
            "DONE = the user's COMPLETE goal is visibly "
            "satisfied in IMAGE 2.\n"
            "CONTINUE = more physical work is still needed.\n\n"

            "Return ONLY one JSON object:\n"
            "{\n"
            '  "screen_changed": true,\n'
            '  "change_matches_action": true,\n'
            '  "status": '
            '"CONFIRMED|NOT_CONFIRMED|WAIT",\n'
            '  "goal_status": "DONE|CONTINUE",\n'
            '  "screen_summary": '
            '"short description of IMAGE 2",\n'
            '  "reason": '
            '"short causal verification reason"\n'
            "}"
        )
        payload = {
            "model": self.modelo_ia_visual,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [
                        imagen_antes_base64,
                        imagen_despues_base64,
                    ],
                }
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx_qwen,
                "num_predict": 180,
            },
        }

        solicitud = QNetworkRequest(
            self.url_ia_visual
        )

        solicitud.setHeader(
            QNetworkRequest.KnownHeaders
            .ContentTypeHeader,
            "application/json",
        )

        cuerpo = QByteArray(
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode(
                "utf-8"
            )
        )

        respuesta = (
            self.gestor_red_ia_visual.post(
                solicitud,
                cuerpo,
            )
        )

        self.respuesta_red_verificacion_chat_qwen = (
            respuesta
        )

        self.inicio_verificacion_chat_qwen_monotonic = (
            time.monotonic()
        )

        self.verificacion_chat_pendiente = {
            "indice_panel": indice_panel,
            "accion": accion,
            "objetivo": objetivo,
        }

        self.actualizar_chat_qwen(
            "👁 Verificando visualmente "
            "la acción ejecutada..."
        )

        respuesta.finished.connect(
            lambda respuesta=respuesta,
            indice_panel=indice_panel,
            accion=accion,
            objetivo=objetivo,
            frame_antes=frame_antes,
            ciclo_id=ciclo_id: (
                self.recibir_verificacion_chat_qwen(
                    respuesta,
                    indice_panel,
                    accion,
                    objetivo,
                    frame_antes,
                    ciclo_id,
                )
            )
        )

    # ========================================================
    # RECIBIR VERIFICACIÓN VISUAL
    # ========================================================

    def recibir_verificacion_chat_qwen(
        self,
        respuesta,
        indice_panel,
        accion,
        objetivo,
        frame_antes=None,
        ciclo_id=None,
    ):
        continuar = False

        nota_continuacion = ""

        try:
            segundos = 0.0

            if (
                self.inicio_verificacion_chat_qwen_monotonic
                is not None
            ):
                segundos = (
                    time.monotonic()
                    - self.inicio_verificacion_chat_qwen_monotonic
                )

            if (
                respuesta.error()
                != QNetworkReply
                .NetworkError
                .NoError
            ):
                cuerpo = bytes(
                    respuesta.readAll()
                ).decode(
                    "utf-8",
                    errors="replace",
                )

                raise ValueError(
                    cuerpo.strip()
                    or respuesta.errorString()
                )

            bruto = bytes(
                respuesta.readAll()
            ).decode(
                "utf-8",
                errors="replace",
            ).strip()

            if not bruto:
                raise ValueError(
                    "Ollama devolvió una verificación vacía."
                )

            envoltura = json.loads(
                bruto
            )

            contenido = str(
                envoltura.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
                or ""
            ).strip()

            if contenido.startswith(
                "```"
            ):
                lineas = (
                    contenido.splitlines()
                )

                if (
                    lineas
                    and lineas[0]
                    .strip()
                    .startswith("```")
                ):
                    lineas = lineas[1:]

                if (
                    lineas
                    and lineas[-1]
                    .strip()
                    == "```"
                ):
                    lineas = lineas[:-1]

                contenido = "\n".join(
                    lineas
                ).strip()

            datos = json.loads(
                contenido or "{}"
            )

            if not isinstance(
                datos,
                dict,
            ):
                raise ValueError(
                    "Formato de verificación inválido."
                )

            estado = str(
                datos.get(
                    "status",
                    "NOT_CONFIRMED",
                )
                or "NOT_CONFIRMED"
            ).strip().upper()

            if estado not in {
                "CONFIRMED",
                "NOT_CONFIRMED",
                "WAIT",
            }:
                estado = "NOT_CONFIRMED"

            estado_objetivo = str(
                datos.get(
                    "goal_status",
                    "CONTINUE",
                )
                or "CONTINUE"
            ).strip().upper()

            # ====================================================
            # CAMBIO CAUSAL DE PANTALLA
            # ====================================================

            cambio_pantalla = (
                datos.get(
                    "screen_changed"
                )
                is True
            )

            cambio_coincide = (
                datos.get(
                    "change_matches_action"
                )
                is True
            )

            # Qwen no puede decir CONFIRMED
            # si el cambio no corresponde a la acción.
            if (
                estado == "CONFIRMED"
                and not cambio_coincide
            ):
                estado = "NOT_CONFIRMED"

            tipo_accion = str(
                accion.get(
                    "type",
                    "",
                )
                or ""
            ).strip().lower()

            # Para navegación exigimos además
            # que realmente haya ocurrido un cambio.
            if tipo_accion in {
                "navegar_url",
                "navegar",
                "buscar_o_navegar",
            }:
                if (
                    not cambio_pantalla
                    or not cambio_coincide
                ):
                    estado = "NOT_CONFIRMED"
                    estado_objetivo = "CONTINUE"

            if estado_objetivo not in {
                "DONE",
                "CONTINUE",
            }:
                estado_objetivo = "CONTINUE"

            # ====================================================
            # DONE NUNCA PUEDE SOBREVIVIR A UNA VERIFICACIÓN
            # QUE NO HAYA SIDO CONFIRMADA
            # ====================================================

            if (
                estado_objetivo == "DONE"
                and estado != "CONFIRMED"
            ):
                estado_objetivo = "CONTINUE"

            resumen = str(
                datos.get(
                    "screen_summary",
                    "",
                )
                or ""
            ).strip()

            razon = str(
                datos.get(
                    "reason",
                    "",
                )
                or ""
            ).strip()

            # --------------------------------------------
            # ACCIÓN CONFIRMADA VISUALMENTE
            # --------------------------------------------

            if estado == "CONFIRMED":
                self.actualizar_estado_herramienta_qwen_panel(
                    indice_panel,
                    "CONFIRMADA",
                    razon,
                )

                self.actualizar_chat_qwen(
                    "✓ ACCIÓN CONFIRMADA\n"
                    + (
                        f"Pantalla: {resumen}\n"
                        if resumen
                        else ""
                    )
                    + (
                        f"Verificación: {razon}\n"
                        if razon
                        else ""
                    )
                    + (
                        "Objetivo: COMPLETADO\n"
                        if estado_objetivo == "DONE"
                        else (
                            "Objetivo: todavía requiere "
                            "más pasos\n"
                        )
                    )
                    + (
                        "Cambio de pantalla: SÍ\n"
                        if cambio_pantalla
                        else "Cambio de pantalla: NO\n"
                    )
                    + (
                        "Cambio corresponde a la acción: SÍ\n"
                        if cambio_coincide
                        else (
                            "Cambio corresponde a la acción: NO\n"
                        )
                    )
                    + (
                        f"Tiempo de verificación: "
                        f"{segundos:.1f} s"
                    )
                )

                if estado_objetivo == "DONE":
                    self.objetivo_chat_qwen_activo = (
                        None
                    )

                    self.pasos_objetivo_chat_qwen = 0

                    self.intentos_verificacion_chat_qwen = (
                        0
                    )

                else:
                    continuar = True

                    nota_continuacion = (
                        "The previous physical action "
                        "was visually CONFIRMED. "
                        "Continue toward the same user "
                        "goal from the CURRENT screen. "
                        "Return exactly ONE next action, "
                        "or ANSWER if the complete goal "
                        "is already satisfied."
                    )

            # --------------------------------------------
            # TODAVÍA ESTÁ CARGANDO
            # --------------------------------------------

            elif estado == "WAIT":
                self.intentos_verificacion_chat_qwen += 1

                if (
                    self.intentos_verificacion_chat_qwen
                    <= 1
                ):
                    self.actualizar_chat_qwen(
                        "La pantalla todavía parece "
                        "estar cambiando. Haré una nueva "
                        "captura antes de decidir."
                    )

                    QTimer.singleShot(
                        900,
                        lambda indice_panel=indice_panel,
                        accion=accion,
                        objetivo=objetivo,
                        frame_antes=frame_antes,
                        ciclo_id=ciclo_id: (
                            self.enviar_verificacion_chat_qwen(
                                indice_panel,
                                accion,
                                objetivo,
                                frame_antes,
                                ciclo_id,
                            )
                        ),
                    )

                else:
                    self.actualizar_estado_herramienta_qwen_panel(
                        indice_panel,
                        "CORRIGIENDO",
                        razon,
                    )

                    continuar = True

                    nota_continuacion = (
                        "The previous action could not "
                        "be visually confirmed after "
                        "waiting. Inspect the CURRENT "
                        "screen and choose exactly ONE "
                        "safe corrective action."
                    )

            # --------------------------------------------
            # ACCIÓN NO CONFIRMADA
            # --------------------------------------------

            else:
                self.actualizar_estado_herramienta_qwen_panel(
                    indice_panel,
                    "CORRIGIENDO",
                    razon,
                )

                self.actualizar_chat_qwen(
                    "⚠ ACCIÓN NO CONFIRMADA\n"
                    + (
                        f"Pantalla: {resumen}\n"
                        if resumen
                        else ""
                    )
                    + (
                        f"Motivo: {razon}\n"
                        if razon
                        else ""
                    )
                    + "Qwen volverá a analizar la "
                    "pantalla antes de intentar corregir."
                )

                continuar = True

                nota_continuacion = (
                    "The previous physical action was "
                    "NOT visually confirmed. "
                    f"Verification reason: {razon}. "
                    "Inspect the CURRENT screenshot and "
                    "choose exactly ONE corrective action "
                    "that moves toward the same user goal. "
                    "Do not blindly repeat the failed action."
                )

        except Exception as error:
            self.actualizar_estado_herramienta_qwen_panel(
                indice_panel,
                "ERROR",
                str(error),
            )

            self.actualizar_chat_qwen(
                "Error verificando visualmente "
                f"la acción: {error}"
            )

            self.objetivo_chat_qwen_activo = None

        finally:
            if (
                self.respuesta_red_verificacion_chat_qwen
                is respuesta
            ):
                self.respuesta_red_verificacion_chat_qwen = (
                    None
                )

            self.inicio_verificacion_chat_qwen_monotonic = (
                None
            )

            self.verificacion_chat_pendiente = (
                None
            )

            respuesta.deleteLater()

        # --------------------------------------------
        # SIGUIENTE DECISIÓN QWEN
        # --------------------------------------------

        if (
            continuar
            and self.objetivo_chat_qwen_activo
        ):
            objetivo_activo = str(
                self.objetivo_chat_qwen_activo
            )

            QTimer.singleShot(
                300,
                lambda objetivo=objetivo_activo,
                nota=nota_continuacion,
                ciclo_id=ciclo_id: (
                    self.enviar_chat_qwen(
                        objetivo,
                        continuacion=True,
                        nota_continuacion=nota,
                        ciclo_id=ciclo_id,
                    )
                ),
            )

    def limpiar_panel_acciones(self):
        if self.grabando:
            QMessageBox.information(
                self,
                "BIN está grabando",
                (
                    "Detén primero MOSTRAR RUTINA antes de "
                    "limpiar el Panel de acciones."
                ),
            )
            return

        tarea_ejecutando = self.obtener_tarea_ejecutando()

        if tarea_ejecutando is not None:
            QMessageBox.information(
                self,
                "BIN está ejecutando",
                (
                    "No limpiaré el Panel de acciones mientras "
                    "una tarea esté ejecutándose."
                ),
            )
            return

        if self.rutina_en_borrador and self.rutina_borrador:
            respuesta = QMessageBox.question(
                self,
                "Limpiar Panel de acciones",
                (
                    "El panel contiene instrucciones que todavía "
                    "no pertenecen a una tarea guardada.\n\n"
                    "¿Quieres eliminarlas del panel?"
                ),
                QMessageBox.Yes | QMessageBox.No,
            )

            if respuesta != QMessageBox.Yes:
                return

        self.tarea_seleccionada_id = None

        self.rutina_en_borrador = True

        self.rutina_borrador = []

        self.rutina_borrador_semantica = []

        self.duracion_rutina_borrador = 0

        self.inicio_grabacion = None

        self.tarjeta_accion_activa = None

        self.refrescar_panel_acciones()

        self.actualizar_chat_bin(
            "Limpié el Panel de acciones. "
            "Las acciones guardadas de tus tareas no fueron modificadas."
        )

    def resetear_tarea_pausada(self, tarea_id):
        tarea = self.obtener_tarea(tarea_id)

        if not tarea:
            return

        if (
            tarea.get("estado") != "EN PAUSA"
            or not tarea.get("current_run_key")
        ):
            return

        respuesta = QMessageBox.question(
            self,
            "Resetear tarea",
            (
                f"¿Quieres abandonar la ejecución pausada de "
                f"'{tarea['nombre']}'?\n\n"
                "BIN olvidará el progreso y el plan de esta ejecución.\n"
                "La tarea guardada y su demostración original se conservarán."
            ),
            QMessageBox.Yes | QMessageBox.No,
        )

        if respuesta != QMessageBox.Yes:
            return

        run_key_cancelado = tarea.get(
            "current_run_key"
        )

        # ----------------------------------------------------
        # MARCAR EJECUCIÓN PROGRAMADA COMO OMITIDA
        # ----------------------------------------------------

        if (
            isinstance(run_key_cancelado, str)
            and run_key_cancelado.startswith("sched-")
        ):
            tarea["last_skipped_run_key"] = (
                run_key_cancelado
            )

            if hasattr(
                self,
                "runs_retrasados_aceptados",
            ):
                self.runs_retrasados_aceptados.discard(
                    (
                        tarea.get("id"),
                        run_key_cancelado,
                    )
                )

        # ----------------------------------------------------
        # LIMPIAR ESTADO DE ESTA EJECUCIÓN
        # ----------------------------------------------------

        tarea["estado"] = "EN ESPERA"

        tarea["elapsed_seconds"] = 0

        tarea["runtime_base_seconds"] = 0

        tarea["transcurrido"] = "00:00:00"

        tarea["progreso"] = 0

        tarea["runtime_started_at"] = None

        tarea["current_run_key"] = None

        tarea["queued_at"] = None

        tarea["completed_at"] = None

        tarea["accion_actual_indice"] = None

        tarea["repeticion_actual"] = 0

        tarea["ejecucion_real_indice"] = 0

        tarea["ejecucion_real_repeticion"] = 1

        tarea["ejecuciones_reales_completadas"] = 0

        tarea["delay_ejecucion_restante_ms"] = 0

        tarea["ejecucion_real_fase"] = "inactiva"

        tarea["elapsed_repeticion_real_ms"] = 0

        tarea["supervisor_espera_acumulada_ms"] = 0

        tarea["supervisor_intentos"] = 0

        tarea["supervisor_ultima_decision"] = None

        tarea["supervisor_ultimo_motivo"] = ""

        tarea["ultimo_checkpoint"] = {}

        # ----------------------------------------------------
        # DESCARTAR EL PLAN TEMPORAL DE QWEN
        # ----------------------------------------------------

        tarea["plan_ia"] = []

        tarea["detalle_estado"] = (
            "Ejecución anterior reseteada · "
            "Esperando próxima programación"
        )

        # ----------------------------------------------------
        # LIMPIAR MOTOR GLOBAL SI BIN ESTÁ LIBRE
        # ----------------------------------------------------

        tarea_ejecutando = (
            self.obtener_tarea_ejecutando()
        )

        if tarea_ejecutando is None:

            if (
                hasattr(
                    self,
                    "timer_ejecucion_accion",
                )
                and self.timer_ejecucion_accion.isActive()
            ):
                self.timer_ejecucion_accion.stop()

            self.cancelar_consulta_ia_visual()

            self.cancelar_consulta_agente_ia()

            self.plan_ejecucion_actual = []

            self.offsets_ejecucion_actual_ms = []

            self.plan_ejecucion_usa_semantica = False

            self.indice_ejecucion_real = 0

            self.repeticion_ejecucion_real = 1

            self.ejecuciones_reales_completadas = 0

            self.ejecuciones_reales_totales = 0

            self.delay_ejecucion_restante_ms = 0

            self.fase_ejecucion_real = "inactiva"

            self.accion_real_actual = None

            self.resultado_accion_real_actual = None

            self.ejecucion_fisica_activa = False

            self.inicio_repeticion_real_monotonic = None

            self.elapsed_repeticion_base_ms = 0

            # --------------------------------------------
            # AGENTE QWEN
            # --------------------------------------------

            self.plan_agente_ia_actual = []

            self.indice_plan_agente_ia = 0

            self.reanalisis_agente_ia = 0

            self.historial_agente_ia = []

            self.pasos_agente_ia_actual = 0

            self.ultima_firma_plan_agente_ia = None

            self.repeticiones_plan_agente_ia = 0

            self.estancamientos_agente_ia = 0

            # --------------------------------------------
            # SUPERVISOR
            # --------------------------------------------

            self.inicio_espera_supervisor_monotonic = None

            self.espera_supervisor_acumulada_ms = 0

            self.intentos_supervisor = 0

            self.ultima_decision_supervisor = None

            self.ultimo_motivo_supervisor = ""

            self.supervisor_hubo_wait = False

            # --------------------------------------------
            # CONTROL IA LEGACY
            # --------------------------------------------

            self.pausa_ia_activa = False

            self.clave_accion_autorizada_ia = None

            self.inicio_control_trayectoria_ia_monotonic = None

            self.correcciones_ia_consecutivas = 0

            self.ultima_correccion_ia = None

        # ----------------------------------------------------
        # QUITAR BARRA FLOTANTE DE CONTINUAR
        # ----------------------------------------------------

        if (
            self.tarea_pausada_flotante_id
            == tarea_id
        ):
            self.pausa_ejecucion_global = False

            self.tarea_pausada_flotante_id = None

            self.ocultar_barra_ejecucion()

        # ----------------------------------------------------
        # LIMPIAR PANEL DE ACCIONES
        # ----------------------------------------------------

        if (
            self.tarea_seleccionada_id
            == tarea_id
        ):
            self.tarea_seleccionada_id = None

            self.rutina_en_borrador = True

            self.rutina_borrador = []

            self.rutina_borrador_semantica = []

            self.duracion_rutina_borrador = 0

            self.inicio_grabacion = None

        # ----------------------------------------------------
        # ACTUALIZAR INTERFAZ
        # ----------------------------------------------------

        self.guardar_tareas_en_disco()

        self.actualizar_tarjeta_tarea(
            tarea_id
        )

        self.refrescar_panel_acciones()

        self.actualizar_cabecera_operativa()

        self.actualizar_estado_cabecera_visor(
            "Tarea reseteada",
            f"· {tarea['nombre']}",
            VERDE,
        )

        self.actualizar_chat_bin(
            f"Reseteé '{tarea['nombre']}'. "
            "Abandoné la ejecución pausada "
            "y limpié su estado temporal."
        )

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
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
                descripcion.setText(
                    "▶ "
                    + descripcion.text()
                )

                self.tarjeta_accion_activa = (
                    tarjeta
                )

            # ----------------------------------------
            # ESTADO EN VIVO DE ACCIONES DE QWEN
            # ----------------------------------------

            estado_ia = str(
                accion.get(
                    "estado_ia",
                    "",
                )
                or ""
            ).strip().upper()

            etiqueta_estado_ia = None

            if estado_ia:
                simbolos = {
                    "PENDIENTE": "○",
                    "EJECUTANDO": "▶",
                    "EJECUTADA": "✓",
                    "VERIFICANDO": "◉",
                    "CONFIRMADA": "✓",
                    "ERROR": "✕",
                    "CORRIGIENDO": "↻",
                }

                colores = {
                    "PENDIENTE": GRIS,
                    "EJECUTANDO": AMARILLO,
                    "EJECUTADA": AZUL,
                    "VERIFICANDO": AMARILLO,
                    "CONFIRMADA": VERDE,
                    "ERROR": ROJO,
                    "CORRIGIENDO": MORADO,
                }

                simbolo = simbolos.get(
                    estado_ia,
                    "•",
                )

                color = colores.get(
                    estado_ia,
                    TEXTO_SECUNDARIO,
                )

                etiqueta_estado_ia = QLabel(
                    f"{simbolo} QWEN · "
                    f"{estado_ia}"
                )

                etiqueta_estado_ia.setStyleSheet(
                    f"""
                    color: {color};
                    font-size: 10px;
                    font-weight: 800;
                    """
                )

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

            layout.addWidget(
                descripcion
            )

            if (
                etiqueta_estado_ia
                is not None
            ):
                layout.addWidget(
                    etiqueta_estado_ia
                )

            layout.addLayout(
                botones
            )

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

        # Si cambia la demostración,
        # Qwen debe comprenderla nuevamente.
        tarea["objetivo_ia"] = None
        tarea["plan_ia"] = []

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

            # La demostración original queda conservada.
            # Qwen construirá su comprensión por separado.
            "objetivo_ia": None,

            "plan_ia": [],

            "memoria_ia": {
                "correcciones_exitosas": [],
                "correcciones_fallidas": [],
            },

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

    def crear_run_key_programado(self, momento):
        return "sched-" + momento.strftime("%Y%m%d-%H%M")

    def obtener_momento_desde_run_key(self, run_key):
        if not isinstance(run_key, str):
            return None

        if not run_key.startswith("sched-"):
            return None

        try:
            return datetime.strptime(
                run_key[len("sched-") :],
                "%Y%m%d-%H%M",
            )
        except Exception:
            return None

    def obtener_ultimo_momento_programado_vencido(
        self,
        tarea,
        ahora=None,
    ):
        if ahora is None:
            ahora = datetime.now()

        try:
            hora, minuto = [
                int(valor)
                for valor in tarea.get("hora", "").split(":")
            ]
        except Exception:
            return None

        dias = tarea.get("dias", [])

        if not dias:
            return None

        # Una tarea solo se considera retrasada cuando terminó
        # completamente su minuto programado.
        limite = ahora.replace(
            second=0,
            microsecond=0,
        ) - timedelta(minutes=1)

        for desplazamiento in range(0, 8):
            fecha = limite - timedelta(days=desplazamiento)

            if fecha.weekday() not in dias:
                continue

            momento = fecha.replace(
                hour=hora,
                minute=minuto,
                second=0,
                microsecond=0,
            )

            if momento <= limite:
                return momento

        return None

    def obtener_tareas_retrasadas(self, ahora=None):
        if ahora is None:
            ahora = datetime.now()

        retrasadas = []

        for tarea in self.tareas:
            estado = tarea.get("estado")

            if estado in [
                "DETENIDA",
                "EN PAUSA",
                "ERROR",
                "REQUIERE CONFIGURACIÓN",
                "EJECUTANDO",
            ]:
                continue

            momento = self.obtener_ultimo_momento_programado_vencido(
                tarea,
                ahora,
            )

            if momento is None:
                continue

            run_key = self.crear_run_key_programado(momento)

            if tarea.get("last_run_key") == run_key:
                continue

            if tarea.get("last_skipped_run_key") == run_key:
                continue

            clave_retraso = (
                tarea.get("id"),
                run_key,
            )

            if clave_retraso in self.runs_retrasados_aceptados:
                continue

            current_run_key = tarea.get("current_run_key")

            if current_run_key and current_run_key != run_key:
                continue

            duracion_total = self.obtener_duracion_total_tarea(tarea)

            if duracion_total <= 0:
                tarea["estado"] = "REQUIERE CONFIGURACIÓN"
                tarea["detalle_estado"] = (
                    "La tarea quedó retrasada, pero no tiene "
                    "acciones ni duración válidas."
                )
                continue

            retrasadas.append(
                {
                    "tarea": tarea,
                    "momento": momento,
                    "run_key": run_key,
                }
            )

        retrasadas.sort(
            key=lambda item: item["momento"]
        )

        return retrasadas

    def mostrar_dialogo_tareas_retrasadas(self, retrasadas):
        if not retrasadas:
            return True

        if self.dialogo_tareas_retrasadas_abierto:
            return False

        if not self.isVisible():
            return False

        ahora = datetime.now()

        if (
            self.proximo_aviso_tareas_retrasadas is not None
            and ahora < self.proximo_aviso_tareas_retrasadas
        ):
            return False

        self.dialogo_tareas_retrasadas_abierto = True

        try:
            dialogo = QDialog(self)
            dialogo.setWindowTitle("BIN IA Asistem — Tareas retrasadas")
            dialogo.setMinimumWidth(620)
            dialogo.setModal(True)

            layout = QVBoxLayout(dialogo)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            titulo = QLabel("TAREAS RETRASADAS")
            titulo.setObjectName("tituloDialogo")
            layout.addWidget(titulo)

            descripcion = QLabel(
                "BIN detectó tareas cuya hora programada ya pasó.\n"
                "Marca ✓ para ejecutarlas o ✕ para omitir esa ejecución."
            )
            descripcion.setObjectName("textoSecundario")
            descripcion.setWordWrap(True)
            layout.addWidget(descripcion)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(
                min(
                    360,
                    max(120, len(retrasadas) * 68),
                )
            )

            contenido = QWidget()
            lista = QVBoxLayout(contenido)
            lista.setContentsMargins(4, 4, 4, 4)
            lista.setSpacing(8)

            decisiones = []

            for item in retrasadas:
                tarea = item["tarea"]
                momento = item["momento"]
                run_key = item["run_key"]

                fila = QFrame()
                fila.setStyleSheet(
                    f"""
                    QFrame {{
                        background-color: {PANEL_SECUNDARIO};
                        border: 1px solid #2b303a;
                        border-radius: 7px;
                    }}
                    """
                )

                fila_layout = QHBoxLayout(fila)
                fila_layout.setContentsMargins(12, 9, 12, 9)
                fila_layout.setSpacing(10)

                texto = QLabel(
                    f"{momento.strftime('%H:%M')}  ·  {tarea.get('nombre', 'Tarea')}"
                )
                texto.setWordWrap(True)
                fila_layout.addWidget(texto, 1)

                boton_no = QPushButton("✕")
                boton_no.setCheckable(True)
                boton_no.setFixedSize(38, 34)
                boton_no.setToolTip("No ejecutar esta tarea retrasada")
                boton_no.setStyleSheet(
                    f"""
                    QPushButton {{
                        color: {ROJO};
                        border: 1px solid {ROJO};
                        border-radius: 6px;
                        font-size: 16px;
                        font-weight: 900;
                    }}
                    QPushButton:checked {{
                        background-color: {ROJO};
                        color: white;
                    }}
                    """
                )

                boton_si = QPushButton("✓")
                boton_si.setCheckable(True)
                boton_si.setChecked(True)
                boton_si.setFixedSize(38, 34)
                boton_si.setToolTip("Ejecutar esta tarea retrasada")
                boton_si.setStyleSheet(
                    f"""
                    QPushButton {{
                        color: {VERDE};
                        border: 1px solid {VERDE};
                        border-radius: 6px;
                        font-size: 16px;
                        font-weight: 900;
                    }}
                    QPushButton:checked {{
                        background-color: {VERDE};
                        color: #07100b;
                    }}
                    """
                )

                grupo = QButtonGroup(dialogo)
                grupo.setExclusive(True)
                grupo.addButton(boton_no, 0)
                grupo.addButton(boton_si, 1)

                fila_layout.addWidget(boton_no)
                fila_layout.addWidget(boton_si)

                lista.addWidget(fila)

                decisiones.append(
                    {
                        "tarea": tarea,
                        "momento": momento,
                        "run_key": run_key,
                        "grupo": grupo,
                    }
                )

            lista.addStretch()
            scroll.setWidget(contenido)
            layout.addWidget(scroll)

            botones = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )

            boton_aplicar = botones.button(QDialogButtonBox.Ok)
            boton_aplicar.setText("APLICAR DECISIONES")

            boton_cancelar = botones.button(QDialogButtonBox.Cancel)
            boton_cancelar.setText("DECIDIR DESPUÉS")

            botones.accepted.connect(dialogo.accept)
            botones.rejected.connect(dialogo.reject)

            layout.addWidget(botones)

            resultado = dialogo.exec()

            if resultado != QDialog.Accepted:
                self.proximo_aviso_tareas_retrasadas = (
                    datetime.now() + timedelta(seconds=30)
                )
                return False

            self.proximo_aviso_tareas_retrasadas = None

            for decision in decisiones:
                tarea = decision["tarea"]
                momento = decision["momento"]
                run_key = decision["run_key"]
                grupo = decision["grupo"]

                clave_retraso = (
                    tarea.get("id"),
                    run_key,
                )

                if grupo.checkedId() == 1:
                    self.runs_retrasados_aceptados.add(
                        clave_retraso
                    )

                    tarea["estado"] = "EN COLA"
                    tarea["current_run_key"] = run_key
                    tarea["queued_at"] = momento.isoformat()
                    tarea["runtime_started_at"] = None
                    tarea["detalle_estado"] = (
                        "Tarea retrasada · Aprobada para ejecutar"
                    )

                else:
                    self.runs_retrasados_aceptados.discard(
                        clave_retraso
                    )

                    tarea["last_skipped_run_key"] = run_key

                    if tarea.get("current_run_key") == run_key:
                        tarea["current_run_key"] = None

                    tarea["queued_at"] = None
                    tarea["runtime_started_at"] = None
                    tarea["estado"] = "EN ESPERA"
                    tarea["detalle_estado"] = (
                        "Ejecución retrasada omitida por el usuario"
                    )

            self.guardar_tareas_en_disco()
            self.actualizar_tarjetas()
            self.actualizar_cabecera_operativa()

            return True

        finally:
            self.dialogo_tareas_retrasadas_abierto = False

    def obtener_proxima_programada_prioritaria(self, desde=None):
        if desde is None:
            desde = datetime.now()

        candidatas = []

        for tarea in self.tareas:
            estado = tarea.get("estado")

            if estado in [
                "DETENIDA",
                "EN PAUSA",
                "ERROR",
                "REQUIERE CONFIGURACIÓN",
            ]:
                continue

            momento = self.calcular_proxima_ejecucion_tarea(
                tarea,
                desde=desde,
            )

            if momento is not None:
                candidatas.append(momento)

        if not candidatas:
            return None

        return min(candidatas)


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

    def ejecutar_combinacion_teclas_replay(
        self,
        teclas,
    ):
        """
        Ejecuta una combinación arbitraria
        de teclas simultáneamente.

        Ejemplos:
        ["win", "r"]
        ["ctrl", "shift", "s"]
        ["shift", "s", "u", "n", "d", "e"]
        """

        if not self.asegurar_controladores_replay():
            return False

        nombres = list(
            teclas
            or []
        )

        if not nombres:
            return False

        objetos = []

        for nombre in nombres:
            objeto = self.modificador_replay(
                nombre
            )

            if objeto is None:
                objeto = (
                    self.tecla_replay_desde_nombre(
                        nombre
                    )
                )

            if objeto is None:
                return False

            objetos.append(
                objeto
            )

        try:
            for objeto in objetos:
                self.keyboard_replay.press(
                    objeto
                )

            for objeto in reversed(
                objetos
            ):
                self.keyboard_replay.release(
                    objeto
                )

            return True

        except Exception:
            for objeto in reversed(
                objetos
            ):
                try:
                    self.keyboard_replay.release(
                        objeto
                    )
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

    def recuperar_bin_al_frente(self):

        try:
            # -----------------------------------------------
            # RESTAURAR ESTADO VISUAL DE QT
            # -----------------------------------------------

            if self.isMinimized():
                if self.pantalla_completa:
                    self.showFullScreen()
                else:
                    self.showNormal()

            self.raise_()
            self.activateWindow()

            QApplication.processEvents()

            if sys.platform != "win32":
                return

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = int(self.winId())

            # -----------------------------------------------
            # OBTENER FOREGROUND ACTUAL
            # -----------------------------------------------

            hwnd_foreground = user32.GetForegroundWindow()

            hilo_actual = kernel32.GetCurrentThreadId()

            hilo_foreground = 0

            if hwnd_foreground:

                hilo_foreground = user32.GetWindowThreadProcessId(
                    hwnd_foreground,
                    None,
                )

            unido = False

            try:
                # -------------------------------------------
                # UNIR TEMPORALMENTE LOS HILOS DE ENTRADA
                # PARA QUE WINDOWS PERMITA RECUPERAR FOCO
                # -------------------------------------------

                if hilo_foreground and hilo_foreground != hilo_actual:

                    unido = bool(
                        user32.AttachThreadInput(
                            hilo_actual,
                            hilo_foreground,
                            True,
                        )
                    )

                # -------------------------------------------
                # TRAER BIN AL FRENTE
                # -------------------------------------------

                user32.BringWindowToTop(hwnd)

                user32.SetForegroundWindow(hwnd)

                user32.SetFocus(hwnd)

                # -------------------------------------------
                # PANTALLA COMPLETA:
                # MANTENER SOBRE LA BARRA DE TAREAS
                # -------------------------------------------

                if self.pantalla_completa:

                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE,
                    )

                else:

                    # Lo elevamos para asegurar que aparece.
                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE,
                    )

            finally:

                if unido:

                    user32.AttachThreadInput(
                        hilo_actual,
                        hilo_foreground,
                        False,
                    )

            # En modo normal no queremos que BIN quede
            # permanentemente siempre encima.
            if not self.pantalla_completa:

                QTimer.singleShot(
                    150,
                    lambda: ctypes.windll.user32.SetWindowPos(
                        int(self.winId()),
                        HWND_NOTOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                    ),
                )

        except Exception as error:

            print(
                "No pude devolver BIN al frente:",
                error,
            )

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

        # ========================================================

    # IA VISUAL LOCAL — CONVERSIÓN DE FRAME
    # ========================================================

    def convertir_frame_ia_a_base64(
        self,
        imagen,
    ):
        if imagen is None:
            return None

        try:
            if imagen.isNull():
                return None
        except Exception:
            return None

        buffer = QBuffer()

        if not buffer.open(
            QIODevice.OpenModeFlag.WriteOnly
        ):
            return None

        try:
            copia = imagen.copy()

            # ====================================================
            # RESOLUCIÓN FIJA DE CALIBRACIÓN PARA QWEN
            # ====================================================

            ancho_maximo = 640
            alto_maximo = 360

            if (
                copia.width() > ancho_maximo
                or copia.height() > alto_maximo
            ):
                copia = copia.scaled(
                    ancho_maximo,
                    alto_maximo,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

            print(
                "[BIN IA] Frame para Qwen: "
                f"{copia.width()}x"
                f"{copia.height()} "
                f"· monitor={self.monitor_captura}"
            )

            if not copia.save(
                buffer,
                "PNG",
            ):
                return None

            datos = bytes(
                buffer.data()
            )

            if not datos:
                return None

            return base64.b64encode(
                datos
            ).decode(
                "ascii"
            )

        finally:
            buffer.close()
    # ========================================================
    # RESUMEN DE ACCIÓN PARA IA
    # ========================================================

    def resumir_accion_para_ia(
        self,
        accion,
    ):
        if not accion:
            return None

        resumen = {
            "id": accion.get("id"),
            "tipo": accion.get("tipo"),
            "descripcion": accion.get(
                "descripcion"
            ),
            "datos": accion.get("datos") or {},
            "contexto_objetivo": accion.get(
                "contexto_objetivo"
            ),
            "contexto_despues": accion.get(
                "contexto_despues"
            ),
        }

        campos_directos = (
            "texto",
            "x",
            "y",
            "x_inicio",
            "y_inicio",
            "x_fin",
            "y_fin",
            "dx",
            "dy",
            "delta",
            "pasos",
            "duracion_ms",
            "boton",
            "tecla",
            "caracter",
            "modificadores",
            "acciones_origen",
        )

        for campo in campos_directos:
            if (
                campo in accion
                and accion.get(campo) is not None
            ):
                resumen[campo] = accion.get(
                    campo
                )

        return resumen

    def resumir_rutina_para_ia(
        self,
        tarea,
    ):
        if not tarea:
            return []

        plan = (
            tarea.get("acciones_semanticas")
            or tarea.get("acciones")
            or []
        )

        resultado = []

        for indice, accion in enumerate(plan):
            datos = accion.get("datos") or {}

            paso = {
                "indice": indice + 1,
                "tipo": accion.get("tipo"),
                "descripcion": accion.get(
                    "descripcion"
                ),
            }

            texto = (
                accion.get("texto")
                if accion.get("texto") is not None
                else datos.get("texto")
            )

            if texto:
                paso["texto"] = str(texto)[:200]

            for campo in (
                "consulta",
                "proceso",
                "destino",
                "navegador",
                "tecla",
                "caracter",
            ):
                valor = datos.get(campo)

                if valor not in (
                    None,
                    "",
                ):
                    paso[campo] = valor

            modificadores = (
                datos.get("modificadores")
                or accion.get("modificadores")
                or []
            )

            if modificadores:
                paso["modificadores"] = modificadores

            contexto = accion.get(
                "contexto_objetivo"
            ) or {}

            proceso_contexto = contexto.get(
                "proceso"
            )

            if proceso_contexto:
                paso["contexto_proceso"] = (
                    proceso_contexto
                )

            resultado.append(paso)

        return resultado
       
    # ========================================================
    # CLAVE DEL CHECKPOINT VISUAL
    # ========================================================

    def construir_clave_ia_visual(
        self,
    ):
        tarea = self.obtener_tarea_ejecutando()

        run_key = ""

        if tarea:
            run_key = str(
                tarea.get(
                    "current_run_key",
                    "",
                )
                or ""
            )

        return (
            f"{run_key}|"
            f"{self.repeticion_ejecucion_real}|"
            f"{self.indice_ejecucion_real}|"
            f"{self.fase_ejecucion_real}"
        )

    # ========================================================
    # PROMPT INTERNO EN INGLÉS
    # ========================================================

    def construir_prompt_ia_visual(
        self,
        contexto,
    ):
        tarea = (
            self.obtener_tarea_ejecutando()
        )

        momento = str(
            contexto.get(
                "momento_ia",
                "",
            )
            or ""
        )

        accion_ejecutada = (
            contexto.get(
                "accion_ejecutada"
            )
        )

        siguiente_accion = (
            contexto.get(
                "siguiente_accion"
            )
        )

        accion_actual = (
            siguiente_accion
            if momento == "preaccion"
            else accion_ejecutada
        )

        def compactar_accion(
            accion,
        ):
            if not accion:
                return None

            datos = dict(
                accion.get(
                    "datos"
                )
                or {}
            )

            resultado = {
                "tipo": accion.get(
                    "tipo"
                ),
                "descripcion": accion.get(
                    "descripcion"
                ),
                "datos": datos,
            }

            for campo in (
                "texto",
                "x",
                "y",
                "x_inicio",
                "y_inicio",
                "x_fin",
                "y_fin",
                "tecla",
                "caracter",
                "modificadores",
            ):
                if (
                    accion.get(campo)
                    is not None
                ):
                    resultado[campo] = (
                        accion.get(campo)
                    )

            return resultado

        rutina = []

        objetivo = None

        memoria = {}

        if tarea:
            rutina = (
                self.resumir_rutina_para_ia(
                    tarea
                )[:30]
            )

            objetivo = tarea.get(
                "objetivo_ia"
            )

            memoria = (
                tarea.get(
                    "memoria_ia"
                )
                or {}
            )

        datos = {
            "task_name": (
                tarea.get("nombre")
                if tarea
                else ""
            ),
            "goal": objetivo,
            "moment": momento,
            "action_index": (
                self.indice_ejecucion_real
                + 1
            ),
            "action_count": len(
                self.plan_ejecucion_actual
            ),
            "current_action": (
                compactar_accion(
                    accion_actual
                )
            ),
            "next_action": (
                compactar_accion(
                    siguiente_accion
                )
            ),
            "current_window": (
                contexto.get(
                    "contexto_actual"
                )
            ),
            "last_execution_result": (
                self.resultado_accion_real_actual
            ),
            "routine_outline": rutina,
            "last_successful_correction": (
                memoria.get(
                    "correcciones_exitosas",
                    [],
                )[-1:]
            ),
        }

        datos_json = json.dumps(
            datos,
            ensure_ascii=False,
            default=str,
        )

        return (
            "You are Qwen3-VL Instruct, the visual "
            "trajectory controller of BIN.\n\n"

            "Inspect the CURRENT screenshot and decide "
            "whether BIN should execute the current "
            "recorded action.\n\n"

            "You have authority to correct the trajectory "
            "while preserving the user's final goal.\n\n"

            "DECISIONS:\n"
            "READY = execute the recorded action unchanged.\n"
            "WAIT = the interface is changing/loading.\n"
            "ADJUST = perform ONE corrective action, then "
            "inspect again; the recorded action remains pending.\n"
            "REPLAN = perform ONE corrective action because "
            "the environment needs a different route; inspect "
            "again afterward.\n"
            "REPLACE = execute ONE supplied tool action INSTEAD "
            "OF the current recorded action.\n"
            "SKIP = current recorded action is redundant or "
            "incorrect and should not execute.\n"
            "FAILED = task cannot reasonably continue.\n"
            "AMBIGUOUS = visible evidence is insufficient.\n\n"

            "VISUAL REPORT:\n"
            "Do NOT provide hidden chain-of-thought. "
            "Instead report observable evidence: what is "
            "visible, what elements you checked, what differs "
            "from what the task needs, and your concise reason.\n\n"

            "checks_required = number of visual/logical "
            "elements that should be checked for this decision.\n"
            "checks_completed = number actually checked.\n\n"

            "AVAILABLE TOOLS:\n"
            "abrir_aplicacion, abrir_inicio, click, "
            "doble_click, abrir_elemento, "
            "abrir_menu_contextual, click_central, "
            "desplazar, scroll, scroll_agrupado, "
            "arrastrar, escribir_texto, copiar, pegar, "
            "cortar, deshacer, rehacer, seleccionar_todo, "
            "guardar, buscar, imprimir, cambiar_aplicacion, "
            "cerrar_ventana, navegar_url, navegar, "
            "buscar_o_navegar, tecla, atajo_teclado.\n\n"

            "For mouse actions use normalized coordinates "
            "x_norm/y_norm between 0 and 1.\n\n"

            "Return ONLY JSON:\n"
            "{\n"
            ' "decision": "READY|WAIT|ADJUST|REPLAN|'
            'REPLACE|SKIP|FAILED|AMBIGUOUS",\n'
            ' "screen_summary": "what is visibly on screen",\n'
            ' "checks_required": 0,\n'
            ' "checks_completed": 0,\n'
            ' "observations": ["visible evidence"],\n'
            ' "mismatches": ["differences or problems"],\n'
            ' "reason": "concise decision reason",\n'
            ' "inferred_goal": "goal or empty string",\n'
            ' "actions": ['
            '{"type":"tool","data":{}}'
            "]\n"
            "}\n\n"

            "Use at most ONE action. READY, WAIT, SKIP, "
            "FAILED and AMBIGUOUS normally use an empty "
            "actions array.\n\n"

            "EXECUTION DATA:\n"
            f"{datos_json}"
        )
       
    # ========================================================
    # CANCELAR CONSULTA VISUAL OBSOLETA
    # ========================================================

    def cancelar_consulta_ia_visual(
        self,
    ):
        respuesta = self.respuesta_red_ia_visual

        self.respuesta_red_ia_visual = None
        self.clave_ia_visual_en_curso = None
        self.clave_resultado_ia_visual = None
        self.resultado_ia_visual = None

        if respuesta is not None:

            try:
                if not respuesta.isFinished():
                    respuesta.abort()

            except Exception:
                pass

    def formatear_reporte_ia_chat(
        self,
        resultado,
    ):
        decision = str(
            resultado.get(
                "decision",
                "AMBIGUOUS",
            )
        )

        resumen = str(
            resultado.get(
                "screen_summary",
                "",
            )
            or "Sin resumen visual."
        )

        motivo = str(
            resultado.get(
                "motivo",
                "",
            )
            or ""
        )

        observaciones = (
            resultado.get(
                "observations"
            )
            or []
        )

        discrepancias = (
            resultado.get(
                "mismatches"
            )
            or []
        )

        completadas = int(
            resultado.get(
                "checks_completed",
                0,
            )
            or 0
        )

        requeridas = int(
            resultado.get(
                "checks_required",
                0,
            )
            or 0
        )

        lineas = [
            f"DECISIÓN: {decision}",
            "",
            f"PANTALLA: {resumen}",
            "",
            (
                "COMPROBACIONES: "
                f"{completadas}/{requeridas}"
            ),
        ]

        if observaciones:
            lineas.append("")
            lineas.append(
                "LO QUE VEO:"
            )

            for valor in observaciones:
                lineas.append(
                    f"• {valor}"
                )

        if discrepancias:
            lineas.append("")
            lineas.append(
                "DIFERENCIAS:"
            )

            for valor in discrepancias:
                lineas.append(
                    f"• {valor}"
                )

        if motivo:
            lineas.append("")
            lineas.append(
                f"POR QUÉ: {motivo}"
            )

        return "\n".join(
            lineas
        )

    # ========================================================
    # RESPUESTA ASÍNCRONA DE OLLAMA
    # ========================================================

    def recibir_respuesta_ia_visual_ollama(
        self,
        clave,
        respuesta,
    ):
        aceptar_resultado = clave == self.clave_ia_visual_en_curso

        # Una consulta cancelada puede emitir igualmente
        # finished(). No debemos intentar leer un
        # QNetworkReply que ya fue cerrado por abort().
        if not aceptar_resultado:
            try:
                respuesta.deleteLater()
            except Exception:
                pass

            return

        resultado = {
            "disponible": True,
            "decision": "AMBIGUOUS",
            "motivo": ("The local visual supervisor " "could not determine the state."),
        }

        try:
            if respuesta.error() != QNetworkReply.NetworkError.NoError:
                cuerpo_error = bytes(
                    respuesta.readAll()
                ).decode(
                    "utf-8",
                    errors="replace",
                )

                detalle_error = (
                    cuerpo_error.strip()
                    or respuesta.errorString()
                )

                print(
                    "[BIN IA] ERROR OLLAMA:",
                    detalle_error,
                )

                resultado = {
                    "disponible": True,
                    "decision": "FAILED",
                    "motivo": (
                        "Ollama local rechazó la consulta: "
                        f"{detalle_error}"
                    ),
                    "acciones": [],
                    "objetivo_inferido": "",
                }

            else:
                bruto = bytes(respuesta.readAll()).decode(
                    "utf-8",
                    errors="replace",
                )

                envoltura = json.loads(bruto)

                contenido = envoltura.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )

                if isinstance(
                    contenido,
                    dict,
                ):
                    datos = contenido
                else:
                    datos = json.loads(str(contenido or "{}"))

                acciones = datos.get(
                    "actions"
                )

                if not isinstance(
                    acciones,
                    list,
                ):
                    acciones = []

                acciones = [
                    valor
                    for valor in acciones
                    if isinstance(valor, dict)
                ]

                decision = str(
                    datos.get(
                        "decision",
                        "AMBIGUOUS",
                    )
                    or "AMBIGUOUS"
                ).upper()

                decisiones_validas = {
                    "READY",
                    "WAIT",
                    "ADJUST",
                    "REPLAN",
                    "REPLACE",
                    "SKIP",
                    "FAILED",
                    "AMBIGUOUS",
                }

                if (
                    decision
                    not in decisiones_validas
                ):
                    decision = "AMBIGUOUS"

                motivo = str(
                    datos.get(
                        "reason",
                        "",
                    )
                    or datos.get(
                        "motivo",
                        "",
                    )
                    or ""
                )

                objetivo_inferido = str(
                    datos.get(
                        "inferred_goal",
                        "",
                    )
                    or ""
                ).strip()

                screen_summary = str(
                    datos.get(
                        "screen_summary",
                        "",
                    )
                    or ""
                ).strip()

                observations = datos.get(
                    "observations"
                )

                if not isinstance(
                    observations,
                    list,
                ):
                    observations = []

                observations = [
                    str(valor)
                    for valor in observations[:12]
                ]

                mismatches = datos.get(
                    "mismatches"
                )

                if not isinstance(
                    mismatches,
                    list,
                ):
                    mismatches = []

                mismatches = [
                    str(valor)
                    for valor in mismatches[:12]
                ]

                try:
                    checks_required = max(
                        0,
                        int(
                            datos.get(
                                "checks_required",
                                0,
                            )
                            or 0
                        ),
                    )
                except Exception:
                    checks_required = 0

                try:
                    checks_completed = max(
                        0,
                        int(
                            datos.get(
                                "checks_completed",
                                0,
                            )
                            or 0
                        ),
                    )
                except Exception:
                    checks_completed = 0

                    

                resultado = {
                    "disponible": True,
                    "decision": decision,
                    "motivo": motivo,
                    "objetivo_inferido": (
                        objetivo_inferido
                    ),
                    "acciones": acciones[:1],

                    # ----------------------------------------
                    # DIAGNÓSTICO VISUAL DE QWEN
                    # ----------------------------------------

                    "screen_summary": (
                        screen_summary
                    ),

                    "observations": (
                        observations
                    ),

                    "mismatches": (
                        mismatches
                    ),

                    "checks_required": (
                        checks_required
                    ),

                    "checks_completed": (
                        checks_completed
                    ),
                }

        except Exception as error:
            resultado = {
                "disponible": True,
                "decision": "AMBIGUOUS",
                "motivo": ("Could not parse Ollama response: " f"{error}"),
            }

        finally:
            if self.respuesta_red_ia_visual is respuesta:
                self.respuesta_red_ia_visual = None

            if self.clave_ia_visual_en_curso == clave:
                self.clave_ia_visual_en_curso = None

            respuesta.deleteLater()

        tarea = self.obtener_tarea_ejecutando()

        clave_actual = self.construir_clave_ia_visual()

        if (
            aceptar_resultado
            and tarea is not None
            and tarea.get("estado") == "EJECUTANDO"
            and clave == clave_actual
        ):
            self.clave_resultado_ia_visual = clave

            self.resultado_ia_visual = resultado

            self.actualizar_chat_qwen(
                self.formatear_reporte_ia_chat(
                    resultado
                )
            )

            print(
                "[BIN IA] "
                f"{resultado.get('decision')} · "
                f"{resultado.get('motivo')}"
            )

    # ========================================================
    # PROVEEDOR VISUAL LOCAL OLLAMA
    # ========================================================

    def proveedor_ia_visual_ollama(
        self,
        imagen,
        contexto,
    ):
        if imagen is None:
            return {
                "disponible": False,
                "decision": "AMBIGUOUS",
                "motivo": ("No visual frame is available."),
            }

        clave = self.construir_clave_ia_visual()

        # -----------------------------------------------
        # RESULTADO YA RECIBIDO
        # -----------------------------------------------

        if (
            self.clave_resultado_ia_visual == clave
            and self.resultado_ia_visual is not None
        ):
            resultado = dict(self.resultado_ia_visual)

            self.clave_resultado_ia_visual = None

            self.resultado_ia_visual = None

            return resultado

        # Descartar resultado viejo.
        if (
            self.clave_resultado_ia_visual is not None
            and self.clave_resultado_ia_visual != clave
        ):
            self.clave_resultado_ia_visual = None

            self.resultado_ia_visual = None

        # -----------------------------------------------
        # CONSULTA EN CURSO
        # -----------------------------------------------

        if self.respuesta_red_ia_visual is not None:
            if self.clave_ia_visual_en_curso == clave:
                return {
                    "disponible": True,
                    "decision": "WAIT",
                    "motivo": ("Local visual AI is " "analyzing the screen."),
                }

            self.cancelar_consulta_ia_visual()

        # -----------------------------------------------
        # CONVERTIR FRAME
        # -----------------------------------------------

        imagen_base64 = self.convertir_frame_ia_a_base64(imagen)

        if not imagen_base64:
            return {
                "disponible": False,
                "decision": "AMBIGUOUS",
                "motivo": ("The current visual frame " "could not be encoded."),
            }

        prompt = self.construir_prompt_ia_visual(contexto)

        esquema_datos_herramienta = {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                },
                "proceso": {
                    "type": "string",
                },
                "ejecutable": {
                    "type": "string",
                },
                "texto": {
                    "type": "string",
                },
                "tecla": {
                    "type": "string",
                },
                "caracter": {
                    "type": "string",
                },
                "modificadores": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "navegador": {
                    "type": "string",
                },
                "destino": {
                    "type": "string",
                },
                "x_norm": {
                    "type": "number",
                },
                "y_norm": {
                    "type": "number",
                },
                "x_inicio_norm": {
                    "type": "number",
                },
                "y_inicio_norm": {
                    "type": "number",
                },
                "x_fin_norm": {
                    "type": "number",
                },
                "y_fin_norm": {
                    "type": "number",
                },
                "x": {
                    "type": "integer",
                },
                "y": {
                    "type": "integer",
                },
                "x_inicio": {
                    "type": "integer",
                },
                "y_inicio": {
                    "type": "integer",
                },
                "x_fin": {
                    "type": "integer",
                },
                "y_fin": {
                    "type": "integer",
                },
                "dx": {
                    "type": "integer",
                },
                "dy": {
                    "type": "integer",
                },
                "delta": {
                    "type": "integer",
                },
                "pasos": {
                    "type": "integer",
                },
                "duracion_ms": {
                    "type": "integer",
                },
                "boton": {
                    "type": "string",
                },
            },
            "additionalProperties": False,
        }

        esquema = {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": [
                        "READY",
                        "WAIT",
                        "ADJUST",
                        "REPLAN",
                        "FAILED",
                        "AMBIGUOUS",
                    ],
                },
                "reason": {
                    "type": "string",
                },
                "inferred_goal": {
                    "type": "string",
                },
                "actions": {
                    "type": "array",
                    "maxItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                            },
                            "data": (
                                esquema_datos_herramienta
                            ),
                        },
                        "required": [
                            "type",
                            "data",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "decision",
                "reason",
                "inferred_goal",
                "actions",
            ],
            "additionalProperties": False,
        }

        payload = {
            "model": self.modelo_ia_visual,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [imagen_base64],
                }
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx_qwen,
                "num_predict": 120,
            },
        }

        solicitud = QNetworkRequest(self.url_ia_visual)

        solicitud.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )

        cuerpo = QByteArray(
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")
        )

        respuesta = self.gestor_red_ia_visual.post(
            solicitud,
            cuerpo,
        )

        self.respuesta_red_ia_visual = respuesta

        self.clave_ia_visual_en_curso = clave

        respuesta.finished.connect(
            lambda clave=clave, respuesta=respuesta: (
                self.recibir_respuesta_ia_visual_ollama(
                    clave,
                    respuesta,
                )
            )
        )

        self.inicio_consulta_ia_visual_monotonic = (
            time.monotonic()
        )

        self.ultimo_aviso_espera_ia_bloque = -1

        resolucion_frame = (
            f"{imagen.width()}×"
            f"{imagen.height()}"
        )

        self.actualizar_chat_qwen(
            "▶ Analizando pantalla\n"
            f"Modelo: {self.modelo_ia_visual}\n"
            f"Captura: {resolucion_frame}\n"
            f"Monitor: {self.monitor_captura}\n"
            f"Acción: "
            f"{self.indice_ejecucion_real + 1}/"
            f"{len(self.plan_ejecucion_actual)}\n"
            f"Fase: {self.fase_ejecucion_real}"
        )

        print("[BIN IA] Analizando pantalla " f"con {self.modelo_ia_visual}...")

        return {
            "disponible": True,
            "decision": "WAIT",
            "motivo": ("Local visual AI is " "analyzing the screen."),
        }

    def evaluar_estado_con_ia(
        self,
        imagen,
        contexto,
    ):
        proveedor = getattr(
            self,
            "proveedor_ia_visual",
            None,
        )

        if not callable(proveedor):
            return {
                "disponible": False,
                "decision": "AMBIGUOUS",
                "motivo": (
                    "Supervisor visual IA "
                    "no configurado."
                ),
                "acciones": [],
                "objetivo_inferido": "",
            }

        try:
            respuesta = proveedor(
                imagen,
                contexto,
            )

        except Exception as error:
            return {
                "disponible": True,
                "decision": "AMBIGUOUS",
                "motivo": (
                    "El proveedor visual no "
                    "pudo evaluar el estado: "
                    f"{error}"
                ),
                "acciones": [],
                "objetivo_inferido": "",
            }

        if isinstance(
            respuesta,
            str,
        ):
            respuesta = {
                "decision": respuesta,
                "motivo": "",
            }

        if not isinstance(
            respuesta,
            dict,
        ):
            return {
                "disponible": True,
                "decision": "AMBIGUOUS",
                "motivo": (
                    "El proveedor visual devolvió "
                    "un formato no reconocido."
                ),
                "acciones": [],
                "objetivo_inferido": "",
            }

        decision = str(
            respuesta.get(
                "decision",
                "AMBIGUOUS",
            )
            or "AMBIGUOUS"
        ).upper()

        if decision not in {
            "READY",
            "WAIT",
            "ADJUST",
            "REPLAN",
            "REPLACE",
            "SKIP",
            "FAILED",
            "AMBIGUOUS",
        }:
            decision = "AMBIGUOUS"

        acciones = respuesta.get(
            "acciones"
        )

        if not isinstance(
            acciones,
            list,
        ):
            acciones = []

        return {
            "disponible": True,
            "decision": decision,

            "motivo": str(
                respuesta.get(
                    "motivo",
                    "",
                )
                or ""
            ),

            "acciones": acciones[:1],

            "objetivo_inferido": str(
                respuesta.get(
                    "objetivo_inferido",
                    "",
                )
                or ""
            ).strip(),

            # --------------------------------------------
            # DIAGNÓSTICO VISUAL DE QWEN
            # --------------------------------------------

            "screen_summary": respuesta.get(
                "screen_summary",
                "",
            ),

            "observations": respuesta.get(
                "observations",
                [],
            ),

            "mismatches": respuesta.get(
                "mismatches",
                [],
            ),

            "checks_required": respuesta.get(
                "checks_required",
                0,
            ),

            "checks_completed": respuesta.get(
                "checks_completed",
                0,
            ),
        }

    # ========================================================
    # AGENTE QWEN — DEMOSTRACIÓN COMPLETA
    # ========================================================

    def resumir_demostracion_para_agente_ia(
        self,
        tarea,
    ):
        resultado = []

        for indice, accion in enumerate(
            tarea.get("acciones") or []
        ):
            paso = {
                "paso": indice + 1,
                "tipo": accion.get("tipo"),
                "descripcion": accion.get(
                    "descripcion",
                    "",
                ),
            }

            datos = accion.get("datos") or {}

            for campo in (
                "texto",
                "tecla",
                "caracter",
                "modificadores",
                "x",
                "y",
                "dx",
                "dy",
                "delta",
                "pasos",
            ):
                valor = accion.get(campo)

                if valor is None:
                    valor = datos.get(campo)

                if valor not in (
                    None,
                    "",
                    [],
                ):
                    if campo == "texto":
                        valor = str(valor)[:240]

                    paso[campo] = valor

            contexto = (
                accion.get("contexto_objetivo")
                or {}
            )

            despues = (
                accion.get("contexto_despues")
                or {}
            )

            if contexto.get("proceso"):
                paso["proceso_antes"] = (
                    contexto.get("proceso")
                )

            if despues.get("proceso"):
                paso["proceso_despues"] = (
                    despues.get("proceso")
                )

            resultado.append(paso)

        return resultado

    # ========================================================
    # PROMPT ÚNICO DE LA TAREA
    # ========================================================

    def construir_prompt_agente_ia(
        self,
        tarea,
        motivo="inicio",
        error=None,
    ):
        objetivo_guardado = tarea.get(
            "objetivo_ia"
        )

        if isinstance(
            objetivo_guardado,
            dict,
        ):
            objetivo_guardado = (
                objetivo_guardado.get(
                    "descripcion",
                    "",
                )
            )

        nivel_recuperacion = min(
            3,
            max(
                0,
                int(
                    self.reanalisis_agente_ia
                    or 0
                ),
            ),
        )

        datos = {
            "task_name": tarea.get(
                "nombre",
                "",
            ),
            "stored_goal": (
                objetivo_guardado
                or ""
            ),
            "reason_for_analysis": motivo,
            "demonstration": (
                self.resumir_demostracion_para_agente_ia(
                    tarea
                )
            ),
            "current_window": (
                self.obtener_contexto_ventana_activa()
            ),
            "previous_tool_results": (
                self.historial_agente_ia[
                    -12:
                ]
            ),
            "last_error": (
                error
                or None
            ),
            "recovery_level": (
                nivel_recuperacion
            ),
        }

        datos_json = json.dumps(
            datos,
            ensure_ascii=False,
            default=str,
        )

        return (
            "You are Qwen3-VL Instruct acting as the "
            "autonomous visual execution controller of BIN "
            "on Windows.\n\n"

            "The demonstration is evidence of what the user "
            "wanted to achieve. It is NOT a macro that must "
            "be replayed step by step.\n"

            "Infer the user's final objective from the WHOLE "
            "demonstration and the CURRENT screenshot.\n\n"

            "EXECUTION LOOP:\n"

            "1. Inspect the CURRENT screenshot.\n"

            "2. Review previous_tool_results and last_error.\n"

            "3. Decide whether the COMPLETE objective is "
            "already visibly satisfied.\n"

            "4. If it is complete, return DONE.\n"

            "5. Otherwise choose exactly ONE safest next "
            "physical action.\n"

            "6. BIN will execute that one action, capture a "
            "fresh screenshot, and consult you again.\n\n"

            "Never return more than ONE action.\n"

            "Never assume the next screen before seeing it.\n"

            "Never guess coordinates for hidden elements.\n"

            "Never mark DONE because a command was merely "
            "sent. The objective must be visibly satisfied "
            "on the CURRENT screenshot.\n\n"

            "POST-ACTION PROGRESSION RULES:\n"

            "reason_for_analysis=verificar_y_continuar means "
            "the previous physical tool already ran and the "
            "CURRENT screenshot shows its result.\n"

            "First inspect what is visible NOW and determine "
            "what changed after the previous tool.\n"

            "previous_tool_results[*].ok only means BIN was "
            "able to physically send the tool. It does NOT "
            "prove that the interface advanced or that the "
            "user objective was achieved.\n\n"

            "If a previous click already exposed or focused "
            "the text/search/input field required by the "
            "objective, do NOT click the same field again. "
            "Use escribir_texto next.\n"

            "If the required text is already visible in the "
            "correct field and the objective requires opening, "
            "submitting or confirming it, use tecla with "
            "Enter next.\n"

            "If a field is visible but clearly NOT focused, "
            "click that visible field first. Then observe a "
            "fresh screenshot before deciding to type.\n\n"

            "Do not repeat an equivalent successful action "
            "unless the CURRENT screenshot clearly shows "
            "that its effect was lost or never occurred.\n"

            "Every PLAN action must materially advance the "
            "objective from the CURRENT visible state.\n\n"

            "IMPORTANT TOOL ARGUMENTS:\n"
            'escribir_texto: {"texto":"text to type"}\n'
            'tecla: {"tecla":"enter"}\n'
            'click: {"x_norm":0.0,"y_norm":0.0}\n'
            'doble_click: {"x_norm":0.0,"y_norm":0.0}\n'
            'abrir_aplicacion: '
            '{"consulta":"application name"}\n'
            'navegar_url: '
            '{"destino":"https://example.com",'
            '"navegador":"chrome.exe"}\n\n'

            "Prefer semantic actions such as abrir_aplicacion "
            "and navegar_url when they safely express the "
            "user's intent.\n"

            "Use visible click or doble_click when the target "
            "is actually visible in the CURRENT screenshot.\n\n"

            "RECOVERY POLICY:\n"

            "recovery_level 0 = use the shortest normal "
            "route from the current screen.\n"

            "recovery_level 1 = first recover the visible "
            "workspace or correct the active application. "
            "Do only ONE recovery action and observe again.\n"

            "recovery_level 2 = if the target application "
            "still cannot be reached, use Windows Start or "
            "search one action at a time, beginning with "
            "abrir_inicio when appropriate.\n"

            "recovery_level 3 = conservatively explore visible "
            "desktop icons, folders, windows or other obvious "
            "routes ONE action at a time. Do not guess hidden "
            "locations.\n\n"

            "MOUSE RULES:\n"

            "Use x_norm/y_norm between 0 and 1 only when the "
            "target is visibly present in the CURRENT "
            "screenshot.\n"

            "Aim for the center of the visible target.\n\n"

            "AVAILABLE TOOLS:\n"

            "abrir_aplicacion, abrir_inicio, click, "
            "doble_click, abrir_elemento, "
            "abrir_menu_contextual, desplazar, scroll, "
            "scroll_agrupado, arrastrar, escribir_texto, "
            "copiar, pegar, cortar, deshacer, rehacer, "
            "seleccionar_todo, guardar, buscar, imprimir, "
            "cambiar_aplicacion, cerrar_ventana, navegar_url, "
            "navegar, buscar_o_navegar, tecla, "
            "atajo_teclado.\n\n"

            "For navegar_url, navegar or buscar_o_navegar, "
            "include navegador such as chrome.exe when "
            "known.\n\n"

            "Return ONLY one compact valid JSON object. "
            "No markdown. No hidden chain-of-thought.\n\n"

            "JSON SHAPE:\n"
            "{\n"
            '  "status": "PLAN|DONE|FAILED",\n'
            '  "objective": "short final objective",\n'
            '  "screen_summary": "short visible state",\n'
            '  "reason": "short observable reason",\n'
            '  "actions": [\n'
            '    {'
            '"type":"tool_name",'
            '"data":{}'
            '}\n'
            "  ]\n"
            "}\n\n"

            "STATUS RULES:\n"

            "PLAN = exactly ONE next physical action. "
            "actions must contain exactly one object.\n"

            "DONE = the complete objective is visibly "
            "satisfied now. actions must be empty.\n"

            "FAILED = the objective cannot reasonably "
            "continue. actions must be empty.\n\n"

            "EXECUTION CONTEXT:\n"
            f"{datos_json}"
        )
    # ========================================================
    # CANCELAR CONSULTA DEL AGENTE
    # ========================================================

    def cancelar_consulta_agente_ia(
        self,
    ):
        respuesta = (
            self.respuesta_red_agente_ia
        )

        self.respuesta_red_agente_ia = None

        self.inicio_consulta_agente_ia_monotonic = (
            None
        )

        if respuesta is not None:
            try:
                if not respuesta.isFinished():
                    respuesta.abort()

            except Exception:
                pass

    # ========================================================
    # INICIAR EJECUTOR DEL AGENTE
    # ========================================================

    def iniciar_ejecutor_agente_ia(
        self,
        tarea,
        reanudar=False,
    ):
        if not tarea:
            return False

        self.cancelar_consulta_ia_visual()
        self.cancelar_consulta_agente_ia()

        self.ejecucion_fisica_activa = True

        # El plan viejo de replay ya no gobierna.
        self.plan_ejecucion_actual = []
        self.offsets_ejecucion_actual_ms = []
        self.plan_ejecucion_usa_semantica = False

        self.plan_agente_ia_actual = []
        self.indice_plan_agente_ia = 0

        self.reanalisis_agente_ia = 0
        self.historial_agente_ia = []

        self.pasos_agente_ia_actual = 0

        self.ultima_firma_plan_agente_ia = None
        self.repeticiones_plan_agente_ia = 0

        self.estancamientos_agente_ia = 0

        self.accion_real_actual = None
        self.resultado_accion_real_actual = None

        self.delay_ejecucion_restante_ms = 0

        if reanudar:
            self.repeticion_ejecucion_real = max(
                1,
                int(
                    tarea.get(
                        "ejecucion_real_repeticion",
                        1,
                    )
                    or 1
                ),
            )

            self.ejecuciones_reales_completadas = max(
                0,
                int(
                    tarea.get(
                        "ejecuciones_reales_completadas",
                        0,
                    )
                    or 0
                ),
            )

            self.elapsed_repeticion_base_ms = max(
                0,
                int(
                    tarea.get(
                        "elapsed_repeticion_real_ms",
                        0,
                    )
                    or 0
                ),
            )

        else:
            self.repeticion_ejecucion_real = 1
            self.ejecuciones_reales_completadas = 0
            self.elapsed_repeticion_base_ms = 0

            # Nuevo análisis de esta ejecución.
            tarea["plan_ia"] = []

        self.inicio_repeticion_real_monotonic = (
            time.monotonic()
        )

        self.fase_ejecucion_real = (
            "agente_planificando"
        )

        self.ejecuciones_reales_totales = max(
            1,
            self.obtener_repeticiones_tarea(
                tarea
            ),
        )

        tarea["ejecucion_real_fase"] = (
            self.fase_ejecucion_real
        )

        tarea["ejecucion_real_repeticion"] = (
            self.repeticion_ejecucion_real
        )

        tarea["repeticion_actual"] = (
            self.repeticion_ejecucion_real
        )

        tarea["accion_actual_indice"] = None

        tarea["detalle_estado"] = (
            f"Repetición "
            f"{self.repeticion_ejecucion_real}/"
            f"{self.obtener_repeticiones_tarea(tarea)} "
            "· Qwen comprendiendo la rutina..."
        )

        self.grabando = False

        self.mantener_bin_visible_replay(
            True
        )

        self.guardar_tareas_en_disco()

        return self.solicitar_plan_agente_ia(
            tarea,
            motivo=(
                "reanudar"
                if reanudar
                else "inicio"
            ),
        )

    # ========================================================
    # ENVIAR TODA LA TAREA EN UNA SOLA CONSULTA
    # ========================================================

    def solicitar_plan_agente_ia(
        self,
        tarea,
        motivo="inicio",
        error=None,
    ):
        if (
            not tarea
            or tarea.get("estado")
            != "EJECUTANDO"
            or not self.ejecucion_fisica_activa
        ):
            return False

        # No ejecutar dos Qwen pesados a la vez.
        if (
            self.respuesta_red_chat_qwen
            is not None
        ):
            try:
                if not (
                    self.respuesta_red_chat_qwen
                    .isFinished()
                ):
                    self.actualizar_chat_bin(
                        "Qwen está respondiendo en "
                        "el chat. Espera a que termine "
                        "para ejecutar la tarea."
                    )
                    return False

            except Exception:
                pass

        self.cancelar_consulta_ia_visual()
        self.cancelar_consulta_agente_ia()

        # ====================================================
        # QWEN SIEMPRE RECIBE UNA CAPTURA TOMADA AHORA
        # ====================================================

        frame = (
            self.capturar_frame_fresco_ia()
        )

        imagen_base64 = (
            self.convertir_frame_ia_a_base64(
                frame
            )
        )

        if not imagen_base64:
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "Qwen no recibió una captura "
                    "válida para comprender la tarea."
                ),
            )
            return False

        prompt = self.construir_prompt_agente_ia(
            tarea,
            motivo=motivo,
            error=error,
        )

        print(
            "[BIN IA] Consulta agente:"
        )

        print(
            f"[BIN IA] caracteres_prompt="
            f"{len(prompt)}"
        )

        print(
            f"[BIN IA] acciones_demo="
            f"{len(tarea.get('acciones') or [])}"
        )

        print(
            f"[BIN IA] num_ctx="
            f"{self.num_ctx_qwen}"
        )

        payload = {
            "model": self.modelo_ia_visual,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [
                        imagen_base64
                    ],
                }
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx_qwen,
                "num_predict": 1600,
            },
        }

        solicitud = QNetworkRequest(
            self.url_ia_visual
        )

        solicitud.setHeader(
            QNetworkRequest.KnownHeaders
            .ContentTypeHeader,
            "application/json",
        )

        cuerpo = QByteArray(
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode(
                "utf-8"
            )
        )

        respuesta = (
            self.gestor_red_ia_visual.post(
                solicitud,
                cuerpo,
            )
        )

        self.respuesta_red_agente_ia = (
            respuesta
        )

        self.inicio_consulta_agente_ia_monotonic = (
            time.monotonic()
        )

        self.fase_ejecucion_real = (
            "agente_planificando"
        )

        tarea["ejecucion_real_fase"] = (
            self.fase_ejecucion_real
        )

        self.actualizar_chat_qwen(
            "🧠 Analizando la rutina completa "
            "en una sola consulta...\n"
            f"Pasos demostrados: "
            f"{len(tarea.get('acciones') or [])}\n"
            f"Motivo: {motivo}"
        )

        respuesta.finished.connect(
            lambda tarea_id=tarea.get("id"),
            motivo=motivo,
            respuesta=respuesta: (
                self.recibir_plan_agente_ia(
                    tarea_id,
                    motivo,
                    respuesta,
                )
            )
        )

        return True

    # ========================================================
    # RECIBIR PLAN COMPLETO DE QWEN
    # ========================================================

    def recibir_plan_agente_ia(
        self,
        tarea_id,
        motivo,
        respuesta,
    ):
        datos = None
        error_texto = None
        segundos = 0.0

        try:
            if (
                self.inicio_consulta_agente_ia_monotonic
                is not None
            ):
                segundos = (
                    time.monotonic()
                    - self.inicio_consulta_agente_ia_monotonic
                )

            if (
                respuesta.error()
                != QNetworkReply
                .NetworkError
                .NoError
            ):
                cuerpo_error = bytes(
                    respuesta.readAll()
                ).decode(
                    "utf-8",
                    errors="replace",
                )

                error_texto = (
                    cuerpo_error.strip()
                    or respuesta.errorString()
                )

            else:
                bruto = bytes(
                    respuesta.readAll()
                ).decode(
                    "utf-8",
                    errors="replace",
                )

                envoltura = json.loads(
                    bruto
                )

                contenido = str(
                    envoltura.get(
                        "message",
                        {},
                    ).get(
                        "content",
                        "",
                    )
                    or ""
                ).strip()

                # Tolerancia por si Qwen envía
                # accidentalmente ```json.
                if contenido.startswith(
                    "```"
                ):
                    lineas = (
                        contenido.splitlines()
                    )

                    if (
                        lineas
                        and lineas[0]
                        .startswith("```")
                    ):
                        lineas = lineas[1:]

                    if (
                        lineas
                        and lineas[-1].strip()
                        == "```"
                    ):
                        lineas = lineas[:-1]

                    contenido = "\n".join(
                        lineas
                    ).strip()

                datos = json.loads(
                    contenido or "{}"
                )

                if not isinstance(
                    datos,
                    dict,
                ):
                    raise ValueError(
                        "Qwen no devolvió "
                        "un objeto JSON."
                    )

        except Exception as error:
            error_texto = str(error)

        finally:
            if (
                self.respuesta_red_agente_ia
                is respuesta
            ):
                self.respuesta_red_agente_ia = (
                    None
                )

            self.inicio_consulta_agente_ia_monotonic = (
                None
            )

            respuesta.deleteLater()

        tarea = self.obtener_tarea(
            tarea_id
        )

        if (
            tarea is None
            or tarea.get("estado")
            != "EJECUTANDO"
            or self.tarea_ejecutando_id
            != tarea_id
            or not self.ejecucion_fisica_activa
        ):
            return

        if error_texto:
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "Qwen no pudo crear el "
                    "plan de ejecución.\n\n"
                    f"{error_texto}"
                ),
            )
            return

        estado = str(
            datos.get(
                "status",
                "FAILED",
            )
            or "FAILED"
        ).upper()

        if estado not in {
            "PLAN",
            "DONE",
            "FAILED",
        }:
            estado = "FAILED"

        objetivo = str(
            datos.get(
                "objective",
                "",
            )
            or ""
        ).strip()

        resumen = str(
            datos.get(
                "screen_summary",
                "",
            )
            or ""
        ).strip()

        razon = str(
            datos.get(
                "reason",
                "",
            )
            or ""
        ).strip()

        acciones_brutas = datos.get(
            "actions"
        )

        if not isinstance(
            acciones_brutas,
            list,
        ):
            acciones_brutas = []

        acciones = []

        for item in acciones_brutas[:1]:
            if not isinstance(
                item,
                dict,
            ):
                continue

            tipo = str(
                item.get(
                    "type",
                    "",
                )
                or ""
            ).strip().lower()

            datos_herramienta = (
                item.get("data")
            )

            if (
                not tipo
                or not isinstance(
                    datos_herramienta,
                    dict,
                )
            ):
                continue

            acciones.append(
                {
                    "type": tipo,
                    "data": datos_herramienta,
                    "reobserve_after": bool(
                        item.get(
                            "reobserve_after",
                            False,
                        )
                    ),
                }
            )

        # ====================================================
        # DETECTAR PROPUESTAS REPETIDAS / ESTANCAMIENTO
        # ====================================================

        if estado == "PLAN" and acciones:
            siguiente = acciones[0]

            tipo_siguiente = str(
                siguiente.get(
                    "type",
                    "",
                )
                or ""
            ).strip().lower()

            datos_firma = dict(
                siguiente.get(
                    "data"
                )
                or {}
            )

            # Pequeñas diferencias de uno o dos píxeles
            # normalizados no deben engañar al detector.
            for campo in (
                "x_norm",
                "y_norm",
                "x_inicio_norm",
                "y_inicio_norm",
                "x_fin_norm",
                "y_fin_norm",
            ):
                if campo not in datos_firma:
                    continue

                try:
                    datos_firma[campo] = round(
                        float(
                            datos_firma[campo]
                        ),
                        2,
                    )
                except Exception:
                    pass

            firma_siguiente = json.dumps(
                {
                    "type": tipo_siguiente,
                    "data": datos_firma,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            if (
                firma_siguiente
                == self.ultima_firma_plan_agente_ia
            ):
                self.repeticiones_plan_agente_ia += 1

            else:
                self.ultima_firma_plan_agente_ia = (
                    firma_siguiente
                )

                self.repeticiones_plan_agente_ia = 0

                self.estancamientos_agente_ia = 0

            # Acciones que no conviene duplicar
            # inmediatamente.
            acciones_sensibles = {
                "escribir_texto",
                "tecla",
                "abrir_inicio",
                "abrir_aplicacion",
                "navegar_url",
                "navegar",
                "buscar_o_navegar",
            }

            # Para clicks dejamos un reintento.
            # Para escribir/Enter/navegar no:
            # duplicarlos puede ser destructivo.
            limite_repeticion = (
                0
                if tipo_siguiente
                in acciones_sensibles
                else 1
            )

            if (
                self.repeticiones_plan_agente_ia
                > limite_repeticion
            ):
                self.estancamientos_agente_ia += 1

                if (
                    self.estancamientos_agente_ia
                    >= self.max_estancamientos_agente_ia
                ):
                    self.finalizar_ejecucion_con_error(
                        tarea,
                        (
                            "Qwen quedó repitiendo "
                            "acciones sin progreso "
                            "suficiente."
                        ),
                    )
                    return

                self.reanalisis_agente_ia = min(
                    self.max_reanalisis_agente_ia,
                    self.reanalisis_agente_ia + 1,
                )

                self.actualizar_chat_qwen(
                    "⚠ Detecté una acción repetida "
                    "sin progreso suficiente. "
                    "No la ejecutaré otra vez. "
                    "Qwen debe buscar otra ruta."
                )

                QTimer.singleShot(
                    250,
                    lambda tarea=tarea: (
                        self.solicitar_plan_agente_ia(
                            tarea,
                            motivo="estancamiento",
                            error={
                                "detalle": (
                                    "La acción propuesta "
                                    "repite una acción anterior "
                                    "sin progreso suficiente. "
                                    "Observa la pantalla actual "
                                    "y elige una acción diferente "
                                    "que avance el objetivo."
                                )
                            },
                        )
                    ),
                )

                return

        # --------------------------------------------
        # GUARDAR OBJETIVO DEDUCIDO
        # --------------------------------------------

        if objetivo:
            tarea["objetivo_ia"] = {
                "descripcion": objetivo,
                "creado_por": (
                    "qwen3-vl-agent"
                ),
                "timestamp": (
                    datetime.now()
                    .isoformat()
                ),
            }

        # El plan_ia guarda la ruta que Qwen
        # realmente fue construyendo.
        if motivo in {
            "inicio",
            "reanudar",
        }:
            tarea["plan_ia"] = []

        tarea.setdefault(
            "plan_ia",
            [],
        ).extend(
            json.loads(
                json.dumps(
                    acciones
                )
            )
        )

        self.guardar_tareas_en_disco()

        # --------------------------------------------
        # MOSTRAR QUÉ ENTENDIÓ QWEN
        # --------------------------------------------

        lineas = [
            (
                "OBJETIVO: "
                f"{objetivo or 'No definido'}"
            ),
            (
                "PANTALLA: "
                f"{resumen or 'Sin resumen'}"
            ),
            (
                "PLAN: "
                f"{len(acciones)} acción(es)"
            ),
        ]

        for indice, accion in enumerate(
            acciones,
            start=1,
        ):
            marca = (
                " ↻"
                if accion.get(
                    "reobserve_after"
                )
                else ""
            )

            lineas.append(
                f"{indice}. "
                f"{accion.get('type')}"
                f"{marca}"
            )

        lineas.append(
            f"Tiempo de análisis: "
            f"{segundos:.1f} s"
        )

        if razon:
            lineas.append(
                f"Motivo: {razon}"
            )

        self.actualizar_chat_qwen(
            "\n".join(lineas)
        )

        # --------------------------------------------
        # OBJETIVO YA CONSEGUIDO
        # --------------------------------------------

        if estado == "DONE":
            self.finalizar_repeticion_agente_ia(
                tarea
            )
            return

        if estado == "FAILED":
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    razon
                    or (
                        "Qwen indicó que la "
                        "tarea no puede continuar."
                    )
                ),
            )
            return

        if not acciones:
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "Qwen devolvió PLAN pero "
                    "no entregó acciones."
                ),
            )
            return

        self.plan_agente_ia_actual = (
            acciones
        )

        self.indice_plan_agente_ia = 0

        self.fase_ejecucion_real = (
            "agente_ejecutando"
        )

        tarea["ejecucion_real_fase"] = (
            self.fase_ejecucion_real
        )

        restantes = len(
            acciones
        )

        self.ejecuciones_reales_totales = max(
            self.ejecuciones_reales_totales,
            (
                self.ejecuciones_reales_completadas
                + restantes
            ),
        )

        self.timer_ejecucion_accion.start(
            0
        )

    # ========================================================
    # PEQUEÑAS ESPERAS ENTRE HERRAMIENTAS
    # ========================================================

    def delay_agente_ia_ms(
        self,
        tipo,
    ):
        tipo = str(
            tipo or ""
        ).strip().lower()

        if tipo == "abrir_aplicacion":
            return 2500

        if tipo in {
            "navegar_url",
            "navegar",
            "buscar_o_navegar",
        }:
            return 1800

        if tipo in {
            "abrir_inicio",
            "cambiar_aplicacion",
            "cerrar_ventana",
        }:
            return 700

        if tipo in {
            "click",
            "doble_click",
            "abrir_elemento",
            "abrir_menu_contextual",
        }:
            return 650

        if tipo in {
            "scroll",
            "scroll_agrupado",
            "desplazar",
        }:
            return 850

        if tipo in {
            "tecla",
            "atajo_teclado",
        }:
            return 350

        return 250

    # ========================================================
    # EJECUTAR EL LOTE SIN VOLVER A PREGUNTAR
    # ========================================================

    def procesar_siguiente_accion_agente_ia(
        self,
    ):
        tarea = (
            self.obtener_tarea_ejecutando()
        )

        if (
            not tarea
            or tarea.get("estado")
            != "EJECUTANDO"
            or not self.ejecucion_fisica_activa
            or self.pausa_ejecucion_global
        ):
            return

        if (
            self.indice_plan_agente_ia
            >= len(
                self.plan_agente_ia_actual
            )
        ):
            self.finalizar_repeticion_agente_ia(
                tarea
            )
            return

        herramienta = (
            self.plan_agente_ia_actual[
                self.indice_plan_agente_ia
            ]
        )

        tipo = str(
            herramienta.get(
                "type",
                "",
            )
            or ""
        ).strip().lower()

        tipo = str(
            herramienta.get(
                "type",
                "",
            )
            or ""
        ).strip().lower()

        numero = (
            self.indice_plan_agente_ia
            + 1
        )

        total = len(
            self.plan_agente_ia_actual
        )

        tarea["accion_actual_indice"] = None

        tarea["detalle_estado"] = (
            f"Repetición "
            f"{self.repeticion_ejecucion_real}/"
            f"{self.obtener_repeticiones_tarea(tarea)} "
            f"· IA {numero}/{total} · {tipo}"
        )

        self.actualizar_estado_cabecera_visor(
            "Qwen ejecutando",
            (
                f"· IA "
                f"{numero}/{total} "
                f"· {tipo}"
            ),
            AMARILLO,
        )

        resultado = (
            self.ejecutar_herramienta_ia(
                tarea,
                herramienta,
            )
        )

        registro = {
            "type": tipo,
            "data": (
                herramienta.get(
                    "data"
                )
                or {}
            ),
            "ok": bool(
                resultado.get("ok")
            ),
            "detalle": str(
                resultado.get(
                    "detalle",
                    "",
                )
                or ""
            ),
        }

        self.historial_agente_ia.append(
            registro
        )

        if (
            len(
                self.historial_agente_ia
            )
            > 30
        ):
            self.historial_agente_ia = (
                self.historial_agente_ia[
                    -30:
                ]
            )

        # --------------------------------------------
        # FALLÓ UNA HERRAMIENTA:
        # AHORA SÍ VOLVER A QWEN
        # --------------------------------------------

        if not resultado.get("ok"):
            if (
                self.reanalisis_agente_ia
                >= self.max_reanalisis_agente_ia
            ):
                self.finalizar_ejecucion_con_error(
                    tarea,
                    (
                        "Qwen agotó los "
                        "reanálisis permitidos.\n\n"
                        f"{resultado.get('detalle', '')}"
                    ),
                )
                return

            self.reanalisis_agente_ia += 1

            self.fase_ejecucion_real = (
                "agente_planificando"
            )

            tarea["ejecucion_real_fase"] = (
                self.fase_ejecucion_real
            )

            self.actualizar_chat_qwen(
                "⚠ Una acción del plan falló. "
                "Voy a mirar la pantalla otra vez "
                "y corregir la ruta."
            )

            QTimer.singleShot(
                700,
                lambda tarea=tarea,
                resultado=resultado: (
                    self.solicitar_plan_agente_ia(
                        tarea,
                        motivo="error_herramienta",
                        error=resultado,
                    )
                ),
            )

            return

        self.indice_plan_agente_ia += 1

        self.ejecuciones_reales_completadas += 1

        self.pasos_agente_ia_actual += 1

        tarea[
            "ejecuciones_reales_completadas"
        ] = (
            self.ejecuciones_reales_completadas
        )

        # ====================================================
        # UNA ACCIÓN = UNA NUEVA OBSERVACIÓN
        # ====================================================

        self.plan_agente_ia_actual = []

        self.indice_plan_agente_ia = 0

        self.fase_ejecucion_real = (
            "agente_planificando"
        )

        tarea["ejecucion_real_fase"] = (
            self.fase_ejecucion_real
        )

        tarea["accion_actual_indice"] = (
            None
        )

        tarea["detalle_estado"] = (
            f"Repetición "
            f"{self.repeticion_ejecucion_real}/"
            f"{self.obtener_repeticiones_tarea(tarea)} "
            "· Qwen verificando el resultado..."
        )

        self.guardar_tareas_en_disco()

        self.actualizar_chat_qwen(
            "👁 Acción ejecutada. "
            "Tomaré una captura nueva antes "
            "de decidir el siguiente paso."
        )

        QTimer.singleShot(
            self.delay_agente_ia_ms(
                tipo
            ),
            lambda tarea=tarea: (
                self.solicitar_plan_agente_ia(
                    tarea,
                    motivo=(
                        "verificar_y_continuar"
                    ),
                )
            ),
        )

        return

    # ========================================================
    # TERMINAR REPETICIÓN DEL AGENTE
    # ========================================================

    def finalizar_repeticion_agente_ia(
        self,
        tarea,
    ):
        repeticiones = (
            self.obtener_repeticiones_tarea(
                tarea
            )
        )

        if (
            self.repeticion_ejecucion_real
            >= repeticiones
        ):
            self.finalizar_ejecucion(
                tarea
            )
            return

        self.repeticion_ejecucion_real += 1

        self.plan_agente_ia_actual = []
        self.indice_plan_agente_ia = 0

        self.reanalisis_agente_ia = 0
        self.historial_agente_ia = []

        self.pasos_agente_ia_actual = 0

        self.ultima_firma_plan_agente_ia = None
        self.repeticiones_plan_agente_ia = 0

        self.estancamientos_agente_ia = 0

        self.elapsed_repeticion_base_ms = 0

        self.inicio_repeticion_real_monotonic = (
            time.monotonic()
        )

        self.fase_ejecucion_real = (
            "agente_planificando"
        )

        tarea["repeticion_actual"] = (
            self.repeticion_ejecucion_real
        )

        tarea[
            "ejecucion_real_repeticion"
        ] = (
            self.repeticion_ejecucion_real
        )

        tarea["ejecucion_real_fase"] = (
            self.fase_ejecucion_real
        )

        tarea["accion_actual_indice"] = None

        tarea["detalle_estado"] = (
            f"Repetición "
            f"{self.repeticion_ejecucion_real}/"
            f"{repeticiones} · "
            "Qwen preparando la siguiente vuelta..."
        )

        self.guardar_tareas_en_disco()

        # Una consulta global por repetición,
        # no una consulta por cada paso.
        QTimer.singleShot(
            600,
            lambda tarea=tarea: (
                self.solicitar_plan_agente_ia(
                    tarea,
                    motivo="nueva_repeticion",
                )
            ),
        )

    # ========================================================
    # CONTROL DE TRAYECTORIA QWEN
    # ========================================================

    def construir_clave_accion_ia(
        self,
        tarea,
        momento,
    ):
        return (
            f"{tarea.get('current_run_key', '')}|"
            f"{self.repeticion_ejecucion_real}|"
            f"{self.indice_ejecucion_real}|"
            f"{momento}"
        )

    def guardar_objetivo_inferido_ia(
        self,
        tarea,
        objetivo,
    ):
        objetivo = str(
            objetivo
            or ""
        ).strip()

        if not objetivo:
            return

        actual = tarea.get(
            "objetivo_ia"
        )

        if actual:
            return

        tarea["objetivo_ia"] = {
            "descripcion": objetivo,
            "creado_por": "qwen3-vl",
            "timestamp": (
                datetime.now().isoformat()
            ),
        }

        self.guardar_tareas_en_disco()

        print(
            "[BIN IA] Objetivo aprendido: "
            f"{objetivo}"
        )

    def convertir_datos_herramienta_ia(
        self,
        datos,
    ):
        datos = dict(
            datos
            or {}
        )

        def convertir_punto(
            campo_x,
            campo_y,
            destino_x,
            destino_y,
        ):
            if (
                datos.get(campo_x)
                is None
                or datos.get(campo_y)
                is None
            ):
                return True

            try:
                x_norm = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            datos[campo_x]
                        ),
                    ),
                )

                y_norm = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            datos[campo_y]
                        ),
                    ),
                )

            except Exception:
                return False

            punto = (
                self.convertir_punto_visor_a_windows(
                    x_norm,
                    y_norm,
                )
            )

            if punto is None:
                return False

            datos[destino_x] = int(
                punto[0]
            )

            datos[destino_y] = int(
                punto[1]
            )

            return True

        if not convertir_punto(
            "x_norm",
            "y_norm",
            "x",
            "y",
        ):
            return None

        if not convertir_punto(
            "x_inicio_norm",
            "y_inicio_norm",
            "x_inicio",
            "y_inicio",
        ):
            return None

        if not convertir_punto(
            "x_fin_norm",
            "y_fin_norm",
            "x_fin",
            "y_fin",
        ):
            return None

        campos_norm = (
            "x_norm",
            "y_norm",
            "x_inicio_norm",
            "y_inicio_norm",
            "x_fin_norm",
            "y_fin_norm",
        )

        for campo in campos_norm:
            datos.pop(
                campo,
                None,
            )

        return datos

    def ejecutar_herramienta_ia(
        self,
        tarea,
        herramienta,
    ):
        if not isinstance(
            herramienta,
            dict,
        ):
            return {
                "ok": False,
                "detalle": (
                    "Herramienta IA inválida."
                ),
            }

        tipo = str(
            herramienta.get(
                "type",
                "",
            )
            or ""
        ).strip().lower()

        tipos_permitidos = {
            "abrir_aplicacion",
            "abrir_inicio",
            "click",
            "doble_click",
            "abrir_elemento",
            "abrir_menu_contextual",
            "click_central",
            "desplazar",
            "scroll",
            "scroll_agrupado",
            "arrastrar",
            "escribir_texto",
            "copiar",
            "pegar",
            "cortar",
            "deshacer",
            "rehacer",
            "seleccionar_todo",
            "guardar",
            "buscar",
            "imprimir",
            "cambiar_aplicacion",
            "cerrar_ventana",
            "navegar_url",
            "navegar",
            "buscar_o_navegar",
            "tecla",
            "atajo_teclado",
        }

        if tipo not in tipos_permitidos:
            return {
                "ok": False,
                "detalle": (
                    "Qwen solicitó una herramienta "
                    f"no permitida: {tipo}"
                ),
            }

        # ====================================================
        # NORMALIZAR ARGUMENTOS GENERADOS POR QWEN
        # ====================================================

        datos_brutos = dict(
            herramienta.get(
                "data"
            )
            or {}
        )

        # Texto
        if (
            "texto" not in datos_brutos
            and "text" in datos_brutos
        ):
            datos_brutos["texto"] = (
                datos_brutos.get(
                    "text"
                )
            )

        # Aplicación
        if (
            "consulta" not in datos_brutos
            and "app_name" in datos_brutos
        ):
            datos_brutos["consulta"] = (
                datos_brutos.get(
                    "app_name"
                )
            )

        if (
            "consulta" not in datos_brutos
            and "application" in datos_brutos
        ):
            datos_brutos["consulta"] = (
                datos_brutos.get(
                    "application"
                )
            )

        # Proceso
        if (
            "proceso" not in datos_brutos
            and "process" in datos_brutos
        ):
            datos_brutos["proceso"] = (
                datos_brutos.get(
                    "process"
                )
            )

        # Navegación
        if (
            "destino" not in datos_brutos
            and "url" in datos_brutos
        ):
            datos_brutos["destino"] = (
                datos_brutos.get(
                    "url"
                )
            )

        if (
            "navegador" not in datos_brutos
            and "browser" in datos_brutos
        ):
            datos_brutos["navegador"] = (
                datos_brutos.get(
                    "browser"
                )
            )

        # ====================================================
        # TECLADO / CONTEXTO OBJETIVO
        # ====================================================

        if (
            "tecla" not in datos_brutos
            and "key" in datos_brutos
        ):
            datos_brutos["tecla"] = (
                datos_brutos.get(
                    "key"
                )
            )

        if (
            "teclas" not in datos_brutos
            and "keys" in datos_brutos
        ):
            datos_brutos["teclas"] = (
                datos_brutos.get(
                    "keys"
                )
            )

        if (
            "modificadores" not in datos_brutos
            and "modifiers" in datos_brutos
        ):
            datos_brutos["modificadores"] = (
                datos_brutos.get(
                    "modifiers"
                )
            )

        if (
            "proceso_objetivo" not in datos_brutos
            and "target_process" in datos_brutos
        ):
            datos_brutos["proceso_objetivo"] = (
                datos_brutos.get(
                    "target_process"
                )
            )

        if (
            "titulo_objetivo" not in datos_brutos
            and "target_title" in datos_brutos
        ):
            datos_brutos["titulo_objetivo"] = (
                datos_brutos.get(
                    "target_title"
                )
            )

        if (
            "clase_objetivo" not in datos_brutos
            and "target_class" in datos_brutos
        ):
            datos_brutos["clase_objetivo"] = (
                datos_brutos.get(
                    "target_class"
                )
            )

        datos = (
            self.convertir_datos_herramienta_ia(
                datos_brutos
            )
        )

        if datos is None:
            return {
                "ok": False,
                "detalle": (
                    "No pude convertir las "
                    "coordenadas de Qwen."
                ),
            }

        # ====================================================
        # NAVEGACIÓN URL SEGURA
        # ====================================================

        if tipo == "navegar_url":
            return (
                self.ejecutar_navegacion_url_ia_segura(
                    datos
                )
            )

        # ====================================================
        # NAVEGACIÓN CONTROLADA POR QWEN
        # ====================================================
        #
        # Antes de Ctrl+L necesitamos garantizar
        # que el navegador indicado por Qwen sea
        # realmente el foreground.
        # ====================================================

        if tipo in {
            "navegar",
            "buscar_o_navegar",
        }:
            navegador = str(
                datos.get(
                    "navegador",
                    "",
                )
                or ""
            ).strip().lower()

            if navegador:
                navegador = (
                    self.normalizar_proceso_aplicacion(
                        proceso=navegador,
                    )
                )

            else:
                contexto = (
                    self.obtener_contexto_ventana_activa()
                    or {}
                )

                navegador = (
                    self.normalizar_proceso_aplicacion(
                        proceso=str(
                            contexto.get(
                                "proceso",
                                "",
                            )
                            or ""
                        ),
                    )
                )

            if not navegador:
                return {
                    "ok": False,
                    "detalle": (
                        "Qwen no indicó "
                        "un navegador válido."
                    ),
                }

            datos["navegador"] = navegador

            ventana = (
                self.buscar_ventana_contexto_replay(
                    {
                        "proceso": navegador,
                        "titulo": "",
                        "clase": "",
                    },
                    activar=True,
                )
            )

            if not ventana.get("ok"):
                return {
                    "ok": False,
                    "detalle": (
                        f"El navegador {navegador} "
                        "todavía no está disponible."
                    ),
                }

        # ====================================================
        # CONSTRUIR CONTEXTO OBJETIVO PARA QWEN
        # ====================================================

        contexto_objetivo = None

        proceso_objetivo = str(
            datos.get(
                "proceso_objetivo",
                "",
            )
            or ""
        ).strip().lower()

        titulo_objetivo = str(
            datos.get(
                "titulo_objetivo",
                "",
            )
            or ""
        ).strip()

        clase_objetivo = str(
            datos.get(
                "clase_objetivo",
                "",
            )
            or ""
        ).strip()

        if proceso_objetivo:
            proceso_objetivo = (
                self.normalizar_proceso_aplicacion(
                    proceso=proceso_objetivo,
                )
                or proceso_objetivo
            )

            contexto_objetivo = {
                "proceso": proceso_objetivo,
                "titulo": titulo_objetivo,
                "clase": clase_objetivo,
            }

        elif bool(
            datos.get(
                "usar_foreground",
                False,
            )
        ):
            contexto_objetivo = (
                self.obtener_contexto_foreground_externo()
            )

            if not contexto_objetivo:
                return {
                    "ok": False,
                    "detalle": (
                        "Qwen pidió escribir sobre el "
                        "foreground, pero BIN no encontró "
                        "una ventana externa válida."
                    ),
                }

        elif tipo in {
            "escribir_texto",
            "tecla",
        }:
            return {
                "ok": False,
                "detalle": (
                    "Qwen no indicó un destino seguro "
                    "para la acción de teclado."
                ),
            }

        accion_ia = {
            "tipo": tipo,
            "descripcion": (
                f"Corrección IA · {tipo}"
            ),
            "datos": datos,
            "contexto_objetivo": contexto_objetivo,
        }

        print(
            "[BIN IA] Herramienta: "
            f"{tipo} · {datos}"
        )

        return (
            self.ejecutar_accion_semantica_real(
                accion_ia,
                tarea,
            )
        )

    def registrar_correccion_ia(
        self,
        tarea,
        exitosa,
        registro,
    ):
        memoria = tarea.setdefault(
            "memoria_ia",
            {},
        )

        clave = (
            "correcciones_exitosas"
            if exitosa
            else "correcciones_fallidas"
        )

        lista = memoria.setdefault(
            clave,
            [],
        )

        lista.append(
            registro
        )

        # No dejar crecer tareas.json
        # indefinidamente.
        if len(lista) > 40:
            del lista[:-40]

        self.guardar_tareas_en_disco()

    def iniciar_control_trayectoria_ia(
        self,
        tarea,
        accion,
        momento="preaccion",
    ):
        fase = (
            "ia_preaccion"
            if momento == "preaccion"
            else "ia_postaccion"
        )

        nueva_fase = (
            self.fase_ejecucion_real
            != fase
        )

        self.accion_real_actual = accion
        self.fase_ejecucion_real = fase

        if nueva_fase:
            self.cancelar_consulta_ia_visual()

            self.inicio_control_trayectoria_ia_monotonic = (
                time.monotonic()
            )

            self.correcciones_ia_consecutivas = 0
            self.ultima_correccion_ia = None

        self.pausa_ia_activa = True

        self.guardar_estado_ejecutor_real_en_tarea(
            tarea
        )

        self.timer_ejecucion_accion.start(
            0
        )

    def procesar_control_trayectoria_ia(
        self,
    ):
        tarea = (
            self.obtener_tarea_ejecutando()
        )

        if (
            not tarea
            or not self.ejecucion_fisica_activa
            or tarea.get("estado")
            != "EJECUTANDO"
        ):
            return

        # Una pausa explícita del usuario
        # siempre tiene prioridad.
        if self.pausa_ejecucion_global:
            return

        accion = self.accion_real_actual

        if accion is None:
            self.finalizar_ejecucion_con_error(
                tarea,
                "Qwen perdió la acción que debía supervisar.",
            )
            return

        momento = (
            "preaccion"
            if self.fase_ejecucion_real
            == "ia_preaccion"
            else "postaccion"
        )

        if (
            self.inicio_control_trayectoria_ia_monotonic
            is None
        ):
            self.inicio_control_trayectoria_ia_monotonic = (
                time.monotonic()
            )

        transcurrido_ms = int(
            max(
                0.0,
                time.monotonic()
                - self.inicio_control_trayectoria_ia_monotonic,
            )
            * 1000
        )

        if (
            transcurrido_ms
            >= self.timeout_control_trayectoria_ia_ms
        ):
            # --------------------------------------------
            # QWEN DEMASIADO LENTO
            # --------------------------------------------
            # No convertimos lentitud de la IA en un
            # error de la tarea.
            #
            # Cancelamos la inferencia y devolvemos el
            # control al supervisor rápido de Python.
            # --------------------------------------------

            self.cancelar_consulta_ia_visual()

            self.pausa_ia_activa = False

            self.inicio_control_trayectoria_ia_monotonic = (
                None
            )

            self.correcciones_ia_consecutivas = 0
            self.ultima_correccion_ia = None

            self.mostrar_barra_ejecucion()

            self.actualizar_chat_bin(
                "Qwen tardó más de 6 segundos. "
                "BIN continúa mediante supervisión local."
            )

            if momento == "preaccion":
                self.iniciar_supervision_accion(
                    tarea,
                    accion,
                    modo="preaccion",
                    delay_inicial_ms=0,
                )

            else:
                self.iniciar_supervision_accion(
                    tarea,
                    accion,
                    modo="postaccion",
                    delay_inicial_ms=(
                        self.delay_minimo_supervision_accion(
                            accion
                        )
                    ),
                )

            return

        frame = None

        if self.frame_actual is not None:
            try:
                frame = (
                    self.frame_actual.copy()
                )
            except Exception:
                frame = self.frame_actual

        siguiente_accion = (
            accion
            if momento == "preaccion"
            else self.obtener_siguiente_accion_plan_real()
        )

        contexto_actual = (
            self.obtener_contexto_ventana_activa()
        )

        ia = self.evaluar_estado_con_ia(
            frame,
            {
                "momento_ia": momento,
                "accion_ejecutada": (
                    None
                    if momento
                    == "preaccion"
                    else accion
                ),
                "siguiente_accion": (
                    siguiente_accion
                ),
                "contexto_actual": (
                    contexto_actual
                ),
                "contexto_esperado_despues": (
                    accion.get(
                        "contexto_despues"
                    )
                ),
                "contexto_esperado_siguiente": (
                    (
                        siguiente_accion.get(
                            "contexto_objetivo"
                        )
                        if siguiente_accion
                        else None
                    )
                ),
            },
        )

        if not ia.get(
            "disponible"
        ):
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "El control inteligente está activo, "
                    "pero Qwen/Ollama no está disponible."
                ),
            )
            return

        self.guardar_objetivo_inferido_ia(
            tarea,
            ia.get(
                "objetivo_inferido"
            ),
        )

        decision = str(
            ia.get(
                "decision",
                "AMBIGUOUS",
            )
            or "AMBIGUOUS"
        ).upper()

        motivo = str(
            ia.get(
                "motivo",
                "",
            )
            or ""
        )

        print(
            "[BIN IA TRAYECTORIA] "
            f"{momento} · "
            f"{decision} · "
            f"{motivo}"
        )

        # --------------------------------------------
        # READY
        # --------------------------------------------

        if decision == "READY":
            if (
                self.ultima_correccion_ia
                is not None
            ):
                self.registrar_correccion_ia(
                    tarea,
                    True,
                    {
                        **self.ultima_correccion_ia,
                        "verificada": (
                            datetime.now().isoformat()
                        ),
                    },
                )

            self.pausa_ia_activa = False
            self.correcciones_ia_consecutivas = 0
            self.ultima_correccion_ia = None
            self.inicio_control_trayectoria_ia_monotonic = (
                None
            )

            self.mostrar_barra_ejecucion()

            if momento == "preaccion":
                self.clave_accion_autorizada_ia = (
                    self.construir_clave_accion_ia(
                        tarea,
                        "preaccion",
                    )
                )

                self.fase_ejecucion_real = (
                    "espera_accion"
                )

                self.delay_ejecucion_restante_ms = 0

                self.guardar_estado_ejecutor_real_en_tarea(
                    tarea
                )

                self.timer_ejecucion_accion.start(
                    0
                )

                return

            self.completar_accion_real_supervisada(
                tarea
            )

            return

        # --------------------------------------------
        # SKIP
        # --------------------------------------------

        if decision == "SKIP":
            self.pausa_ia_activa = False

            self.correcciones_ia_consecutivas = 0

            self.ultima_correccion_ia = None

            self.inicio_control_trayectoria_ia_monotonic = (
                None
            )

            self.actualizar_chat_qwen(
                "⏭ Acción original omitida por Qwen."
            )

            self.mostrar_barra_ejecucion()

            self.completar_accion_real_supervisada(
                tarea
            )

            return

        # --------------------------------------------
        # REPLACE
        # --------------------------------------------

        if decision == "REPLACE":
            acciones = (
                ia.get(
                    "acciones"
                )
                or []
            )

            if not acciones:
                self.finalizar_ejecucion_con_error(
                    tarea,
                    (
                        "Qwen solicitó REPLACE "
                        "sin entregar una acción."
                    ),
                )
                return

            herramienta = acciones[0]

            resultado = (
                self.ejecutar_herramienta_ia(
                    tarea,
                    herramienta,
                )
            )

            registro = {
                "timestamp": (
                    datetime.now().isoformat()
                ),
                "indice": (
                    self.indice_ejecucion_real
                ),
                "repeticion": (
                    self.repeticion_ejecucion_real
                ),
                "momento": momento,
                "decision": "REPLACE",
                "motivo": motivo,
                "herramienta": herramienta,
                "resultado": resultado,
            }

            if not resultado.get(
                "ok"
            ):
                self.registrar_correccion_ia(
                    tarea,
                    False,
                    registro,
                )

                self.finalizar_ejecucion_con_error(
                    tarea,
                    (
                        "Qwen intentó reemplazar "
                        "la acción, pero la corrección "
                        "falló.\n\n"
                        f"{resultado.get('detalle', '')}"
                    ),
                )

                return

            self.registrar_correccion_ia(
                tarea,
                True,
                registro,
            )

            self.actualizar_chat_qwen(
                "↪ Reemplacé la acción original.\n"
                f"Nueva acción: "
                f"{herramienta.get('type', '')}"
            )

            self.pausa_ia_activa = False

            self.inicio_control_trayectoria_ia_monotonic = (
                None
            )

            self.mostrar_barra_ejecucion()

            self.completar_accion_real_supervisada(
                tarea
            )

            return

        # --------------------------------------------
        # FAILED
        # --------------------------------------------

        if decision == "FAILED":
            if (
                self.ultima_correccion_ia
                is not None
            ):
                self.registrar_correccion_ia(
                    tarea,
                    False,
                    self.ultima_correccion_ia,
                )

            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "Qwen detuvo la trayectoria.\n\n"
                    f"{motivo}"
                ),
            )

            return

        # --------------------------------------------
        # ADJUST / REPLAN
        # --------------------------------------------

        if decision in {
            "ADJUST",
            "REPLAN",
        }:
            self.pausa_ia_activa = True

            self.mostrar_barra_ejecucion_ia(
                motivo
                or "Corrigiendo trayectoria"
            )

            if (
                self.correcciones_ia_consecutivas
                >= self.max_correcciones_ia_consecutivas
            ):
                self.finalizar_ejecucion_con_error(
                    tarea,
                    (
                        "Qwen alcanzó el máximo "
                        "de correcciones consecutivas."
                    ),
                )
                return

            acciones = ia.get(
                "acciones"
            ) or []

            if acciones:
                herramienta = acciones[0]

                resultado = (
                    self.ejecutar_herramienta_ia(
                        tarea,
                        herramienta,
                    )
                )

                self.correcciones_ia_consecutivas += 1

                self.ultima_correccion_ia = {
                    "timestamp": (
                        datetime.now().isoformat()
                    ),
                    "indice": (
                        self.indice_ejecucion_real
                    ),
                    "repeticion": (
                        self.repeticion_ejecucion_real
                    ),
                    "momento": momento,
                    "decision": decision,
                    "motivo": motivo,
                    "herramienta": herramienta,
                    "resultado": resultado,
                }

                if not resultado.get(
                    "ok"
                ):
                    print(
                        "[BIN IA] La corrección "
                        "no pudo ejecutarse: "
                        f"{resultado.get('detalle', '')}"
                    )

            self.delay_ejecucion_restante_ms = (
                self.intervalo_control_trayectoria_ia_ms
            )

            self.guardar_estado_ejecutor_real_en_tarea(
                tarea
            )

            self.timer_ejecucion_accion.start(
                self.intervalo_control_trayectoria_ia_ms
            )

            return

        # --------------------------------------------
        # WAIT / AMBIGUOUS
        # --------------------------------------------

        self.pausa_ia_activa = True

        self.mostrar_barra_ejecucion_ia(
            motivo
            or "Observando pantalla"
        )

        self.delay_ejecucion_restante_ms = (
            self.intervalo_control_trayectoria_ia_ms
        )

        self.guardar_estado_ejecutor_real_en_tarea(
            tarea
        )

        self.timer_ejecucion_accion.start(
            self.intervalo_control_trayectoria_ia_ms
        )

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

    # ========================================================
    # NAVEGACIÓN URL SEGURA PARA QWEN
    # ========================================================

    def ejecutar_navegacion_url_ia_segura(
        self,
        datos,
    ):
        datos = dict(
            datos
            or {}
        )

        destino = str(
            datos.get(
                "destino",
                "",
            )
            or ""
        ).strip()

        if not destino:
            return {
                "ok": False,
                "metodo": "navegacion_segura",
                "detalle": (
                    "Qwen no indicó un destino."
                ),
            }

        navegador = str(
            datos.get(
                "navegador",
                "",
            )
            or ""
        ).strip().lower()

        if navegador:
            navegador = (
                self.normalizar_proceso_aplicacion(
                    proceso=navegador,
                )
            )

        # Si Qwen no indicó navegador,
        # intentar usar el navegador foreground.
        if not navegador:
            contexto = (
                self.obtener_contexto_ventana_activa()
                or {}
            )

            navegador = (
                self.normalizar_proceso_aplicacion(
                    proceso=str(
                        contexto.get(
                            "proceso",
                            "",
                        )
                        or ""
                    )
                )
            )

        navegadores_permitidos = {
            "chrome.exe",
            "msedge.exe",
            "firefox.exe",
            "brave.exe",
            "opera.exe",
        }

        if navegador not in navegadores_permitidos:
            return {
                "ok": False,
                "metodo": "navegacion_segura",
                "detalle": (
                    "Qwen no indicó un navegador "
                    "compatible."
                ),
            }

        ruta = (
            self.resolver_ruta_aplicacion_windows(
                navegador,
                datos.get(
                    "ejecutable",
                    "",
                ),
            )
        )

        try:
            # --------------------------------------------
            # MÉTODO PRINCIPAL
            # --------------------------------------------
            #
            # No usamos Ctrl+L.
            # No escribimos físicamente la URL.
            #
            # El navegador recibe directamente
            # el destino como argumento.
            # --------------------------------------------

            if ruta:
                subprocess.Popen(
                    [
                        ruta,
                        destino,
                    ],
                    close_fds=True,
                )

                return {
                    "ok": True,
                    "metodo": "subprocess_url",
                    "detalle": (
                        f"{navegador} recibió "
                        f"el destino: {destino}"
                    ),
                }

            # --------------------------------------------
            # FALLBACK WINDOWS
            # --------------------------------------------

            if sys.platform == "win32":
                resultado = (
                    ctypes.windll.shell32
                    .ShellExecuteW(
                        None,
                        "open",
                        navegador,
                        destino,
                        None,
                        1,
                    )
                )

                if int(resultado) > 32:
                    return {
                        "ok": True,
                        "metodo": "ShellExecuteW_url",
                        "detalle": (
                            f"{navegador} recibió "
                            f"el destino: {destino}"
                        ),
                    }

        except Exception as error:
            return {
                "ok": False,
                "metodo": "navegacion_segura",
                "detalle": str(error),
            }

        return {
            "ok": False,
            "metodo": "navegacion_segura",
            "detalle": (
                "No pude resolver el navegador "
                f"{navegador}."
            ),
        }

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

                # ====================================================
        # COMPONENTES DEL SHELL DE WINDOWS
        # ====================================================
        #
        # SearchApp / StartMenuExperienceHost no son
        # aplicaciones normales que debamos localizar y abrir
        # mediante subprocess.
        #
        # Si la demostración produjo uno de estos procesos,
        # la intención real es abrir Inicio / búsqueda.
        # ====================================================

        if proceso in {
            "searchapp.exe",
            "searchhost.exe",
            "startmenuexperiencehost.exe",
        }:
            return self.ejecutar_abrir_inicio()

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
                activar=True,
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
        # ====================================================
        # WINDOWS NATIVO
        # ====================================================

        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32

                VK_LWIN = 0x5B
                KEYEVENTF_KEYUP = 0x0002

                # Presionar Windows.
                user32.keybd_event(
                    VK_LWIN,
                    0,
                    0,
                    0,
                )

                # Pequeñísima pausa para que Windows
                # registre correctamente la pulsación.
                ctypes.windll.kernel32.Sleep(
                    35
                )

                # Soltar Windows.
                user32.keybd_event(
                    VK_LWIN,
                    0,
                    KEYEVENTF_KEYUP,
                    0,
                )

                return {
                    "ok": True,
                    "estado": "ENVIADO",
                    "recuperable": False,
                    "metodo": "WindowsNative",
                    "detalle": (
                        "Abrir menú Inicio"
                    ),
                }

            except Exception as error:
                print(
                    "[BIN] Windows nativo no pudo "
                    f"abrir Inicio: {error}"
                )

        # ====================================================
        # FALLBACK PYNPUT
        # ====================================================

        if not self.asegurar_controladores_replay():
            return {
                "ok": False,
                "estado": "SIN_TECLADO",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": (
                    "Controlador de teclado "
                    "no disponible."
                ),
            }

        tecla_win = (
            self.tecla_replay_desde_nombre(
                "cmd"
            )
        )

        if tecla_win is None:
            return {
                "ok": False,
                "estado": "WIN_NO_DISPONIBLE",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": (
                    "pynput no expuso "
                    "la tecla Windows."
                ),
            }

        try:
            self.keyboard_replay.press(
                tecla_win
            )

            self.keyboard_replay.release(
                tecla_win
            )

            return {
                "ok": True,
                "estado": "ENVIADO",
                "recuperable": False,
                "metodo": "pynput",
                "detalle": (
                    "Abrir menú Inicio"
                ),
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

        # ====================================================
        # DESTINO SEGURO PARA ACCIONES DE TECLADO DE QWEN
        # ====================================================

        def preparar_destino_teclado_ia():
            if not contexto:
                return {
                    "ok": False,
                    "detalle": (
                        "La acción de teclado no tiene "
                        "contexto objetivo."
                    ),
                }

            proceso_esperado = str(
                contexto.get(
                    "proceso",
                    "",
                )
                or ""
            ).strip().lower()

            limite = (
                time.monotonic()
                + 2.5
            )

            ultimo_resultado = {}

            while True:
                ultimo_resultado = (
                    self.resolver_contexto_teclado_replay(
                        contexto,
                        permitir_foreground_externo=False,
                    )
                )

                if ultimo_resultado.get("ok"):
                    contexto_actual = (
                        self.obtener_contexto_ventana_activa()
                        or {}
                    )

                    proceso_actual = str(
                        contexto_actual.get(
                            "proceso",
                            "",
                        )
                        or ""
                    ).strip().lower()

                    # ----------------------------------------
                    # VERIFICACIÓN FINAL
                    # ----------------------------------------
                    #
                    # Aunque Windows diga que activó una
                    # ventana, BIN vuelve a comprobar que
                    # realmente quedó el proceso esperado
                    # antes de escribir una sola tecla.
                    # ----------------------------------------

                    if (
                        not proceso_esperado
                        or proceso_actual
                        == proceso_esperado
                    ):
                        return {
                            "ok": True,
                            "detalle": (
                                proceso_actual
                                or "contexto confirmado"
                            ),
                        }

                if (
                    time.monotonic()
                    >= limite
                ):
                    break

                # La aplicación puede haberse abierto
                # milisegundos antes y todavía no tener
                # una ventana lista.
                QApplication.processEvents()

                if sys.platform == "win32":
                    ctypes.windll.kernel32.Sleep(
                        60
                    )

            return {
                "ok": False,
                "detalle": (
                    "No pude confirmar el destino "
                    "de teclado. "
                    + str(
                        ultimo_resultado.get(
                            "detalle",
                            "",
                        )
                        or ""
                    )
                ),
            }

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

            # ====================================================
            # CONFIRMAR DESTINO ANTES DE ESCRIBIR
            # ====================================================

            resultado_contexto = (
                preparar_destino_teclado_ia()
            )

            if not resultado_contexto.get(
                "ok"
            ):
                return {
                    "ok": False,
                    "estado": "CONTEXTO_NO_CONFIRMADO",
                    "recuperable": True,
                    "metodo": "teclado_contexto",
                    "detalle": (
                        "BIN bloqueó la escritura porque "
                        "no pudo confirmar la ventana "
                        "objetivo. "
                        + str(
                            resultado_contexto.get(
                                "detalle",
                                "",
                            )
                            or ""
                        )
                    ),
                }

            if not self.asegurar_controladores_replay():
                return {
                    "ok": False,
                    "metodo": "pynput",
                    "detalle": (
                        "Controlador de teclado "
                        "no disponible"
                    ),
                }

            texto = str(
                datos.get(
                    "texto",
                    "",
                )
                or ""
            )

            try:
                self.keyboard_replay.type(
                    texto
                )

                return {
                    "ok": True,
                    "estado": "ENVIADO",
                    "metodo": "pynput",
                    "detalle": (
                        "Texto enviado a "
                        + str(
                            resultado_contexto.get(
                                "detalle",
                                "destino confirmado",
                            )
                        )
                    ),
                }

            except Exception as error:
                return {
                    "ok": False,
                    "estado": "ERROR_TECLADO",
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

        if tipo == "tecla":

            # Una tecla normal pertenece a una
            # aplicación concreta: Enter, Escape,
            # Tab, etc.
            resultado_contexto = (
                preparar_destino_teclado_ia()
            )

            if not resultado_contexto.get(
                "ok"
            ):
                return {
                    "ok": False,
                    "estado": "CONTEXTO_NO_CONFIRMADO",
                    "recuperable": True,
                    "metodo": "teclado_contexto",
                    "detalle": (
                        "BIN bloqueó la tecla porque "
                        "no pudo confirmar la ventana "
                        "objetivo. "
                        + str(
                            resultado_contexto.get(
                                "detalle",
                                "",
                            )
                            or ""
                        )
                    ),
                }

            ok = self.ejecutar_atajo_replay(
                [],
                datos.get("tecla"),
                datos.get("caracter"),
            )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": "tecla",
            }

        if tipo == "atajo_teclado":

            # ====================================================
            # ATAJOS GLOBALES
            # ====================================================
            #
            # No forzamos una aplicación aquí.
            #
            # Esto mantiene funcionando:
            # Win+R
            # Win+S
            # Alt+F4
            # Ctrl+Shift+S
            # y combinaciones arbitrarias decididas por Qwen.
            # ====================================================

            teclas = (
                datos.get("teclas")
                or []
            )

            if teclas:
                ok = (
                    self.ejecutar_combinacion_teclas_replay(
                        teclas
                    )
                )
            else:
                ok = self.ejecutar_atajo_replay(
                    datos.get(
                        "modificadores"
                    )
                    or [],
                    datos.get("tecla"),
                    datos.get("caracter"),
                )

            return {
                "ok": bool(ok),
                "metodo": "pynput",
                "detalle": "atajo_teclado",
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
                tarea.get(
                    "ejecucion_real_fase",
                    "espera_accion",
                )
                or "espera_accion"
            )

            if self.fase_ejecucion_real == "checkpoint":
                self.fase_ejecucion_real = "supervisor"

            # Una pausa ocurrida mientras Qwen esperaba
            # ANTES de ejecutar una acción no debe obligar
            # a repetir esa inferencia al continuar.
            #
            # Volvemos al ejecutor normal y dejamos que
            # Python decida si realmente existe una
            # desalineación que necesite a Qwen.
            if self.fase_ejecucion_real == "ia_preaccion":
                self.fase_ejecucion_real = "espera_accion"

                tarea["ejecucion_real_fase"] = (
                    "espera_accion"
                )

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

        self.cancelar_consulta_ia_visual()

        self.pausa_ia_activa = False
        self.clave_accion_autorizada_ia = None
        self.inicio_control_trayectoria_ia_monotonic = None
        self.correcciones_ia_consecutivas = 0
        self.ultima_correccion_ia = None
        self.modo_fallback_contexto = False
        self.ultimo_resultado_contexto_replay = None

        if (
            reanudar
            and self.fase_ejecucion_real
            in {
                "supervisor",
                "supervisor_preaccion",
                "ia_preaccion",
                "ia_postaccion",
            }
            and 0 <= self.indice_ejecucion_real < len(plan)
        ):
            self.accion_real_actual = plan[
                self.indice_ejecucion_real
            ]

            if self.fase_ejecucion_real in {
                "supervisor",
                "supervisor_preaccion",
            }:
                self.inicio_espera_supervisor_monotonic = (
                    time.monotonic()
                )
            else:
                self.inicio_espera_supervisor_monotonic = None

                self.inicio_control_trayectoria_ia_monotonic = (
                    time.monotonic()
                )

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

        # ====================================================
        # NUEVO AGENTE QWEN
        # ====================================================

        if (
            self.modo_agente_ia_activo
            and self.fase_ejecucion_real
            == "agente_ejecutando"
        ):
            self.procesar_siguiente_accion_agente_ia()
            return

        if (
            self.modo_agente_ia_activo
            and self.fase_ejecucion_real
            == "agente_planificando"
        ):
            # La consulta HTTP es asíncrona.
            # No hay nada que hacer mientras Qwen responde.
            return

        # ====================================================
        # MOTOR LEGACY
        # ====================================================

        if self.fase_ejecucion_real in {
            "ia_preaccion",
            "ia_postaccion",
        }:
            self.procesar_control_trayectoria_ia()
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

        # ========================================================
    # DECIDIR CUÁNDO QWEN NECESITA MIRAR
    # ========================================================

    def accion_requiere_precheck_ia(
        self,
        accion,
    ):
        if not accion:
            return False

        # --------------------------------------------
        # CONTROL TOTAL QWEN
        # --------------------------------------------
        # Toda acción real debe ser aprobada,
        # corregida, reemplazada o saltada por Qwen.
        # --------------------------------------------

        return True
    
    def accion_requiere_postcheck_ia(
        self,
        accion,
    ):
        if not accion:
            return False

        tipo = str(
            accion.get(
                "tipo",
                "",
            )
            or ""
        ).strip().lower()

        # Acciones que normalmente producen
        # un cambio visual importante.
        if tipo in {
            "abrir_aplicacion",
            "abrir_inicio",
            "navegar",
            "navegar_url",
            "buscar_o_navegar",
            "click",
            "doble_click",
            "abrir_elemento",
            "abrir_menu_contextual",
            "cerrar_ventana",
            "cambiar_aplicacion",
        }:
            return True

        # Enter frecuentemente confirma una búsqueda,
        # abre una aplicación, navega o envía un formulario.
        if tipo in {
            "tecla",
            "atajo_teclado",
            "texto_tecla",
        }:
            datos = accion.get("datos") or {}

            tecla = str(
                datos.get(
                    "tecla",
                    accion.get(
                        "tecla",
                        "",
                    ),
                )
                or ""
            ).strip().lower()

            if tecla in {
                "enter",
                "return",
            }:
                return True

        return False

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
        # QWEN AUTORIZA LA TRAYECTORIA
        # ====================================================

        if (
            self.control_trayectoria_ia_activo
            and self.accion_requiere_precheck_ia(
                accion
            )
        ):
            clave_esperada = (
                self.construir_clave_accion_ia(
                    tarea,
                    "preaccion",
                )
            )

            if (
                self.clave_accion_autorizada_ia
                != clave_esperada
            ):
                self.iniciar_control_trayectoria_ia(
                    tarea,
                    accion,
                    momento="preaccion",
                )

                return

            # Autorización consumida.
            self.clave_accion_autorizada_ia = None

        else:
            # Puede existir una autorización proveniente
            # de una recuperación previa de contexto.
            self.clave_accion_autorizada_ia = None

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
            if self.control_trayectoria_ia_activo:
                self.resultado_accion_real_actual = (
                    preparacion
                )

                self.iniciar_control_trayectoria_ia(
                    tarea,
                    accion,
                    momento="preaccion",
                )

                return
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

        # ====================================================
        # SUPERVISIÓN RÁPIDA DESPUÉS DE LA ACCIÓN
        # ====================================================
        #
        # Primero usamos el supervisor determinista de BIN.
        # Windows/proceso/ventana/contexto pueden comprobarse
        # en milisegundos sin despertar a Qwen.
        # ====================================================

        self.iniciar_supervision_accion(
            tarea,
            accion,
            modo="postaccion",
            delay_inicial_ms=(
                self.delay_minimo_supervision_accion(
                    accion
                )
            ),
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

        if self.modo_agente_ia_activo:
            iniciado = (
                self.iniciar_ejecutor_agente_ia(
                    tarea,
                    reanudar=False,
                )
            )
        else:
            iniciado = (
                self.iniciar_ejecutor_real(
                    tarea,
                    reanudar=False,
                )
            )

        if not iniciado:
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "No se pudo preparar "
                    "el ejecutor de la tarea."
                ),
            )
            return

        self.actualizar_tarjeta_tarea(tarea["id"])
        self.refrescar_panel_acciones()
        self.actualizar_cabecera_operativa()
        self.guardar_tareas_en_disco()

        self.pausa_ejecucion_global = False
        self.tarea_pausada_flotante_id = None

        self.mostrar_barra_ejecucion()

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

        self.cancelar_consulta_ia_visual()
        self.cancelar_consulta_agente_ia()

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
            "ia_preaccion",
            "ia_postaccion",
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

        QTimer.singleShot(
            100,
            self.iniciar_siguiente_en_cola,
        )

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

        if self.modo_agente_ia_activo:
            iniciado = (
                self.iniciar_ejecutor_agente_ia(
                    tarea,
                    reanudar=True,
                )
            )
        else:
            iniciado = (
                self.iniciar_ejecutor_real(
                    tarea,
                    reanudar=True,
                )
            )

        if not iniciado:
            self.finalizar_ejecucion_con_error(
                tarea,
                (
                    "No se pudo restaurar "
                    "el ejecutor de la tarea."
                ),
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

        self.pausa_ejecucion_global = False
        self.tarea_pausada_flotante_id = None

        self.mostrar_barra_ejecucion()

    def finalizar_ejecucion(self, tarea):
        duracion_total = self.obtener_duracion_total_tarea(tarea)
        repeticiones = self.obtener_repeticiones_tarea(tarea)

        if hasattr(self, "timer_ejecucion_accion"):
            self.timer_ejecucion_accion.stop()
            self.cancelar_consulta_ia_visual()
            self.cancelar_consulta_agente_ia()
        self.pausa_ia_activa = False
        self.clave_accion_autorizada_ia = None
        self.inicio_control_trayectoria_ia_monotonic = None
        self.correcciones_ia_consecutivas = 0
        self.ultima_correccion_ia = None

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

        run_key_finalizado = tarea.get("current_run_key")

        if run_key_finalizado:
            self.runs_retrasados_aceptados.discard(
                (
                    tarea.get("id"),
                    run_key_finalizado,
                )
            )

        tarea["last_run_key"] = run_key_finalizado
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

        self.pausa_ejecucion_global = False
        self.tarea_pausada_flotante_id = None
        self.ocultar_barra_ejecucion()

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
            80,
            self.recuperar_bin_al_frente,
        )

        QTimer.singleShot(
            250,
            self.iniciar_siguiente_en_cola,
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
            self.cancelar_consulta_ia_visual()
            self.cancelar_consulta_agente_ia()

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

        self.pausa_ejecucion_global = False
        self.tarea_pausada_flotante_id = None
        self.ocultar_barra_ejecucion()

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
        if self.pausa_ejecucion_global:
            return

        if self.grabando:
            return

        if self.dialogo_tareas_retrasadas_abierto:
            return

        if self.obtener_tarea_ejecutando():
            return

        ahora = datetime.now()

        # ----------------------------------------------------
        # 1. IDENTIFICAR RETRASOS SIN DECISIÓN
        # ----------------------------------------------------

        retrasadas_sin_decision = self.obtener_tareas_retrasadas(
            ahora
        )

        claves_sin_decision = {
            (
                item["tarea"].get("id"),
                item["run_key"],
            )
            for item in retrasadas_sin_decision
        }

        # ----------------------------------------------------
        # 2. REVISAR LO QUE YA ESTÁ EN COLA
        # ----------------------------------------------------

        en_cola = [
            tarea
            for tarea in self.tareas
            if tarea.get("estado") == "EN COLA"
        ]

        # ----------------------------------------------------
        # 3. PRIORIDAD ABSOLUTA: TAREA QUE TODAVÍA VA A TIEMPO
        # ----------------------------------------------------

        programadas_prioritarias = []

        for tarea in en_cola:
            run_key = tarea.get("current_run_key")

            clave = (
                tarea.get("id"),
                run_key,
            )

            if clave in claves_sin_decision:
                continue

            if clave in self.runs_retrasados_aceptados:
                continue

            momento = self.obtener_momento_desde_run_key(
                run_key
            )

            programadas_prioritarias.append(
                (
                    momento or datetime.max,
                    tarea,
                )
            )

        if programadas_prioritarias:
            programadas_prioritarias.sort(
                key=lambda item: item[0]
            )

            siguiente = programadas_prioritarias[0][1]
            run_key = siguiente.get("current_run_key")

            self.iniciar_ejecucion(
                siguiente,
                run_key=run_key,
                origen="programada",
            )
            return

        # ----------------------------------------------------
        # 4. PROTEGER UNA TAREA PROGRAMADA QUE ESTÁ POR LLEGAR
        # ----------------------------------------------------

        proxima_programada = self.obtener_proxima_programada_prioritaria(
            desde=ahora,
        )

        segundos_hasta_proxima = None

        if proxima_programada is not None:
            segundos_hasta_proxima = max(
                0,
                int(
                    (
                        proxima_programada - ahora
                    ).total_seconds()
                ),
            )

            # Si faltan pocos minutos para una tarea que todavía
            # puede comenzar a tiempo, BIN no inicia una retrasada.
            if (
                segundos_hasta_proxima
                <= UMBRAL_PROTEGER_TAREA_PROGRAMADA_SEGUNDOS
            ):
                return

        # ----------------------------------------------------
        # 5. MOSTRAR UNA SOLA LISTA CON TODOS LOS RETRASOS
        # ----------------------------------------------------

        if retrasadas_sin_decision:
            self.mostrar_dialogo_tareas_retrasadas(
                retrasadas_sin_decision
            )

        # Si el usuario eligió DECIDIR DESPUÉS, BIN no ejecutará
        # ninguna de esas tareas hasta que exista una decisión.
        retrasadas_sin_decision = self.obtener_tareas_retrasadas()

        if retrasadas_sin_decision:
            return

        # ----------------------------------------------------
        # 6. COLA DE TAREAS RETRASADAS APROBADAS
        # ----------------------------------------------------

        en_cola = [
            tarea
            for tarea in self.tareas
            if tarea.get("estado") == "EN COLA"
        ]

        retrasadas_aprobadas = []

        for tarea in en_cola:
            run_key = tarea.get("current_run_key")

            clave = (
                tarea.get("id"),
                run_key,
            )

            if clave not in self.runs_retrasados_aceptados:
                continue

            momento = self.obtener_momento_desde_run_key(
                run_key
            )

            retrasadas_aprobadas.append(
                (
                    momento or datetime.max,
                    tarea,
                )
            )

        if not retrasadas_aprobadas:
            return

        # Las retrasadas se ejecutan según la hora en la que
        # originalmente debieron comenzar.
        retrasadas_aprobadas.sort(
            key=lambda item: item[0]
        )

        siguiente = retrasadas_aprobadas[0][1]
        ahora = datetime.now()

        # ----------------------------------------------------
        # 7. VOLVER A COMPROBAR LA SIGUIENTE PROGRAMADA
        # ----------------------------------------------------

        proxima_programada = self.obtener_proxima_programada_prioritaria(
            desde=ahora,
        )

        if proxima_programada is not None:
            segundos_hasta_proxima = max(
                0,
                int(
                    (
                        proxima_programada - ahora
                    ).total_seconds()
                ),
            )

            if (
                segundos_hasta_proxima
                <= UMBRAL_PROTEGER_TAREA_PROGRAMADA_SEGUNDOS
            ):
                return

            duracion_retrasada = self.obtener_duracion_total_tarea(
                siguiente
            )

            if (
                duracion_retrasada > 0
                and (
                    duracion_retrasada
                    + MARGEN_SEGURIDAD_ENTRE_TAREAS_SEGUNDOS
                )
                >= segundos_hasta_proxima
            ):
                return

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

        if self.dialogo_tareas_retrasadas_abierto:
            self.actualizar_tarjetas()
            self.actualizar_cabecera_operativa()
            return

        if self.pausa_ejecucion_global:
            self.actualizar_tarjetas()
            self.actualizar_cabecera_operativa()
            return

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

            if tarea.get("last_skipped_run_key") == run_key:
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

        if not self.obtener_tarea_ejecutando():
            self.iniciar_siguiente_en_cola()

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
    # BARRA FLOTANTE DE EJECUCIÓN
    # ========================================================

    def crear_barra_ejecucion(
        self,
    ):
        if self.barra_ejecucion is not None:
            return

        self.barra_ejecucion = QWidget(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )

        self.barra_ejecucion.setObjectName("barra_ejecucion")

        self.barra_ejecucion.setAttribute(
            Qt.WA_DeleteOnClose,
            False,
        )

        self.barra_ejecucion.setStyleSheet(f"""
            QWidget#barra_ejecucion {{
                background-color: rgba(7, 10, 18, 242);
                border: 1px solid {BORGONA};
                border-radius: 14px;
            }}

            QLabel {{
                color: {TEXTO};
                font-size: 12px;
                font-weight: 700;
            }}

            QPushButton {{
                background-color: {AMARILLO};
                color: #111111;
                border: 1px solid {BORGONA};
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 800;
            }}

            QPushButton:hover {{
                background-color: #ffd75e;
            }}
            """)

        layout = QHBoxLayout(self.barra_ejecucion)

        layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        layout.setSpacing(10)

        self.label_barra_ejecucion = QLabel("● BIN ejecutando tarea")

        self.boton_pausa_barra_ejecucion = QPushButton("PAUSAR EJECUCIÓN DE TAREAS")

        self.boton_pausa_barra_ejecucion.clicked.connect(
            self.alternar_pausa_ejecucion_flotante
        )

        layout.addWidget(self.label_barra_ejecucion)

        layout.addWidget(self.boton_pausa_barra_ejecucion)

        self.barra_ejecucion.adjustSize()

    # ========================================================
    # POSICIONAR BARRA EN LA PANTALLA DE BIN
    # ========================================================

    def posicionar_barra_ejecucion(
        self,
    ):
        if self.barra_ejecucion is None:
            return

        pantalla = self.screen()

        if pantalla is None:
            pantalla = QApplication.primaryScreen()

        if pantalla is None:
            return

        area = pantalla.availableGeometry()

        self.barra_ejecucion.adjustSize()

        ancho = self.barra_ejecucion.width()

        margen = 18

        x = area.right() - ancho - margen

        y = area.top() + margen

        self.barra_ejecucion.move(
            x,
            y,
        )

    # ========================================================
    # MOSTRAR BARRA DE EJECUCIÓN
    # ========================================================

    def mostrar_barra_ejecucion(
        self,
    ):
        self.crear_barra_ejecucion()

        if self.barra_ejecucion is None:
            return

        self.label_barra_ejecucion.setText("● BIN ejecutando tarea")

        self.boton_pausa_barra_ejecucion.setText("PAUSAR EJECUCIÓN DE TAREAS")

        self.posicionar_barra_ejecucion()

        self.barra_ejecucion.show()

        self.barra_ejecucion.raise_()

    # ========================================================
    # MOSTRAR ESTADO PAUSADO
    # ========================================================

    def mostrar_barra_ejecucion_pausada(
        self,
    ):
        self.crear_barra_ejecucion()

        if self.barra_ejecucion is None:
            return

        self.label_barra_ejecucion.setText("● Ejecución pausada")

        self.boton_pausa_barra_ejecucion.setText("CONTINUAR EJECUCIÓN")

        self.posicionar_barra_ejecucion()

        self.barra_ejecucion.show()

        self.barra_ejecucion.raise_()


    # ========================================================
    # MOSTRAR IA CORRIGIENDO LA TRAYECTORIA
    # ========================================================

    def mostrar_barra_ejecucion_ia(
        self,
        detalle="",
    ):
        self.crear_barra_ejecucion()

        if self.barra_ejecucion is None:
            return

        texto = "● IA ajustando trayectoria"

        detalle = str(
            detalle
            or ""
        ).strip()

        if len(detalle) > 70:
            detalle = (
                detalle[:67]
                + "..."
            )

        if detalle:
            texto += f" · {detalle}"

        self.label_barra_ejecucion.setText(
            texto
        )

        # Aunque Qwen tenga el control temporal,
        # el usuario siempre conserva PAUSAR.
        self.boton_pausa_barra_ejecucion.setText(
            "PAUSAR EJECUCIÓN DE TAREAS"
        )

        self.posicionar_barra_ejecucion()

        self.barra_ejecucion.show()
        self.barra_ejecucion.raise_()

    # ========================================================
    # OCULTAR BARRA DE EJECUCIÓN
    # ========================================================

    def ocultar_barra_ejecucion(
        self,
    ):
        if self.barra_ejecucion is not None:
            self.barra_ejecucion.hide()

    # ========================================================
    # PAUSAR / CONTINUAR DESDE BARRA FLOTANTE
    # ========================================================

    def alternar_pausa_ejecucion_flotante(
        self,
    ):
        # -----------------------------------------------
        # PAUSAR EJECUCIÓN ACTUAL
        # -----------------------------------------------

        tarea = self.obtener_tarea_ejecutando()

        if tarea is not None and tarea.get("estado") == "EJECUTANDO":
            self.tarea_pausada_flotante_id = tarea.get("id")

            self.pausa_ejecucion_global = True

            self.pausar_ejecucion(tarea)

            self.mostrar_barra_ejecucion_pausada()

            QTimer.singleShot(
                50,
                self.recuperar_bin_al_frente,
            )

            return

        # -----------------------------------------------
        # CONTINUAR EJECUCIÓN PAUSADA
        # -----------------------------------------------

        if self.pausa_ejecucion_global and self.tarea_pausada_flotante_id is not None:
            tarea = self.obtener_tarea(self.tarea_pausada_flotante_id)

            if (
                tarea is None
                or tarea.get("estado") != "EN PAUSA"
                or not tarea.get("current_run_key")
            ):
                self.pausa_ejecucion_global = False
                self.tarea_pausada_flotante_id = None
                self.ocultar_barra_ejecucion()
                return

            self.pausa_ejecucion_global = False

            self.continuar_ejecucion(tarea)

            self.mostrar_barra_ejecucion()

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

            if sys.platform == "win32":

                try:

                    ctypes.windll.user32.SetWindowPos(
                        int(self.winId()),
                        HWND_NOTOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                    )

                except Exception:
                    pass

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

    # ========================================================
    # PERMITIR BIN EN CAPTURAS DE WINDOWS
    # ========================================================

    def permitir_bin_en_capturas(self):

        if sys.platform != "win32":
            return False

        try:

            hwnd = int(self.winId())

            resultado = ctypes.windll.user32.SetWindowDisplayAffinity(
                hwnd,
                WDA_NONE,
            )

            if resultado:

                self.bin_excluido_de_captura = False

                if hasattr(
                    self,
                    "mensaje_chat",
                ):

                    self.mensaje_chat.setText(
                        "BIN: Mi interfaz puede mostrarse "
                        "en capturas y transmisiones."
                    )

                return True

            if hasattr(
                self,
                "mensaje_chat",
            ):

                self.mensaje_chat.setText(
                    "BIN: Windows no pudo modificar " "la configuración de captura."
                )

            return False

        except Exception as error:

            if hasattr(
                self,
                "mensaje_chat",
            ):

                self.mensaje_chat.setText(
                    "BIN: No pude configurar la "
                    "visibilidad en capturas.\n\n"
                    f"{error}"
                )

            return False

    # ========================================================
    # OBTENER GEOMETRÍA DEL MONITOR CAPTURADO
    # ========================================================

    def actualizar_geometria_monitor_captura(
        self,
    ):

        if mss is None:
            return False

        try:

            with mss.MSS() as capturador:

                monitores = capturador.monitors

                if len(monitores) <= 1:

                    self.geometria_monitor_captura = None

                    self.geometrias_monitores_captura = []

                    return False

                geometrias = []

                for indice in range(
                    1,
                    len(monitores),
                ):

                    monitor = monitores[indice]

                    geometrias.append(
                        {
                            "indice": indice,
                            "left": int(monitor["left"]),
                            "top": int(monitor["top"]),
                            "width": int(monitor["width"]),
                            "height": int(monitor["height"]),
                        }
                    )

                self.geometrias_monitores_captura = geometrias

                indice = int(self.monitor_captura or 1)

                if indice <= 0 or indice >= len(monitores):
                    indice = 1

                self.monitor_captura = indice

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

            self.geometrias_monitores_captura = []

            self.actualizar_chat_bin(
                "No pude obtener la geometría " "de los monitores.\n\n" f"{error}"
            )

            return False

    def cambiar_monitor_captura(
        self,
        monitor_index,
    ):

        try:

            monitor_index = int(monitor_index)

        except Exception:
            return False

        if monitor_index < 1:
            return False

        if not self.geometrias_monitores_captura:

            self.actualizar_geometria_monitor_captura()

        geometria = None

        for item in self.geometrias_monitores_captura:

            if (
                int(
                    item.get(
                        "indice",
                        0,
                    )
                )
                == monitor_index
            ):

                geometria = item
                break

        if geometria is None:
            return False

        cambio = self.monitor_captura != monitor_index

        self.monitor_captura = monitor_index

        self.geometria_monitor_captura = {
            "left": geometria["left"],
            "top": geometria["top"],
            "width": geometria["width"],
            "height": geometria["height"],
        }

        if self.hilo_captura and self.hilo_captura.isRunning():

            self.hilo_captura.cambiar_monitor(monitor_index)

        return cambio

    def actualizar_monitor_captura_segun_ventana_activa(
        self,
    ):

        if sys.platform != "win32":
            return self.monitor_captura

        try:

            user32 = ctypes.windll.user32

            hwnd = user32.GetForegroundWindow()

            if not hwnd:
                return self.monitor_captura

            # Cuando BIN vuelve al frente,
            # conservamos el último monitor externo.
            if int(hwnd) == int(self.winId()):
                return self.monitor_captura

            rect = wintypes.RECT()

            if not user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect),
            ):
                return self.monitor_captura

            if rect.right <= rect.left or rect.bottom <= rect.top:
                return self.monitor_captura

            if not self.geometrias_monitores_captura:

                if not self.actualizar_geometria_monitor_captura():
                    return self.monitor_captura

            mejor_monitor = None
            mejor_area = 0

            for monitor in self.geometrias_monitores_captura:

                izquierda = max(
                    rect.left,
                    monitor["left"],
                )

                arriba = max(
                    rect.top,
                    monitor["top"],
                )

                derecha = min(
                    rect.right,
                    monitor["left"] + monitor["width"],
                )

                abajo = min(
                    rect.bottom,
                    monitor["top"] + monitor["height"],
                )

                ancho = max(
                    0,
                    derecha - izquierda,
                )

                alto = max(
                    0,
                    abajo - arriba,
                )

                area = ancho * alto

                if area > mejor_area:

                    mejor_area = area

                    mejor_monitor = int(monitor["indice"])

            if mejor_monitor is None:

                centro_x = (rect.left + rect.right) // 2

                centro_y = (rect.top + rect.bottom) // 2

                for monitor in self.geometrias_monitores_captura:

                    if monitor["left"] <= centro_x < (
                        monitor["left"] + monitor["width"]
                    ) and monitor["top"] <= centro_y < (
                        monitor["top"] + monitor["height"]
                    ):

                        mejor_monitor = int(monitor["indice"])

                        break

            if mejor_monitor is not None:

                self.cambiar_monitor_captura(mejor_monitor)

            return self.monitor_captura

        except Exception:

            return self.monitor_captura

    # ========================================================
    # CAPTURA FRESCA PARA QWEN
    # ========================================================

    def capturar_frame_fresco_ia(
        self,
    ):
        """
        Obtiene una captura física del monitor en este instante.

        No depende de self.frame_actual porque ese frame puede
        estar congelado mientras BIN es la ventana foreground.
        """

        if mss is None:
            return None

        try:
            # Mantener el monitor externo que BIN ya venía
            # observando. Si otra aplicación está foreground,
            # esta función actualizará el monitor normalmente.
            self.actualizar_monitor_captura_segun_ventana_activa()

            if not self.geometrias_monitores_captura:
                self.actualizar_geometria_monitor_captura()

            indice = int(
                self.monitor_captura
                or 1
            )

            with mss.MSS() as capturador:
                monitores = capturador.monitors

                if len(monitores) <= 1:
                    return None

                if (
                    indice <= 0
                    or indice >= len(monitores)
                ):
                    indice = 1

                monitor = monitores[
                    indice
                ]

                captura = capturador.grab(
                    monitor
                )

                imagen = QImage(
                    captura.rgb,
                    captura.width,
                    captura.height,
                    captura.width * 3,
                    QImage.Format_RGB888,
                ).copy()

            if imagen.isNull():
                return None

            # Actualizamos también la geometría usada para
            # convertir las coordenadas normalizadas de Qwen.
            self.monitor_captura = indice

            self.geometria_monitor_captura = {
                "left": int(
                    monitor["left"]
                ),
                "top": int(
                    monitor["top"]
                ),
                "width": int(
                    monitor["width"]
                ),
                "height": int(
                    monitor["height"]
                ),
            }

            # Esta pasa a ser la fotografía realmente reciente.
            self.frame_actual = (
                imagen.copy()
            )

            # =================================================
            # EL VISOR DEBE MOSTRAR EXACTAMENTE
            # LA MISMA CAPTURA QUE RECIBIRÁ QWEN
            # =================================================

            self.mostrar_frame_en_visor(
                self.frame_actual
            )

            QApplication.processEvents()

            self.actualizar_estado_cabecera_visor(
                "Captura actualizada",
                datetime.now().strftime(
                    "%H:%M:%S"
                ),
                AZUL,
            )

            print(
                "[BIN IA] Captura fresca · "
                f"monitor={indice} · "
                f"{imagen.width()}x"
                f"{imagen.height()} · "
                "Visor actualizado"
            )

            return (
                self.frame_actual.copy()
            )

        except Exception as error:
            print(
                "[BIN IA] Error en captura fresca:",
                error,
            )

            return None

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
    # MOSTRAR UN FRAME EN EL VISOR IA
    # ========================================================

    def mostrar_frame_en_visor(
        self,
        imagen,
    ):
        """
        Muestra en el Visor IA exactamente el frame recibido.

        Esta función NO captura nada.
        Solamente sincroniza la imagen visible del visor
        con el frame que BIN acaba de aceptar o capturar.
        """

        if imagen is None:
            return False

        try:
            if imagen.isNull():
                return False
        except Exception:
            return False

        if not hasattr(
            self,
            "visor_imagen",
        ):
            return False

        ancho = (
            self.visor_imagen.width()
        )

        alto = (
            self.visor_imagen.height()
        )

        if (
            ancho <= 1
            or alto <= 1
        ):
            return False

        pixmap = QPixmap.fromImage(
            imagen
        )

        pixmap_escalado = pixmap.scaled(
            ancho,
            alto,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.visor_imagen.setPixmap(
            pixmap_escalado
        )

        return True

    # ========================================================
    # RECIBIR FRAME DEL ESCRITORIO
    # ========================================================

    def recibir_frame_pantalla(
        self,
        imagen,
    ):

        if imagen.isNull():
            return

        self.actualizar_monitor_captura_segun_ventana_activa()

        # ====================================================
        # EVITAR EFECTO ESPEJO DE BIN
        # ====================================================

        if sys.platform == "win32":

            try:

                hwnd_bin = int(
                    self.winId()
                )

                hwnd_foreground = (
                    ctypes.windll.user32
                    .GetForegroundWindow()
                )

                # Mientras BIN está foreground,
                # el hilo normal no reemplaza continuamente
                # la imagen para evitar el efecto espejo.
                #
                # Las capturas solicitadas explícitamente
                # por Qwen SÍ podrán actualizar el visor
                # mediante capturar_frame_fresco_ia().
                if (
                    hwnd_foreground
                    == hwnd_bin
                ):
                    return

            except Exception:
                pass

        # ====================================================
        # FRAME EXTERNO VÁLIDO
        # ====================================================

        self.frame_actual = (
            imagen.copy()
        )

        self.mostrar_frame_en_visor(
            self.frame_actual
        )
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
        self.ocultar_barra_ejecucion()

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

                # No convertimos una tarea en cola en una pausa
                # permanente. Al abrir BIN nuevamente, el scheduler
                # comprobará si esa ejecución quedó retrasada y
                # volverá a pedir una decisión al usuario.
                item["estado"] = "EN ESPERA"

                item["current_run_key"] = None

                item["queued_at"] = None

                item["runtime_started_at"] = None

                item["detalle_estado"] = (
                    "Pendiente de reevaluar programación al iniciar BIN"
                )

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

            QLabel#logoImagen {{

                background:
                    transparent;

                padding:
                    0px;

            }}

            QLabel#logoNombre {{

                color:
                    #b7bdc8;

                font-size:
                    11px;

                font-weight:
                    700;

                letter-spacing:
                    1px;

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

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "BIN.IA.Asistem.v1.6"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    bin_app = BIN()

    bin_app.show()

    sys.exit(app.exec())
