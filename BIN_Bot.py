# -*- coding: utf-8 -*-

"""
BIN_Bot.py
============================================================

ChatBOT ligero para BIN Light.

NO UTILIZA:
- Qwen.
- IA local pesada.
- Flask.
- Servidor local.
- APIs de inteligencia artificial.

FUNCIONES:
- Conversación básica natural.
- Bancos de 25 a 50 variantes.
- Presentación de BIN.
- Saludos.
- Despedidas.
- Agradecimientos.
- Confirmaciones.
- Preguntas básicas.
- Consulta del manual real de BIN.
- El manual es la única fuente técnica del software.
- Índice automático del manual.
- Confianza 0-100.
- Umbral local: 82 %.
- Matemáticas seguras.
- Porcentajes.
- Potencias.
- Raíz cuadrada.
- Promedios.
- Regla de tres simple.
- Detección de Internet.
- Google como respaldo sin API.
- Banco natural para respuestas externas.
- Banco natural para falta de Internet.
- Modo DEBUG.
- Uso independiente desde CMD.
- Uso como módulo desde BIN Light.
- Reconocimiento preliminar de archivos de aprendizaje JSON.

USO CMD:

    python BIN_Bot.py

DEBUG:

    python BIN_Bot.py --debug

SELF TEST:

    python BIN_Bot.py --selftest

USO DESDE BIN LIGHT:

    from BIN_Bot import BINBot

    self.bin_bot = BINBot(
        manual_texto=MANUAL_BIN_LIGHT
    )

    self.conectar_ia_bot(
        self.bin_bot
    )

El método público principal es:

    responder(texto, contexto)

============================================================
"""

import argparse
import ast
import html
import json
import math
import operator
import os
import random
import re
import socket
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import webbrowser

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

from datetime import datetime, timezone


try:

    from selenium import webdriver

    from selenium.webdriver.support.ui import WebDriverWait

    SELENIUM_DISPONIBLE = True


except Exception:

    webdriver = None

    WebDriverWait = None

    SELENIUM_DISPONIBLE = False


# ============================================================
# VERSIÓN
# ============================================================

BIN_BOT_VERSION = "2.0.1"

BIN_LIGHT_COMPATIBLE = "1.6.18"

UMBRAL_LOCAL_DEFECTO = 82.0


# ============================================================
# ORÍGENES DE RESPUESTA
# ============================================================

ORIGEN_CONVERSACION = "CONVERSACION"

ORIGEN_MATEMATICA = "MATEMATICA"

ORIGEN_MANUAL = "MANUAL"

ORIGEN_GOOGLE = "GOOGLE"

ORIGEN_MEMORIA = "MEMORIA"

ORIGEN_SIN_INTERNET = "SIN_INTERNET"

ORIGEN_ERROR = "ERROR"

ORIGEN_ARCHIVO = "ARCHIVO_APRENDIZAJE"


# ============================================================
# ARCHIVOS DE APRENDIZAJE
# ============================================================

TIPO_APRENDIZAJE = "BIN_APRENDIZAJE"

SCHEMA_APRENDIZAJE_SOPORTADO = 1


# ============================================================
# CONFIGURACIÓN
# ============================================================

@dataclass
class BINBotConfig:

    umbral_local: float = UMBRAL_LOCAL_DEFECTO

    idioma: str = "ES"

    debug: bool = False

    random_seed: object = None

    permitir_google: bool = True

    network_timeout: float = 2.5

    google_timeout: float = 6.0

    google_hl: str = "es"

    google_max_chars: int = 1300

    google_render_timeout: float = 12.0

    google_debug_html_path: str = "data/BIN_Google_Debug.html"

    google_headless: bool = False

    google_captcha_timeout: float = 180.0

    google_profile_dir: str = "data/BIN_Google_Profile"

    memoria_path: str = "data/memoria.json"

    memoria_umbral: float = 82.0

    # ========================================================
    # MANUAL OFICIAL DE BIN
    # ========================================================

    manual_json_path: str = "data/manual_bin_bot.json"

    comandos_teclado_path: str = "data/comandos_teclado.json"

    google_aceptar_fragmento_resultado: bool = True

    abrir_google_en_navegador_si_falla: bool = False

    manual_max_chars: int = 1100

    manual_max_sentences: int = 5

    math_max_abs_value: float = 1e100

    math_max_power: float = 1000.0

    math_max_expression_length: int = 180

    max_workers: int = 2

    internet_test_urls: tuple = (
        "https://www.google.com/generate_204",
        "https://www.gstatic.com/generate_204",
        "https://www.google.com/",
    )


# ============================================================
# RESULTADO ESTÁNDAR
# ============================================================

@dataclass
class BINBotResponse:

    texto: str

    confianza: float

    origen: str

    intencion: str = ""

    detalle: str = ""

    metadata: dict = field(
        default_factory=dict
    )

    def as_dict(
        self,
    ):

        return {

            "texto": (
                self.texto
            ),

            "respuesta": (
                self.texto
            ),

            "confianza": round(
                float(
                    self.confianza
                ),
                2,
            ),

            "origen": (
                self.origen
            ),

            "intencion": (
                self.intencion
            ),

            "detalle": (
                self.detalle
            ),

            "metadata": dict(
                self.metadata
                or {}
            ),
        }


# ============================================================
# NORMALIZACIÓN
# ============================================================

STOPWORDS = {

    "a",
    "al",
    "algo",
    "ante",
    "como",
    "con",
    "cual",
    "cuando",
    "de",
    "del",
    "desde",
    "donde",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "es",
    "esa",
    "ese",
    "eso",
    "esta",
    "este",
    "esto",
    "ha",
    "hace",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "para",
    "pero",
    "por",
    "porque",
    "que",
    "se",
    "si",
    "sin",
    "su",
    "sus",
    "te",
    "tu",
    "tus",
    "un",
    "una",
    "uno",
    "unos",
    "unas",
    "y",
    "ya",
    "yo",
    "puedo",
    "puede",
    "podria",
    "quiero",
    "quisiera",
    "necesito",
    "favor",

}


def quitar_tildes(
    texto,
):

    texto = unicodedata.normalize(
        "NFKD",
        str(
            texto
            or ""
        ),
    )

    return "".join(

        caracter

        for caracter in texto

        if not unicodedata.combining(
            caracter
        )
    )


