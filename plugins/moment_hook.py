"""MkDocs Moment hook — delegates to the plugin package."""

from mkdocs_moment.plugin import MomentPlugin

_plugin = MomentPlugin()


def on_config(config):
    return _plugin.on_config(config)


def on_files(files, config):
    return _plugin.on_files(files, config)


def on_page_markdown(markdown, page, config, files):
    return _plugin.on_page_markdown(markdown, page, config, files)


def on_page_context(context, page, config, nav):
    return _plugin.on_page_context(context, page, config, nav)


def on_post_build(config):
    return _plugin.on_post_build(config)
