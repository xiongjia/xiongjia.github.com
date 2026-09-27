"""Macro modules loaded by the ``macros`` plugin at build time.

``loader.py`` is the single entry point (``extra`` → ``macros`` plugin config in
``mkdocs.yml``); it delegates to each section's module. Section modules are
executed **by file path** by the plugin, so they bootstrap the repo root onto
``sys.path`` themselves instead of relying on this package being imported.
"""
