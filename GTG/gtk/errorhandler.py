
from gi.repository import GObject, GLib, Gtk
from gettext import gettext as _
import traceback
import sys

from GTG.core import info


class ExceptionHandlerDialog(Gtk.MessageDialog):
    RESPONSE_EXIT_GTG = 1
    RESPONSE_CONTINUE = 2

    def __init__(self, exception=None, main_msg=None, ignorable=False, context_info=None):
        self.ignorable = ignorable

        if ignorable:
            title = _("GTG encountered an error")
            desc = _("""
                      GTG encountered an internal error, but it'll continue
                      running. However, more unexpected things can happen,
                      and thus be careful.
                      Please report the error with the following information
                      and steps to trigger it to: {url}

                      Warning: Exiting may loose unsaved changes.
                      """.format(url=info.REPORT_BUG_URL))
        else:
            title = _("GTG encountered an error and needs to exit")
            desc = _("""
                      GTG encountered an internal error and needs to exit.
                      Please report the error with the following information
                      and steps to trigger it to: {url}

                      Warning: Exiting may loose unsaved changes.
                      """.format(url=info.REPORT_BUG_URL))

        # super().__init__(title, None, Gtk.DialogFlags.MODAL)
        super().__init__(None,
                         Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                         Gtk.MessageType.ERROR,
                         Gtk.ButtonsType.NONE,
                         desc)
        self.set_title(title)

        self.add_button(_("Exit GTG"), self.RESPONSE_EXIT_GTG)
        if ignorable:
            self.add_button(_("Continue"), self.RESPONSE_CONTINUE)
        else:
            pass

        self._expander = Gtk.Expander()
        self._expander.set_label(_("Additional information"))
        self._additional_info = Gtk.TextView()
        self._additional_info.set_buffer(Gtk.TextBuffer())
        self._expander.add(self._additional_info)
        self.get_content_area().add(self._expander)
        self._expander.show_all()

        self._exception = exception
        self.set_context_info(context_info)

    def set_exception(self, exception):
        self._exception = exception
        self._update_additional_info()

    def set_context_info(self, info):
        self._context_info = str(info) if info != None else None
        self._update_additional_info()

    def _update_additional_info(self):
        # self._expander.set_visible(self._exception is not None)
        body = str(self._exception)
        if isinstance(self._exception, Exception):
            body = traceback.format_exception(type(self._exception),
                                              self._exception,
                                              self._exception.__traceback__)
            body = "".join(body)

        python_version = sys.version.replace('\n', '  ')
        versions = f"""
        GTG {info.VERSION}
        Python {python_version}
        GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}
        GLib {'.'.join(map(str, GLib.glib_version))}
        PyGLib {'.'.join(map(str, GLib.pyglib_version))}
        PyGObject {'.'.join(map(str, GObject.pygobject_version))}
        """

        text = ""
        if self._context_info is not None:
            text = text + self._context_info + "\n\n"
        text = text + body + "\n\n"
        text = text + versions

        self._additional_info.get_buffer().set_text(text)


def handle_response(dialog, response_id):
    print("handle_response {}".format(response_id))
    if response_id == ExceptionHandlerDialog.RESPONSE_CONTINUE:
        pass
    elif response_id == ExceptionHandlerDialog.RESPONSE_EXIT_GTG:
        sys.exit(1)


def do_error_dialog(exception, main_msg=None, ignorable=False, context_info=None):
    dialog = ExceptionHandlerDialog(exception, main_msg, ignorable, context_info)
    dialog.connect('response', handle_response)
    dialog.show_all()


def errorhandler(func):
    def inner(*arg, **kwargs):
        try:
            func(*arg, **kwargs)
        except Exception as e:
            try:
                do_error_dialog(e)
            except Exception as ie:
                print("Exception occured while trying to handle it:")
                traceback.print_exception(type(ie), ie, ie.__traceback__)
                print("-----")
            raise e
    return inner