def normalizar_texto(
    texto,
):

    texto = quitar_tildes(
        texto
    ).lower()

    texto = texto.replace(
        "¿",
        " ",
    )

    texto = texto.replace(
        "?",
        " ",
    )

    texto = texto.replace(
        "¡",
        " ",
    )

    texto = texto.replace(
        "!",
        " ",
    )

    texto = re.sub(
        r"[^a-z0-9ñ%+\-*/^().,:=\s]",
        " ",
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


# ============================================================
# GRUPOS SEMÁNTICOS LIGEROS
# ============================================================

CANONICAL_GROUPS = {

    "crear": {

        "crear",
        "crea",
        "creo",
        "creando",

        "hacer",
        "hago",

        "nueva",
        "nuevo",

        "agregar",
        "anadir",
        "añadir",
        "generar",

        "empezar",
        "empiezo",
        "empieza",
        "empezando",

        "comenzar",
        "comienzo",
        "comienza",
        "comenzando",

        "iniciar",
        "inicio",
        "inicia",
        "iniciando",
    },

    "tarea": {

        "tarea",
        "tareas",
        "rutina",
        "rutinas",
        "automatizacion",
        "automatizaciones",
        "automatizar",
    },

    "demostracion": {

        "demostracion",
        "demostrar",
        "mostrar",
        "grabacion",
        "grabar",
        "entrenamiento",
        "aprendizaje",
    },

    "ventana": {

        "ventana",
        "ventanas",
        "posicion",
        "tamano",
        "geometria",
    },

    "navegador": {

        "navegador",
        "navegadores",
        "chrome",
        "edge",
        "brave",
        "opera",
        "firefox",
        "web",
        "pagina",
        "sitio",
    },

    "cuenta": {

        "cuenta",
        "cuentas",
        "perfil",
        "perfiles",
        "correo",
        "email",
        "gmail",
    },

    "credencial": {

        "password",
        "contrasena",
        "clave",
        "pin",
        "token",
        "credencial",
        "credenciales",
        "passkey",
        "2fa",
        "autenticacion",
    },

    "accion": {

        "accion",
        "acciones",
        "paso",
        "pasos",
        "comando",
        "comandos",
    },

    "texto": {

        "texto",
        "escribir",
        "escritura",
        "teclear",
        "pegar",
    },

    "teclado": {

        "teclado",
        "tecla",
        "teclas",
        "atajo",
        "atajos",
    },

    "click": {

        "click",
        "clic",
        "clics",
        "raton",
        "mouse",
    },

    "configuracion": {

        "configuracion",
        "ajustes",
        "setting",
        "settings",
    },

    "manual": {

        "manual",
        "guia",
        "documentacion",
        "instrucciones",
    },

    "error": {

        "error",
        "errores",
        "fallo",
        "falla",
        "problema",
        "problemas",
    },

    "ejecucion": {

        "ejecucion",
        "ejecutar",
        "ejecuta",
        "correr",
        "run",
    },

    "pausa": {

        "pausa",
        "pausar",
        "detener",
        "parar",
        "stop",
    },

    "reset": {

        "reset",
        "resetear",
        "reiniciar",
        "restablecer",
    },

    "programacion": {

        "horario",
        "horarios",
        "programar",
        "programacion",
        "hora",
        "dias",
        "repeticion",
        "repeticiones",
    },

}


CANONICAL_LOOKUP = {}


for canon, palabras in (
    CANONICAL_GROUPS.items()
):

    for palabra in palabras:

        CANONICAL_LOOKUP[
            normalizar_texto(
                palabra
            )
        ] = canon


def canonicalizar_token(
    token,
):

    token = normalizar_texto(
        token
    )

    if token in CANONICAL_LOOKUP:

        return CANONICAL_LOOKUP[
            token
        ]

    original = token

    sufijos = (

        "amientos",
        "imientos",
        "aciones",
        "adores",
        "adoras",
        "amiento",
        "imiento",
        "acion",
        "idades",
        "mente",
        "ando",
        "iendo",
        "ados",
        "adas",
        "idos",
        "idas",
        "es",
        "os",
        "as",
        "s",
    )

    for sufijo in sufijos:

        if (
            len(
                token
            )
            > len(
                sufijo
            )
            + 3
            and token.endswith(
                sufijo
            )
        ):

            token = token[
                :-len(
                    sufijo
                )
            ]

            break

    return CANONICAL_LOOKUP.get(
        token,
        CANONICAL_LOOKUP.get(
            original,
            token,
        ),
    )


def tokenizar(
    texto,
    quitar_stopwords=True,
):

    normal = normalizar_texto(
        texto
    )

    tokens = re.findall(
        r"[a-z0-9ñ]+",
        normal,
    )

    salida = []

    for token in tokens:

        if (
            quitar_stopwords
            and token in STOPWORDS
        ):

            continue

        token = canonicalizar_token(
            token
        )

        if (
            quitar_stopwords
            and token in STOPWORDS
        ):

            continue

        if (
            len(
                token
            )
            <= 1
            and not token.isdigit()
        ):

            continue

        salida.append(
            token
        )

    return salida


def fuzzy_token_match(
    a,
    b,
):

    if a == b:

        return True

    if (
        len(
            a
        )
        >= 4
        and len(
            b
        )
        >= 4
    ):

        if (
            a.startswith(
                b
            )
            or b.startswith(
                a
            )
        ):

            return True

        return (
            SequenceMatcher(
                None,
                a,
                b,
            ).ratio()
            >= 0.82
        )

    return False


def cobertura_tokens(
    query_tokens,
    target_tokens,
    weights=None,
):

    if not query_tokens:

        return 0.0

    target_unique = list(
        dict.fromkeys(
            target_tokens
        )
    )

    total = 0.0

    matched = 0.0

    for query_token in query_tokens:

        peso = float(
            (
                weights
                or {}
            ).get(
                query_token,
                1.0,
            )
        )

        total += peso

        encontrado = any(

            fuzzy_token_match(
                query_token,
                target_token,
            )

            for target_token in target_unique
        )

        if encontrado:

            matched += peso

    if total <= 0:

        return 0.0

    return matched / total


def limitar_texto(
    texto,
    max_chars,
):

    texto = re.sub(
        r"[ \t]+",
        " ",
        str(
            texto
            or ""
        ),
    ).strip()

    if len(
        texto
    ) <= max_chars:

        return texto

    corte = texto[
        :max_chars
    ].rstrip()

    ultimo = max(

        corte.rfind(
            ". "
        ),

        corte.rfind(
            "! "
        ),

        corte.rfind(
            "? "
        ),
    )

    if ultimo >= int(
        max_chars
        * 0.62
    ):

        corte = corte[
            :ultimo
            + 1
        ]

    return (
        corte.rstrip()
        + "…"
    )


# ============================================================
# CREAR BANCOS GRANDES
# ============================================================

def combinar_respuestas(
    inicios,
    finales,
    limite=40,
):

    resultado = []

    for inicio in inicios:

        for final in finales:

            texto = (
                inicio
                + " "
                + final
            ).strip()

            if texto not in resultado:

                resultado.append(
                    texto
                )

            if len(
                resultado
            ) >= limite:

                return resultado

    return resultado


class BancosBIN:

    # ========================================================
    # SALUDOS — 40
    # ========================================================

    SALUDOS = combinar_respuestas(

        [

            "Hola.",
            "¡Hola!",
            "Buenas.",
            "Qué gusto leerte.",
            "Hola, estoy aquí.",
            "Buenas, aquí estoy.",
            "Hola. Todo listo por aquí.",
            "¡Buenas!",
        ],

        [

            "¿En qué puedo ayudarte?",
            "¿Qué necesitas?",
            "¿Qué quieres consultar?",
            "¿Qué hacemos?",
            "Dime, ¿en qué te ayudo?",
        ],

        40,
    )


    # ========================================================
    # DESPEDIDAS — 30
    # ========================================================

    DESPEDIDAS = combinar_respuestas(

        [

            "Nos vemos.",
            "Hasta luego.",
            "Perfecto, hablamos luego.",
            "De acuerdo, nos vemos.",
            "Hasta la próxima.",
            "Que estés bien.",
        ],

        [

            "Aquí estaré cuando me necesites.",
            "Cuando quieras continuamos.",
            "Puedes volver cuando quieras.",
            "Seguimos cuando te haga falta.",
            "Que tengas un buen día.",
        ],

        30,
    )


    # ========================================================
    # AGRADECIMIENTOS — 30
    # ========================================================

    AGRADECIMIENTOS = combinar_respuestas(

        [

            "Con gusto.",
            "Claro.",
            "Para eso estoy.",
            "Un placer.",
            "Encantado de ayudarte.",
            "No hay problema.",
        ],

        [

            "Si necesitas algo más, dime.",
            "Podemos seguir cuando quieras.",
            "¿Hay algo más que quieras revisar?",
            "Aquí sigo por si necesitas otra cosa.",
            "Cuando quieras continuamos.",
        ],

        30,
    )


    # ========================================================
    # ESTADO — 30
    # ========================================================

    ESTADO = combinar_respuestas(

        [

            "Estoy listo.",
            "Todo bien por aquí.",
            "Estoy funcionando con normalidad.",
            "Estoy disponible.",
            "Aquí estoy, preparado.",
            "Todo en orden.",
        ],

        [

            "¿Qué quieres hacer?",
            "¿En qué puedo ayudarte?",
            "¿Qué revisamos?",
            "Dime qué necesitas.",
            "¿Qué consulta tienes?",
        ],

        30,
    )


    # ========================================================
    # PRESENTACIÓN — 25
    # ========================================================

    PRESENTACION = combinar_respuestas(

        [

            "Soy BIN, el asistente ligero integrado en BIN Light.",
            "Me llamo BIN y soy el asistente local de BIN Light.",
            "Soy BIN, el ChatBOT ligero que acompaña a BIN Light.",
            "Puedes llamarme BIN. Soy el asistente conversacional de BIN Light.",
            "Soy BIN. Estoy integrado en BIN Light como asistente local.",
        ],

        [

            (
                "Puedo orientarte sobre el software, resolver cálculos "
                "y buscar información cuando mi conocimiento local "
                "no sea suficiente."
            ),

            (
                "Puedo ayudarte con consultas sobre BIN, operaciones "
                "matemáticas y búsquedas externas cuando sea necesario."
            ),

            (
                "Mi trabajo es ayudarte a usar BIN y resolver consultas "
                "ligeras sin cargar un modelo de IA pesado."
            ),

            (
                "Trabajo de forma ligera: conversación local, manual de "
                "BIN, matemáticas y respaldo web cuando hace falta."
            ),

            (
                "Estoy diseñado para ser útil sin añadir el consumo de "
                "un modelo local pesado."
            ),
        ],

        25,
    )


    # ========================================================
    # CAPACIDADES — 25
    # ========================================================

    CAPACIDADES = combinar_respuestas(

        [

            "Puedo ayudarte de varias formas.",
            "Dentro de BIN Light tengo varias funciones útiles.",
            "Sí, puedo ayudarte con distintas consultas.",
            "Mi función es acompañarte dentro de BIN Light.",
            "Puedo servirte como asistente ligero.",
        ],

        [

            (
                "Puedo responder preguntas sobre BIN usando su manual, "
                "resolver operaciones matemáticas y buscar información "
                "en Google cuando no tenga suficiente certeza."
            ),

            (
                "Puedo conversar contigo, consultar el manual de BIN, "
                "hacer cálculos y usar Google como respaldo si una "
                "respuesta local no alcanza suficiente confianza."
            ),

            (
                "Puedo orientarte con el uso de BIN, resolver matemáticas "
                "y buscar fuera cuando la respuesta no esté suficientemente "
                "respaldada por el manual."
            ),

            (
                "Puedo atender consultas básicas, ayudarte con el software, "
                "calcular y recurrir a Google cuando haga falta."
            ),

            (
                "Puedo responder sobre BIN desde su propia documentación, "
                "hacer cálculos locales y buscar información adicional "
                "si estoy conectado."
            ),
        ],

        25,
    )


    # ========================================================
    # CONFIRMACIONES — 30
    # ========================================================

    CONFIRMACIONES = combinar_respuestas(

        [

            "Perfecto.",
            "De acuerdo.",
            "Entendido.",
            "Claro.",
            "Bien.",
            "Listo.",
        ],

        [

            "¿Qué hacemos ahora?",
            "Dime qué necesitas.",
            "Podemos continuar.",
            "¿Qué quieres revisar?",
            "Te sigo.",
        ],

        30,
    )


    # ========================================================
    # COMENTARIOS POSITIVOS — 30
    # ========================================================

    COMENTARIOS_POSITIVOS = combinar_respuestas(

        [

            "Me alegra saberlo.",
            "Qué bueno.",
            "Excelente.",
            "Me alegra que esté funcionando.",
            "Perfecto.",
            "Eso suena bien.",
        ],

        [

            "Podemos seguir probando.",
            "Seguimos cuando quieras.",
            "¿Qué quieres revisar ahora?",
            "Puedes continuar con otra consulta.",
            "Aquí sigo.",
        ],

        30,
    )


    # ========================================================
    # INTRODUCCIONES DEL MANUAL — 40
    # ========================================================

    MANUAL_INTROS = combinar_respuestas(

        [

            "Sí. En BIN funciona así:",
            "Claro. BIN lo contempla de esta manera:",
            "Encontré la parte del manual que corresponde a tu consulta:",
            "Esto es lo que BIN establece para ese caso:",
            "La documentación de BIN indica lo siguiente:",
            "Revisé el manual local y esto es lo relevante:",
            "Para ese punto, BIN especifica esto:",
            "Según la documentación actual de BIN:",
        ],

        [

            "",
            "Te resumo la parte más relacionada.",
            "Esta es la información más cercana a lo que preguntas.",
            "Voy directamente a lo importante.",
            "Esto es lo que aplica.",
        ],

        40,
    )


    # ========================================================
    # CIERRES DEL MANUAL — 25
    # ========================================================

    MANUAL_CIERRES = combinar_respuestas(

        [

            "Si quieres,",
            "Si te sirve,",
            "Si necesitas más detalle,",
            "También puedo",
            "Cuando quieras,",
        ],

        [

            "puedo buscar otra parte del manual.",
            "puedo revisar una sección más específica.",
            "podemos afinar la pregunta.",
            "puedo intentar localizar el paso exacto.",
            "puedo seguir con otra consulta sobre BIN.",
        ],

        25,
    )


    # ========================================================
    # GOOGLE — 40
    # ========================================================

    WEB_INTROS = combinar_respuestas(

        [

            "Encontré información que puede ayudarte:",
            "Revisé información adicional y encontré esto:",
            "Busqué un poco más y esto parece responder a tu consulta:",
            "No tenía suficiente certeza local, así que investigué:",
            "Encontré una explicación que encaja con tu pregunta:",
            "Consulté información adicional y esto es lo más relevante:",
            "Estuve revisando y encontré lo siguiente:",
            "Encontré una respuesta útil para tu consulta:",
        ],

        [

            "",
            "Te dejo lo principal.",
            "Esto es lo más directo que encontré.",
            "Voy con la parte útil.",
            "Esto parece ser lo más relevante.",
        ],

        40,
    )


    # ========================================================
    # CIERRES GOOGLE — 25
    # ========================================================

    WEB_CIERRES = combinar_respuestas(

        [

            "Si quieres,",
            "Si te interesa,",
            "También puedo",
            "Si necesitas,",
            "Cuando quieras,",
        ],

        [

            "puedo ayudarte a formular otra búsqueda.",
            "podemos profundizar en esa respuesta.",
            "puedo intentar buscarlo de otra manera.",
            "puedo revisar una variante de la consulta.",
            "podemos continuar desde ahí.",
        ],

        25,
    )

    # ========================================================
    # MEMORIA LOCAL — 30
    # ========================================================

    MEMORIA_INTROS = combinar_respuestas(

        [

            "Tengo información guardada sobre eso:",
            "Ya había aprendido algo relacionado con esa consulta:",
            "Encontré una respuesta en mi memoria local:",
            "Tengo una respuesta guardada que puede ayudarte:",
            "Ya había encontrado información sobre este tema:",
            "Puedo responderte con información que guardé anteriormente:",
        ],

        [

            "",
            "Esto es lo que tengo registrado.",
            "Te comparto lo que había guardado.",
            "Esta es la información que recuerdo.",
            "Esto es lo que encontré anteriormente.",
        ],

        30,
    )

    # ========================================================
    # SIN INTERNET — 40
    # ========================================================

    SIN_INTERNET = combinar_respuestas(

        [

            (
                "No tengo una respuesta suficientemente segura "
                "en mi conocimiento local."
            ),

            (
                "Esta vez no encontré una respuesta local "
                "con suficiente confianza."
            ),

            "No quiero darte una respuesta dudosa.",

            (
                "No encontré información suficiente para "
                "responderte con seguridad."
            ),

            (
                "Mi conocimiento local no alcanza para "
                "responder eso con confianza."
            ),

            (
                "No tengo esa respuesta suficientemente "
                "respaldada ahora mismo."
            ),

            (
                "No pude confirmar una respuesta fiable "
                "con lo que tengo localmente."
            ),

            (
                "No encontré una coincidencia suficientemente "
                "clara en mi información local."
            ),
        ],

        [

            (
                "Si me conectas a Internet, "
                "puedo intentar buscarla."
            ),

            (
                "Con conexión a Internet "
                "puedo investigarla por ti."
            ),

            (
                "Cuando haya conexión, "
                "puedo ayudarte a buscarla."
            ),

            (
                "Si recuperas la conexión, "
                "puedo consultar información adicional."
            ),

            (
                "Con Internet disponible puedo "
                "intentar encontrar una respuesta."
            ),
        ],

        40,
    )


    # ========================================================
    # GOOGLE SIN RESPUESTA CLARA — 30
    # ========================================================

    WEB_SIN_RESPUESTA = combinar_respuestas(

        [

            (
                "Tengo conexión, pero no pude obtener una "
                "respuesta automática suficientemente clara de Google."
            ),

            (
                "Pude consultar Google, aunque esta vez no encontré "
                "un bloque de respuesta suficientemente útil."
            ),

            (
                "La búsqueda se realizó, pero no pude extraer "
                "una respuesta automática confiable."
            ),

            (
                "Google respondió, pero no encontré una respuesta "
                "automática que pueda presentarte con suficiente claridad."
            ),

            (
                "La consulta externa funcionó, aunque no pude "
                "aislar una respuesta clara."
            ),

            (
                "Encontré resultados, pero no una respuesta "
                "automática suficientemente limpia."
            ),
        ],

        [

            "Puedes reformular la pregunta y lo intento de nuevo.",
            "Prueba con una consulta un poco más específica.",
            "Podemos intentar otra forma de preguntarlo.",
            "Dame un poco más de contexto y vuelvo a buscar.",
            "Puedo hacer otro intento con términos más precisos.",
        ],

        30,
    )


    # ========================================================
    # ERRORES — 30
    # ========================================================

    ERRORES = combinar_respuestas(

        [

            "Ocurrió un problema mientras procesaba la consulta.",
            "Algo falló al intentar responder.",
            "No pude completar esa consulta correctamente.",
            "Encontré un error durante el procesamiento.",
            "Esta consulta no terminó como esperaba.",
            "Tuve un problema interno al responder.",
        ],

        [

            "Puedes intentarlo otra vez.",
            "Si vuelve a ocurrir, podemos revisar el detalle.",
            "Prueba de nuevo en un momento.",
            "Podemos volver a intentarlo.",
            "Reformula la consulta y lo reviso.",
        ],

        30,
    )


# ============================================================
# INTENCIONES BÁSICAS
# ============================================================

INTENT_PATTERNS = {

    "saludo": [

        r"^(hola|holi|hey|ey|buenas|saludos)[\s.]*$",

        r"^buenos dias[\s.]*$",

        r"^buenas tardes[\s.]*$",

        r"^buenas noches[\s.]*$",

        r"^(hola|holi|hey|ey|buenas)[,\s.]+(que tal|como estas|como te va|como andas|todo bien)[\s.]*$",

        r"^(hola|holi|hey|ey|buenas)[,\s.]+(que hay|que cuentas)[\s.]*$",
    ],


    "despedida": [

        r"^(adios|chao|chau|bye|hasta luego|hasta pronto|nos vemos)[\s.]*$",

        r"^me voy[\s.]*$",

        r"^hablamos luego[\s.]*$",

        r"^hasta manana[\s.]*$",

        r"^me despido[\s.]*$",
    ],


    "agradecimiento": [

        r"^(gracias|muchas gracias|mil gracias|te agradezco|agradecido|agradecida)[\s.]*$",

        r"^(muchas\s+)?gracias por .+$",

        r"^te agradezco .+$",

        r"^muy amable[\s.]*$",
    ],


    "comentario_positivo": [

        r".*\bme alegro\b.*",

        r".*\bque bien\b.*",

        r".*\bgenial\b.*",

        r".*\bexcelente\b.*",

        r".*\bya funciona\b.*",

        r".*\bya funcionas\b.*",

        r".*\bfunciona correctamente\b.*",

        r".*\besta funcionando\b.*",

        r".*\bpor fin funciona\b.*",
    ],


    "estado": [

        r"^como estas[\s.]*$",

        r"^como te encuentras[\s.]*$",

        r"^como te va[\s.]*$",

        r"^como andas[\s.]*$",

        r"^todo bien[\s.]*$",

        r"^que tal estas[\s.]*$",

        r"^que tal[\s.]*$",

        r"^(bien|muy bien|todo bien)[,\s]+(y tu|y usted)[\s.]*$",

        r"^estas ahi[\s.]*$",

        r"^sigues ahi[\s.]*$",
    ],


    "presentacion": [

        r".*\bquien eres\b.*",

        r".*\bcomo te llamas\b.*",

        r".*\bcual es tu nombre\b.*",

        r".*\bque nombre tienes\b.*",

        r".*\bpresentate\b.*",

        r".*\bque eres\b.*",
    ],


    "capacidades": [

        r".*\bque puedes hacer\b.*",

        r".*\ben que puedes ayudar\b.*",

        r".*\bcomo puedes ayudar\b.*",

        r".*\bpara que sirves\b.*",

        r".*\bque funciones tienes\b.*",

        r".*\bque sabes hacer\b.*",

        r".*\bcapacidades tienes\b.*",
    ],


    "menu": [

        r"^(menu|opciones|comandos|ayuda)[\s.]*$",

        r"^/?ayuda[\s.]*$",

        r".*\blista de comandos\b.*",

        r".*\blista de opciones\b.*",

        r".*\bmuestrame los comandos\b.*",

        r".*\bmuestrame tus comandos\b.*",

        r".*\bver comandos\b.*",

        r".*\bver opciones\b.*",

        r".*\bmenu de comandos\b.*",

        r".*\bcuales son los comandos\b.*",

        r".*\bque comandos tienes\b.*",

        r".*\bque comandos manejas\b.*",

        r".*\bcomandos que manejas\b.*",

        r".*\bcomandos disponibles\b.*",
    ],


    "confirmacion": [

        r"^(si|ok|okay|vale|perfecto|listo|de acuerdo|entiendo|entendido)[\s.]*$",
    ],
}
# ============================================================
# MOTOR MATEMÁTICO
# ============================================================

class MathError(
    ValueError
):
    pass


class SafeMath:

    BIN_OPS = {

        ast.Add: operator.add,

        ast.Sub: operator.sub,

        ast.Mult: operator.mul,

        ast.Div: operator.truediv,

        ast.FloorDiv: operator.floordiv,

        ast.Mod: operator.mod,

        ast.Pow: operator.pow,
    }


    UNARY_OPS = {

        ast.UAdd: operator.pos,

        ast.USub: operator.neg,
    }


    def __init__(
        self,
        config,
    ):

        self.config = config


    def validar_valor(
        self,
        value,
    ):

        if isinstance(
            value,
            bool,
        ):

            raise MathError(
                "Valor booleano no permitido."
            )

        if not isinstance(
            value,
            (
                int,
                float,
            ),
        ):

            raise MathError(
                "Resultado no numérico."
            )

        if not math.isfinite(
            float(
                value
            )
        ):

            raise MathError(
                "Resultado no finito."
            )

        if abs(
            float(
                value
            )
        ) > self.config.math_max_abs_value:

            raise MathError(
                "Resultado fuera del límite permitido."
            )

        return value


    def evaluar_nodo(
        self,
        node,
    ):

        if isinstance(
            node,
            ast.Expression,
        ):

            return self.evaluar_nodo(
                node.body
            )

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and isinstance(
                node.value,
                (
                    int,
                    float,
                ),
            )
        ):

            return self.validar_valor(
                node.value
            )

        if (
            isinstance(
                node,
                ast.UnaryOp,
            )
            and type(
                node.op
            ) in self.UNARY_OPS
        ):

            value = self.evaluar_nodo(
                node.operand
            )

            result = self.UNARY_OPS[
                type(
                    node.op
                )
            ](
                value
            )

            return self.validar_valor(
                result
            )

        if (
            isinstance(
                node,
                ast.BinOp,
            )
            and type(
                node.op
            ) in self.BIN_OPS
        ):

            izquierda = self.evaluar_nodo(
                node.left
            )

            derecha = self.evaluar_nodo(
                node.right
            )

            if isinstance(
                node.op,
                ast.Pow,
            ):

                if abs(
                    float(
                        derecha
                    )
                ) > self.config.math_max_power:

                    raise MathError(
                        "Exponente demasiado grande."
                    )

            if isinstance(
                node.op,
                (
                    ast.Div,
                    ast.FloorDiv,
                    ast.Mod,
                ),
            ):

                if derecha == 0:

                    raise MathError(
                        "No se puede dividir entre cero."
                    )

            resultado = self.BIN_OPS[
                type(
                    node.op
                )
            ](
                izquierda,
                derecha,
            )

            return self.validar_valor(
                resultado
            )

        raise MathError(
            "La expresión contiene elementos no permitidos."
        )


    def evaluar(
        self,
        expression,
    ):

        expression = str(
            expression
            or ""
        ).strip()

        if not expression:

            raise MathError(
                "Expresión vacía."
            )

        if len(
            expression
        ) > self.config.math_max_expression_length:

            raise MathError(
                "Expresión demasiado larga."
            )

        try:

            tree = ast.parse(
                expression,
                mode="eval",
            )

        except SyntaxError as error:

            raise MathError(
                "Expresión matemática inválida."
            ) from error

        return self.evaluar_nodo(
            tree
        )


    @staticmethod
    def formatear(
        value,
    ):

        if isinstance(
            value,
            int,
        ):

            return str(
                value
            )

        value = float(
            value
        )

        if value.is_integer():

            return str(
                int(
                    value
                )
            )

        return f"{value:.12g}"


    def limpiar_expresion(
        self,
        texto,
    ):

        texto = normalizar_texto(
            texto
        )

        prefijos = [

            "cuanto es ",

            "cuanto da ",

            "calcula ",

            "calcular ",

            "resuelve ",

            "resolver ",

            "resultado de ",

            "dime cuanto es ",
        ]

        for prefijo in prefijos:

            if texto.startswith(
                prefijo
            ):

                texto = texto[
                    len(
                        prefijo
                    ):
                ].strip()

                break

        texto = re.sub(
            r"(?<=\d),(?=\d)",
            ".",
            texto,
        )

        texto = texto.replace(
            "^",
            "**",
        )

        texto = re.sub(
            r"\belevado a\b",
            "**",
            texto,
        )

        texto = re.sub(
            r"\bdividido entre\b",
            "/",
            texto,
        )

        texto = re.sub(
            r"\bdividido por\b",
            "/",
            texto,
        )

        texto = re.sub(
            r"\bentre\b",
            "/",
            texto,
        )

        texto = re.sub(
            r"\bmas\b",
            "+",
            texto,
        )

        texto = re.sub(
            r"\bmenos\b",
            "-",
            texto,
        )

        texto = re.sub(
            r"(?<=[0-9)])\s+por\s+(?=[0-9(+-])",
            " * ",
            texto,
        )

        texto = re.sub(
            r"(?<=\d)\s*x\s*(?=\d)",
            "*",
            texto,
        )

        return texto.strip()


    def intentar_resolver(
        self,
        texto,
    ):

        raw = str(
            texto
            or ""
        ).strip()

        norm = normalizar_texto(
            raw
        )

        if not raw:

            return None


        # ====================================================
        # PORCENTAJES
        # ====================================================

        match = re.search(

            r"(-?\d+(?:[.,]\d+)?)\s*(?:%|por ciento)\s+de\s+(.+)$",

            norm,
        )

        if match:

            porcentaje = float(
                match.group(
                    1
                ).replace(
                    ",",
                    ".",
                )
            )

            resto = self.limpiar_expresion(
                match.group(
                    2
                )
            )

            if re.search(
                r"[a-zñ]",
                resto,
            ):

                return None

            try:

                base = self.evaluar(
                    resto
                )

                resultado = (
                    porcentaje
                    / 100.0
                ) * base

                resultado = self.validar_valor(
                    resultado
                )

            except Exception:

                return None

            return {

                "resultado": resultado,

                "texto": self.formatear(
                    resultado
                ),

                "tipo": "porcentaje",

                "expresion": (
                    f"{porcentaje}% de {resto}"
                ),
            }


        # ====================================================
        # RAÍZ
        # ====================================================

        match = re.search(
            r"raiz(?: cuadrada)? de (.+)$",
            norm,
        )

        if match:

            expresion = self.limpiar_expresion(
                match.group(
                    1
                )
            )

            if re.search(
                r"[a-zñ]",
                expresion,
            ):

                return None

            try:

                numero = self.evaluar(
                    expresion
                )

                if numero < 0:

                    raise MathError(
                        "Número negativo."
                    )

                resultado = math.sqrt(
                    numero
                )

            except Exception:

                return None

            return {

                "resultado": resultado,

                "texto": self.formatear(
                    resultado
                ),

                "tipo": "raiz",

                "expresion": expresion,
            }


        # ====================================================
        # PROMEDIO
        # ====================================================

        if (
            norm.startswith(
                "promedio de "
            )
            or norm.startswith(
                "media de "
            )
        ):

            numeros = [

                float(
                    numero.replace(
                        ",",
                        ".",
                    )
                )

                for numero in re.findall(
                    r"-?\d+(?:[.,]\d+)?",
                    norm,
                )
            ]

            if len(
                numeros
            ) >= 2:

                resultado = (
                    sum(
                        numeros
                    )
                    / len(
                        numeros
                    )
                )

                return {

                    "resultado": resultado,

                    "texto": self.formatear(
                        resultado
                    ),

                    "tipo": "promedio",

                    "expresion": str(
                        numeros
                    ),
                }


        # ====================================================
        # REGLA DE TRES SIMPLE
        # ====================================================

        if "regla de tres" in norm:

            numeros = [

                float(
                    numero.replace(
                        ",",
                        ".",
                    )
                )

                for numero in re.findall(
                    r"-?\d+(?:[.,]\d+)?",
                    norm,
                )
            ]

            if (
                len(
                    numeros
                )
                == 3
                and numeros[
                    0
                ]
                != 0
            ):

                a = numeros[
                    0
                ]

                b = numeros[
                    1
                ]

                c = numeros[
                    2
                ]

                resultado = (
                    b
                    * c
                    / a
                )

                return {

                    "resultado": resultado,

                    "texto": self.formatear(
                        resultado
                    ),

                    "tipo": "regla_de_tres",

                    "expresion": (
                        f"({b} * {c}) / {a}"
                    ),
                }


        # ====================================================
        # EXPRESIÓN NORMAL
        # ====================================================

        expresion = self.limpiar_expresion(
            raw
        )

        if not re.search(
            r"\d",
            expresion,
        ):

            return None

        if not re.search(
            r"[+\-*/()%]",
            expresion,
        ):

            return None

        if re.search(
            r"[a-zñ]",
            expresion,
        ):

            return None

        if not re.fullmatch(
            r"[0-9+\-*/().%\s]+",
            expresion,
        ):

            return None

        try:

            resultado = self.evaluar(
                expresion
            )

        except Exception:

            return None

        return {

            "resultado": resultado,

            "texto": self.formatear(
                resultado
            ),

            "tipo": "expresion",

            "expresion": expresion,
        }


# ============================================================
# SECCIÓN DEL MANUAL
# ============================================================

@dataclass
class ManualSection:

    title: str

    body: str

    title_norm: str

    title_tokens: list

    body_tokens: list

    paragraphs: list


# ============================================================
# ÍNDICE DEL MANUAL
# ============================================================

