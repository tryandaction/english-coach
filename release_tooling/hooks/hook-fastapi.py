# PyInstaller hook for fastapi - fix typing imports for Python 3.13
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Ensure typing_extensions is available
hiddenimports = ['typing_extensions'] + collect_submodules('fastapi')
datas = collect_data_files('fastapi')
