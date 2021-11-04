gtg_plugin_sources = [
  '__init__.py',
]

python3.install_sources(gtg_plugin_sources, subdir: 'GTG' / 'plugins', pure: true)
plugin_install_dir = python3.get_install_dir(subdir: 'GTG' / 'plugins', pure: true)

gtg_plugins = [
  'export',
  'send-email',
  'untouched-tasks',
  'urgency-color',
  'hamster',
  'dev_console',
  'gamify',
]

# HACK to workaround bug TODO
# by including all the PO files as a dependency.
pofiles = []
fs = import('fs')
langs = fs.read(meson.source_root() / 'po' / 'LINGUAS', encoding: 'utf-8')
foreach lang : langs.split('\n')
  if not lang.startswith('#')
    pofiles += meson.source_root() / 'po' / lang.strip() + '.po'
  endif
endforeach

foreach plugin : gtg_plugins
  pofiles_with_input = [plugin + '.gtg-plugin']
  pofiles_with_input += pofiles # Trying to keep the array flat
  i18n.merge_file(
    input: pofiles_with_input,
    output: plugin + '.gtg-plugin',
    po_dir: meson.source_root() / 'po',
    install: true,
    install_dir: plugin_install_dir,
    type: 'desktop',
    args: ['--language=Desktop',
      '--keyword=name', '--keyword=short-description', '--keyword=description'],
    build_by_default: true,
  )
  subdir(plugin.underscorify())
endforeach