class ManualIndex:

    def __init__(
        self,
        manual_texto="",
    ):

        self.manual_texto = ""

        self.sections = []

        self.df = {}

        self.actualizar(
            manual_texto
        )


    def actualizar(
        self,
        manual_texto,
    ):

        self.manual_texto = str(
            manual_texto
            or ""
        )

        self.sections = self.parse_sections(
            self.manual_texto
        )

        self.build_df()


    def crear_section(
        self,
        title,
        body,
    ):

        paragraphs = [

            re.sub(
                r"\s+",
                " ",
                parte,
            ).strip()

            for parte in re.split(
                r"\n\s*\n",
                body,
            )

            if re.sub(
                r"\s+",
                " ",
                parte,
            ).strip()
        ]

        return ManualSection(

            title=title,

            body=body,

            title_norm=normalizar_texto(
                title
            ),

            title_tokens=tokenizar(
                title
            ),

            body_tokens=tokenizar(
                body
            ),

            paragraphs=paragraphs,
        )


    def parse_sections(
        self,
        texto,
    ):

        texto = str(
            texto
            or ""
        ).replace(
            "\r\n",
            "\n",
        )

        patron = re.compile(

            r"(?m)^={8,}\s*$\n^([^\n]+?)\s*$\n^={8,}\s*$"
        )

        matches = list(
            patron.finditer(
                texto
            )
        )

        sections = []

        if not matches:

            if texto.strip():

                sections.append(
                    self.crear_section(
                        "MANUAL BIN",
                        texto.strip(),
                    )
                )

            return sections


        preambulo = texto[
            :matches[
                0
            ].start()
        ].strip()

        if preambulo:

            sections.append(
                self.crear_section(
                    "INTRODUCCIÓN",
                    preambulo,
                )
            )


        for indice, match in enumerate(
            matches
        ):

            title = match.group(
                1
            ).strip()

            inicio = match.end()

            if (
                indice
                + 1
                < len(
                    matches
                )
            ):

                final = matches[
                    indice
                    + 1
                ].start()

            else:

                final = len(
                    texto
                )

            body = texto[
                inicio:final
            ].strip()

            if body:

                sections.append(
                    self.crear_section(
                        title,
                        body,
                    )
                )

        return sections


    def build_df(
        self,
    ):

        self.df = {}

        for section in self.sections:

            tokens = set(

                section.title_tokens
                + section.body_tokens
            )

            for token in tokens:

                self.df[
                    token
                ] = (
                    self.df.get(
                        token,
                        0,
                    )
                    + 1
                )


    def weights(
        self,
        query_tokens,
    ):

        numero_secciones = max(
            1,
            len(
                self.sections
            ),
        )

        salida = {}

        for token in query_tokens:

            df = self.df.get(
                token,
                0,
            )

            salida[
                token
            ] = (

                1.0

                + math.log(

                    (
                        numero_secciones
                        + 1.0
                    )

                    / (
                        df
                        + 1.0
                    )
                )
            )

        return salida


    def score_section(
        self,
        query_norm,
        query_tokens,
        section,
        weights,
    ):

        body_cov = cobertura_tokens(

            query_tokens,

            section.body_tokens,

            weights,
        )

        title_cov = cobertura_tokens(

            query_tokens,

            section.title_tokens,

            weights,
        )

        best_par_cov = 0.0

        best_sequence = 0.0


        for paragraph in section.paragraphs[
            :80
        ]:

            tokens = tokenizar(
                paragraph
            )

            cobertura = cobertura_tokens(

                query_tokens,

                tokens,

                weights,
            )

            best_par_cov = max(
                best_par_cov,
                cobertura,
            )

            sequence = SequenceMatcher(

                None,

                query_norm,

                normalizar_texto(
                    paragraph
                )[
                    :max(
                        100,
                        len(
                            query_norm
                        )
                        * 4,
                    )
                ],
            ).ratio()

            best_sequence = max(
                best_sequence,
                sequence,
            )


        title_sequence = SequenceMatcher(

            None,

            query_norm,

            section.title_norm,
        ).ratio()


        sequence_score = max(

            best_sequence,

            title_sequence,
        )


        score = (

            (
                0.35
                * body_cov
            )

            + (
                0.30
                * best_par_cov
            )

            + (
                0.20
                * title_cov
            )

            + (
                0.15
                * sequence_score
            )

        ) * 100.0


        # ----------------------------------------------------
        # CALIBRACIÓN PARA EL UMBRAL DE 82 %
        # ----------------------------------------------------

        if len(
            query_tokens
        ) >= 2:

            if best_par_cov >= 0.999:

                score = max(
                    score,
                    91.0,
                )

            elif body_cov >= 0.999:

                score = max(
                    score,
                    86.0,
                )

            elif (
                body_cov >= 0.82
                and best_par_cov >= 0.72
            ):

                score = max(
                    score,
                    83.0,
                )

            if (
                title_cov >= 0.67
                and body_cov >= 0.80
            ):

                score = max(
                    score,
                    94.0,
                )


        # Una sola palabra genérica no debe disparar
        # respuestas técnicas con demasiada facilidad.

        if (
            len(
                query_tokens
            )
            == 1
            and title_cov < 0.999
        ):

            score = min(
                score,
                78.0,
            )


        return (

            min(
                100.0,
                max(
                    0.0,
                    score,
                ),
            ),

            {

                "body_cov": body_cov,

                "best_par_cov": best_par_cov,

                "title_cov": title_cov,

                "sequence": sequence_score,
            },
        )


    def buscar(
        self,
        consulta,
    ):

        query_norm = normalizar_texto(
            consulta
        )


        query_tokens = tokenizar(
            consulta
        )


        # ====================================================
        # PALABRAS QUE FORMAN PARTE DE LA PREGUNTA
        # PERO NO DEL CONCEPTO QUE QUEREMOS BUSCAR.
        # ====================================================

        palabras_consulta = {

            "sirve",
            "servir",
            "explica",
            "explicar",
            "hace",
            "hacer",
        }


        # ====================================================
        # EQUIVALENCIAS NATURALES PARA CONSULTAR EL MANUAL
        # ====================================================

        equivalencias = {

            "agrego": "crear",
            "agrega": "crear",
            "agregas": "crear",
            "agregue": "crear",
            "agregando": "crear",
        }


        query_tokens = [

            equivalencias.get(
                token,
                token,
            )

            for token in query_tokens

            if token not in palabras_consulta
        ]


        if (
            not query_tokens
            or not self.sections
        ):

            return {

                "confianza": 0.0,

                "section": None,

                "scores": {},

                "query_tokens": query_tokens,
            }


        weights = self.weights(
            query_tokens
        )


        best_section = None

        best_score = 0.0

        best_detail = {}


        for section in self.sections:

            score, detalle = self.score_section(

                query_norm,

                query_tokens,

                section,

                weights,
            )


            if score > best_score:

                best_score = score

                best_section = section

                best_detail = detalle


        return {

            "confianza": round(
                best_score,
                2,
            ),

            "section": best_section,

            "scores": best_detail,

            "query_tokens": query_tokens,
        }
    
    def extraer_respuesta(
        self,
        consulta,
        section,
        max_sentences=5,
        max_chars=1100,
    ):

        query_tokens = tokenizar(
            consulta
        )

        if not query_tokens:

            return limitar_texto(
                section.body,
                max_chars,
            )


        weights = self.weights(
            query_tokens
        )

        candidatos = []

        orden = 0


        for paragraph in (
            section.paragraphs
        ):

            oraciones = re.split(

                r"(?<=[.!?])\s+",

                paragraph,
            )

            for oracion in oraciones:

                oracion = re.sub(
                    r"\s+",
                    " ",
                    oracion,
                ).strip(
                    " -"
                )

                if len(
                    oracion
                ) < 12:

                    continue

                tokens = tokenizar(
                    oracion
                )

                cobertura = cobertura_tokens(

                    query_tokens,

                    tokens,

                    weights,
                )

                score = (
                    cobertura
                    * 100.0
                )

                candidatos.append(
                    (
                        orden,
                        score,
                        oracion,
                    )
                )

                orden += 1


        if not candidatos:

            return limitar_texto(
                section.body,
                max_chars,
            )


        candidatos.sort(

            key=lambda item: item[
                1
            ],

            reverse=True,
        )


        seleccionados = candidatos[
            :max(
                1,
                max_sentences,
            )
        ]


        seleccionados.sort(

            key=lambda item: item[
                0
            ]
        )


        if (
            seleccionados
            and max(
                item[
                    1
                ]
                for item in seleccionados
            )
            < 30.0
        ):

            base = (

                section.paragraphs[
                    0
                ]

                if section.paragraphs

                else section.body
            )

            return limitar_texto(
                base,
                max_chars,
            )


        texto = " ".join(

            item[
                2
            ]

            for item in seleccionados
        )


        return limitar_texto(
            texto,
            max_chars,
        )


# ============================================================
# MANUAL DE BIN — JSON + COMPATIBILIDAD CON main.py
# ============================================================

def extraer_manual_desde_python(
    python_path,
    variable_name="MANUAL_BIN_LIGHT",
):

    path = Path(
        python_path
    )


    if (
        not path.exists()
        or not path.is_file()
    ):

        return ""


    try:

        source = path.read_text(
            encoding="utf-8",
        )

        module = ast.parse(
            source,
            filename=str(
                path
            ),
        )


    except Exception:

        return ""


    for node in module.body:

        if isinstance(
            node,
            ast.Assign,
        ):

            targets = [

                target.id

                for target in node.targets

                if isinstance(
                    target,
                    ast.Name,
                )
            ]


            if variable_name not in targets:

                continue


            try:

                value = ast.literal_eval(
                    node.value
                )


            except Exception:

                continue


            if isinstance(
                value,
                str,
            ):

                return value


    return ""


def slug_manual(
    texto,
):

    texto = normalizar_texto(
        texto
    )


    texto = re.sub(

        r"[^a-z0-9]+",

        "_",

        texto,
    )


    texto = texto.strip(
        "_"
    )


    return (
        texto
        or "seccion"
    )


def convertir_manual_texto_a_json(
    texto,
):

    texto = str(
        texto
        or ""
    ).replace(
        "\r\n",
        "\n",
    )


    patron = re.compile(

        r"(?m)^={8,}\s*$\n^([^\n]+?)\s*$\n^={8,}\s*$"
    )


    matches = list(
        patron.finditer(
            texto
        )
    )


    secciones = []


    def agregar_seccion(
        titulo,
        contenido,
        indice,
    ):

        contenido = str(
            contenido
            or ""
        ).strip()


        if not contenido:

            return


        parrafos = [

            re.sub(
                r"\s+",
                " ",
                parte,
            ).strip()

            for parte in re.split(
                r"\n\s*\n",
                contenido,
            )

            if re.sub(
                r"\s+",
                " ",
                parte,
            ).strip()
        ]


        resumen = (

            parrafos[
                0
            ][
                :300
            ]

            if parrafos

            else ""
        )


        secciones.append(

            {

                "id": (
                    f"{indice:02d}_"
                    + slug_manual(
                        titulo
                    )
                ),

                "titulo": str(
                    titulo
                ).strip(),

                "aliases": [

                    str(
                        titulo
                    ).strip()
                ],

                "resumen": resumen,

                "bloques": [

                    {

                        "tipo": "texto",

                        "contenido": contenido,
                    }
                ],
            }
        )


    indice = 1


    if not matches:

        agregar_seccion(

            "MANUAL BIN",

            texto,

            indice,
        )


    else:

        preambulo = texto[
            :matches[
                0
            ].start()
        ].strip()


        if preambulo:

            agregar_seccion(

                "INTRODUCCIÓN",

                preambulo,

                indice,
            )

            indice += 1


        for posicion, match in enumerate(
            matches
        ):

            titulo = match.group(
                1
            ).strip()


            inicio = match.end()


            if (
                posicion
                + 1
                < len(
                    matches
                )
            ):

                final = matches[
                    posicion
                    + 1
                ].start()


            else:

                final = len(
                    texto
                )


            contenido = texto[
                inicio:final
            ].strip()


            agregar_seccion(

                titulo,

                contenido,

                indice,
            )


            indice += 1


    return {

        "tipo": "BIN_MANUAL",

        "schema_version": 1,

        "bin_version": (
            BIN_LIGHT_COMPATIBLE
        ),

        "titulo": (
            "BIN IA ASISTEM — LIGHT"
        ),

        "actualizado_en": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "secciones": secciones,
    }


def manual_json_a_texto(
    data,
):

    if not isinstance(
        data,
        dict,
    ):

        return ""


    secciones = data.get(
        "secciones"
    )


    if not isinstance(
        secciones,
        list,
    ):

        return ""


    partes = []


    for seccion in secciones:

        if not isinstance(
            seccion,
            dict,
        ):

            continue


        titulo = str(

            seccion.get(
                "titulo"
            )

            or "SECCIÓN"

        ).strip()


        cuerpo = []


        # ====================================================
        # RESUMEN
        # ====================================================

        resumen = str(

            seccion.get(
                "resumen"
            )

            or ""

        ).strip()


        if resumen:

            cuerpo.append(
                resumen
            )


        # ====================================================
        # ALIASES
        # ====================================================

        aliases = seccion.get(
            "aliases"
        )


        if isinstance(
            aliases,
            list,
        ):

            aliases_limpios = [

                str(
                    alias
                    or ""
                ).strip()

                for alias in aliases

                if str(
                    alias
                    or ""
                ).strip()
            ]


            if aliases_limpios:

                cuerpo.append(

                    "También puede consultarse como: "

                    + ", ".join(
                        aliases_limpios
                    )
                )


        # ====================================================
        # BLOQUES DEL MANUAL
        # ====================================================

        tiene_interacciones_estructuradas = isinstance(

            seccion.get(
                "interacciones"
            ),

            list,
        )


        for bloque in (

            seccion.get(
                "bloques"
            )

            or []

        ):

            if not isinstance(
                bloque,
                dict,
            ):

                continue


            tipo_bloque = str(

                bloque.get(
                    "tipo"
                )

                or ""

            ).strip().lower()


            contenido = str(

                bloque.get(
                    "contenido"
                )

                or ""

            ).strip()


            if contenido:

                cuerpo.append(
                    contenido
                )


            # =================================================
            # IMAGEN
            # =================================================

            if tipo_bloque == "imagen":

                alt = str(

                    bloque.get(
                        "alt"
                    )

                    or ""

                ).strip()


                descripcion = str(

                    bloque.get(
                        "descripcion"
                    )

                    or ""

                ).strip()


                if alt:

                    cuerpo.append(

                        "Imagen de referencia: "

                        + alt
                    )


                if descripcion:

                    cuerpo.append(
                        descripcion
                    )


            # =================================================
            # ITEMS
            # =================================================

            items = bloque.get(
                "items"
            )


            # Si ya tenemos las interacciones como objetos,
            # no necesitamos indexarlas también desde el
            # bloque textual duplicado.

            if (
                tipo_bloque == "interacciones"
                and tiene_interacciones_estructuradas
            ):

                items = []


            if isinstance(
                items,
                list,
            ):

                for item in items:

                    texto_item = str(
                        item
                        or ""
                    ).strip()


                    if texto_item:

                        cuerpo.append(
                            texto_item
                        )


        # ====================================================
        # INTERACCIONES NUMERADAS
        # ====================================================

        interacciones = seccion.get(
            "interacciones"
        )


        if isinstance(
            interacciones,
            list,
        ):

            for interaccion in interacciones:

                if not isinstance(
                    interaccion,
                    dict,
                ):

                    continue


                numero = interaccion.get(
                    "numero"
                )


                control = str(

                    interaccion.get(
                        "control"
                    )

                    or interaccion.get(
                        "nombre"
                    )

                    or "Control"

                ).strip()


                descripcion = str(

                    interaccion.get(
                        "descripcion"
                    )

                    or ""

                ).strip()


                accion = str(

                    interaccion.get(
                        "accion_usuario"
                    )

                    or ""

                ).strip()


                resultado = str(

                    interaccion.get(
                        "resultado"
                    )

                    or ""

                ).strip()


                notas = str(

                    interaccion.get(
                        "notas"
                    )

                    or ""

                ).strip()


                partes_interaccion = []


                if numero is not None:

                    partes_interaccion.append(

                        f"Número {numero}."
                    )


                partes_interaccion.append(

                    control + "."
                )


                if descripcion:

                    partes_interaccion.append(
                        descripcion
                    )


                if accion:

                    partes_interaccion.append(

                        "Acción del usuario: "

                        + accion
                    )


                if resultado:

                    partes_interaccion.append(

                        "Resultado: "

                        + resultado
                    )


                if notas:

                    partes_interaccion.append(

                        "Nota: "

                        + notas
                    )


                cuerpo.append(

                    " ".join(
                        partes_interaccion
                    )
                )


        # ====================================================
        # ELEMENTOS INFORMATIVOS
        # ====================================================

        elementos = seccion.get(
            "elementos_informativos"
        )


        if isinstance(
            elementos,
            list,
        ):

            for elemento in elementos:

                if isinstance(
                    elemento,
                    dict,
                ):

                    nombre = str(

                        elemento.get(
                            "nombre"
                        )

                        or elemento.get(
                            "control"
                        )

                        or ""

                    ).strip()


                    descripcion = str(

                        elemento.get(
                            "descripcion"
                        )

                        or ""

                    ).strip()


                    texto_elemento = (

                        (
                            nombre
                            + ". "
                        )

                        if nombre

                        else ""

                    ) + descripcion


                else:

                    texto_elemento = str(
                        elemento
                        or ""
                    ).strip()


                if texto_elemento:

                    cuerpo.append(
                        texto_elemento
                    )


        if not cuerpo:

            continue


        partes.append(

            "\n".join(

                [

                    "=" * 60,

                    titulo,

                    "=" * 60,

                    "",

                    "\n\n".join(
                        cuerpo
                    ),
                ]
            )
        )


    return "\n\n".join(
        partes
    ).strip()

def cargar_manual_json(
    ruta,
):

    ruta = Path(
        ruta
    )


    if not ruta.exists():

        return (
            None,
            "",
        )


    try:

        data = json.loads(

            ruta.read_text(
                encoding="utf-8"
            )
        )


    except Exception:

        return (
            None,
            "",
        )


    if not isinstance(
        data,
        dict,
    ):

        return (
            None,
            "",
        )


    if (
        str(
            data.get(
                "tipo"
            )
            or ""
        ).strip()
        != "BIN_MANUAL"
    ):

        return (
            None,
            "",
        )


    texto = manual_json_a_texto(
        data
    )


    return (
        data,
        texto,
    )


def guardar_manual_json(
    ruta,
    data,
):

    ruta = Path(
        ruta
    )


    ruta.parent.mkdir(

        parents=True,

        exist_ok=True,
    )


    temporal = ruta.with_suffix(
        ruta.suffix
        + ".tmp"
    )


    temporal.write_text(

        json.dumps(

            data,

            ensure_ascii=False,

            indent=4,
        ),

        encoding="utf-8",
    )


    os.replace(

        temporal,

        ruta,
    )


# ============================================================
# HTML VISIBLE
# ============================================================

class VisibleHTMLParser(
    HTMLParser
):

    BLOCK_TAGS = {

        "div",
        "p",
        "section",
        "article",
        "li",
        "br",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "td",
        "tr",
    }


    SKIP_TAGS = {

        "script",
        "style",
        "svg",
        "noscript",
    }


    def __init__(
        self,
    ):

        super().__init__(
            convert_charrefs=True
        )

        self.skip_depth = 0

        self.parts = []


    def handle_starttag(
        self,
        tag,
        attrs,
    ):

        tag = tag.lower()

        if tag in self.SKIP_TAGS:

            self.skip_depth += 1

            return

        if self.skip_depth:

            return

        if tag in self.BLOCK_TAGS:

            self.parts.append(
                "\n"
            )


    def handle_endtag(
        self,
        tag,
    ):

        tag = tag.lower()

        if tag in self.SKIP_TAGS:

            if self.skip_depth:

                self.skip_depth -= 1

            return

        if self.skip_depth:

            return

        if tag in self.BLOCK_TAGS:

            self.parts.append(
                "\n"
            )


    def handle_data(
        self,
        data,
    ):

        if self.skip_depth:

            return

        data = html.unescape(
            data
            or ""
        )

        data = re.sub(
            r"\s+",
            " ",
            data,
        ).strip()

        if data:

            self.parts.append(
                data
            )

# ============================================================
# EXTRAER <mark class="MAeH">
# ============================================================

class MarkMAeHParser(
    HTMLParser
):


    def __init__(
        self,
    ):

        super().__init__(
            convert_charrefs=True
        )

        self.capturando = 0

        self.texto_actual = []

        self.resultados = []


    def handle_starttag(
        self,
        tag,
        attrs,
    ):

        tag = str(
            tag
            or ""
        ).lower()


        if self.capturando:

            self.capturando += 1

            return


        if tag != "mark":

            return


        atributos = dict(
            attrs
        )


        clases = str(
            atributos.get(
                "class",
                "",
            )
            or ""
        ).split()


        encontrado = any(

            str(
                clase
            ).strip().lower()
            == "maeh"

            for clase in clases
        )


        if encontrado:

            self.capturando = 1

            self.texto_actual = []


    def handle_endtag(
        self,
        tag,
    ):

        if not self.capturando:

            return


        self.capturando -= 1


        if self.capturando != 0:

            return


        texto = re.sub(

            r"\s+",

            " ",

            " ".join(
                self.texto_actual
            ),

        ).strip()


        if (
            texto
            and texto not in self.resultados
        ):

            self.resultados.append(
                texto
            )


        self.texto_actual = []


    def handle_data(
        self,
        data,
    ):

        if not self.capturando:

            return


        texto = str(
            data
            or ""
        ).strip()


        if texto:

            self.texto_actual.append(
                texto
            )

# ============================================================
# GOOGLE SIN API
# ============================================================

