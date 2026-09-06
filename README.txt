BIN IA ASISTEM — LIGHT
V1.6.15

============================================================
BIN IA ASISTEM — LIGHT v1.6.15
============================================================

BIN Light es una versión ligera de BIN orientada a la
automatización de tareas repetitivas en Windows.

Esta versión NO utiliza IA local.

En su lugar, trabaja mediante un sistema avanzado de análisis
automático, supervisión de contexto, decisiones condicionales,
correcciones y ejecución física de acciones.

BIN observa el entorno de trabajo, registra las acciones
demostradas por el usuario y utiliza la información disponible
de ventanas, aplicaciones, navegadores y recursos para intentar
reproducir la tarea de la forma más estable posible.

La prioridad de BIN Light es:

- Bajo consumo de recursos.
- Automatización mecánica de tareas.
- Ejecución de secuencias largas.
- Supervisión del estado de las ventanas.
- Corrección automática cuando el entorno cambia.
- Funcionamiento en equipos modestos.
- Capacidad para permanecer activo durante períodos prolongados.
- El asistente de BIN funciona en una sola pantalla (La principal) Por la que idealmente, si se pienza grabar instrucciones, y/o ejecutar tareas automatizada, se recomienda desconectar las pantallas externas y dejarla sola con la principal.

============================================================
REQUISITOS
============================================================

Sistema recomendado:

Windows 10 / Windows 11
Python 3


Dependencias externas:

PySide6
psutil
mss
pynput


Instalación:

python -m pip install PySide6 psutil mss pynput


Para comprobar las dependencias:

python -c "import PySide6, psutil, mss, pynput; print('BIN Light: dependencias OK')"


Para comprobar el archivo principal:

python -m py_compile main.py


Para ejecutar BIN:

python main.py


============================================================
IMPORTANTE — ESTA VERSIÓN NO UTILIZA IA LOCAL
============================================================

BIN Light v1.6.15 no incorpora un modelo de inteligencia
artificial local.

Las decisiones durante una automatización son realizadas por
el propio motor de BIN utilizando:

- Contexto de las acciones.
- Estado de las ventanas.
- Procesos activos.
- Posición y dimensiones de ventanas.
- Rutas de archivos y carpetas.
- URL del navegador.
- Perfil del navegador.
- Cuenta asociada cuando puede ser identificada.
- Historial de la demostración.
- Reglas y parámetros condicionales.
- Verificaciones antes y después de las acciones.
- Sistemas de corrección y recuperación.

El objetivo es que BIN pueda adaptarse a pequeñas diferencias
entre la demostración original y el entorno encontrado durante
la ejecución.


============================================================
CHAT DE BIN
============================================================

BIN incluye un chat operativo integrado.

En esta versión el chat funciona principalmente como registro
y asistente local del sistema.

Permite mostrar información sobre:

- Acciones observadas.
- Contextos detectados.
- Correcciones realizadas.
- Esperas.
- Verificaciones.
- Errores.
- Estado de una ejecución.

BIN también puede interactuar con Google Chrome durante las
automatizaciones.

Cuando existe conexión a Internet, las tareas demostradas
pueden utilizar páginas y servicios web normalmente.


============================================================
AUTOMATIZACIÓN DE VENTANAS
============================================================

BIN Light supervisa continuamente las ventanas disponibles
en Windows.

Durante una tarea puede utilizar información como:

- Aplicación o proceso.
- Título de la ventana.
- Clase de ventana.
- Posición.
- Tamaño.
- Estado de la ventana.
- Recurso abierto.
- Ruta.
- URL.
- Perfil del navegador.
- Cuenta asociada.

Cuando BIN encuentra una ventana que corresponde al contexto
esperado, puede intentar corregir automáticamente su posición,
tamaño, URL u otros estados compatibles antes de continuar con
la siguiente acción.

Esto ayuda a conservar las condiciones necesarias para que
clics, scrolls, escritura y comandos físicos ocurran en el
lugar esperado.


============================================================
NAVEGADORES
============================================================

BIN puede trabajar con navegadores compatibles durante una
automatización.

Para obtener mejores resultados se recomienda utilizar una
configuración sencilla y consistente.

Especialmente en Google Chrome:

Utiliza, siempre que sea posible, una sola cuenta de Google
por cada perfil del navegador utilizado en una tarea.

BIN puede identificar información del perfil y, cuando es
observable, la cuenta asociada.

Las contraseñas, autenticación multifactor, passkeys,
confirmaciones desde teléfonos u otros mecanismos de seguridad
deben ser realizados manualmente por el usuario.


============================================================
RECOMENDACIONES DE USO
============================================================

1. REDUCE LA CANTIDAD DE PASOS

Utiliza la menor cantidad de acciones posible.

Una tarea corta y directa normalmente será más resistente que
una tarea llena de movimientos innecesarios.


2. UTILIZA PASOS CLAROS Y PAUSADOS

Evita realizar demasiadas acciones seguidas durante la
demostración.

BIN necesita tiempo para observar los cambios producidos en
Windows.


3. UTILIZA ESPERAS RAZONABLES

Para aplicaciones o páginas que necesitan tiempo de carga,
puede ser conveniente esperar aproximadamente entre 5 y
12 segundos antes de continuar.

Esto también permite que BIN tenga tiempo para detectar y
corregir cambios inesperados.


4. MANTÉN EL MISMO SOFTWARE

Si enseñas una rutina utilizando una versión determinada de
un programa, intenta conservar esa misma versión.

Una actualización importante del software puede modificar:

