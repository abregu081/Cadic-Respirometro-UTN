# setup.py
# Empaquetado con cx_Freeze (recomendado para "setup.py")
#
# Uso (Windows recomendado para generar .exe):
#   python -m pip install --upgrade pip
#   pip install cx_Freeze
#   python setup.py build
#   # opcional (Windows): python setup.py bdist_msi
#
# Nota:
# - Compilar .exe de Windows normalmente se hace EN Windows (no cross-compile fácil desde Linux).
# - Este setup incluye Setting.ini / HistorialProgramaciones.json y cualquier *.cfg del proyecto.

import os
import sys
from pathlib import Path
from cx_Freeze import setup, Executable


# -------------------------
# 1) Detectar script de entrada
CANDIDATES = [
    "app/main.py",
    "main.py"
]

def find_entry():
    for p in CANDIDATES:
        if Path(p).exists():
            return p
    raise FileNotFoundError(
        "No encontré el script principal. Probé: " + ", ".join(CANDIDATES) +
        ". Editá CANDIDATES en setup.py."
    )

ENTRY_SCRIPT = find_entry()


# -------------------------
# 2) Archivos a incluir
def add_if_exists(include_list, src, dst=None):
    src_path = Path(src)
    if src_path.exists():
        include_list.append((str(src_path), dst or src_path.name))

include_files = []

# Setting.ini (root o app/)
add_if_exists(include_files, "Setting.ini", "Setting.ini")
add_if_exists(include_files, "app/Setting.ini", "Setting.ini")

# Historial (si existe; si no, la app lo crea)
add_if_exists(include_files, "HistorialProgramaciones.json", "HistorialProgramaciones.json")
add_if_exists(include_files, "app/HistorialProgramaciones.json", "HistorialProgramaciones.json")

# Incluir cualquier .cfg (por si tu app usa configs externas)
for cfg in list(Path(".").glob("*.cfg")) + list(Path("app").glob("*.cfg")):
    include_files.append((str(cfg), cfg.name))


build_exe_options = {
    "include_files": include_files,
    # Si tenés imports dinámicos (por ejemplo: importlib), podés forzar "packages"/"includes"
    "packages": [
        "flet",
    ],
    # Ejemplo de includes forzados:
    # "includes": ["asyncio", "json"],
    "excludes": [
        "tkinter",
        "unittest",
    ],
    # En Windows, incluir runtime de MSVC (útil para evitar errores en PCs destino)
    "include_msvcr": True if sys.platform == "win32" else False,
}


base = "Win32GUI" if sys.platform == "win32" else None

executables = [
    Executable(
        script=ENTRY_SCRIPT,
        base=base,
        target_name="ControlRespirometro.exe" if sys.platform == "win32" else "ControlRespirometro",
    )
]


# -------------------------
# 5) Setup
setup(
    name="ControlRespirometro",
    version="1.0.0",
    description="Control Respirómetro CADIC (Flet + MQTT + Programaciones)",
    options={"build_exe": build_exe_options},
    executables=executables,
)
