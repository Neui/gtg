# -----------------------------------------------------------------------------
# Getting Things GNOME! - a personal organizer for the GNOME desktop
# Copyright (c) 2008-2013 - Lionel Dricot & Bertrand Rousseau
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------
"""Reusable logging configuration.

GTG modules and plugins that wish to use logging should import the log object::

  from GTG.core.logger import log

...and target it with debug or info messages::

  log.debug('Something has gone terribly wrong!')

"""
import logging
import os
from gi.repository import GLib

CATEGORY = 'gtg'

class PythonToGLibLoggerHandler(logging.Handler):
    """An python logger handler that forwards to the GLib logging system"""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def _level_to_glib(self, level):
        if level > 50:
            return GLib.LogLevelFlags.LEVEL_CRITICAL
        if level > 40:
            return GLib.LogLevelFlags.LEVEL_ERROR
        if level > 30:
            return GLib.LogLevelFlags.LEVEL_WARNING
        if level > 20:
            return GLib.LogLevelFlags.LEVEL_INFO
        if level > 10:
            return GLib.LogLevelFlags.LEVEL_DEBUG
        return GLib.LogLevelFlags.LEVEL_DEBUG
        # Not used: GLib.LogLevelFlags.LEVEL_MESSAGE

    def emit(self, record):
        log_level = self._level_to_glib(record.levelno)
        fields = GLib.Variant('a{sv}', {
            'MESSAGE': GLib.Variant('s', self.format(record)),
            'CODE_FUNC': GLib.Variant('s', record.funcName),
            'CODE_FILE': GLib.Variant('s', record.pathname),
            'CODE_LINE': GLib.Variant('i', record.lineno),
            'PYTHON_MESSAGE': GLib.Variant('s', record.getMessage()),
            'PYTHON_MODULE': GLib.Variant('s', record.module),
        })
        GLib.log_variant(record.name, log_level, fields)

log = logging.getLogger(CATEGORY)

handler = PythonToGLibLoggerHandler()

formatter = logging.Formatter("[%(module)s:%(funcName)s:%(lineno)d] %(message)s")
handler.setFormatter(formatter)

log.addHandler(handler)

def glib_set_debug(debug):
    """Instruct the default GLib logger to output debug messages"""
    glib_categories = os.environ.get('G_MESSAGES_DEBUG', '').split(' ')
    if debug and 'all' in glib_categories:
        pass # all already includes gtg
    elif debug and CATEGORY not in glib_categories:
        glib_categories.append(CATEGORY)
    elif debug:
        return # Do nothing, debug is already enabled
    else:
        try:
            glib_categories.remove(CATEGORY)
        except ValueError:
            pass
        try:
            glib_categories.remove('all')
        except ValueError:
            pass
    g_messages_debug = ' '.join(glib_categories)
    os.environ['G_MESSAGES_DEBUG'] = g_messages_debug
    os.putenv('G_MESSAGES_DEBUG', g_messages_debug)

def glib_in_debug():
    """Returns whenever the default GLib logger would output debug messages"""
    glib_categories = os.environ.get('G_MESSAGES_DEBUG', '').split(' ')
    return any([e in (CATEGORY, 'all') for e in glib_categories])

def log_debug_enabled():
    """Return whether the logger is enabled for debug messages."""

    return glib_in_debug() or log.isEnabledFor(logging.DEBUG)
