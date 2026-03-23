# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for english-coach CLOUD version (license-based)
# Build: python build_cloud.py

import os
import sys
from pathlib import Path

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.pyinstaller_package_bundle import (
    collect_package_binaries,
    collect_package_datas,
    collect_package_hiddenimports,
    package_dir,
)

block_cipher = None

_PACKAGE_NAMES = [
    'webview',
    'pythonnet',
    'uvicorn',
    'fastapi',
    'starlette',
    'annotated_doc',
    'pydantic',
    'pydantic_core',
    'typing_inspection',
]
_PACKAGE_DIRS = {name: package_dir(name) for name in _PACKAGE_NAMES}
_PYTHONNET = _PACKAGE_DIRS['pythonnet']

# Make Python.Runtime.dll discoverable by the old hook-clr.py
# by adding its directory to PATH before Analysis runs
_pyruntime_dir = str(_PYTHONNET / 'runtime')
os.environ['PATH'] = _pyruntime_dir + os.pathsep + os.environ.get('PATH', '')


def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        marker = item if isinstance(item, str) else tuple(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


_collected_datas = []
_collected_binaries = []
for _pkg_name in _PACKAGE_NAMES:
    _collected_datas.extend(collect_package_datas(_pkg_name))
    _collected_binaries.extend(collect_package_binaries(_pkg_name))

_generated_hiddenimports = []
for _pkg_name in _PACKAGE_NAMES:
    _filter_fn = None
    if _pkg_name == 'webview':
        _filter_fn = lambda name: not name.startswith('webview.platforms.android')
    _generated_hiddenimports.extend(
        collect_package_hiddenimports(_pkg_name, filter_fn=_filter_fn)
    )
_generated_hiddenimports.extend(collect_package_hiddenimports('clr_loader'))

_core_hiddenimports = [
    'openai',
    'edge_tts',
    'rich',
    'typer',
    'yaml',
    'frontmatter',
    'sqlite3',
    'logging.config',
    'logging.handlers',
    'email.mime',
    'email.mime.multipart',
    'email.mime.text',
    'email.mime.base',
    'typing',
    'typing_extensions',
    'click',
    'utils.paths',
    'utils.logger',
    'core.ingestion.pipeline',
    'core.knowledge_base.store',
    'core.srs.engine',
    'core.user_model.profile',
    'ai.client',
    'ai.tts',
    'ai.question_distribution',
    'ai.reading_question_generators',
    'modes.vocab',
    'modes.reading',
    'modes.writing',
    'modes.speaking',
    'modes.grammar',
    'modes.chat',
    'modes.plan',
    'modes.words',
    'modes.notebook',
    'modes.mock_exam',
    'modes.lookup',
    'modes.anki_export',
    'modes.users',
    'modes.packs',
    'cli.display',
    'gui.server',
    'gui.deps',
    'gui.api.vocab',
    'gui.api.grammar',
    'gui.api.reading',
    'gui.api.writing',
    'gui.api.speaking',
    'gui.api.chat',
    'gui.api.progress',
    'gui.api.setup',
    'gui.api.practice',
    'gui.api.mock_exam',
    'gui.api.license',
    'gui.api.history',
    'gui.api.voice',
    'gui.api.listening',
    'gui.api.wordbooks',
    'gui.api.warehouse',
    'gui.license',
    'h11',
    'sse_starlette',
    'pkg_resources.py2_warn',
    'clr',
]

a = Analysis(
    [str(ROOT / 'gui' / 'main.py')],
    pathex=[str(ROOT)],
    binaries=_dedupe(_collected_binaries),
    datas=[
        (str(ROOT / 'config.yaml'), '.'),
        # Bundle the full content tree so packaged builds ship the same resources as dev.
        (str(ROOT / 'content'), 'content'),
        (str(ROOT / 'gui' / 'static'), 'gui/static'),
    ] + _dedupe(_collected_datas),
    hiddenimports=_dedupe(_core_hiddenimports + _generated_hiddenimports),
    hookspath=[str(ROOT / 'release_tooling' / 'hooks')],
    runtime_hooks=[
        str(ROOT / 'release_tooling' / 'runtime_hooks' / 'fix_typing.py'),
        str(ROOT / 'release_tooling' / 'runtime_hooks' / 'fix_uvicorn_types.py'),
    ],
    excludes=[
        # Large ML/AI libraries (not used)
        'chromadb',
        'sentence_transformers',
        'torch',
        'transformers',
        'numpy',
        'pandas',
        'matplotlib',
        'tkinter',
        'faster_whisper',
        'ctranslate2',
        'av',
        # Additional exclusions for faster startup
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Output directly into releases/ so no manual move needed
import pathlib
pathlib.Path(ROOT / 'releases').mkdir(exist_ok=True)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='english-coach-cloud',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
