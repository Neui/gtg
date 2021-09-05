
"""
This file handles about the internal representation of the sidebar.
Since the tags and saved searches are now split (before they were all tags,
even the special entries), this tries to combine them together by
basically wrapping them.
"""

import logging
import abc
import dataclasses
from typing import *

from gettext import gettext as _

from GTG.core.tag import Tag
from GTG.core.saved_searches import SavedSearch
from GTG.gtk.tree_util import CombinedTreeModel, FixedTreeModel

from gi.repository import GObject, Gtk

log = logging.getLogger(__name__)


class SidebarEntry(GObject.Object):
    """
    An entry in the sidebar, such as a tag, an saved search or something
    special.
    """

    def __init__(self):
        raise NotImplementedError # TODO: Turn it into a abstract class

    def render_icon(self, surface):
        """The icon to render."""
        log.warn("TODO: implement render_icon")
        #raise NotImplementedError

    @GObject.property(type=str, default='')
    def display_name(self):
        return self._display_name



class SidebarTag(SidebarEntry):
    """
    An sidebar entry that is representing a tag.
    """

    def __init__(self, tag: Tag):
        super(GObject.Object).__init__()
        self.tag = tag
        self._display_name = tag.get_name()


class SidebarSavedSearch(SidebarEntry):
    """
    An sidebar entry that is representing an saved search.
    """

    def __init__(self, saved_search: SavedSearch):
        super(GObject.Object).__init__()
        self.saved_search = saved_search
        self._display_name = saved_search.name


class SidebarSpecial(SidebarEntry):
    """
    An sidebar entry that is representing something special, such as
    an sepearator, all tasks view, or something similar.
    """

    def __init__(self):
        raise NotImplementedError # TODO: Turn it into a abstract class


class SidebarSeparator(SidebarSpecial):
    """An sidebar entry that is representing an uninteractable separator."""

    def __init__(self):
        super(GObject.Object).__init__()
        self._display_name = ''


class SidebarAllTasks(SidebarSpecial):
    """An sidebar entry to show all tasks."""

    def __init__(self):
        super(GObject.Object).__init__()
        self._display_name = _("All tasks")


class SidebarSavedSearches(SidebarSpecial):
    """An sidebar entry to group saved searches under."""

    def __init__(self):
        super(GObject.Object).__init__()
        self._display_name = _("Saved searches")


class SidebarTasksWithoutTags(SidebarSpecial):
    """An sidebar entry to show tasks without tags."""

    def __init__(self):
        super(GObject.Object).__init__()
        self._display_name = _("Tasks with no tags")



class SidebarTreeModel(Gtk.TreeStore):
    """The tree model for the sidebar."""

    def __init__(self, tags_tree=None, saved_searches_tree=None):
        # super().__init__(GObject.TYPE_OBJECT) # TODO make it work?
        super().__init__(GObject.TYPE_PYOBJECT)
        self._tags_tree = tags_tree
        self._saved_searches_tree = saved_searches_tree
        self._entry_saved_searches = SidebarSavedSearches()
        self.recreate()

    @GObject.property(type=object)
    def tags_tree(self):
        return self._tags_tree

    @tags_tree.setter
    def tags_tree(self, value):
        self._tags_tree = value
        self.recreate_tags()

    @GObject.property(type=object)
    def saved_searches_tree(self):
        return self._saved_searches_tree

    @saved_searches_tree.setter
    def saved_searches_tree(self, value):
        self._saved_searches_tree = value
        self.recreate_saved_searches()

    def recreate(self):
        """Clear and completely recreate the sidebar entries."""
        # Currently, the order is fixed.
        self.clear()
        self.append(None, [SidebarAllTasks()])
        self._path_saved_searches = self.get_path(
            self.append(None, [self._entry_saved_searches]))
        self.append(None, [SidebarTasksWithoutTags()])
        self.append(None, [SidebarSeparator()])
        self.recreate_tags()
        self.recreate_saved_searches()

    def _clear_children(self, iter: Gtk.TreeIter):
        # for entry in self[iter]:
        #     self.remove(entry.iter)
        # Alternative if above doesn't work
        while True:
            iter = self.get_iter(self._path_saved_searches)
            if self.iter_n_children(iter) == 0:
                break
            self.remove(self.iter_children(iter))

    def recreate_saved_searches(self):
        """Remove and re-insert the saved searches."""
        log.warn("TODO: implement recreate_saved_searches")
        iter = self.get_iter(self._path_saved_searches)
        self._clear_children(iter)
        iter = self.get_iter(self._path_saved_searches) # Relaod

    def recreate_tags(self):
        """Remove and re-insert the tags."""
        log.warn("TODO: implement recreate_tags")
        if self.tags_tree is None:
            pass
        for tag_id in self.tags_tree.get_nodes():
            tag = self.tags_tree.get_node(tag_id)
            if tag.is_special() or tag.is_search_tag():
                continue
            self.insert(None, -1, [SidebarTag(tag)])

    @staticmethod
    def get_display_name(tree_column: Gtk.TreeViewColumn,
                         cellr: Gtk.CellRenderer,
                         tree_model: Gtk.TreeModel,
                         iter: Gtk.TreeIter,
                         *data):
        value = tree_model.get_value(iter, 0)
        cellr.set_property('text', value.display_name)

    @staticmethod
    def is_seperator(tree_model: Gtk.TreeModel, iter: Gtk.TreeIter, *data):
        """
        Gtk.TreeViewRowSeparatorFunc compatible function to check
        whenever the current column is a seperator.
        """
        value = tree_model.get_value(iter, 0)
        return isinstance(value, SidebarSeparator)





class SidebarTreeModel2(CombinedTreeModel):
    """The tree model for the sidebar."""

    def __init__(self, tags_tree=None, saved_searches_tree=None):
        # super().__init__(GObject.TYPE_OBJECT) # TODO make it work?
        self._tags_tree = tags_tree
        self._saved_searches_tree = saved_searches_tree

        models = [
            SidebarAllTasks(),
            SidebarSavedSearches(saved_searches_tree),
            SidebarTasksWithoutTags(),
            SidebarSeparator(),
        ]
        super().__init__(models, [GObject.TYPE_PYOBJECT])


    @GObject.property(type=object)
    def tags_tree(self):
        return self._tags_tree

    @tags_tree.setter
    def tags_tree(self, value):
        self._tags_tree = value
        self.recreate_tags()

    @GObject.property(type=object)
    def saved_searches_tree(self):
        return self._saved_searches_tree

    @saved_searches_tree.setter
    def saved_searches_tree(self, value):
        self._saved_searches_tree = value
        self.recreate_saved_searches()

    @staticmethod
    def get_display_name(tree_column: Gtk.TreeViewColumn,
                         cellr: Gtk.CellRenderer,
                         tree_model: Gtk.TreeModel,
                         iter: Gtk.TreeIter,
                         *data):
        value = tree_model.get_value(iter, 0)
        cellr.set_property('text', value.display_name)

    @staticmethod
    def is_seperator(tree_model: Gtk.TreeModel, iter: Gtk.TreeIter, *data):
        """
        Gtk.TreeViewRowSeparatorFunc compatible function to check
        whenever the current column is a seperator.
        """
        value = tree_model.get_value(iter, 0)
        return isinstance(value, SidebarSeparator)









class SidebarIconCellRenderer(Gtk.CellRenderer):
    """
    Cell renderer for the sidebar.
    TODO: Move it to its own file, or somewhere more appropiately.
    """

    def __init__(self):
        pass