class GoogleSearch:

    AUTOMATED_MARKERS = (

        "vision general creada por ia",

        "descripcion general de ia",

        "ai overview",

        "featured snippet",

        "respuesta destacada",
    )


    STOP_MARKERS = (

        "mas informacion",

        "resultados web",

        "web results",

        "fuentes",

        "sources",

        "otras preguntas",

        "people also ask",
    )


    BAD_MARKERS = (

        "unusual traffic",

        "trafico inusual",

        "captcha",

        "before you continue to google",

        "antes de continuar a google",
    )


    def __init__(
        self,
        config,
        provider=None,
        internet_checker=None,
    ):

        self.config = config

        self.provider = provider

        self.internet_checker = (
            internet_checker
        )

        self.driver = None


        self.driver_lock = threading.RLock()

    def hay_internet(
        self,
    ):

        if callable(
            self.internet_checker
        ):

            try:

                return bool(
                    self.internet_checker()
                )

            except Exception:

                return False


        headers = {

            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/128.0 Safari/537.36"
            )
        }


        for url in (
            self.config.internet_test_urls
        ):

            try:

                request = urllib.request.Request(

                    url,

                    headers=headers,
                )

                with urllib.request.urlopen(

                    request,

                    timeout=(
                        self.config.network_timeout
                    ),

                ) as response:

                    status = getattr(
                        response,
                        "status",
                        200,
                    )

                    if (
                        200
                        <= int(
                            status
                        )
                        < 500
                    ):

                        return True

            except Exception:

                continue


        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        try:

            with socket.create_connection(

                (
                    "8.8.8.8",
                    53,
                ),

                timeout=min(
                    1.5,
                    self.config.network_timeout,
                ),

            ):

                return True

        except Exception:

            return False


    def usar_provider(
        self,
        consulta,
    ):

        if not callable(
            self.provider
        ):

            return None

        try:

            resultado = self.provider(
                consulta
            )

        except Exception as error:

            return {

                "ok": False,

                "texto": "",

                "metodo": "provider",

                "error": str(
                    error
                ),
            }


        if isinstance(
            resultado,
            str,
        ):

            texto = resultado.strip()

            return {

                "ok": bool(
                    texto
                ),

                "texto": texto,

                "metodo": "provider",

                "tipo": (
                    "respuesta_automatizada"
                ),
            }


        if isinstance(
            resultado,
            dict,
        ):

            texto = str(

                resultado.get(
                    "texto"
                )

                or resultado.get(
                    "respuesta"
                )

                or resultado.get(
                    "mensaje"
                )

                or ""

            ).strip()


            salida = dict(
                resultado
            )

            salida.setdefault(
                "ok",
                bool(
                    texto
                ),
            )

            salida.setdefault(
                "texto",
                texto,
            )

            salida.setdefault(
                "metodo",
                "provider",
            )

            return salida


        return {

            "ok": False,

            "texto": "",

            "metodo": "provider",
        }


    def limpiar_consulta_google(
        self,
        consulta,
    ):

        consulta = str(
            consulta
            or ""
        ).strip()

        consulta_normal = normalizar_texto(
            consulta
        )

        prefijos = [

            "puedes buscar en google ",

            "busca en google ",

            "buscar en google ",

            "consulta en google ",

            "investiga en google ",

            "puedes investigar ",
        ]


        for prefijo in prefijos:

            if consulta_normal.startswith(
                prefijo
            ):

                consulta = consulta[
                    len(
                        prefijo
                    ):
                ].strip()

                break


        return consulta


    def extraer_respuesta_directa_google(
        self,
        page,
    ):

        if not page:

            return None


        # ====================================================
        # BLOQUES QUE GOOGLE SUELE USAR PARA
        # RESPUESTAS DESTACADAS / KNOWLEDGE PANEL /
        # FRAGMENTOS DE RESULTADOS
        # ====================================================

        clases = [

            "hgKElc",

            "IZ6rdc",

            "VwiC3b",

            "BNeawe",

            "kno-rdesc",

            "yXK7lf",
        ]


        candidatos = []


        for clase in clases:

            patron = re.compile(

                rf'<(?:div|span)[^>]*class="[^"]*'
                rf'{re.escape(clase)}'
                rf'[^"]*"[^>]*>(.*?)</(?:div|span)>',

                re.I
                | re.S,
            )


            for match in patron.finditer(
                page
            ):

                fragmento = match.group(
                    1
                )


                # --------------------------------------------
                # QUITAR ETIQUETAS HTML
                # --------------------------------------------

                fragmento = re.sub(

                    r"<script\b.*?</script>",

                    " ",

                    fragmento,

                    flags=(
                        re.I
                        | re.S
                    ),
                )


                fragmento = re.sub(

                    r"<style\b.*?</style>",

                    " ",

                    fragmento,

                    flags=(
                        re.I
                        | re.S
                    ),
                )


                fragmento = re.sub(

                    r"<[^>]+>",

                    " ",

                    fragmento,
                )


                fragmento = html.unescape(
                    fragmento
                )


                fragmento = re.sub(

                    r"\s+",

                    " ",

                    fragmento,
                ).strip()


                # --------------------------------------------
                # DESCARTAR BASURA DE INTERFAZ
                # --------------------------------------------

                normal = normalizar_texto(
                    fragmento
                )


                if len(
                    fragmento
                ) < 45:

                    continue


                if len(
                    fragmento
                ) > 2500:

                    continue


                palabras_no_validas = [

                    "iniciar sesion",

                    "acceder",

                    "imagenes",

                    "videos",

                    "shopping",

                    "herramientas",

                    "resultados de busqueda",

                    "google search",
                ]


                if any(

                    palabra in normal

                    for palabra in palabras_no_validas
                ):

                    continue


                if fragmento not in candidatos:

                    candidatos.append(
                        fragmento
                    )


        if not candidatos:

            return None


        # ====================================================
        # PREFERIR UNA RESPUESTA CON CONTENIDO REAL
        # ====================================================

        candidatos.sort(

            key=lambda texto: (

                len(
                    texto.split()
                ),

                len(
                    texto
                ),
            ),

            reverse=True,
        )


        respuesta = candidatos[
            0
        ]


        respuesta = limitar_texto(

            respuesta,

            self.config.google_max_chars,
        )


        return {

            "ok": True,

            "texto": respuesta,

            "tipo": (
                "respuesta_google"
            ),
        }

    def extraer_visible(
        self,
        page,
    ):

        parser = VisibleHTMLParser()

        try:

            parser.feed(
                page
            )

        except Exception:

            pass


        raw = "\n".join(
            parser.parts
        )


        lineas = [

            re.sub(
                r"\s+",
                " ",
                linea,
            ).strip()

            for linea in raw.splitlines()

            if re.sub(
                r"\s+",
                " ",
                linea,
            ).strip()
        ]


        # ----------------------------------------------------
        # ELIMINAR DUPLICADOS
        # ----------------------------------------------------

        limpias = []

        vistas = set()


        for linea in lineas:

            key = normalizar_texto(
                linea
            )

            if key in vistas:

                continue

            vistas.add(
                key
            )

            limpias.append(
                linea
            )


        texto_total = normalizar_texto(

            "\n".join(
                limpias
            )
        )


        if any(

            marker in texto_total

            for marker in self.BAD_MARKERS
        ):

            return {

                "ok": False,

                "texto": "",

                "tipo": "bloqueado",
            }


        normalizadas = [

            normalizar_texto(
                linea
            )

            for linea in limpias
        ]


        # ====================================================
        # PRIMERO: AI OVERVIEW / RESPUESTA DESTACADA
        # ====================================================

        for indice, linea in enumerate(
            normalizadas
        ):

            if not any(

                marker in linea

                for marker in self.AUTOMATED_MARKERS
            ):

                continue


            recogido = []

            chars = 0


            for siguiente in range(

                indice
                + 1,

                min(
                    len(
                        limpias
                    ),
                    indice
                    + 45,
                ),
            ):

                original = limpias[
                    siguiente
                ]

                normal = normalizadas[
                    siguiente
                ]


                if any(

                    marker in normal

                    for marker in self.STOP_MARKERS
                ):

                    if recogido:

                        break

                    continue


                if len(
                    original
                ) < 18:

                    continue


                recogido.append(
                    original
                )

                chars += (
                    len(
                        original
                    )
                    + 1
                )

                if (
                    chars
                    >= self.config.google_max_chars
                ):

                    break


            respuesta = limitar_texto(

                " ".join(
                    recogido
                ),

                self.config.google_max_chars,
            )


            if len(
                respuesta
            ) >= 45:

                return {

                    "ok": True,

                    "texto": respuesta,

                    "tipo": (
                        "respuesta_automatizada"
                    ),
                }


        # ====================================================
        # SEGUNDO: PRIMER FRAGMENTO ÚTIL
        # ====================================================

        if (
            self.config.google_aceptar_fragmento_resultado
        ):

            for linea in limpias:

                normal = normalizar_texto(
                    linea
                )

                if len(
                    linea
                ) < 70:

                    continue

                if normal.startswith(
                    "google"
                ):

                    continue

                if normal.startswith(
                    "iniciar sesion"
                ):

                    continue

                if normal.startswith(
                    "privacidad"
                ):

                    continue

                return {

                    "ok": True,

                    "texto": limitar_texto(

                        linea,

                        self.config.google_max_chars,
                    ),

                    "tipo": (
                        "fragmento_resultado"
                    ),
                }


        return {

            "ok": False,

            "texto": "",

            "tipo": "sin_respuesta",
        }

    # ========================================================
    # PERFIL PERSISTENTE DE GOOGLE
    # ========================================================

    def _ruta_perfil_google(
        self,
    ):

        ruta = Path(
            self.config.google_profile_dir
        )


        if not ruta.is_absolute():

            ruta = (

                Path(
                    __file__
                ).resolve().parent

                / ruta
            )


        ruta.mkdir(

            parents=True,

            exist_ok=True,
        )


        return ruta


    # ========================================================
    # CREAR CHROME
    # ========================================================

    def _crear_driver(
        self,
    ):

        opciones = webdriver.ChromeOptions()


        opciones.add_argument(
            "--lang=es-CO"
        )


        opciones.add_argument(
            "--disable-notifications"
        )


        opciones.add_argument(
            "--window-size=1280,900"
        )


        opciones.add_argument(

            "--user-data-dir="
            + str(
                self._ruta_perfil_google()
            )
        )


        if self.config.google_headless:

            opciones.add_argument(
                "--headless=new"
            )


        return webdriver.Chrome(
            options=opciones
        )


    # ========================================================
    # OBTENER / REUTILIZAR CHROME
    # ========================================================

    def _obtener_driver(
        self,
    ):

        if self.driver is not None:

            try:

                _ = self.driver.current_window_handle

                return self.driver


            except Exception:

                try:

                    self.driver.quit()

                except Exception:

                    pass


                self.driver = None


        self.driver = self._crear_driver()


        return self.driver


    # ========================================================
    # DETECTAR VERIFICACIÓN DE GOOGLE
    # ========================================================

    def _google_en_verificacion(
        self,
        driver,
    ):

        try:

            url_actual = str(

                driver.current_url

                or ""

            ).lower()


            texto = str(

                driver.execute_script(
                    """
                    return document.body
                        ? document.body.innerText
                        : '';
                    """
                )

                or ""

            )


            normal = normalizar_texto(
                texto
            )


            return (

                "/sorry/" in url_actual

                or "no soy un robot" in normal

                or "trafico inusual" in normal

                or "unusual traffic" in normal

                or "recaptcha" in normal
            )


        except Exception:

            return False


    # ========================================================
    # GUARDAR DOM RENDERIZADO
    # ========================================================

    def _guardar_dom_debug(
        self,
        driver,
    ):

        page = driver.execute_script(
            """
            return document.documentElement.outerHTML;
            """
        )


        page = str(
            page
            or ""
        )


        ruta_debug = Path(
            self.config.google_debug_html_path
        )


        if not ruta_debug.is_absolute():

            ruta_debug = (

                Path(
                    __file__
                ).resolve().parent

                / ruta_debug
            )


        ruta_debug.write_text(

            page,

            encoding="utf-8",
        )


        return (

            page,

            ruta_debug,
        )


    # ========================================================
    # CERRAR GOOGLE
    # ========================================================

    def cerrar(
        self,
    ):

        with self.driver_lock:

            if self.driver is None:

                return


            try:

                self.driver.quit()

            except Exception:

                pass


            self.driver = None

    def buscar(
        self,
        consulta,
    ):

        consulta = self.limpiar_consulta_google(
            consulta
        )


        if not consulta:

            return {

                "ok": False,

                "texto": "",

                "metodo": "google",

                "error": (
                    "Consulta vacía."
                ),
            }


        # ====================================================
        # PROVIDER EXTERNO
        # ====================================================

        provider_result = self.usar_provider(
            consulta
        )


        if provider_result is not None:

            return provider_result


        # ====================================================
        # SELENIUM DISPONIBLE
        # ====================================================

        if not SELENIUM_DISPONIBLE:

            return {

                "ok": False,

                "texto": "",

                "metodo": (
                    "google_selenium_no_disponible"
                ),

                "error": (
                    "Selenium no está instalado."
                ),
            }


        # ====================================================
        # URL GOOGLE
        # ====================================================

        parametros = urllib.parse.urlencode(

            {

                "q": consulta,

                "hl": (
                    self.config.google_hl
                ),

                "gl": "co",
            }
        )


        url = (

            "https://www.google.com/search?"

            + parametros
        )


        # ====================================================
        # UNA SOLA CONSULTA GOOGLE A LA VEZ
        # ====================================================

        with self.driver_lock:

            try:

                driver = self._obtener_driver()


                # =============================================
                # ABRIR CONSULTA
                # =============================================

                driver.get(
                    url
                )


                # =============================================
                # ESPERAR DOCUMENTO
                # =============================================

                try:

                    WebDriverWait(

                        driver,

                        self.config.google_render_timeout,

                    ).until(

                        lambda navegador:

                        navegador.execute_script(
                            "return document.readyState"
                        )
                        == "complete"
                    )


                except Exception:

                    pass


                # =============================================
                # GOOGLE PIDIÓ VERIFICACIÓN
                # =============================================

                if self._google_en_verificacion(
                    driver
                ):

                    if self.config.debug:

                        print(
                            "[BIN DEBUG] GOOGLE_CAPTCHA: "
                            "Google solicitó verificación manual. "
                            "Completa la verificación en Chrome."
                        )


                    try:

                        WebDriverWait(

                            driver,

                            self.config.google_captcha_timeout,

                        ).until(

                            lambda navegador:

                            not self._google_en_verificacion(
                                navegador
                            )
                        )


                        if self.config.debug:

                            print(
                                "[BIN DEBUG] GOOGLE_CAPTCHA: "
                                "Verificación superada. "
                                "Continuando."
                            )


                    except Exception:

                        page, ruta_debug = (
                            self._guardar_dom_debug(
                                driver
                            )
                        )


                        return {

                            "ok": False,

                            "texto": "",

                            "tipo": (
                                "google_verificacion_pendiente"
                            ),

                            "metodo": (
                                "google_selenium_captcha"
                            ),

                            "url": str(
                                driver.current_url
                            ),

                            "html_chars": len(
                                page
                            ),

                            "debug_html": str(
                                ruta_debug
                            ),

                            "error": (
                                "Google solicitó una "
                                "verificación manual."
                            ),
                        }


                # =============================================
                # ESPERAR mark.MAeH
                # =============================================

                try:

                    WebDriverWait(

                        driver,

                        self.config.google_render_timeout,

                    ).until(

                        lambda navegador:

                        bool(

                            navegador.execute_script(
                                """
                                return Array
                                    .from(
                                        document.querySelectorAll('mark')
                                    )
                                    .some(
                                        elemento =>
                                            Array
                                                .from(
                                                    elemento.classList
                                                )
                                                .some(
                                                    clase =>
                                                        clase.toLowerCase()
                                                        === 'maeh'
                                                )
                                            &&
                                            (
                                                elemento.innerText
                                                || ''
                                            ).trim().length > 0
                                    );
                                """
                            )
                        )
                    )


                except Exception:

                    pass


                # =============================================
                # VERIFICAR QUE NO VOLVIÓ AL CAPTCHA
                # =============================================

                if self._google_en_verificacion(
                    driver
                ):

                    page, ruta_debug = (
                        self._guardar_dom_debug(
                            driver
                        )
                    )


                    return {

                        "ok": False,

                        "texto": "",

                        "tipo": (
                            "google_verificacion_pendiente"
                        ),

                        "metodo": (
                            "google_selenium_captcha"
                        ),

                        "url": str(
                            driver.current_url
                        ),

                        "html_chars": len(
                            page
                        ),

                        "debug_html": str(
                            ruta_debug
                        ),

                        "error": (
                            "Google solicitó una "
                            "verificación manual."
                        ),
                    }


                # =============================================
                # EXTRAER HTML RENDERIZADO
                # Y GUARDAR BIN_Google_Debug.html
                # =============================================

                page, ruta_debug = (
                    self._guardar_dom_debug(
                        driver
                    )
                )


                # =============================================
                # LEER EL ARCHIVO QUE ACABAMOS DE GENERAR
                # =============================================

                html_guardado = ruta_debug.read_text(
                    encoding="utf-8"
                )


                # =============================================
                # EXTRAER <mark class="MAeH">
                # =============================================

                parser = MarkMAeHParser()


                parser.feed(
                    html_guardado
                )


                candidatos = [

                    texto.strip()

                    for texto in parser.resultados

                    if str(
                        texto
                        or ""
                    ).strip()
                ]


                # =============================================
                # RESPUESTA ENCONTRADA
                # =============================================

                if candidatos:

                    respuesta = limitar_texto(

                        candidatos[
                            0
                        ],

                        self.config.google_max_chars,
                    )


                    return {

                        "ok": True,

                        "texto": respuesta,

                        "tipo": (
                            "google_mark_maeh"
                        ),

                        "metodo": (
                            "google_selenium_dom"
                        ),

                        "url": str(
                            driver.current_url
                        ),

                        "cantidad_maeh": len(
                            candidatos
                        ),

                        "debug_html": str(
                            ruta_debug
                        ),
                    }


                # =============================================
                # GOOGLE CARGÓ PERO NO EXISTE MAeH
                # =============================================

                return {

                    "ok": False,

                    "texto": "",

                    "tipo": (
                        "sin_mark_maeh"
                    ),

                    "metodo": (
                        "google_selenium_dom"
                    ),

                    "url": str(
                        driver.current_url
                    ),

                    "html_chars": len(
                        page
                    ),

                    "debug_html": str(
                        ruta_debug
                    ),
                }


            except Exception as error:

                # =============================================
                # SI CHROME MURIÓ, RECREAR EN SIGUIENTE CONSULTA
                # =============================================

                try:

                    if self.driver is not None:

                        self.driver.quit()

                except Exception:

                    pass


                self.driver = None


                return {

                    "ok": False,

                    "texto": "",

                    "tipo": (
                        "error_selenium"
                    ),

                    "metodo": (
                        "google_selenium_error"
                    ),

                    "url": url,

                    "error": str(
                        error
                    ),
                }
            
# ============================================================
# ARCHIVOS DE APRENDIZAJE
# ============================================================

def validar_archivo_aprendizaje(
    ruta,
):

    path = Path(
        ruta
    )


    if (
        not path.exists()
        or not path.is_file()
    ):

        return {

            "ok": False,

            "motivo": (
                "El archivo no existe."
            ),
        }


    try:

        contenido = path.read_text(
            encoding="utf-8",
        )

        data = json.loads(
            contenido
        )

    except Exception as error:

        return {

            "ok": False,

            "motivo": (
                "El archivo no contiene JSON válido."
            ),

            "error": str(
                error
            ),
        }


    if not isinstance(
        data,
        dict,
    ):

        return {

            "ok": False,

            "motivo": (
                "La estructura principal no es válida."
            ),
        }


    tipo = str(

        data.get(
            "tipo"
        )

        or ""

    ).strip()


    if tipo != TIPO_APRENDIZAJE:

        return {

            "ok": False,

            "motivo": (
                "No es un archivo de aprendizaje de BIN."
            ),
        }


    try:

        schema = int(

            data.get(
                "schema_version",
                0,
            )

            or 0
        )

    except Exception:

        schema = 0


    if schema <= 0:

        return {

            "ok": False,

            "motivo": (
                "schema_version inválido."
            ),
        }


    if (
        schema
        > SCHEMA_APRENDIZAJE_SOPORTADO
    ):

        return {

            "ok": False,

            "motivo": (
                "El archivo fue creado con un esquema "
                "más nuevo que esta versión de BIN."
            ),
        }


    tarea = data.get(
        "tarea"
    )


    if not isinstance(
        tarea,
        dict,
    ):

        return {

            "ok": False,

            "motivo": (
                "El archivo no contiene una tarea válida."
            ),
        }


    acciones = tarea.get(
        "acciones"
    ) or []


    if not isinstance(
        acciones,
        list,
    ):

        return {

            "ok": False,

            "motivo": (
                "La lista de acciones no es válida."
            ),
        }


    nombre = str(

        data.get(
            "nombre"
        )

        or tarea.get(
            "nombre"
        )

        or path.stem

    ).strip()


    return {

        "ok": True,

        "tipo": tipo,

        "schema_version": schema,

        "bin_version": str(
            data.get(
                "bin_version"
            )
            or ""
        ),

        "nombre": nombre,

        "acciones": len(
            acciones
        ),

        "tarea": tarea,

        "ruta": str(
            path
        ),

        "ejecucion_automatica": False,
    }


