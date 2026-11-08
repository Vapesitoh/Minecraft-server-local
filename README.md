<div align="center">
  <img src="assets/block_icon.png" alt="BlockServer GUI" width="110">

# Minecraft-server-local

### BlockServer GUI — Administrador local de servidores Minecraft para Windows y Linux

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-Compatible-0078D4?logo=windows&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Compatible-FCC624?logo=linux&logoColor=black)
![PySide6](https://img.shields.io/badge/Interfaz-PySide6-41CD52)
![Versión](https://img.shields.io/badge/Versión-1.1.1-19B56C)

**Configura, inicia y administra servidores de Minecraft Java Edition desde una interfaz gráfica moderna, sin depender de comandos para las tareas habituales.**

</div>

---

## 📖 Descripción

**BlockServer GUI** es una aplicación de escritorio escrita en **Python y PySide6** para gestionar servidores locales de **Minecraft Java Edition** en **Windows y Linux**. Incluye una interfaz oscura con navegación lateral, soporte para arrastrar y soltar archivos, consola interactiva, detección automática de Java, administración de perfiles y copias de seguridad.

Funciona en tu computadora: **no es un servicio de alojamiento ni un panel web**. No necesitas crear una cuenta para administrar tus archivos locales.

## ✨ Funcionalidades

| Módulo | Qué permite hacer |
| --- | --- |
| **Dashboard** | Ver el estado del servidor, iniciar, detener, reiniciar, importar archivos y consultar estadísticas del proceso. |
| **Archivos** | Explorar carpetas del servidor, importar archivos, carpetas y ZIP, crear directorios y seleccionar un `.jar` de arranque. |
| **Consola** | Consultar registros en tiempo real y enviar comandos a la entrada estándar del servidor. |
| **Versiones** | Consultar el catálogo oficial de Minecraft Java e instalar servidores **Vanilla** verificando su descarga. |
| **Copias** | Crear y restaurar respaldos ZIP por perfil, con protección previa a una restauración. |
| **Ajustes** | Configurar memoria RAM, Java, archivo de arranque y varias opciones de `server.properties`. |
| **Perfiles** | Mantener varios servidores en carpetas distintas y cambiar entre ellos. |

### ☕ Detección automática de Java

Al abrir el programa, se buscan las instalaciones de Java disponibles en el equipo. Se revisan `JAVA_HOME`, `JDK_HOME`, `PATH`, carpetas habituales y, en Windows, entradas del Registro. La interfaz muestra la **versión y arquitectura** detectadas (32 o 64 bits), permite seleccionar una instalación manualmente y dispone de un botón **Buscar Java** para repetir el análisis.

El modo automático intenta elegir un Java de 64 bits que cumpla los requisitos de versión conocidos del servidor. **El programa detecta Java, pero no lo instala.** La versión de Java necesaria depende de la versión y la plataforma de Minecraft que utilices.

### 🖱️ Protección de los campos numéricos

Los valores de **RAM mínima, RAM máxima, puerto y número máximo de jugadores** no cambian al mover la rueda del ratón o desplazar el touchpad. Para editarlos, **escribe el número directamente** o utiliza **las flechas del control o del teclado**, y guarda la configuración.

### 🎨 Interfaz gráfica

Los controles utilizan iconos vectoriales de **Font Awesome 6**, integrados mediante **QtAwesome**, en lugar de iconos basados en símbolos o emojis del sistema.

## ✅ Requisitos

- **Sistema operativo:** Windows o Linux con entorno de escritorio gráfico.
- **Python:** 3.10 o superior, preferentemente de 64 bits.
- **Java:** JDK/JRE adecuado para el servidor de Minecraft que vayas a ejecutar; se recomienda una instalación de **64 bits** si utilizarás varios GB de RAM.
- **Conexión a Internet:** necesaria para instalar las dependencias de Python y descargar versiones Vanilla desde el catálogo oficial.
- **Memoria y almacenamiento:** dependen del servidor, los mods, el mundo y la cantidad de jugadores.

> **Importante:** Este repositorio contiene el código de la aplicación. **No incluye Java, servidores `.jar` de Minecraft ni un ejecutable `.exe` precompilado.**

## 🚀 Instalación en Windows

1. Instala [Python 3.10+](https://www.python.org/downloads/) y habilita **Add Python to PATH** durante la instalación.
2. Descarga o clona este repositorio y abre su carpeta.
3. Ejecuta **`iniciar_windows.bat`** con doble clic.
4. El script crea un entorno virtual `.venv` (si no existe), instala las dependencias y abre la aplicación.
5. Instala Java si no está disponible. Al iniciar, BlockServer GUI intentará encontrarlo automáticamente.

También puedes iniciar manualmente desde **PowerShell**, dentro de la carpeta del proyecto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## 🐧 Instalación en Linux (Ubuntu / Debian)

Instala los componentes de Python y entra en la carpeta del repositorio:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
git clone https://github.com/TU_USUARIO/Minecraft-server-local.git
cd Minecraft-server-local
chmod +x iniciar_linux.sh
./iniciar_linux.sh
```

**Sustituye `TU_USUARIO` por el propietario real de tu repositorio de GitHub.** Si descargaste un ZIP en lugar de clonar el repositorio, entra directamente en la carpeta extraída y ejecuta los dos últimos comandos.

Para instalar, por ejemplo, Java 21 en Ubuntu:

```bash
sudo apt install openjdk-21-jdk
```

Esta es **solo una opción de instalación**: selecciona el Java que necesite tu versión concreta de Minecraft. Si el entorno gráfico de Qt requiere bibliotecas del sistema adicionales, instálalas según tu distribución. La aplicación **no está pensada para ejecutarse por SSH en un servidor sin escritorio gráfico**.

## 🎮 Primer uso: crear y ejecutar un servidor

1. **Abre BlockServer GUI.** Se realizará la búsqueda automática de Java.
2. **Crea o selecciona un perfil** de servidor. Cada perfil apunta a una carpeta de trabajo.
3. **Añade el servidor:**
   - **Vanilla:** entra en **Versiones**, actualiza el catálogo, selecciona una versión y pulsa **Instalar Vanilla seleccionada**.
   - **Servidor existente:** arrastra un `.jar`, un ZIP de servidor o una carpeta al Dashboard, o utiliza **Importar**.
4. En **Ajustes**, selecciona el Java apropiado, la cantidad de RAM y el método de inicio si corresponde.
5. Pulsa **Ejecutar servidor**.
6. Si aparece el acuerdo de licencia de Minecraft (**EULA**), consulta el enlace oficial, escribe literalmente **`true`** y confirma **solo si aceptas sus términos**.
7. Comprueba el arranque en **Consola**. Cuando el servidor termine de cargar, podrás introducir comandos como `list`, `say`, `save-all` o `stop`.

> La aceptación de la EULA es un paso manual y explícito. La aplicación no debe aceptarla automáticamente en nombre del usuario.

## 🧩 Plataformas y archivos admitidos

| Tipo de servidor | Forma de uso | Observaciones |
| --- | --- | --- |
| **Vanilla** | Descarga desde la aplicación o importación de `.jar`. | Descarga desde los metadatos oficiales de Mojang con verificación de tamaño y SHA-1. |
| **Paper / Purpur / Spigot** | Importar el `.jar` correspondiente. | Necesitas descargarlo previamente desde su fuente confiable. |
| **Fabric / Quilt / Mohist** | Importar `.jar` o archivos/scripts proporcionados por el servidor. | El paquete debe estar correctamente instalado. |
| **Forge / NeoForge** | Usar el script `run.bat`, `run.cmd`, `run.sh` o una configuración de arranque apropiada. | Algunas versiones necesitan librerías e instaladores adicionales. |
| **Modpacks / serverpacks** | Importar un ZIP o carpeta. | Importar archivos **no garantiza** que el paquete esté instalado o listo para arrancar. |
| **Mundos existentes** | Importar la carpeta del mundo. | Puede requerir ajustar `level-name` en `server.properties`. |

El gestor admite **diferentes versiones y plataformas**, pero **no descarga ni instala automáticamente todas las plataformas de terceros**. Solo el flujo de descarga de **Vanilla** está integrado con el catálogo oficial.

## ⚙️ Configuración

En **Ajustes** puedes modificar, entre otras opciones:

- Java automático o ruta manual a `java.exe` / `java`.
- RAM mínima (`-Xms`) y RAM máxima (`-Xmx`).
- Archivo `.jar`, script de inicio o argumentos personalizados.
- Puerto del servidor, número máximo de jugadores y MOTD.
- `online-mode`, PVP, modo de juego, dificultad y nombre del mundo.

**Guarda los cambios con el servidor detenido.** El gestor controla **un proceso de servidor a la vez**, aunque permite almacenar varios perfiles.

### Dónde se guardan los datos

| Sistema | Ubicación de configuración |
| --- | --- |
| Windows | `%APPDATA%\BlockServerGUI\config.json` |
| Linux | `~/.config/blockserver-gui/config.json` |

Por defecto, los archivos de los servidores se guardan dentro de `~/Documents/BlockServerGUI/`; los respaldos se almacenan en `~/Documents/BlockServerGUI/_backups/`, separados por perfil. Puedes vincular también carpetas de servidores que ya existen.

## 💾 Copias de seguridad

Desde la sección **Copias** puedes:

1. Crear un respaldo ZIP de un perfil.
2. Seleccionar un respaldo previo.
3. Restaurarlo después de confirmar la operación.

El programa **exige detener el servidor** antes de respaldar o restaurar. Al restaurar, genera primero una copia del estado previo. **Aun así, se recomienda conservar un respaldo externo de los mundos importantes.**

## 🏗️ Estructura del proyecto

```text
Minecraft-server-local/
├── app.py                         # Punto de entrada de la aplicación
├── blockserver/
│   ├── __init__.py
│   ├── core.py                    # Configuración, Java, importaciones, respaldos y Vanilla
│   ├── engine.py                  # Gestión del proceso Java, consola y métricas
│   ├── ui.py                      # Ventanas y pantallas de PySide6
│   ├── theme.py                   # Apariencia y componentes visuales
│   ├── icons.py                   # Iconos QtAwesome / Font Awesome
│   ├── controls.py                # Campos numéricos protegidos contra scroll
│   └── workers.py                 # Tareas en segundo plano
├── assets/                        # Iconos e imágenes
├── tests/
│   ├── test_core.py
│   └── test_numeric_controls.py
├── requirements.txt               # Dependencias Python
├── iniciar_windows.bat            # Arranque en Windows
├── iniciar_linux.sh               # Arranque en Linux
├── crear_exe_windows.bat          # Compilación opcional de EXE en Windows
├── LEEME_PRIMERO.md               # Guía de uso más detallada
└── README.md                      # Este documento
```

## 📦 Crear un ejecutable `.exe` en Windows

En un equipo **Windows** con Python instalado, ejecuta:

```text
crear_exe_windows.bat
```

Este script utiliza **PyInstaller** y genera el ejecutable en `dist/BlockServerGUI.exe` si la compilación termina correctamente. **El archivo `.exe` no incluye Java**: el equipo donde se ejecute debe disponer de una instalación compatible con el servidor.

## 🧪 Pruebas

Instala las dependencias de pruebas y ejecuta:

```bash
python -m pip install pytest
python -m pytest -q
```

En el entorno donde se preparó **v1.1.1** se registraron **25 pruebas aprobadas y 1 omitida**. La prueba gráfica de los controles numéricos quedó omitida por no disponer allí de PySide6/QtAwesome. **No se ha confirmado en ese entorno una ejecución gráfica completa ni el arranque de un servidor real**. Comprueba estas funciones en tu computadora antes de publicar una versión estable.

## 🔒 Seguridad y limitaciones

- **Revisa los archivos antes de importarlos.** Los scripts de inicio `.bat`, `.cmd` y `.sh` proporcionados por terceros pueden ejecutar código con tus permisos de usuario.
- Los ZIP importados se validan para rechazar rutas peligrosas y enlaces simbólicos y limitar el tamaño extraído. Aun así, utiliza paquetes de procedencia confiable.
- Eliminar archivos desde el explorador intenta enviarlos a la papelera del sistema cuando está disponible.
- La aplicación **no configura automáticamente el firewall, redireccionamiento de puertos, CGNAT ni túneles**. Para que jugadores externos se conecten necesitarás configurar la red por separado.
- El contador de jugadores se estima a partir de los mensajes del servidor y puede variar con plugins que alteren los logs.
- Algunos servidores modificados necesitan instaladores adicionales o scripts especiales.
- Los archivos y mundos permanecen localmente; únicamente las consultas del catálogo y descargas de Vanilla requieren comunicarse con servicios externos.
- No subas al repositorio mundos privados, credenciales, respaldos, configuraciones personales ni el entorno virtual `.venv`.

## 🛠️ Tecnologías

- **Python** — lenguaje principal.
- **PySide6 (Qt)** — interfaz gráfica de escritorio.
- **QtAwesome / Font Awesome** — iconografía.
- **psutil** — información de consumo de recursos.
- **Send2Trash** — integración con la papelera.
- **PyInstaller** — compilación opcional para Windows.

## 🤝 Contribuciones

Se agradecen los reportes de errores, sugerencias y mejoras. Puedes abrir un **Issue** o enviar un **Pull Request** en GitHub. Al reportar un problema, incluye el sistema operativo, versión de Python, versión de Java, plataforma/versión de Minecraft y los mensajes relevantes de la consola **sin compartir datos privados**.

## 📄 Licencias y créditos

El código de este repositorio se rige por el archivo `LICENSE` **si el propietario lo incorpora**. La ausencia de dicho archivo no implica que se otorgue una licencia de uso, modificación o redistribución. Las bibliotecas y los iconos de terceros conservan sus **propias condiciones de licencia**, que deben respetarse al redistribuir la aplicación.

**BlockServer GUI es un proyecto independiente**: no está afiliado ni respaldado por Mojang Studios o Microsoft. Minecraft y sus marcas corresponden a sus titulares. Consulta la [EULA oficial de Minecraft](https://www.minecraft.net/eula).

**Desarrollo:** proyecto mantenido por el propietario del repositorio, con asistencia de herramientas de inteligencia artificial en su elaboración.

---

<div align="center">

**BlockServer GUI · Minecraft-server-local · Windows + Linux**

</div>