- Ventanas.
- Botones.
- Menús.
- Coordenadas.
- Distribución visual.
- Comportamiento.

Si el programa cambia demasiado, lo recomendable es volver a
demostrar la tarea.


5. EN RUTAS WEB, UTILIZA LA URL DIRECTAMENTE

Cuando sea posible, navega directamente hacia la URL necesaria.

Esto suele ser más estable que depender de varios clics para
llegar a una página.


6. MANTÉN UNA MESA DE TRABAJO CONSISTENTE

Para tareas repetitivas es recomendable mantener un orden
similar en el escritorio y en las aplicaciones utilizadas.

BIN puede corregir determinados estados, pero una estructura
predecible siempre mejora la estabilidad.


7. CIERRA VENTANAS INNECESARIAS

Antes de iniciar una automatización importante, intenta cerrar
programas, ventanas o pestañas que no sean necesarias.

Esto reduce posibles ambigüedades.


8. RECOMENDACIÓN IMPORTANTE PARA VENTANAS

Antes y después de mover o cambiar el tamaño de una ventana
durante una demostración, haz clic en su barra de título.

Esto ayuda a BIN a observar correctamente la ventana activa y
actualizar información como:

- Posición.
- Tamaño.
- Aplicación.
- Contexto.
- URL, cuando corresponde.


9. EVITA PASOS INNECESARIOS

Si una operación puede realizarse con una acción directa,
prefiere esa opción.

Menos pasos significan menos puntos posibles de fallo.

10. Deja siempre las ventanas extendidas. No dejes pestañas extremadamentes pequeñas o reducidas ya sea durante la demostración, despues de la demostración, o si no estás usando el asistente. Ya que windows guarda en su memoria las ultimas caracteristicas de las ventanas, y eso aumentaria la cantidad de procesamientos por verificación, aumentando los tiempos de ejecución, y un posible error de ejecución de tarea

11. Si se requiere organizar Mesa de trabajo web, Lo mejor es hacerlo de manera escrita, y no en modo demostración. este es mucho más exacto.

12. Si es un entrenamiento que no requiere uso de software, y son tareas repetitivas, Se sugiere limpiar de acciones innecesarias el panel de acción; de tal manera, que la instrucción sea más directa.

13. Verifica constantemente las sesiones de las cuentas en los buscadores, que estén abiertas, ya que en ocaciones, el sistema las cierra automaticamente, o por borrado de cookies.

14. En lo que sea posible, se recomienda ejecutar acciónes de llamados solo con clics en lo que sea posible.

15. Despues de una entrenar o grabar una rutina, es recomendable leer los minipronts y limpiar los scrolls y clics que se requieran para llamar una ventana, para que la IA llame la ventana directamente.

16. Si no se tiene dominio completo del software, se recomienda dividir la tarea en secciónes ejemoplo Tarea 1: organizar mesa de trabajo 1:00 PM / tarea 2: Ejecutar acción Publicar en redes sociales 1:05 PM. Tarea 3: cerrar ventanas de mesa de trabajo 1:45 PM

17. BIN puede iniciar tu equipo si está en estado de suspención, o invernación. Pero se recomienda crear una sección para BIN donde no tenga contraseña, ya que BIN actualmente no está autorizado para memorizar contraseñas.

18. NO GRABES INICIOS DE SESIÓN, CONTRASEÑAS NI CÓDIGOS DE AUTENTICACIÓN. BIN Light registra acciones de teclado y no dispone actualmente de una bóveda segura de credenciales. Inicia sesión manualmente antes de grabar una rutina. Si una sesión expira, autentícate manualmente antes de volver a ejecutarla.

19. Se recomienda que dentro del proceso si el archivo requiere guardar cambios, Dentro de la demostración, y la instrucción manual, Se haga el guardado de los archivos manipulados por BIN. De esta manera evitaremos coliciones con el cerrado de ventana automatico de archivos que requieren guardados. Ya que como medida de protección de sus datos he información tratada, el software no hace acciones automaticas para este caso.

============================================================
CONSIDERACIONES PARA AUTOMATIZACIONES WEB
============================================================

Las páginas web son entornos dinámicos.

Una misma página puede cambiar debido a:

- Tiempo de carga.
- Redirecciones.
- Sesiones.
- Cookies.
- Publicidad.
- Actualizaciones del sitio.
- Estado de la cuenta.
- Conexión a Internet.

Por esta razón, las automatizaciones web pueden necesitar más
tiempo de espera y supervisión que una aplicación local.


============================================================
FILOSOFÍA DE BIN LIGHT
============================================================

Durante la demostración, BIN intenta capturar todo.

Durante la ejecución, BIN analiza el entorno e intenta mantener
las condiciones necesarias para continuar la tarea.

Cuando puede corregir un estado de forma segura, intenta
corregirlo.

Cuando una acción física sigue siendo necesaria, conserva y
ejecuta la acción física.

El objetivo no es sustituir todas las acciones del usuario,
sino reproducir de forma confiable las tareas que el usuario
le ha enseñado.


============================================================
VERSIÓN
============================================================

BIN IA Asistem — Light

Versión estable:

v1.6.15


Esta versión ha sido probada realizando una secuencia completa
de automatización con supervisión y corrección de ventanas y
contextos web.


============================================================
ESTADO DEL PROYECTO
============================================================

BIN Light continúa en desarrollo.

Las nuevas funciones deben incorporarse conservando como
prioridades:

- Estabilidad.
- Bajo consumo.
- Ejecución prolongada.
- Compatibilidad con Windows.
- Recuperación ante cambios del entorno.
- Automatizaciones comprensibles y reproducibles.