# ============================================================
# DETECTAR INFORMACIÓN POTENCIALMENTE SENSIBLE
# ============================================================

PATRONES_SENSIBLES = {

    "correo": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),

    "password": re.compile(
        r"\b(password|contrasena|contraseña)\b",
        re.I,
    ),

    "pin": re.compile(
        r"\bpin\b",
        re.I,
    ),

    "token": re.compile(
        r"\b(token|bearer|secret|api[\s_-]*key)\b",
        re.I,
    ),

    "autenticacion": re.compile(
        r"\b(2fa|otp|codigo de autenticacion|código de autenticación)\b",
        re.I,
    ),
}


def detectar_informacion_sensible(
    objeto,
):

    try:

        texto = json.dumps(

            objeto,

            ensure_ascii=False,

            default=str,
        )

    except Exception:

        texto = str(
            objeto
        )


    detectados = []


    for nombre, patron in (
        PATRONES_SENSIBLES.items()
    ):

        if patron.search(
            texto
        ):

            detectados.append(
                nombre
            )


    return detectados


# ============================================================
# MEMORIA LOCAL DE CONSULTAS GOOGLE
# ============================================================

class MemoriaBIN:


    def __init__(
        self,
        ruta="memoria.json",
        umbral=82.0,
    ):

        ruta = Path(
            ruta
        )


        if not ruta.is_absolute():

            ruta = (

                Path(
                    __file__
                ).resolve().parent

                / ruta
            )


        self.ruta = ruta

        self.umbral = float(
            umbral
        )

        self.lock = threading.RLock()


    # ========================================================
    # FECHA
    # ========================================================

    def ahora(
        self,
    ):

        return datetime.now(
            timezone.utc
        ).isoformat()


    # ========================================================
    # ESTRUCTURA VACÍA
    # ========================================================

    def estructura_vacia(
        self,
    ):

        return {

            "tipo": "BIN_MEMORIA",

            "schema_version": 1,

            "actualizado_en": (
                self.ahora()
            ),

            "memorias": [],
        }


    # ========================================================
    # CARGAR
    # ========================================================

    def cargar(
        self,
    ):

        with self.lock:

            if not self.ruta.exists():

                return self.estructura_vacia()


            try:

                data = json.loads(

                    self.ruta.read_text(
                        encoding="utf-8"
                    )
                )

            except Exception:

                return self.estructura_vacia()


            if not isinstance(
                data,
                dict,
            ):

                return self.estructura_vacia()


            memorias = data.get(
                "memorias"
            )


            if not isinstance(
                memorias,
                list,
            ):

                data[
                    "memorias"
                ] = []


            return data


    # ========================================================
    # GUARDAR ARCHIVO
    # ========================================================

    def guardar_archivo(
        self,
        data,
    ):

        with self.lock:

            self.ruta.parent.mkdir(

                parents=True,

                exist_ok=True,
            )

            data[
                "actualizado_en"
            ] = self.ahora()

            temporal = self.ruta.with_suffix(

                self.ruta.suffix
                + ".tmp"
            )

            temporal.write_text(

                json.dumps(

                    data,

                    ensure_ascii=False,

                    indent=4,
                ),

                encoding="utf-8",
            )

            os.replace(

                temporal,

                self.ruta,
            )


    # ========================================================
    # GUARDAR APRENDIZAJE
    # ========================================================

    def aprender(
        self,
        consulta,
        respuesta,
        fuente="GOOGLE",
    ):

        consulta = str(
            consulta
            or ""
        ).strip()

        respuesta = str(
            respuesta
            or ""
        ).strip()

        if (
            not consulta
            or not respuesta
        ):

            return {

                "ok": False,

                "motivo": (
                    "Consulta o respuesta vacía."
                ),
            }

        consulta_normal = normalizar_texto(
            consulta
        )

        respuesta_normal = normalizar_texto(
            respuesta
        )

        with self.lock:

            data = self.cargar()


            memorias = data.get(
                "memorias",
                [],
            )


            # =================================================
            # SI LA MISMA CONSULTA EXISTÍA CON OTRA RESPUESTA,
            # LA QUITAMOS DE ESA RESPUESTA.
            # GOOGLE ONLINE PASA A SER LA INFORMACIÓN MÁS RECIENTE.
            # =================================================

            for memoria in memorias:

                respuesta_existente = (
                    normalizar_texto(
                        memoria.get(
                            "respuesta",
                            "",
                        )
                    )
                )


                if (
                    respuesta_existente
                    == respuesta_normal
                ):

                    continue


                consultas = memoria.get(
                    "consultas"
                ) or []


                memoria[
                    "consultas"
                ] = [

                    item

                    for item in consultas

                    if normalizar_texto(
                        item
                    )
                    != consulta_normal
                ]


            # Eliminar respuestas sin consultas.

            memorias = [

                memoria

                for memoria in memorias

                if (
                    memoria.get(
                        "consultas"
                    )
                    or []
                )
            ]


            # =================================================
            # ¿YA EXISTE ESTA RESPUESTA?
            # =================================================

            memoria_objetivo = None


            for memoria in memorias:

                existente = normalizar_texto(

                    memoria.get(
                        "respuesta",
                        "",
                    )
                )


                if existente == respuesta_normal:

                    memoria_objetivo = memoria

                    break


            # =================================================
            # RESPUESTA YA EXISTE:
            # AGREGAMOS OTRA CONSULTA
            # =================================================

            if memoria_objetivo is not None:

                consultas = memoria_objetivo.setdefault(

                    "consultas",

                    [],
                )


                existe_consulta = any(

                    normalizar_texto(
                        item
                    )
                    == consulta_normal

                    for item in consultas
                )


                if not existe_consulta:

                    consultas.append(
                        consulta
                    )


                memoria_objetivo[
                    "respuesta"
                ] = respuesta


                memoria_objetivo[
                    "actualizado_en"
                ] = self.ahora()


                memoria_objetivo[
                    "veces_aprendida"
                ] = (

                    int(
                        memoria_objetivo.get(
                            "veces_aprendida",
                            0,
                        )
                        or 0
                    )

                    + 1
                )


                data[
                    "memorias"
                ] = memorias


                self.guardar_archivo(
                    data
                )


                return {

                    "ok": True,

                    "accion": (
                        "consulta_agregada"
                        if not existe_consulta
                        else "actualizada"
                    ),

                    "consultas": len(
                        consultas
                    ),
                }


            # =================================================
            # RESPUESTA NUEVA
            # =================================================

            nueva = {

                "respuesta": respuesta,

                "consultas": [

                    consulta
                ],

                "fuente": fuente,

                "creado_en": (
                    self.ahora()
                ),

                "actualizado_en": (
                    self.ahora()
                ),

                "veces_aprendida": 1,
            }


            memorias.append(
                nueva
            )


            data[
                "memorias"
            ] = memorias


            self.guardar_archivo(
                data
            )


            return {

                "ok": True,

                "accion": (
                    "respuesta_nueva"
                ),

                "consultas": 1,
            }


    # ========================================================
    # BUSCAR CONSULTA EN MEMORIA
    # ========================================================

    def buscar(
        self,
        consulta,
    ):

        consulta = str(
            consulta
            or ""
        ).strip()


        consulta_normal = normalizar_texto(
            consulta
        )


        if not consulta_normal:

            return {

                "ok": False,

                "confianza": 0.0,
            }


        data = self.cargar()


        mejor = None

        mejor_confianza = 0.0

        query_tokens = tokenizar(
            consulta
        )


        for memoria in data.get(
            "memorias",
            [],
        ):

            respuesta = str(

                memoria.get(
                    "respuesta"
                )

                or ""

            ).strip()


            for consulta_guardada in (
                memoria.get(
                    "consultas"
                )
                or []
            ):

                guardada_normal = normalizar_texto(
                    consulta_guardada
                )


                # =============================================
                # COINCIDENCIA EXACTA
                # =============================================

                if (
                    consulta_normal
                    == guardada_normal
                ):

                    return {

                        "ok": True,

                        "respuesta": respuesta,

                        "confianza": 100.0,

                        "consulta_guardada": (
                            consulta_guardada
                        ),
                    }


                # =============================================
                # COINCIDENCIA APROXIMADA
                # =============================================

                sequence = SequenceMatcher(

                    None,

                    consulta_normal,

                    guardada_normal,

                ).ratio()


                guardada_tokens = tokenizar(
                    consulta_guardada
                )


                cobertura_consulta = cobertura_tokens(

                    query_tokens,

                    guardada_tokens,
                )


                cobertura_guardada = cobertura_tokens(

                    guardada_tokens,

                    query_tokens,
                )


                semantica = (

                    0.70
                    * cobertura_consulta

                    + 0.30
                    * cobertura_guardada
                )


                confianza = max(

                    sequence,

                    semantica,

                ) * 100.0


                if confianza > mejor_confianza:

                    mejor_confianza = confianza


                    mejor = {

                        "respuesta": respuesta,

                        "consulta_guardada": (
                            consulta_guardada
                        ),
                    }


        if (
            mejor is not None
            and mejor_confianza
            >= self.umbral
        ):

            return {

                "ok": True,

                "respuesta": mejor[
                    "respuesta"
                ],

                "confianza": round(
                    mejor_confianza,
                    2,
                ),

                "consulta_guardada": (
                    mejor[
                        "consulta_guardada"
                    ]
                ),
            }

        return {

            "ok": False,

            "confianza": round(
                mejor_confianza,
                2,
            ),
        }

    # ========================================================
    # ESTADO
    # ========================================================

    def estado(
        self,
    ):

        data = self.cargar()


        memorias = data.get(
            "memorias",
            [],
        )


        consultas = sum(

            len(
                memoria.get(
                    "consultas"
                )
                or []
            )

            for memoria in memorias
        )


        return {

            "ruta": str(
                self.ruta
            ),

            "respuestas": len(
                memorias
            ),

            "consultas": consultas,

            "umbral": (
                self.umbral
            ),
        }

# ============================================================
# MOTOR PRINCIPAL
# ============================================================

