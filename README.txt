============================================
NOTAS DE INSTALACIÓN Y ENTORNO VIRTUAL — BIN
============================================

Cuando se instale por primera vez el proyecto desde el repositorio, se debe clonar el proyecto y crear un entorno virtual nuevo para esa computadora.

COMANDOS DE PRIMERA INSTALACIÓN:
============================================

git clone <URL_DEL_REPOSITORIO>
cd BIN_IA_asistem

python -m venv .venv
source .venv/Scripts/activate

python -m pip install -r requirements.txt

python main.py

============================================
EXPLICACIÓN DEL PROCESO
============================================

1. CLONAR EL PROYECTO
============================================

Primero se descarga el proyecto desde GitHub: git clone <URL_DEL_REPOSITORIO>

Luego se entra en la carpeta del proyecto: cd BIN_IA_asistem


2. CREAR EL ENTORNO VIRTUAL
============================================

Se crea el entorno virtual con: python -m venv .venv

Esto crea una carpeta llamada: .venv

La carpeta .venv contiene el entorno de Python exclusivo para BIN y las librerías instaladas para este proyecto.
Cada computadora debe crear su propio .venv.
No se debe copiar el .venv desde otra computadora y tampoco se debe subir a GitHub.


3. ACTIVAR EL ENTORNO VIRTUAL
============================================

En Git Bash: source .venv/Scripts/activate

Cuando esté activo debe aparecer algo parecido a:

(.venv)

al principio de la terminal.
Eso significa que Python y pip están trabajando dentro del entorno virtual de BIN.


Si se usa PowerShell: .\.venv\Scripts\Activate.ps1


Si se usa CMD: .venv\Scripts\activate.bat


4. INSTALAR TODO LO QUE NECESITA BIN
============================================

Luego se instala todo lo que necesita BIN usando: python -m pip install -r requirements.txt

El archivo requirements.txt contiene la lista de librerías necesarias para ejecutar el proyecto.

Por ejemplo:

PySide6
psutil
mss
pynput
black

Esto evita tener que instalar cada dependencia manualmente en una computadora nueva.


5. EJECUTAR BIN
============================================

Una vez instaladas todas las dependencias: python main.py

============================================
USO NORMAL DESPUÉS DE LA PRIMERA INSTALACIÓN
=============================================

Cuando el proyecto ya fue instalado en una computadora, NO se vuelve a crear el .venv.

No volver a ejecutar:

python -m venv .venv

Solo hay que entrar en el proyecto, activar el entorno y ejecutar BIN:

cd BIN_IA_asistem

source .venv/Scripts/activate

python main.py


CUANDO SE HACE GIT PULL
=======================

Cuando se actualice el proyecto desde GitHub: git pull

Después conviene volver a ejecutar: python -m pip install -r requirements.txt

Esto permite instalar automáticamente cualquier dependencia nueva que se haya agregado al proyecto.

Flujo recomendado:

git pull

source .venv/Scripts/activate

python -m pip install -r requirements.txt

python main.py


CUANDO SE AGREGA UNA NUEVA LIBRERÍA
===================================

Si BIN empieza a utilizar una librería nueva, primero se instala normalmente.

Ejemplo:

python -m pip install playwright

Después se debe actualizar requirements.txt:

python -m pip freeze > requirements.txt

Luego se suben los cambios a Git:

git add requirements.txt

git commit -m "Actualizar dependencias"

git push

De esta forma, cuando otra computadora haga git pull, podrá instalar la nueva dependencia con:

python -m pip install -r requirements.txt


GITIGNORE
=========

Debemos asegurarnos de que la carpeta .venv esté incluida en el archivo:

.gitignore

La regla principal es:

.venv/

Esto evita que Git intente subir todo el entorno virtual al repositorio.


.gitignore recomendado para BIN:

.venv/
venv/
env/

__pycache__/
*.pyc
*.pyo
*.pyd

.vscode/

.DS_Store
Thumbs.db

*.tmp
*.log

build/
dist/
*.egg-info/

.env
.env.*


POR QUÉ .venv NO DEBE SUBIRSE A GIT
===================================

La carpeta .venv contiene librerías instaladas específicamente para una computadora y puede contener rutas internas propias de esa máquina.

Por eso:

.venv NO se comparte.

requirements.txt SÍ se comparte.

Cada computadora reconstruye su propio entorno usando:

python -m venv .venv

y:

python -m pip install -r requirements.txt


COMPROBAR QUE .venv ESTÁ SIENDO IGNORADO
========================================

Se puede comprobar con:

git status

La carpeta .venv no debería aparecer como archivo pendiente.


También se puede comprobar directamente con:

git check-ignore -v .venv/


SI .venv YA FUE SUBIDO A GIT
=============================

Agregar .venv/ al .gitignore no basta si Git ya estaba siguiendo esa carpeta.

En ese caso hay que ejecutar:

git rm -r --cached .venv

Esto deja de rastrear la carpeta en Git, pero NO elimina el .venv de la computadora.

Después:

git add .gitignore

git commit -m "Ignorar entorno virtual"

git push


RESUMEN RÁPIDO
==============

PRIMERA INSTALACIÓN:

git clone <URL_DEL_REPOSITORIO>
cd BIN_IA_asistem
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py


USO NORMAL:

cd BIN_IA_asistem
source .venv/Scripts/activate
python main.py


DESPUÉS DE GIT PULL:

git pull
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python main.py


SI SE AGREGA UNA LIBRERÍA NUEVA:

python -m pip install NOMBRE_LIBRERIA
python -m pip freeze > requirements.txt
git add requirements.txt
git commit -m "Actualizar dependencias"
git push


REGLA FUNDAMENTAL DE .gitignore:

.venv/

El entorno virtual nunca debe viajar dentro del repositorio.

=============================
Para inicializar el proyecto despues de dejar todo instalado
=============================
source .venv/Scripts/activate ---> Para activarlo
python main.py ---> para comenzar el trabajo

=============================
Para hacer comprobaciones durante la codificación
=============================
python -m black main.py
python -m py_compile main.py
python main.py

Así:

black ordena/formatea el código.
py_compile comprueba que no haya errores de sintaxis.
python main.py inicia BIN.

=============================
IA contratada
=============================
La IA se llama ollama y se activa en CMD con=> ollama run qwen3-vl:4b --->Eliminar
ollama run qwen3-vl:4b-instruct ----> elegida