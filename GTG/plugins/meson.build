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
]

message('---------------------------')
message('If you see "../GTG/plugins/meson.build: ... invalid value to variable." in following this, gettext has not been installed!')
message('---------------------------')
# ../GTG/plugins/meson.build:19:2: ERROR: Tried to assign an invalid value to variable.

foreach plugin : gtg_plugins
  # HACK: Abusing when gettext is not installed, meson will return an invalid
  # value that meson complains when trying to assign to a variable.
  # Taking advantage of that to error when gettext is missing.
  # Also see https://github.com/mesonbuild/meson/issues/6165
  something = i18n.merge_file(
    input: plugin + '.gtg-plugin.desktop', # Big hack to make xgettext detect
    output: plugin + '.gtg-plugin',
    po_dir: meson.source_root() / 'po',
    install: true,
    install_dir: plugin_install_dir,
    type: 'desktop',
    args: ['--keyword=name', '--keyword=short-description', '--keyword=description']
  )
  subdir(plugin.underscorify())
endforeach