class BINBot:


    def __init__(
        self,
        manual_texto=None,
        manual_path=None,
        main_path=None,
        config=None,
        google_provider=None,
        internet_checker=None,
        debug_hook=None,
    ):

        self.config = (
            config
            or BINBotConfig()
        )


        self.random = random.Random(
            self.config.random_seed
        )


        self.debug_hook = (
            debug_hook
        )


        self.manual_path = (

            Path(
                manual_path
            )

            if manual_path

            else None
        )


        self.main_path = (

            Path(
                main_path
            )

            if main_path

            else None
        )


        manual = self.resolver_manual(
            manual_texto
        )


        self.manual_index = ManualIndex(
            manual
        )


        self.math = SafeMath(
            self.config
        )


        self.google = GoogleSearch(

            self.config,

            provider=google_provider,

            internet_checker=internet_checker,
        )

        self.memoria = MemoriaBIN(

            ruta=(
                self.config.memoria_path
            ),

            umbral=(
                self.config.memoria_umbral
            ),
        )

        self.executor = ThreadPoolExecutor(

            max_workers=max(
                1,
                int(
                    self.config.max_workers
                ),
            )
        )


        self.lock = threading.RLock()


        # ====================================================
        # ESTADO DEL MENÚ INTERACTIVO
        # ====================================================

        self.menu_activo = False


        # ====================================================
        # ESTADO DE CONSULTA PENDIENTE DEL MANUAL
        # ====================================================
        #
        # Se utiliza cuando una interacción numerada existe
        # en más de una pantalla.
        #
        # Ejemplo:
        #
        # Usuario:
        #   ¿Qué hace el número 25?
        #
        # BIN:
        #   [1] Interfaz principal
        #   [2] Editar acción de ventana
        #
        # Usuario:
        #   2
        #
        # BIN recuerda qué número estaba resolviendo.
        # ====================================================

        self.manual_pendiente = None


        self.debug(

            "INIT",

            {

                "version": BIN_BOT_VERSION,

                "umbral": (
                    self.config.umbral_local
                ),

                "manual_chars": len(
                    manual
                ),

                "manual_sections": len(
                    self.manual_index.sections
                ),
            },
        )


    # ========================================================
    # DEBUG
    # ========================================================

    def debug(
        self,
        evento,
        datos=None,
    ):

        datos = dict(
            datos
            or {}
        )


        if callable(
            self.debug_hook
        ):

            try:

                self.debug_hook(
                    evento,
                    datos,
                )

            except Exception:

                pass


        if not self.config.debug:

            return


        print(

            "[BIN DEBUG] "
            + str(
                evento
            )
            + ": "
            + json.dumps(

                datos,

                ensure_ascii=False,

                default=str,
            )
        )


    # ========================================================
    # MANUAL
    # ========================================================

    def ruta_manual_json(
        self,
    ):

        ruta = Path(
            self.config.manual_json_path
        )


        if not ruta.is_absolute():

            ruta = (

                Path(
                    __file__
                ).resolve().parent

                / ruta
            )


        return ruta


    def resolver_manual(
        self,
        manual_texto,
    ):

        self.manual_data = {}


        # ====================================================
        # TEXTO PASADO DIRECTAMENTE
        # ====================================================

        if manual_texto is not None:

            texto = str(
                manual_texto
            )


            self.manual_data = (
                convertir_manual_texto_a_json(
                    texto
                )
            )


            return texto


        # ====================================================
        # MANUAL EXPLÍCITO
        # ====================================================

        if self.manual_path:

            try:

                if (
                    self.manual_path.suffix.lower()
                    == ".json"
                ):

                    data, texto = cargar_manual_json(
                        self.manual_path
                    )


                    if data and texto:

                        self.manual_data = data

                        return texto


                else:

                    texto = self.manual_path.read_text(
                        encoding="utf-8"
                    )


                    if texto.strip():

                        self.manual_data = (
                            convertir_manual_texto_a_json(
                                texto
                            )
                        )

                        return texto


            except Exception:

                pass


        # ====================================================
        # FUENTE PRINCIPAL:
        # data/manual_bin_bot.json
        # ====================================================

        ruta_json = self.ruta_manual_json()


        data, texto = cargar_manual_json(
            ruta_json
        )


        if data and texto:

            self.manual_data = data

            return texto


        # ====================================================
        # FALLBACK TEMPORAL DESDE main.py
        # ====================================================

        if self.main_path is None:

            candidato = Path(
                __file__
            ).resolve().with_name(
                "main.py"
            )


            if candidato.exists():

                self.main_path = candidato


        if self.main_path:

            texto = extraer_manual_desde_python(
                self.main_path
            )


            if texto:

                data = (
                    convertir_manual_texto_a_json(
                        texto
                    )
                )


                self.manual_data = data


                return texto


        return ""


    def actualizar_manual(
        self,
        manual_texto,
        manual_data=None,
    ):

        with self.lock:

            self.manual_index.actualizar(
                manual_texto
            )


            if isinstance(
                manual_data,
                dict,
            ):

                self.manual_data = manual_data


            else:

                self.manual_data = (
                    convertir_manual_texto_a_json(
                        manual_texto
                    )
                )


    def recargar_manual(
        self,
    ):

        # ====================================================
        # PRIMERO:
        # data/manual_bin_bot.json
        # ====================================================

        ruta_json = self.ruta_manual_json()


        data, texto = cargar_manual_json(
            ruta_json
        )


        if data and texto:

            self.actualizar_manual(

                texto,

                manual_data=data,
            )


            return True


        # ====================================================
        # MANUAL EXPLÍCITO
        # ====================================================

        if self.manual_path:

            try:

                if (
                    self.manual_path.suffix.lower()
                    == ".json"
                ):

                    data, texto = cargar_manual_json(
                        self.manual_path
                    )


                    if data and texto:

                        self.actualizar_manual(

                            texto,

                            manual_data=data,
                        )


                        return True


                else:

                    texto = self.manual_path.read_text(
                        encoding="utf-8"
                    )


                    if texto.strip():

                        self.actualizar_manual(
                            texto
                        )


                        return True


            except Exception:

                pass


        # ====================================================
        # FALLBACK TEMPORAL main.py
        # ====================================================

        if self.main_path:

            texto = extraer_manual_desde_python(
                self.main_path
            )


            if texto:

                self.actualizar_manual(
                    texto
                )


                return True


        return False


    # ========================================================
    # OBTENER SECCIÓN JSON
    # ========================================================

    def obtener_seccion_manual_json(
        self,
        titulo,
    ):

        data = getattr(
            self,
            "manual_data",
            {},
        )


        secciones = (

            data.get(
                "secciones"
            )

            if isinstance(
                data,
                dict,
            )

            else None
        )


        if not isinstance(
            secciones,
            list,
        ):

            return None


        titulo_normal = normalizar_texto(
            titulo
        )


        for seccion in secciones:

            if not isinstance(
                seccion,
                dict,
            ):

                continue


            titulo_seccion = normalizar_texto(

                seccion.get(
                    "titulo"
                )
            )


            if titulo_seccion == titulo_normal:

                return dict(
                    seccion
                )


        return None


    # ========================================================
    # RESOLVER RECURSO / IMAGEN DEL MANUAL
    # ========================================================

    def resolver_ruta_recurso_manual(
        self,
        ruta,
    ):

        ruta_original = str(
            ruta
            or ""
        ).strip()


        if not ruta_original:

            return {

                "ruta_configurada": "",

                "ruta_relativa": "",

                "ruta_absoluta": "",

                "nombre": "",

                "existe": False,
            }


        base = Path(
            __file__
        ).resolve().parent


        recurso = Path(
            ruta_original
        )


        if not recurso.is_absolute():

            recurso = (
                base
                / recurso
            )


        recurso = recurso.resolve(
            strict=False
        )


        # ====================================================
        # FALLBACK PARA NOMBRES DE ARCHIVO DIFERENTES
        #
        # JSON:
        # src/Captura1_numerada.png
        #
        # DISCO:
        # src/captura (1).png
        # ====================================================

        if not recurso.exists():

            nombre_original = Path(
                ruta_original
            ).stem


            numero_match = re.search(

                r"(\d+)",

                nombre_original,
            )


            carpeta = recurso.parent


            if (
                numero_match
                and carpeta.exists()
                and carpeta.is_dir()
            ):

                numero = numero_match.group(
                    1
                )


                candidatos = []


                for candidato in carpeta.iterdir():

                    if not candidato.is_file():

                        continue


                    if candidato.suffix.lower() not in {

                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".webp",

                    }:

                        continue


                    normal_candidato = normalizar_texto(
                        candidato.stem
                    )


                    if (
                        "captura"
                        in normal_candidato
                    ):

                        numero_candidato = re.search(

                            r"\b"
                            + re.escape(
                                numero
                            )
                            + r"\b",

                            normal_candidato,
                        )


                        if numero_candidato:

                            candidatos.append(
                                candidato
                            )


                if len(
                    candidatos
                ) == 1:

                    recurso = candidatos[
                        0
                    ].resolve()


        try:

            relativa = recurso.relative_to(
                base
            )


            ruta_relativa = (
                relativa.as_posix()
            )


        except Exception:

            ruta_relativa = (
                ruta_original.replace(
                    "\\",
                    "/",
                )
            )


        return {

            "ruta_configurada": (
                ruta_original.replace(
                    "\\",
                    "/",
                )
            ),

            "ruta_relativa": ruta_relativa,

            "ruta_absoluta": str(
                recurso
            ),

            "nombre": recurso.name,

            "existe": recurso.exists(),
        }


    # ========================================================
    # OBTENER IMÁGENES DE UNA SECCIÓN
    # ========================================================

    def extraer_imagenes_seccion_manual(
        self,
        seccion_json,
    ):

        if not isinstance(
            seccion_json,
            dict,
        ):

            return []


        imagenes = []


        for bloque in (

            seccion_json.get(
                "bloques"
            )

            or []

        ):

            if not isinstance(
                bloque,
                dict,
            ):

                continue


            if (
                str(
                    bloque.get(
                        "tipo"
                    )
                    or ""
                ).strip().lower()
                != "imagen"
            ):

                continue


            ruta = str(

                bloque.get(
                    "ruta"
                )

                or ""

            ).strip()


            if not ruta:

                continue


            recurso = (
                self.resolver_ruta_recurso_manual(
                    ruta
                )
            )


            imagenes.append(

                {

                    "tipo": "imagen",

                    "ruta": recurso[
                        "ruta_relativa"
                    ],

                    "ruta_configurada": recurso[
                        "ruta_configurada"
                    ],

                    "ruta_absoluta": recurso[
                        "ruta_absoluta"
                    ],

                    "nombre": recurso[
                        "nombre"
                    ],

                    "existe": recurso[
                        "existe"
                    ],

                    "alt": str(

                        bloque.get(
                            "alt"
                        )

                        or ""

                    ).strip(),

                    "descripcion": str(

                        bloque.get(
                            "descripcion"
                        )

                        or ""

                    ).strip(),
                }
            )


        return imagenes


    # ========================================================
    # TEXTO PARA CMD
    # ========================================================

    def texto_referencias_imagenes(
        self,
        imagenes,
    ):

        imagenes = [

            imagen

            for imagen in (
                imagenes
                or []
            )

            if isinstance(
                imagen,
                dict,
            )
        ]


        if not imagenes:

            return ""


        lineas = [

            "Imagen de referencia:"
        ]


        for imagen in imagenes:

            ruta = str(

                imagen.get(
                    "ruta"
                )

                or imagen.get(
                    "nombre"
                )

                or ""

            ).strip()


            if ruta:

                lineas.append(

                    "- "
                    + ruta
                )


        return "\n".join(
            lineas
        )


    # ========================================================
    # RESPUESTA ESTRUCTURADA PARA UNA INTERACCIÓN
    # ========================================================

    def crear_respuesta_interaccion_manual(
        self,
        seccion,
        interaccion,
        confianza=100.0,
        intencion="manual_interaccion",
    ):

        imagenes = (
            self.extraer_imagenes_seccion_manual(
                seccion
            )
        )


        numero = interaccion.get(
            "numero"
        )


        control = str(

            interaccion.get(
                "control"
            )

            or interaccion.get(
                "nombre"
            )

            or "Control"

        ).strip()


        descripcion = str(

            interaccion.get(
                "descripcion"
            )

            or ""

        ).strip()


        accion = str(

            interaccion.get(
                "accion_usuario"
            )

            or ""

        ).strip()


        resultado_accion = str(

            interaccion.get(
                "resultado"
            )

            or ""

        ).strip()


        notas = str(

            interaccion.get(
                "notas"
            )

            or ""

        ).strip()


        encabezado = control


        if numero is not None:

            encabezado = (

                f"Número {numero} — {control}"
            )


        partes = [

            encabezado,

            descripcion,
        ]


        if accion:

            partes.append(

                "Cómo se usa: "
                + accion
            )


        if resultado_accion:

            partes.append(

                "Resultado: "
                + resultado_accion
            )


        if notas:

            partes.append(

                "Nota: "
                + notas
            )


        referencia_imagen = (
            self.texto_referencias_imagenes(
                imagenes
            )
        )


        if referencia_imagen:

            partes.append(
                referencia_imagen
            )


        return BINBotResponse(

            texto="\n\n".join(

                parte

                for parte in partes

                if str(
                    parte
                    or ""
                ).strip()
            ),

            confianza=confianza,

            origen=ORIGEN_MANUAL,

            intencion=intencion,

            detalle=(
                "Interacción obtenida de manual_bin_bot.json."
            ),

            metadata={

                "seccion_manual": (
                    seccion.get(
                        "titulo"
                    )
                ),

                "seccion_id": (
                    seccion.get(
                        "id"
                    )
                ),

                "interaccion": dict(
                    interaccion
                ),

                "imagenes": imagenes,

                "mostrar_imagen": bool(
                    imagenes
                ),
            },
        )


    # ========================================================
    # BUSCAR INTERACCIÓN POR NÚMERO
    # ========================================================

    def buscar_interaccion_numerada_manual(
        self,
        consulta,
    ):

        consulta = str(
            consulta
            or ""
        ).strip()


        normal = normalizar_texto(
            consulta
        )


        numero = None


        match = re.search(

            r"\bnumero\s+(\d{1,3})\b",

            normal,
        )


        if not match:

            match = re.search(

                r"#\s*(\d{1,3})\b",

                consulta,
            )


        if (
            not match
            and any(

                palabra in normal

                for palabra in (

                    "pantalla",
                    "captura",
                    "boton",
                    "control",
                    "interaccion",

                )
            )
        ):

            match = re.search(

                r"\b(\d{1,3})\b",

                normal,
            )


        if match:

            try:

                numero = int(

                    match.group(
                        1
                    )
                )


            except Exception:

                numero = None


        if numero is None:

            return None


        data = getattr(
            self,
            "manual_data",
            {},
        )


        secciones = (

            data.get(
                "secciones"
            )

            if isinstance(
                data,
                dict,
            )

            else []
        )


        candidatos = []


        for seccion in (
            secciones
            or []
        ):

            if not isinstance(
                seccion,
                dict,
            ):

                continue


            interacciones = seccion.get(
                "interacciones"
            )


            if not isinstance(
                interacciones,
                list,
            ):

                continue


            for interaccion in interacciones:

                if not isinstance(
                    interaccion,
                    dict,
                ):

                    continue


                try:

                    numero_interaccion = int(

                        interaccion.get(
                            "numero"
                        )
                    )


                except Exception:

                    continue


                if numero_interaccion != numero:

                    continue


                candidatos.append(

                    {

                        "seccion": seccion,

                        "interaccion": interaccion,
                    }
                )


        if not candidatos:

            return None


        if len(
            candidatos
        ) == 1:

            return {

                "ambiguo": False,

                **candidatos[
                    0
                ],
            }


        # ====================================================
        # IDENTIFICAR LA PANTALLA
        # ====================================================

        query_tokens = [

            token

            for token in tokenizar(
                consulta
            )

            if (
                not token.isdigit()
                and token not in {

                    "numero",
                    "boton",
                    "control",
                    "interaccion",

                }
            )
        ]


        mejor = None

        mejor_score = 0.0


        for candidato in candidatos:

            seccion = candidato[
                "seccion"
            ]


            interaccion = candidato[
                "interaccion"
            ]


            aliases = seccion.get(
                "aliases"
            )


            if not isinstance(
                aliases,
                list,
            ):

                aliases = []


            descriptor = " ".join(

                [

                    str(
                        seccion.get(
                            "titulo"
                        )
                        or ""
                    ),

                    " ".join(

                        str(
                            alias
                            or ""
                        )

                        for alias in aliases
                    ),

                    str(
                        interaccion.get(
                            "control"
                        )
                        or ""
                    ),
                ]
            )


            descriptor_tokens = tokenizar(
                descriptor
            )


            # Pantalla e interfaz son equivalentes
            # únicamente al identificar una captura.

            if "pantalla" in query_tokens:

                descriptor_tokens.append(
                    "pantalla"
                )


            if "interfaz" in query_tokens:

                descriptor_tokens.append(
                    "interfaz"
                )


            cobertura = cobertura_tokens(

                query_tokens,

                descriptor_tokens,
            )


            secuencia = SequenceMatcher(

                None,

                normal,

                normalizar_texto(
                    descriptor
                ),

            ).ratio()


            bonus = 0.0


            titulo_normal = normalizar_texto(

                seccion.get(
                    "titulo"
                )
            )


            if (
                titulo_normal
                and titulo_normal in normal
            ):

                bonus += 0.55


            for alias in aliases:

                alias_normal = normalizar_texto(
                    alias
                )


                if (
                    len(
                        alias_normal
                    )
                    >= 4
                    and alias_normal
                    in normal
                ):

                    bonus = max(
                        bonus,
                        0.55,
                    )


            score = (

                0.65
                * cobertura

                + 0.35
                * secuencia

                + bonus
            )


            if score > mejor_score:

                mejor_score = score

                mejor = candidato


        if (
            mejor is not None
            and mejor_score >= 0.45
        ):

            return {

                "ambiguo": False,

                **mejor,
            }


        return {

            "ambiguo": True,

            "numero": numero,

            "pantallas": [

                str(

                    candidato[
                        "seccion"
                    ].get(
                        "titulo"
                    )

                    or "Pantalla"
                )

                for candidato in candidatos
            ],

            # =================================================
            # CONSERVAR LOS OBJETOS REALES
            # =================================================
            #
            # Esto permite que el siguiente mensaje del usuario
            # seleccione una pantalla sin volver a buscar todo.
            # =================================================

            "candidatos": candidatos,
        }


    def respuesta_interaccion_numerada_manual(
        self,
        consulta,
    ):

        resultado = (
            self.buscar_interaccion_numerada_manual(
                consulta
            )
        )


        if not resultado:

            return None


        # ====================================================
        # NÚMERO PRESENTE EN MÁS DE UNA PANTALLA
        # ====================================================

        if resultado.get(
            "ambiguo"
        ):

            numero = resultado.get(
                "numero"
            )


            candidatos = list(

                resultado.get(
                    "candidatos"
                )

                or []
            )


            # Guardamos temporalmente la consulta.

            self.manual_pendiente = {

                "tipo": (
                    "seleccion_pantalla_numero"
                ),

                "numero": numero,

                "candidatos": candidatos,
            }


            lineas = [

                (
                    f"El número {numero} aparece en varias "
                    "pantallas del manual."
                ),

                "",

                "¿A cuál te refieres?",
                "",
            ]


            for indice, candidato in enumerate(
                candidatos,
                start=1,
            ):

                seccion = candidato.get(
                    "seccion"
                ) or {}


                titulo = str(

                    seccion.get(
                        "titulo"
                    )

                    or "Pantalla"

                ).strip()


                lineas.append(

                    f"[{indice}] {titulo}"
                )


            lineas.extend(

                [

                    "",

                    (
                        "Puedes responder con el número "
                        "o con el nombre de la pantalla."
                    ),

                    (
                        "Escribe cancelar para salir "
                        "de esta selección."
                    ),
                ]
            )


            return BINBotResponse(

                texto="\n".join(
                    lineas
                ),

                confianza=100.0,

                origen=ORIGEN_MANUAL,

                intencion=(
                    "manual_numero_ambiguo"
                ),

                detalle=(
                    "BIN está esperando que el usuario "
                    "seleccione una pantalla."
                ),

                metadata={

                    "numero": numero,

                    "pantallas": [

                        str(

                            candidato.get(
                                "seccion",
                                {}
                            ).get(
                                "titulo"
                            )

                            or "Pantalla"
                        )

                        for candidato in candidatos
                    ],

                    "seleccion_pendiente": True,
                },
            )


        # ====================================================
        # SOLO EXISTE UNA COINCIDENCIA
        # ====================================================

        return (
            self.crear_respuesta_interaccion_manual(

                resultado[
                    "seccion"
                ],

                resultado[
                    "interaccion"
                ],

                confianza=100.0,

                intencion=(
                    "manual_interaccion_numerada"
                ),
            )
        )


    # ========================================================
    # RESOLVER UNA SELECCIÓN PENDIENTE DEL MANUAL
    # ========================================================

    def resolver_manual_pendiente(
        self,
        texto,
    ):

        pendiente = getattr(

            self,

            "manual_pendiente",

            None,
        )


        if not isinstance(
            pendiente,
            dict,
        ):

            return None


        candidatos = list(

            pendiente.get(
                "candidatos"
            )

            or []
        )


        if not candidatos:

            self.manual_pendiente = None

            return None


        texto = str(
            texto
            or ""
        ).strip()


        normal = normalizar_texto(
            texto
        )


        # ====================================================
        # CANCELAR
        # ====================================================

        if normal in {

            "cancelar",
            "cancela",
            "cancel",
            "salir",

        }:

            self.manual_pendiente = None


            return BINBotResponse(

                texto=(

                    "Selección del manual cancelada. "
                    "Puedes hacer otra consulta."
                ),

                confianza=100.0,

                origen=ORIGEN_MANUAL,

                intencion=(
                    "manual_seleccion_cancelada"
                ),
            )


        seleccionado = None


        # ====================================================
        # SELECCIÓN POR NÚMERO
        # ====================================================

        match = re.fullmatch(

            r"(?:opcion\s*)?(\d{1,2})",

            normal,
        )


        if match:

            indice = int(

                match.group(
                    1
                )
            ) - 1


            if (
                0
                <= indice
                < len(
                    candidatos
                )
            ):

                seleccionado = candidatos[
                    indice
                ]


        # ====================================================
        # SELECCIÓN POR NOMBRE DE PANTALLA
        # ====================================================

        if seleccionado is None:

            query_tokens = [

                token

                for token in tokenizar(
                    texto
                )

                if token not in {

                    "pantalla",
                    "captura",
                    "opcion",
                }
            ]


            mejor = None

            mejor_score = 0.0


            for candidato in candidatos:

                seccion = candidato.get(
                    "seccion"
                ) or {}


                titulo = str(

                    seccion.get(
                        "titulo"
                    )

                    or ""

                ).strip()


                aliases = seccion.get(
                    "aliases"
                )


                if not isinstance(
                    aliases,
                    list,
                ):

                    aliases = []


                descriptor = " ".join(

                    [

                        titulo,

                        " ".join(

                            str(
                                alias
                                or ""
                            )

                            for alias in aliases
                        ),
                    ]
                )


                descriptor_tokens = tokenizar(
                    descriptor
                )


                cobertura = cobertura_tokens(

                    query_tokens,

                    descriptor_tokens,
                )


                secuencia = SequenceMatcher(

                    None,

                    normal,

                    normalizar_texto(
                        descriptor
                    ),

                ).ratio()


                # --------------------------------------------
                # BONUS SI EL TÍTULO O ALIAS APARECE COMPLETO
                # --------------------------------------------

                bonus = 0.0


                titulo_normal = normalizar_texto(
                    titulo
                )


                if (
                    titulo_normal
                    and titulo_normal in normal
                ):

                    bonus = 0.40


                for alias in aliases:

                    alias_normal = normalizar_texto(
                        alias
                    )


                    if (
                        len(
                            alias_normal
                        )
                        >= 4
                        and alias_normal
                        in normal
                    ):

                        bonus = max(
                            bonus,
                            0.40,
                        )


                score = (

                    0.70
                    * cobertura

                    + 0.30
                    * secuencia

                    + bonus
                )


                if score > mejor_score:

                    mejor_score = score

                    mejor = candidato


            # Permite pequeños errores de escritura:
            #
            # "edtar acción de ventana"
            # puede coincidir con
            # "Editar acción de ventana".

            if (
                mejor is not None
                and mejor_score >= 0.45
            ):

                seleccionado = mejor


        # ====================================================
        # NO PUDO IDENTIFICAR LA RESPUESTA
        # ====================================================

        if seleccionado is None:

            lineas = [

                "No pude identificar esa pantalla.",

                "",

                "Elige una de estas opciones:",
                "",
            ]


            for indice, candidato in enumerate(
                candidatos,
                start=1,
            ):

                titulo = str(

                    candidato.get(
                        "seccion",
                        {}
                    ).get(
                        "titulo"
                    )

                    or "Pantalla"

                ).strip()


                lineas.append(

                    f"[{indice}] {titulo}"
                )


            lineas.extend(

                [

                    "",

                    (
                        "También puedes escribir cancelar."
                    ),
                ]
            )


            return BINBotResponse(

                texto="\n".join(
                    lineas
                ),

                confianza=100.0,

                origen=ORIGEN_MANUAL,

                intencion=(
                    "manual_seleccion_pendiente"
                ),
            )


        # ====================================================
        # SELECCIÓN RESUELTA
        # ====================================================

        self.manual_pendiente = None


        return (
            self.crear_respuesta_interaccion_manual(

                seleccionado[
                    "seccion"
                ],

                seleccionado[
                    "interaccion"
                ],

                confianza=100.0,

                intencion=(
                    "manual_interaccion_numerada"
                ),
            )
        )

    # ========================================================
    # CONTROL ESCRITO LITERALMENTE
    # ========================================================

    def respuesta_control_literal_manual(
        self,
        consulta,
    ):

        normal = normalizar_texto(
            consulta
        )


        data = getattr(
            self,
            "manual_data",
            {},
        )


        secciones = (

            data.get(
                "secciones"
            )

            if isinstance(
                data,
                dict,
            )

            else []
        )


        coincidencias = []


        for seccion in (
            secciones
            or []
        ):

            if not isinstance(
                seccion,
                dict,
            ):

                continue


            interacciones = seccion.get(
                "interacciones"
            )


            if not isinstance(
                interacciones,
                list,
            ):

                continue


            for interaccion in interacciones:

                if not isinstance(
                    interaccion,
                    dict,
                ):

                    continue


                control = normalizar_texto(

                    interaccion.get(
                        "control"
                    )

                    or interaccion.get(
                        "nombre"
                    )

                    or ""
                )


                control = control.strip(
                    "+- "
                )


                if (
                    len(
                        control
                    )
                    >= 4
                    and control
                    in normal
                ):

                    coincidencias.append(

                        (
                            seccion,
                            interaccion,
                        )
                    )


        # Sólo respondemos directamente si
        # la coincidencia es inequívoca.

        if len(
            coincidencias
        ) != 1:

            return None


        seccion, interaccion = (
            coincidencias[
                0
            ]
        )


        return (
            self.crear_respuesta_interaccion_manual(

                seccion,

                interaccion,

                confianza=100.0,

                intencion=(
                    "manual_control_literal"
                ),
            )
        )


    # ========================================================
    # BANCO
    # ========================================================
    def choice(
        self,
        banco,
    ):

        if not banco:

            return ""

        return self.random.choice(
            list(
                banco
            )
        ).strip()


    # ========================================================
    # SALUDO ESPECIALIZADO
    # ========================================================

    def saludo_con_ayuda(
        self,
    ):

        saludo = self.choice(
            BancosBIN.SALUDOS
        )


        return (

            saludo

            + "\n\n"

            + (
                "Si quieres conocer mis funciones o necesitas "
                "ayuda especializada con BIN, escribe /ayuda."
            )
        )


    # ========================================================
    # MENÚ PRINCIPAL DEL CHAT
    # ========================================================

    def texto_menu_principal(
        self,
    ):

        return """

¿Qué quieres hacer?

[1] Ver todo lo que BIN puede hacer
[2] Ver operaciones matemáticas disponibles
[3] Ver comandos de BIN Bot
[4] Ver comandos de automatización / teclado
[5] Ver estado de BIN
[6] Ver estado de mi memoria
[7] Consultar el manual de BIN
[8] Recargar el manual
[9] Activar / desactivar DEBUG
[10] Ver ejemplos de consultas
[0] Cerrar este menú

Puedes responder únicamente con el número.

""".strip()


    # ========================================================
    # MOSTRAR MENÚ
    # ========================================================

    def respuesta_menu(
        self,
    ):

        self.menu_activo = True


        return BINBotResponse(

            texto=self.texto_menu_principal(),

            confianza=100.0,

            origen=ORIGEN_CONVERSACION,

            intencion="menu",

            detalle=(
                "Menú interactivo local de BIN."
            ),
        )


    # ========================================================
    # CAPACIDADES DETALLADAS
    # ========================================================

    def texto_capacidades_detalladas(
        self,
    ):

        return """

CAPACIDADES DE BIN BOT

1. Conversación local
   - Saludos.
   - Despedidas.
   - Agradecimientos.
   - Presentación.
   - Confirmaciones.
   - Conversaciones básicas.
   - Estado general del asistente.

2. Consultas especializadas de BIN Light
   - Consulta el manual oficial de BIN.
   - Busca instrucciones sobre funciones del software.
   - Localiza información relacionada con una pregunta.
   - Utiliza un sistema de confianza antes de responder.

3. Matemáticas locales
   - Suma.
   - Resta.
   - Multiplicación.
   - División.
   - División entera.
   - Módulo.
   - Potencias.
   - Porcentajes.
   - Raíz cuadrada.
   - Promedios.
   - Regla de tres.
   - Expresiones con paréntesis.

4. Consultas externas
   - Cuando la información local no alcanza suficiente
     confianza, BIN puede consultar Google.
   - Utiliza un navegador real renderizado.
   - Puede obtener la respuesta principal de la
     Visión general creada por IA cuando Google la ofrece.

5. Aprendizaje de búsquedas
   - Las respuestas externas pueden guardarse automáticamente.
   - Una misma respuesta puede relacionarse con varias formas
     diferentes de preguntar.
   - El aprendizaje permanece después de cerrar BIN.

6. Memoria local
   - Las respuestas aprendidas se guardan en memoria.json.
   - BIN puede reutilizar ese conocimiento posteriormente.
   - Las consultas similares se comparan mediante confianza.

7. Funcionamiento sin Internet
   - La conversación básica continúa funcionando.
   - Las matemáticas continúan funcionando.
   - El manual funciona localmente.
   - Las respuestas previamente aprendidas siguen disponibles.
   - Si BIN no sabe algo, informa que necesita conexión.

8. Contexto operativo de BIN Light
   - Puede conocer la tarea seleccionada.
   - Puede informar si BIN está ejecutando una tarea.
   - BIN Light puede enviarle información de contexto.

9. Archivos de aprendizaje
   - Reconoce archivos BIN_APRENDIZAJE.
   - Valida versión y estructura.
   - BIN Light podrá ofrecer VER / AGREGAR / CANCELAR.

10. Diagnóstico
    - DEBUG.
    - Estado del manual.
    - Estado de memoria.
    - Confianza de las respuestas.
    - Origen de las respuestas.

BIN Bot mantiene estas funciones sin utilizar un modelo
local pesado.

""".strip()


    # ========================================================
    # OPERACIONES MATEMÁTICAS
    # ========================================================

    def texto_operaciones_matematicas(
        self,
    ):

        return """

OPERACIONES MATEMÁTICAS DISPONIBLES

BIN las procesa localmente, sin necesidad de Internet.

1. Suma
   25 + 17

2. Resta
   900 - 50

3. Multiplicación
   12 * 8

4. División
   450 / 9

5. División entera
   17 // 5

6. Módulo / residuo
   17 % 5

7. Potencias
   5 ^ 3
   5 ** 3

8. Porcentajes
   25% de 480

9. Raíz cuadrada
   raíz cuadrada de 144

10. Promedios
    promedio de 10, 15 y 20

11. Regla de tres
    regla de tres 5 20 8

12. Expresiones combinadas
    (25 + 5) * 4

Las matemáticas se procesan antes de cualquier
consulta externa.

""".strip()


    # ========================================================
    # RESUMEN DE ESTADO
    # ========================================================

    def texto_estado_resumido(
        self,
    ):

        memoria = self.memoria.estado()


        manual_cargado = bool(
            self.manual_index.manual_texto.strip()
        )


        return (

            "Estado actual de BIN:\n\n"

            f"Versión ChatBOT: {BIN_BOT_VERSION}\n"

            f"BIN Light compatible: {BIN_LIGHT_COMPATIBLE}\n"

            f"Manual cargado: "
            f"{'Sí' if manual_cargado else 'No'}\n"

            f"Secciones del manual: "
            f"{len(self.manual_index.sections)}\n"

            f"Google habilitado: "
            f"{'Sí' if self.config.permitir_google else 'No'}\n"

            f"DEBUG: "
            f"{'Activo' if self.config.debug else 'Desactivado'}\n"

            f"Respuestas aprendidas: "
            f"{memoria.get('respuestas', 0)}\n"

            f"Consultas aprendidas: "
            f"{memoria.get('consultas', 0)}"
        )


    # ========================================================
    # COMANDOS DE BIN BOT
    # ========================================================

    def texto_comandos_chat(
        self,
    ):

        return """

COMANDOS DE BIN BOT

/ayuda
    Abrir la ayuda especializada.

/estado
    Ver el estado interno de BIN.

/debug on
    Activar diagnóstico.

/debug off
    Desactivar diagnóstico.

/recargar
    Volver a cargar el manual.

/archivo RUTA
    Revisar un archivo de aprendizaje.

/salir
    Cerrar BIN Bot desde consola.

También puedes escribir:

ayuda
menu
opciones
comandos
que puedes hacer

""".strip()


    # ========================================================
    # COMANDOS DE AUTOMATIZACIÓN
    # ========================================================

    def texto_comandos_automatizacion(
        self,
    ):

        ruta = Path(
            self.config.comandos_teclado_path
        )


        if not ruta.is_absolute():

            ruta = (

                Path(
                    __file__
                ).resolve().parent

                / ruta
            )


        if not ruta.exists():

            return (

                "No encontré la biblioteca de comandos en:\n\n"

                + str(
                    ruta
                )
            )


        try:

            datos = json.loads(

                ruta.read_text(
                    encoding="utf-8"
                )
            )


        except Exception as error:

            return (

                "No pude leer la biblioteca de comandos.\n\n"

                + str(
                    error
                )
            )


        if not isinstance(
            datos,
            list,
        ):

            return (
                "La biblioteca de comandos no tiene "
                "una estructura válida."
            )


        lineas = [

            "COMANDOS DE AUTOMATIZACIÓN / TECLADO",

            "",
        ]


        numero = 0


        for comando in datos:

            if not isinstance(
                comando,
                dict,
            ):

                continue


            numero += 1


            nombre = str(

                comando.get(
                    "nombre"
                )

                or comando.get(
                    "id"
                )

                or "Comando"

            ).strip()


            parametros = comando.get(
                "parametros"
            ) or []


            teclas = []


            for parametro in parametros:

                if not isinstance(
                    parametro,
                    dict,
                ):

                    continue


                tecla = str(

                    parametro.get(
                        "tecla"
                    )

                    or ""

                ).strip()


                if not tecla:

                    continue


                try:

                    repeticiones = max(

                        1,

                        int(
                            parametro.get(
                                "repeticiones",
                                1,
                            )
                            or 1
                        ),
                    )


                except Exception:

                    repeticiones = 1


                if repeticiones > 1:

                    teclas.append(

                        f"{tecla}^{repeticiones}"
                    )

                else:

                    teclas.append(
                        tecla
                    )


            secuencia = (

                " + ".join(
                    teclas
                )

                if teclas

                else "Sin parámetros"
            )


            lineas.append(

                f"{numero}. {nombre}"
            )


            lineas.append(

                f"   {secuencia}"
            )


        if numero == 0:

            return (
                "La biblioteca existe, pero no contiene "
                "comandos disponibles."
            )


        return "\n".join(
            lineas
        )


    # ========================================================
    # ÍNDICE DEL MANUAL
    # ========================================================

    def texto_indice_manual(
        self,
    ):

        secciones = (
            self.manual_index.sections
        )

        if not secciones:

            return (

                "El manual de BIN todavía no está cargado.\n\n"

                "BIN intentará utilizar data/manual_bin_bot.json."
            )

        lineas = [

            "SECCIONES DEL MANUAL DE BIN",

            "",
        ]

        for indice, seccion in enumerate(
            secciones,
            start=1,
        ):

            lineas.append(

                f"{indice}. {seccion.title}"
            )


        lineas.extend(

            [

                "",

                (
                    "Puedes preguntarme directamente por "
                    "cualquiera de estos temas."
                ),
            ]
        )


        return "\n".join(
            lineas
        )


    # ========================================================
    # EJEMPLOS
    # ========================================================

    def texto_ejemplos_consulta(
        self,
    ):

        return """

EJEMPLOS DE CONSULTAS

Sobre BIN:
• ¿Qué puedes hacer?
• ¿Cómo creo una tarea en BIN?
• ¿Cómo escribo texto en modo manual?
• ¿Qué comandos de teclado tienes?

Matemáticas:
• 25% de 480
• raíz cuadrada de 144
• promedio de 10, 15 y 20
• (25 + 5) * 4

Consultas generales:
• ¿Qué es una API?
• Explícame qué es JavaScript
• ¿Los perros tienen conciencia?

Primero intento resolver la consulta localmente.

Si no tengo suficiente certeza y hay Internet,
puedo consultar información externa.

Las respuestas obtenidas externamente pueden
guardarse en mi memoria local.

""".strip()


    # ========================================================
    # EJECUTAR OPCIÓN DEL MENÚ
    # ========================================================

    def ejecutar_opcion_menu(
        self,
        texto,
    ):

        if not getattr(
            self,
            "menu_activo",
            False,
        ):

            return None


        normal = normalizar_texto(
            texto
        )


        match = re.fullmatch(

            r"(?:opcion\s*)?(10|[0-9])",

            normal,
        )


        if not match:

            return None


        opcion = int(
            match.group(
                1
            )
        )


        # ====================================================
        # UNA OPCIÓN COMPLETA CIERRA EL MENÚ
        # ====================================================
        #
        # Si el usuario quiere volver a utilizarlo,
        # puede escribir nuevamente:
        #
        # /ayuda
        # ayuda
        # menu
        # opciones
        # ====================================================

        self.menu_activo = False


        if opcion == 0:

            self.menu_activo = False


            texto_respuesta = (

                "Menú cerrado. Puedes seguir "
                "hablando conmigo normalmente."
            )

            intencion = "menu_cerrar"


        elif opcion == 1:

            texto_respuesta = (
                self.texto_capacidades_detalladas()
            )

            intencion = "menu_capacidades"


        elif opcion == 2:

            texto_respuesta = (
                self.texto_operaciones_matematicas()
            )

            intencion = "menu_matematicas"


        elif opcion == 3:

            texto_respuesta = (
                self.texto_comandos_chat()
            )

            intencion = "menu_comandos_chat"


        elif opcion == 4:

            texto_respuesta = (
                self.texto_comandos_automatizacion()
            )

            intencion = "menu_comandos_automatizacion"


        elif opcion == 5:

            texto_respuesta = (
                self.texto_estado_resumido()
            )

            intencion = "menu_estado"


        elif opcion == 6:

            memoria = self.memoria.estado()


            texto_respuesta = (

                "Estado de mi memoria local:\n\n"

                f"Respuestas guardadas: "
                f"{memoria.get('respuestas', 0)}\n"

                f"Consultas asociadas: "
                f"{memoria.get('consultas', 0)}\n"

                f"Umbral de coincidencia: "
                f"{memoria.get('umbral', 0)} %\n"

                f"Archivo: "
                f"{memoria.get('ruta', '')}"
            )

            intencion = "menu_memoria"


        elif opcion == 7:

            texto_respuesta = (
                self.texto_indice_manual()
            )

            intencion = "menu_manual"


        elif opcion == 8:

            correcto = self.recargar_manual()


            texto_respuesta = (

                "Manual recargado correctamente."

                if correcto

                else (
                    "No pude recargar el manual. "
                    "No encontré una fuente válida."
                )
            )

            intencion = "menu_recargar_manual"


        elif opcion == 9:

            self.config.debug = (
                not self.config.debug
            )


            texto_respuesta = (

                "DEBUG activado."

                if self.config.debug

                else "DEBUG desactivado."
            )

            intencion = "menu_debug_toggle"


        elif opcion == 10:

            texto_respuesta = (
                self.texto_ejemplos_consulta()
            )

            intencion = "menu_ejemplos"


        else:

            return None


        return BINBotResponse(

            texto=texto_respuesta,

            confianza=100.0,

            origen=ORIGEN_CONVERSACION,

            intencion=intencion,
        )

    # ========================================================
    # COMANDOS INTERNOS ESCRITOS EN EL CHAT
    # ========================================================

    def responder_comando_interno(
        self,
        texto,
    ):

        normal = normalizar_texto(
            texto
        )


        if normal in {

            "/estado",

            "estado de bin",

            "estado del bot",
        }:

            return BINBotResponse(

                texto=self.texto_estado_resumido(),

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="comando_estado",
            )


        if normal in {

            "/debug on",

            "debug on",

            "activar debug",

        }:

            self.config.debug = True


            return BINBotResponse(

                texto="DEBUG activado.",

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="comando_debug_on",
            )


        if normal in {

            "/debug off",

            "debug off",

            "desactivar debug",

        }:

            self.config.debug = False


            return BINBotResponse(

                texto="DEBUG desactivado.",

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="comando_debug_off",
            )


        if normal in {

            "/recargar",

            "recargar manual",

            "recarga el manual",

        }:

            correcto = self.recargar_manual()


            return BINBotResponse(

                texto=(

                    "Manual recargado."

                    if correcto

                    else "No pude recargar el manual."
                ),

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="comando_recargar",
            )


        return None

    # ========================================================
    # INTENCIÓN
    # ========================================================

    def detectar_intencion(
        self,
        texto,
    ):

        normal = normalizar_texto(
            texto
        )


        for intencion, patrones in (
            INTENT_PATTERNS.items()
        ):

            for patron in patrones:

                if re.search(
                    patron,
                    normal,
                ):

                    return intencion


        return None


    def respuesta_conversacional(
        self,
        intencion,
    ):

        if intencion == "menu":

            return self.respuesta_menu()


        if intencion == "capacidades":

            return BINBotResponse(

                texto=(
                    self.texto_capacidades_detalladas()
                ),

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="capacidades",

                detalle=(
                    "Descripción detallada de capacidades."
                ),
            )


        if intencion == "saludo":

            return BINBotResponse(

                texto=self.saludo_con_ayuda(),

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="saludo",

                detalle=(
                    "Saludo local con ayuda especializada."
                ),
            )


        bancos = {

            "saludo": (
                BancosBIN.SALUDOS
            ),

            "despedida": (
                BancosBIN.DESPEDIDAS
            ),

            "agradecimiento": (
                BancosBIN.AGRADECIMIENTOS
            ),

            "comentario_positivo": (
                BancosBIN.COMENTARIOS_POSITIVOS
            ),

            "estado": (
                BancosBIN.ESTADO
            ),

            "presentacion": (
                BancosBIN.PRESENTACION
            ),

            "capacidades": (
                BancosBIN.CAPACIDADES
            ),

            "confirmacion": (
                BancosBIN.CONFIRMACIONES
            ),
        }


        banco = bancos.get(
            intencion
        )


        if not banco:

            return None


        return BINBotResponse(

            texto=self.choice(
                banco
            ),

            confianza=100.0,

            origen=ORIGEN_CONVERSACION,

            intencion=intencion,

            detalle=(
                "Respuesta conversacional local."
            ),
        )

    # ========================================================
    # CONTEXTO DE BIN LIGHT
    # ========================================================

    def responder_contexto(
        self,
        texto,
        contexto,
    ):

        contexto = contexto or {}

        normal = normalizar_texto(
            texto
        )


        if (
            "tarea seleccionada"
            in normal
            or "tarea tengo seleccionada"
            in normal
        ):

            tarea = contexto.get(
                "tarea_seleccionada"
            )


            if isinstance(
                tarea,
                dict,
            ):

                nombre = str(
                    tarea.get(
                        "nombre"
                    )
                    or "Sin nombre"
                )

                estado = str(
                    tarea.get(
                        "estado"
                    )
                    or ""
                )

                acciones = int(
                    tarea.get(
                        "acciones"
                    )
                    or 0
                )


                respuesta = (

                    f"La tarea seleccionada es “{nombre}”. "
                    f"Estado: {estado or 'sin estado informado'}. "
                    f"Contiene {acciones} acción"
                    f"{'' if acciones == 1 else 'es'}."
                )


            else:

                respuesta = (
                    "Ahora mismo no hay una tarea seleccionada."
                )


            return BINBotResponse(

                texto=respuesta,

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="contexto_tarea",
            )


        if (
            "estas ocupado"
            in normal
            or "bin esta ocupado"
            in normal
        ):

            ocupado = bool(
                contexto.get(
                    "bin_ocupado"
                )
            )


            if ocupado:

                respuesta = (
                    "Sí. BIN tiene una tarea en ejecución en este momento."
                )

            else:

                respuesta = (
                    "No. BIN no tiene una tarea en ejecución en este momento."
                )


            return BINBotResponse(

                texto=respuesta,

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="estado_operativo",
            )


        return None

    # ========================================================
    # RESPONDER DESDE MEMORIA
    # ========================================================

    def responder_desde_memoria(
        self,
        texto,
    ):

        resultado = self.memoria.buscar(
            texto
        )


        if not resultado.get(
            "ok"
        ):

            return None


        intro = self.choice(
            BancosBIN.MEMORIA_INTROS
        )


        contenido = str(

            resultado.get(
                "respuesta"
            )

            or ""

        ).strip()


        return BINBotResponse(

            texto=(

                intro

                + "\n\n"

                + contenido

            ).strip(),

            confianza=float(

                resultado.get(
                    "confianza",
                    0.0,
                )

                or 0.0
            ),

            origen=ORIGEN_MEMORIA,

            intencion=(
                "consulta_memoria"
            ),

            detalle=(
                "Respuesta obtenida desde memoria.json."
            ),

            metadata={

                "consulta_guardada": (
                    resultado.get(
                        "consulta_guardada"
                    )
                ),
            },
        )

    # ========================================================
    # RESPONDER
    # ========================================================

    def responder(
        self,
        texto,
        contexto=None,
    ):

        inicio = time.monotonic()


        texto = str(
            texto
            or ""
        ).strip()


        contexto = dict(
            contexto
            or {}
        )


        if not texto:

            return BINBotResponse(

                texto=(
                    "Escribe una consulta y la reviso."
                ),

                confianza=100.0,

                origen=ORIGEN_CONVERSACION,

                intencion="vacio",

            ).as_dict()


        try:

            # =================================================
            # 0. SELECCIÓN PENDIENTE DEL MANUAL
            # =================================================
            #
            # Tiene prioridad incluso sobre el menú.
            #
            # Esto permite:
            #
            # BIN: ¿Qué pantalla?
            # [1] ...
            # [2] ...
            #
            # Usuario: 2
            #
            # sin que ese 2 sea interpretado como
            # una opción del menú principal.
            # =================================================

            respuesta_pendiente = (
                self.resolver_manual_pendiente(
                    texto
                )
            )


            if respuesta_pendiente:

                return self.finalizar(

                    respuesta_pendiente,

                    texto,

                    inicio,
                )


            # =================================================
            # 0.5 OPCIONES DEL MENÚ
            # =================================================

            respuesta_menu = self.ejecutar_opcion_menu(
                texto
            )


            if respuesta_menu:

                return self.finalizar(

                    respuesta_menu,

                    texto,

                    inicio,
                )


            # =================================================
            # 0.5 COMANDOS INTERNOS
            # =================================================

            respuesta_comando = self.responder_comando_interno(
                texto
            )


            if respuesta_comando:

                return self.finalizar(

                    respuesta_comando,

                    texto,

                    inicio,
                )


            # =================================================
            # 1. CONVERSACIÓN
            # =================================================

            intencion = self.detectar_intencion(
                texto
            )


            if intencion:

                respuesta = self.respuesta_conversacional(
                    intencion
                )

                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )


            # =================================================
            # 2. CONTEXTO OPERATIVO
            # =================================================

            respuesta_contexto = self.responder_contexto(

                texto,

                contexto,
            )


            if respuesta_contexto:

                return self.finalizar(

                    respuesta_contexto,

                    texto,

                    inicio,
                )


            # =================================================
            # 3. MATEMÁTICAS
            # =================================================

            resultado_math = self.math.intentar_resolver(
                texto
            )


            if resultado_math is not None:

                respuesta = BINBotResponse(

                    texto=(
                        "El resultado es "
                        + resultado_math[
                            "texto"
                        ]
                        + "."
                    ),

                    confianza=100.0,

                    origen=ORIGEN_MATEMATICA,

                    intencion=resultado_math.get(
                        "tipo",
                        "matematica",
                    ),

                    detalle=(
                        "Operación resuelta localmente."
                    ),

                    metadata={

                        "expresion": (
                            resultado_math.get(
                                "expresion"
                            )
                        ),

                        "resultado": (
                            resultado_math.get(
                                "resultado"
                            )
                        ),
                    },
                )


                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )


            # =================================================
            # 4. MANUAL
            # =================================================

            # -------------------------------------------------
            # 4.0 INTERACCIONES NUMERADAS
            # -------------------------------------------------

            respuesta_numero = (
                self.respuesta_interaccion_numerada_manual(
                    texto
                )
            )


            if respuesta_numero:

                return self.finalizar(

                    respuesta_numero,

                    texto,

                    inicio,
                )


            # -------------------------------------------------
            # 4.1 CONTROL ESCRITO LITERALMENTE
            # -------------------------------------------------

            respuesta_control = (
                self.respuesta_control_literal_manual(
                    texto
                )
            )


            if respuesta_control:

                return self.finalizar(

                    respuesta_control,

                    texto,

                    inicio,
                )


            # -------------------------------------------------
            # 4.2 BÚSQUEDA GENERAL EN EL MANUAL
            # -------------------------------------------------

            resultado_manual = self.manual_index.buscar(
                texto
            )


            confianza_manual = float(

                resultado_manual.get(
                    "confianza",
                    0.0,
                )

                or 0.0
            )


            seccion = resultado_manual.get(
                "section"
            )


            self.debug(

                "MANUAL",

                {

                    "consulta": texto,

                    "confianza": confianza_manual,

                    "seccion": (

                        seccion.title

                        if seccion

                        else None
                    ),

                    "scores": (
                        resultado_manual.get(
                            "scores"
                        )
                    ),
                },
            )


            if (
                seccion is not None
                and confianza_manual
                >= self.config.umbral_local
            ):

                contenido = (
                    self.manual_index.extraer_respuesta(

                        texto,

                        seccion,

                        max_sentences=(
                            self.config.manual_max_sentences
                        ),

                        max_chars=(
                            self.config.manual_max_chars
                        ),
                    )
                )


                intro = self.choice(
                    BancosBIN.MANUAL_INTROS
                )


                cierre = ""


                if (
                    self.random.random()
                    < 0.35
                ):

                    cierre = (

                        "\n\n"

                        + self.choice(
                            BancosBIN.MANUAL_CIERRES
                        )
                    )


                seccion_json = (
                    self.obtener_seccion_manual_json(
                        seccion.title
                    )
                )


                bloques = []

                imagenes = []


                if isinstance(
                    seccion_json,
                    dict,
                ):

                    bloques = list(

                        seccion_json.get(
                            "bloques"
                        )

                        or []
                    )


                    imagenes = (
                        self.extraer_imagenes_seccion_manual(
                            seccion_json
                        )
                    )


                referencia_imagen = (
                    self.texto_referencias_imagenes(
                        imagenes
                    )
                )


                texto_manual = (

                    intro

                    + "\n\n"

                    + contenido

                    + cierre

                ).strip()


                if referencia_imagen:

                    texto_manual = (

                        texto_manual

                        + "\n\n"

                        + referencia_imagen

                    ).strip()


                respuesta = BINBotResponse(

                    texto=texto_manual,

                    confianza=(
                        confianza_manual
                    ),

                    origen=ORIGEN_MANUAL,

                    intencion="consulta_bin",

                    detalle=(
                        "Respuesta obtenida del "
                        "manual local JSON."
                    ),

                    metadata={

                        "seccion_manual": (
                            seccion.title
                        ),

                        "scores": (
                            resultado_manual.get(
                                "scores"
                            )
                        ),

                        "manual": (
                            seccion_json
                        ),

                        "bloques": (
                            bloques
                        ),

                        "imagenes": (
                            imagenes
                        ),

                        "mostrar_imagen": bool(
                            imagenes
                        ),
                    },
                )


                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )


            # =================================================
            # 5. GOOGLE
            # =================================================

            if not self.config.permitir_google:
                respuesta_memoria = (
                    self.responder_desde_memoria(
                        texto
                    )
                )


                if respuesta_memoria:

                    return self.finalizar(

                        respuesta_memoria,

                        texto,

                        inicio,
                    )

                respuesta = BINBotResponse(

                    texto=self.choice(
                        BancosBIN.SIN_INTERNET
                    ),

                    confianza=(
                        confianza_manual
                    ),

                    origen=(
                        ORIGEN_SIN_INTERNET
                    ),

                    intencion=(
                        "google_deshabilitado"
                    ),
                )


                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )


            internet = self.google.hay_internet()


            self.debug(

                "INTERNET",

                {

                    "disponible": internet
                },
            )


            if not internet:

                respuesta_memoria = (
                    self.responder_desde_memoria(
                        texto
                    )
                )


                if respuesta_memoria:

                    return self.finalizar(

                        respuesta_memoria,

                        texto,

                        inicio,
                    )

                respuesta = BINBotResponse(

                    texto=self.choice(
                        BancosBIN.SIN_INTERNET
                    ),

                    confianza=(
                        confianza_manual
                    ),

                    origen=(
                        ORIGEN_SIN_INTERNET
                    ),

                    intencion="sin_internet",

                    detalle=(
                        "Confianza local inferior al umbral "
                        "y sin conexión."
                    ),

                    metadata={

                        "confianza_local": (
                            confianza_manual
                        ),

                        "umbral_local": (
                            self.config.umbral_local
                        ),
                    },
                )


                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )


            resultado_google = self.google.buscar(
                texto
            )


            self.debug(

                "GOOGLE",

                {

                    "ok": (
                        resultado_google.get(
                            "ok"
                        )
                    ),

                    "tipo": (
                        resultado_google.get(
                            "tipo"
                        )
                    ),

                    "metodo": (
                        resultado_google.get(
                            "metodo"
                        )
                    ),
                },
            )


            if (
                resultado_google.get(
                    "ok"
                )
                and str(
                    resultado_google.get(
                        "texto"
                    )
                    or ""
                ).strip()
            ):

                contenido = limitar_texto(

                    resultado_google.get(
                        "texto"
                    ),

                    self.config.google_max_chars,
                )

                aprendizaje = self.memoria.aprender(

                    consulta=texto,

                    respuesta=contenido,

                    fuente="GOOGLE",
                )


                self.debug(

                    "MEMORIA_APRENDIZAJE",

                    {

                        "consulta": texto,

                        "guardado": (
                            aprendizaje.get(
                                "ok"
                            )
                        ),

                        "accion": (
                            aprendizaje.get(
                                "accion"
                            )
                        ),

                        "consultas": (
                            aprendizaje.get(
                                "consultas"
                            )
                        ),
                    },
                )


                intro = self.choice(
                    BancosBIN.WEB_INTROS
                )


                cierre = ""


                if (
                    self.random.random()
                    < 0.32
                ):

                    cierre = (

                        "\n\n"

                        + self.choice(
                            BancosBIN.WEB_CIERRES
                        )
                    )


                respuesta = BINBotResponse(

                    texto=(

                        intro

                        + "\n\n"

                        + contenido

                        + cierre
                    ).strip(),

                    confianza=(
                        confianza_manual
                    ),

                    origen=ORIGEN_GOOGLE,

                    intencion="consulta_externa",

                    detalle=(
                        "Consulta Google activada porque "
                        "la confianza local fue inferior al 82 %."
                    ),

                    metadata={

                        "confianza_local": (
                            confianza_manual
                        ),

                        "umbral_local": (
                            self.config.umbral_local
                        ),

                        "tipo_resultado_google": (
                            resultado_google.get(
                                "tipo"
                            )
                        ),

                        "metodo_google": (
                            resultado_google.get(
                                "metodo"
                            )
                        ),

                        "memoria": (
                            aprendizaje
                        ),

                        "url_google": (
                            resultado_google.get(
                                "url"
                            )
                        ),

                        "google_debug_html": (
                            resultado_google.get(
                                "debug_html"
                            )
                        ),
                    },
                )


                return self.finalizar(

                    respuesta,

                    texto,

                    inicio,
                )

            respuesta_memoria = (
                self.responder_desde_memoria(
                    texto
                )
            )


            if respuesta_memoria:

                return self.finalizar(

                    respuesta_memoria,

                    texto,

                    inicio,
                )

            # =================================================
            # GOOGLE NO DIO RESPUESTA AUTOMÁTICA
            # =================================================

            respuesta = BINBotResponse(

                texto=self.choice(
                    BancosBIN.WEB_SIN_RESPUESTA
                ),

                confianza=(
                    confianza_manual
                ),

                origen=ORIGEN_GOOGLE,

                intencion="google_sin_respuesta",

                metadata={

                    "confianza_local": (
                        confianza_manual
                    ),

                    "error_google": (
                        resultado_google.get(
                            "error"
                        )
                    ),

                    "url_google": (
                        resultado_google.get(
                            "url"
                        )
                    ),

                    "google_debug_html": (
                        resultado_google.get(
                            "debug_html"
                        )
                    ),
                },
            )


            return self.finalizar(

                respuesta,

                texto,

                inicio,
            )


        except Exception as error:

            self.debug(

                "ERROR",

                {

                    "error": repr(
                        error
                    )
                },
            )


            respuesta = BINBotResponse(

                texto=self.choice(
                    BancosBIN.ERRORES
                ),

                confianza=0.0,

                origen=ORIGEN_ERROR,

                intencion="error",

                detalle=str(
                    error
                ),
            )


            return self.finalizar(

                respuesta,

                texto,

                inicio,
            )


    # ========================================================
    # FINALIZAR RESULTADO
    # ========================================================

    def finalizar(
        self,
        respuesta,
        consulta,
        inicio,
    ):

        elapsed = round(

            (
                time.monotonic()
                - inicio
            )
            * 1000.0,

            2,
        )


        respuesta.metadata = dict(
            respuesta.metadata
            or {}
        )


        respuesta.metadata[
            "elapsed_ms"
        ] = elapsed


        respuesta.metadata[
            "bin_bot_version"
        ] = BIN_BOT_VERSION


        payload = respuesta.as_dict()


        self.debug(

            "RESPUESTA",

            {

                "consulta": consulta,

                "origen": (
                    payload[
                        "origen"
                    ]
                ),

                "confianza": (
                    payload[
                        "confianza"
                    ]
                ),

                "intencion": (
                    payload[
                        "intencion"
                    ]
                ),

                "elapsed_ms": elapsed,
            },
        )


        return payload


    # ========================================================
    # ASYNC
    # ========================================================

    def responder_async(
        self,
        texto,
        contexto=None,
        callback=None,
    ):

        futuro = self.executor.submit(

            self.responder,

            texto,

            contexto,
        )


        if callable(
            callback
        ):

            def terminado(
                future,
            ):

                try:

                    callback(
                        future.result()
                    )

                except Exception:

                    pass


            futuro.add_done_callback(
                terminado
            )


        return futuro


    # ========================================================
    # ARCHIVO DE APRENDIZAJE
    # ========================================================

    def procesar_archivo(
        self,
        ruta,
    ):

        resultado = validar_archivo_aprendizaje(
            ruta
        )


        if not resultado.get(
            "ok"
        ):

            return {

                "texto": (
                    "No pude reconocer ese archivo como "
                    "un entrenamiento compatible de BIN."
                ),

                "confianza": 100.0,

                "origen": ORIGEN_ARCHIVO,

                "intencion": (
                    "archivo_no_valido"
                ),

                "detalle": (
                    resultado.get(
                        "motivo",
                        "",
                    )
                ),

                "metadata": resultado,
            }


        nombre = resultado.get(
            "nombre",
            "Sin nombre",
        )


        acciones = int(

            resultado.get(
                "acciones",
                0,
            )

            or 0
        )


        texto = (

            "Archivo de aprendizaje detectado.\n\n"

            f"Entrenamiento: {nombre}\n"

            f"Acciones: {acciones}\n\n"

            "¿Deseas agregarlo a la lista de tareas?"
        )


        return {

            "texto": texto,

            "confianza": 100.0,

            "origen": ORIGEN_ARCHIVO,

            "intencion": (
                "archivo_aprendizaje_detectado"
            ),

            "detalle": (
                "BIN Light debe mostrar VER / AGREGAR / CANCELAR."
            ),

            "metadata": resultado,
        }

    # ========================================================
    # ESTADO
    # ========================================================

    def estado(
        self,
    ):

        return {

            "memoria": (
                self.memoria.estado()
            ),

            "bin_bot_version": (
                BIN_BOT_VERSION
            ),

            "bin_light_compatible": (
                BIN_LIGHT_COMPATIBLE
            ),

            "umbral_local": (
                self.config.umbral_local
            ),

            "google_permitido": (
                self.config.permitir_google
            ),

            "manual_cargado": bool(
                self.manual_index.manual_texto.strip()
            ),

            "manual_chars": len(
                self.manual_index.manual_texto
            ),

            "manual_sections": len(
                self.manual_index.sections
            ),

            "bancos": {

                "saludos": len(
                    BancosBIN.SALUDOS
                ),

                "despedidas": len(
                    BancosBIN.DESPEDIDAS
                ),

                "agradecimientos": len(
                    BancosBIN.AGRADECIMIENTOS
                ),

                "estado": len(
                    BancosBIN.ESTADO
                ),

                "presentacion": len(
                    BancosBIN.PRESENTACION
                ),

                "capacidades": len(
                    BancosBIN.CAPACIDADES
                ),

                "confirmaciones": len(
                    BancosBIN.CONFIRMACIONES
                ),

                "manual_intros": len(
                    BancosBIN.MANUAL_INTROS
                ),

                "manual_cierres": len(
                    BancosBIN.MANUAL_CIERRES
                ),

                "web_intros": len(
                    BancosBIN.WEB_INTROS
                ),

                "web_cierres": len(
                    BancosBIN.WEB_CIERRES
                ),

                "sin_internet": len(
                    BancosBIN.SIN_INTERNET
                ),

                "web_sin_respuesta": len(
                    BancosBIN.WEB_SIN_RESPUESTA
                ),

                "errores": len(
                    BancosBIN.ERRORES
                ),
            },
        }


    # ========================================================
    # CERRAR
    # ========================================================

    def cerrar(
        self,
    ):

        try:

            self.google.cerrar()

        except Exception:

            pass


        try:

            self.executor.shutdown(

                wait=False,

                cancel_futures=True,
            )

        except Exception:

            pass


# ============================================================
# SELF TEST
# ============================================================

SELF_TEST_MANUAL = """

============================================================
BIN LIGHT
============================================================

BIN Light es una versión ligera orientada a automatización
de tareas repetitivas en Windows.

============================================================
CREAR TAREAS
============================================================

Para crear una tarea utiliza el botón NUEVA de la lista
de tareas. Configura el nombre, horario y días antes de guardar.

============================================================
DEMOSTRACIONES
============================================================

Para mostrar una rutina inicia la demostración y realiza
los pasos de forma clara y pausada.

============================================================
NAVEGADORES
============================================================

BIN puede trabajar con navegadores compatibles.
Las contraseñas y autenticaciones deben ser realizadas
manualmente por el usuario.

"""


def ejecutar_selftest():

    config = BINBotConfig(

        debug=False,

        random_seed=1,

        memoria_path="data/memoria_selftest.json",
    )


    def internet_falso():

        return True


    def google_falso(
        consulta,
    ):

        return (
            "Respuesta externa simulada para comprobar "
            "la ruta de Google."
        )


    bot = BINBot(

        manual_texto=SELF_TEST_MANUAL,

        config=config,

        google_provider=google_falso,

        internet_checker=internet_falso,
    )


    pruebas = []


    resultado = bot.responder(
        "hola"
    )

    pruebas.append(
        (
            "SALUDO",
            resultado[
                "origen"
            ]
            == ORIGEN_CONVERSACION,
        )
    )


    resultado = bot.responder(
        "15% de 420"
    )

    pruebas.append(
        (
            "MATEMATICA",
            (
                resultado[
                    "origen"
                ]
                == ORIGEN_MATEMATICA
                and "63"
                in resultado[
                    "texto"
                ]
            ),
        )
    )


    resultado = bot.responder(
        "como crear una tarea"
    )

    pruebas.append(
        (
            "MANUAL",
            resultado[
                "origen"
            ]
            == ORIGEN_MANUAL,
        )
    )


    resultado = bot.responder(
        "que es la fotosintesis"
    )

    pruebas.append(
        (
            "GOOGLE",
            resultado[
                "origen"
            ]
            == ORIGEN_GOOGLE,
        )
    )


    estado = bot.estado()


    for nombre, cantidad in (
        estado[
            "bancos"
        ].items()
    ):

        pruebas.append(
            (
                "BANCO_"
                + nombre.upper(),

                cantidad >= 25,
            )
        )


    correcto = True


    for nombre, resultado in pruebas:

        print(

            "[SELFTEST]",

            nombre,

            "OK"
            if resultado
            else "FALLO",
        )

        if not resultado:

            correcto = False


    bot.cerrar()

    try:

        ruta_memoria_test = (

            Path(
                __file__
            ).resolve().parent

            / "data"

            / "memoria_selftest.json"
        )


        if ruta_memoria_test.exists():

            ruta_memoria_test.unlink()


    except Exception:

        pass

    print()


    if correcto:

        print(
            "SELFTEST COMPLETADO: OK"
        )

    else:

        print(
            "SELFTEST COMPLETADO: FALLO"
        )


    return correcto


# ============================================================
# CMD
# ============================================================

AYUDA_CMD = """

COMANDOS

/ayuda
    Ver comandos.

/estado
    Ver configuración y estado interno.

/debug on
    Activar diagnóstico.

/debug off
    Desactivar diagnóstico.

/recargar
    Volver a cargar el manual.

/archivo RUTA
    Analizar un archivo de aprendizaje.

/salir
    Cerrar BIN Bot.

También puedes conversar normalmente.

"""


def configurar_utf8():

    for nombre in (
        "stdout",
        "stderr",
    ):

        stream = getattr(
            sys,
            nombre,
            None,
        )

        if (
            stream is not None
            and hasattr(
                stream,
                "reconfigure",
            )
        ):

            try:

                stream.reconfigure(
                    encoding="utf-8",
                )

            except Exception:

                pass


def ejecutar_cmd(
    bot,
):

    configurar_utf8()


    print()

    print(
        "BIN Bot "
        + BIN_BOT_VERSION
    )

    print(
        "ChatBOT ligero para BIN Light"
    )

    print()

    print(
        "Escribe /ayuda para abrir la ayuda especializada."
    )

    print()


    print(

        "BIN:",

        bot.saludo_con_ayuda(),
    )


    while True:

        try:

            usuario = input(
                "\nTú: "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError,
        ):

            print()

            print(
                "BIN: Nos vemos."
            )

            break


        if not usuario:

            continue


        comando = usuario.lower().strip()


        if comando in {

            "/salir",

            "salir",

            "exit",

            "quit",
        }:

            print()

            print(

                "BIN:",

                bot.choice(
                    BancosBIN.DESPEDIDAS
                ),
            )

            break


        # ====================================================
        # ESTADO COMPLETO PARA DESARROLLO
        # ====================================================

        if comando == "/estado":

            print(

                json.dumps(

                    bot.estado(),

                    indent=2,

                    ensure_ascii=False,
                )
            )

            continue


        # ====================================================
        # ARCHIVO DE APRENDIZAJE
        # ====================================================

        if comando.startswith(
            "/archivo "
        ):

            ruta = usuario.split(
                None,
                1,
            )[
                1
            ].strip().strip(
                '"'
            )


            resultado = bot.procesar_archivo(
                ruta
            )


            print()

            print(

                "BIN:",

                resultado[
                    "texto"
                ],
            )

            continue


        # ====================================================
        # TODO LO DEMÁS PASA POR EL MOTOR DEL BOT
        # ====================================================

        resultado = bot.responder(
            usuario
        )


        print()

        print(

            "BIN:",

            resultado[
                "texto"
            ],
        )

# ============================================================
# ARGUMENTOS CMD
# ============================================================

def construir_argumentos():

    parser = argparse.ArgumentParser(

        description=(
            "BIN Bot ligero para BIN Light."
        )
    )


    parser.add_argument(

        "--manual",

        help=(
            "Ruta opcional a un archivo de manual."
        ),
    )


    parser.add_argument(

        "--main",

        help=(
            "Ruta opcional a main.py para leer "
            "MANUAL_BIN_LIGHT sin ejecutar main.py."
        ),
    )


    parser.add_argument(

        "--umbral",

        type=float,

        default=82.0,
    )


    parser.add_argument(

        "--debug",

        action="store_true",
    )


    parser.add_argument(

        "--sin-google",

        action="store_true",
    )


    parser.add_argument(

        "--consulta",
    )


    parser.add_argument(

        "--selftest",

        action="store_true",
    )


    return parser


# ============================================================
# MAIN
# ============================================================

def main():

    argumentos = construir_argumentos().parse_args()


    if argumentos.selftest:

        correcto = ejecutar_selftest()

        return (
            0
            if correcto
            else 1
        )


    config = BINBotConfig(

        umbral_local=float(
            argumentos.umbral
        ),

        debug=bool(
            argumentos.debug
        ),

        permitir_google=(
            not argumentos.sin_google
        ),
    )


    bot = BINBot(

        manual_path=(
            argumentos.manual
        ),

        main_path=(
            argumentos.main
        ),

        config=config,
    )


    if argumentos.consulta:

        resultado = bot.responder(
            argumentos.consulta
        )


        print(
            resultado[
                "texto"
            ]
        )


        if config.debug:

            print()

            print(

                json.dumps(

                    resultado,

                    indent=2,

                    ensure_ascii=False,
                )
            )


        bot.cerrar()

        return 0


    try:

        ejecutar_cmd(
            bot
        )

    finally:

        bot.cerrar()


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )