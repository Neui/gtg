import logging
import dataclasses
from typing import Any, Optional, Union, Callable
from collections.abc import Iterable

from gi.repository import GObject, Gtk


log = logging.getLogger(__name__)


class CombinedTreeModel(Gtk.TreeModel):
    """
    TreeModel that is put together by multiple other TreeModels.
    Doesn't store the data itself.
    Currently live modification of the used models (aka adding and
    removing models) is currently not supported.
    """

    """
    Internals: The _models attribute is a list of ModelInfos, which
    describes what model covers what indecies in the "virtual" combined
    root node.

    Note: model path and model iters refer to the model-specific path and iter,
    this path and this iter refer to this class created path and iters.

    The TreeIters each have a stamp value that increase with each row change.
    TODO: How they store the data
    """

    @dataclasses.dataclass
    class ModelInfo:
        """
        Internal TreeModel bookkeeping info.
        """

        model: Gtk.TreeModel

        start_index: int
        """ Virtual start index. """

        end_index: int
        """ Virtual end index, one element past the end. """

        signal_handlers: [int]
        """ Signal handler IDs to unregister when needed. """

        path_to_iter: dict[tuple[int, ...], Gtk.TreeIter]
        """ Cache, maps model path to an model-iter """

        path_to_this_iter: dict[tuple[int, ...], Gtk.TreeIter]
        """ Cache, maps model path to an this-iter """

        @property
        def size(self):
            return self.end_index - self.start_index

    default_types = (GObject.TYPE_PYOBJECT,)

    def __init__(self,
                 models: Iterable[Union[Gtk.TreeModel,
                                        tuple[Gtk.TreeModel,
                                              Iterable[Callable[Any],
                                                       GObject.Value]
                                              ]
                                        ]
                                  ],
                 types: Union[Gtk.TreeModel, Iterable[GObject.GType]] = default_types
                 ):
        super().__init__()
        self.__init = True  # During init don't fire signals to prevent overhead
        self._models = []
        self.stamp = 1

        if isinstance(types, Gtk.TreeModel):  # Copy the types
            types = [types.get_column_type(cid)
                     for cid in range(types.get_n_columns())]
        self.types = tuple(types)

        for t in self.types:
            if not isinstance(t, GObject.GType):
                raise ValueError("types element %r isn't a GType" % (t,))
        else:
            raise ValueError("types must not be empty")

        self._invalid_treeiter = Gtk.TreeIter()
        """Iterator that is considered invalid. It always has a stamp of 0."""
        self._invalid_treeiter.stamp = 0

        for m in models:
            if isinstance(m, Gtk.TreeModel):
                model = m
                model_types = None
            else:
                model = m[0]
                model_types = m[1]
            self._register_model(model, len(self._models))
        log.debug("TODO: Verify models variable and columns etc.")
        self.__init = False

    def _register_model(self, model: Gtk.TreeModel, pos: int,
                        types: Optional[Any] = None):
        """
        Register model.
        Sets up internal structure to handle it, as well as connecting
        signals.
        """
        # TODO: Verify types and how to map them to this object

        info = ModelInfo(model, -1, -1, [], {})
        self._models.insert(pos, info)

        try:
            prev = self._models[pos - 1]
            info.start_index = prev.end_index
        except IndexError: # We inserted at the beginning
            info.start_index = 0

        size = model.iter_n_children(None)
        if not self.__init:
            while x in range(size):
                info.end_index = info.start_index + x

                for next in self._models[pos + 1:]:
                    next.start_index += 1
                    next.end_index += 1

                # TODO: Handle children?
                log.warn("after-init row_inserted, children yet to be fired")
                self._invalidate_treeiters()
                indices = [info.end_index]
                path = Gtk.TreePath.new_from_indices(indices)
                iter = self._get_treeiter(info, None, indices)
                self.row_inserted(path, iter)
            assert info.size == size
        else:
            info.end_index = info.start_index + size
            assert info.size == size

            for next in self._models[pos + 1:]:
                next.start_index += size
                next.end_index += size

        s1 = model.connect("row-changed", self._handle_row_changed)
        s2 = model.connect("row-deleted", self._handle_row_deleted)
        s3 = model.connect("row-has-child-toggled", self._handle_row_has_child_toggled)
        s4 = model.connect("row-inserted", self._handle_row_insered)
        s5 = model.connect("rows-reordered", self._handle_rows_reordered)
        info.signal_handlers.extend([s1, s2, s3, s4, s5])

    def _unregister_model(self, model: Gtk.TreeModel):
        info = self._find_info(model)
        pos = self._models.index(info)
        for signal_handler in info.signal_handlers:
            model.disconnect(signal_handler)

        if not self.__init:
            while info.size > 0:
                info.end_index -= 1
                for next in self._models[pos + 1:]:
                    next.start_index -= 1
                    next.end_index -= 1

                # TODO: Handle children?
                log.warn("after-init row_deleted, children yet to be fired")
                self._invalidate_treeiters()
                path = Gtk.TreePath.new_from_indices([info.end_inde + 1])
                self.row_deleted(path)
        else:
            for next in self._models[pos + 1:]:
                next.start_index -= info.size
                next.end_index -= info.size

        del self._models[pos]

    def _find_info(self, tree_model: Gtk.TreeModel) -> ModelInfo:
        """
        Returns the ModelInfo class corresponding to the specified tree_model.
        Throws ValueError if it couldn't find it.
        """
        for info in self._models:
            if info.model is tree_model:
                return info
        raise ValueError("TreeModel {} not found".format(tree_model))

    def _find_info_from_path(self, path: Gtk.TreePath) -> ModelInfo:
        assert path is not None

        indices = path.get_indices()
        if indices == []:
            return None  # Root path

        return self._find_info_from_index(indicies[0])

    def _find_info_from_index(self, index: int) -> ModelInfo:
        assert index is not None

        # TODO: Maybe try to make this more efficent with more models
        for info in self._models:
            if info.start_index <= indeces[0] < info.end_index:
                return info
        raise IndexError("Path out of index: %r" % (path,))

    def _translate_this_path(self, path: Gtk.TreePath,
                             info: Optional[ModelInfo] = None
                             ) -> (Gtk.TreePath, ModelInfo):
        """
        Translate path from this TreeModel to a path for the TreeModel
        in info.
        info may be None, in which it uses the path to find the Info object.
        """
        if path.get_depth() == 0:
            return (path, None)

        if info is None:
            info = self._find_info_from_index(indices[0])

        indices = path.get_indices()
        indices[0] -= info.start_index
        return (Gtk.TreePath.new_from_indices(indices), info)

    def _get_treeiter(self, info: ModelInfo, model_iter: Optional[Gtk.TreeIter],
                      indices) -> Gtk.TreeIter:
        iter = info.path_to_this_iter.get(indices)
        if iter is not None:
            return iter

        if model_iter is None:
            model_iter = info.model.get_iter(new_path)
        info.path_to_iter[indices] = model_iter
        iter = Gtk.TreeIter()
        iter.stamp = self.stamp
        iter.user_data = info
        iter.user_data2 = model_iter
        iter.user_data3 = indices

        info.path_to_this_iter[indices] = iter
        return iter

    def _get_from_iter(self, iter: Gtk.TreeIter
                       ) -> (ModelInfo, Gtk.TreeIter, tuple):
        info: ModelInfo = iter.user_data
        model_iter: Gtk.TreeIter = iter.user_data2
        indices: tuple = iter.user_data3
        return (info, model_iter, indices)

    def _invalidate_treeiters(self, info: Optional[ModelInfo] = None):
        """
        Invalidates all existing Gtk.TreeIter.
        A Gtk.TreeIter stays valid as long the tree doesn't change
        (and no signals being fired). However, unfortunately, we can't
        implement our own memory managment "solution", and thus need to
        allocate some memory to store the data, that'll then live
        forever until one of the above happens.
        Thus, as a side effect, it cleans up memory.
        """
        # Make sure stamp is in valid int range because it is written to
        # the TreeIter
        imin, imax = (GLib.MININT, GLib.MAXINT)
        umax = imax + abs(imin)
        new_stamp = ((self.stamp + abs(imin) + 1) % umax) - abs(imin)
        if new_stamp == 0:  # 0 is already used for invalid iter
            new_stamp += 1
        self.stamp = new_stamp
        for info in self._models:
            info.path_to_iter.clear()
            info.path_to_this_iter.clear()

    def _translate_model_path(self, info: ModelInfo, path: Gtk.TreePath
                              ) -> Gtk.TreePath:
        """
        Translates path from the model inside the info to a path for use
        for this TreeModel.
        """
        indices = path.get_indices()
        indices[0] += info.start_index
        return Gtk.TreePath.new_from_indices(indices)

    def _translate_model_path_and_iter(self, info: Info, path: Gtk.TreePath,
                                       iter: Optional[Gtk.TreeIter]
                                       ) -> (Gtk.TreePath, Gtk.TreeIter):
        """
        Translates path (and iter) from the model inside the info to a path for
        use for this TreeModel.
        If iter is None, then None is returned for the TreeIter part because
        this means the root node.
        """
        new_path = self._translate_path(info, path)
        new_iter = None  # for rows_reordered
        if iter is not None:
            new_iter = self.get_iter(new_path)
        return new_path, new_iter

    # Handle signals from TreeModels we use

    def _handle_row_changed(self, tree_model: Gtk.TreeModel,
                            path: Gtk.TreePath, iter: Gtk.TreeIter):
        assert tree_model is not None
        assert path is not None
        assert iter is not None

        info = self._find_info(tree_model)
        new_path, new_iter = self._translate_model_path_and_iter(info, path, iter)
        self.row_inserted(new_path, new_iter)

    def _handle_row_deleted(self, tree_model: Gtk.TreeModel,
                            path: Gtk.TreePath):
        assert tree_model is not None
        assert path is not None
        info = self._find_info(tree_model)

        info.end_index -= 1
        info_index = self._models.index(info)
        for i in self._models[info_index + 1:]:
            i.start_index -= 1
            i.end_index -= 1

        new_path = self._translate_model_path(info, path)
        self._invalidate_treeiters(info)
        self.row_deleted(new_path)

    def _handle_has_child_toggled(self, tree_model: Gtk.TreeModel,
                          path: Gtk.TreePath, iter: Gtk.TreeIter):
        info = self._find_info(tree_model)
        new_path, new_iter = self._translate_model_path_and_iter(info, path, iter)
        self.has_child_toggled(new_path, new_iter)

    def _handle_row_inserted(self, tree_model: Gtk.TreeModel,
                             path: Gtk.TreePath, iter: Gtk.TreeIter):
        assert tree_model is not None
        assert path is not None
        assert iter is not None

        info = self._find_info(tree_model)

        info.end_index += 1
        info_index = self._models.index(info)
        for i in self._models[info_index + 1:]:
            i.start_index += 1
            i.end_index += 1

        new_path, new_iter = self._translate_model_path_and_iter(info, path, iter)
        self._invalidate_treeiters(info)
        self.row_inserted(new_path, new_iter)

    def _handle_rows_reordered(self, tree_model: Gtk.TreeModel,
                               path: Gtk.TreePath, iter: Gtk.TreeIter,
                               new_order: [int]):
        assert tree_model is not None
        assert path is not None
        assert new_order is not None

        info = self._find_info(tree_model)
        new_path, new_iter = self._translate_model_path_and_iter(info, path, iter)

        if iter is None:  # Reordering happens on our level, also translate new_order
            new_new_order = list(range(self._models[-1].end_index))
            # new_new_order maps 1 to 1, now replace relevant part with new_order
            for index in range(info.start_index, info.end_index):
                old_index = index - info.start_index
                new_new_order[index] = new_order[old_index] + info.start_index
            new_order = new_new_order

        self._invalidate_treeiters(info)
        self.rows_reordered(new_path, new_iter, new_order)

    # Gtk.TreeModel interface implementation

    def do_get_flags(self) -> Gtk.TreeModelFlags:
        return 0  # Iters don't persist (unfortunately), and it's a tree

    def do_get_n_columns(self):
        return len(self.types)

    def do_get_column_type(self, index: int) -> GObject.GType:
        return self.types[index]

    def do_get_iter(self, treepath: Gtk.TreePath) -> tuple[bool, Gtk.TreeIter]:
        try:
            new_path, info = self._translate_this_path(treepath)
            indices = tuple(new_path.get_indices())
            return (True, self._get_treeiter(info, None, indices))
        except ValueError:
            return (False, self._invalid_treeiter)

    def do_get_path(self, iter: Gtk.TreeIter) -> Gtk.TreePath:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        info, model_iter, indices = self._get_from_iter(iter)

        new_indices = list(indices)
        new_indices[0] += info.start_index
        return Gtk.TreePath.new_from_indices(new_indices)

    def do_get_value(self, iter: Gtk.TreeIter, column: int) -> GObject.Value:
        pass  # TODO
        path = self._get_path(iter)
        node = self.tree.get_node(path[-1])
        value = self.types[column][1](node)
        if value is None:
            return GObject.Value(GObject.TYPE_POINTER, value)
        return value

    def do_iter_next(self, iter: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        info, model_iter, indices = self._get_from_iter(iter)

        try:
            new_iter = info.model.iter_next(model_iter)
        except ValueError:
            return (False, self._invalid_treeiter)

        indices = list(indices)
        if indices != []:
            indices[-1] += 1

        return (True, self._get_treeiter(info, new_iter, indices))

    def do_iter_previous(self, iter: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        info, model_iter, indices = self._get_from_iter(iter)

        try:
            new_iter = info.model.iter_previous(model_iter)
        except ValueError:
            return (False, self._invalid_treeiter)

        indices = list(indices)
        if indices != []:
            indices[-1] -= 1

        return (True, self._get_treeiter(info, new_iter, indices))

    def do_iter_children(self, iter: Optional[Gtk.TreeIter]
                         ) -> tuple[bool, Gtk.TreeIter]:
        if iter is None:
            return self.do_iter_first()
        try:
            assert iter.stamp == self.stamp
            if iter.stamp != self.stamp:
                return (False, self._invalid_treeiter)

            info, model_iter, indices = self._get_from_iter(iter)

            try:
                new_iter = info.model.iter_children(model_iter)
            except ValueError:
                return (False, self._invalid_treeiter)

            indices = list(indices)
            indices.append(0)

            return (True, self._get_treeiter(info, new_iter, indices))
        except ValueError:
            return (False, self._invalid_treeiter)

    def do_iter_has_child(self, iter: Gtk.TreeIter) -> bool:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return False

        info, model_iter, indices = self._get_from_iter(iter)
        return info.model.iter_has_children(model_iter)

    def do_iter_n_children(self, iter: Optional[Gtk.TreeIter]) -> int:
        if iter is None:  # Root
            size = 0
            for info in self._models:
                size += info.size
            return size

        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return False

        info, model_iter, indices = self._get_from_iter(iter)
        return info.model.iter_n_children(model_iter)

    def do_iter_nth_child(self, parent: Optional[Gtk.TreeIter], n: int
                          ) -> (bool, Gtk.TreeIter):
        if parent is None:  # Root
            return self.do_get_iter(Gtk.TreePath.new_from_indices([n]))

        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        info, model_iter, indices = self._get_from_iter(parent)

        try:
            new_iter = info.model.iter_nth_child(model_iter, n)
        except ValueError:
            return (False, self._invalid_treeiter)

        indices = list(indices)
        indices.append(n)

        return (True, self._get_treeiter(info, new_iter, indices))

    def do_iter_parent(self, child: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        info, model_iter, indices = self._get_from_iter(child)

        try:
            new_iter = info.model.iter_parent(model_iter)
        except ValueError:
            return (False, self._invalid_treeiter)

        indices = list(indices)[:-1]

        return (True, self._get_treeiter(info, new_iter, indices))

    def do_ref_node(self, iter: Gtk.TreeIter):
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return

        info, model_iter, indices = self._get_from_iter(iter)
        info.model.ref_node(model_iter)

    def do_unref_node(self, iter: Gtk.TreeIter):
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return

        info, model_iter, indices = self._get_from_iter(iter)
        info.model.unref_node(model_iter)



class FixedTreeModel(Gtk.TreeModel):
    """
    TreeModel that can't be changed and just represents a static list.
    """

    default_types = (GObject.TYPE_PYOBJECT,
                     lambda o: GObject.Value(GObject.TYPE_PYOBJECT, o),)

    def __init__(self, data: Iterable[Any],
                 types: Iterable[tuple[GObject.GType,
                                       Callable[[Any], GObject.Value]]
                                 ] = default_types
                 ):
        super().__init__()
        self.data = tuple(data)
        self.stamp = 1

        self.types = tuple(types)
        for t in self.types:
            if len(t) != 2:
                raise ValueError("types element %r doesn't have 2 elements" % (t,))
            if not isinstance(t[0], GObject.GType):
                raise ValueError("types element %r doesn't have a GType: %r" % (t, t[0]))
            if not callable(t[1]):
                raise ValueError("types element %r is not callable: %r" % (t, t[1]))
        else:
            raise ValueError("types must not be empty")

        """Iterator that is considered invalid. It always has a stamp of 0."""
        self._invalid_treeiter = Gtk.TreeIter()
        self._invalid_treeiter.stamp = 0

    def _get_iter(self, index: int) -> Gtk.TreeIter:
        """
        From the index return the iterator.
        """
        self.data[index]  # Cause IndexError
        iter = Gtk.TreeIter()
        iter.stamp = self.stamp
        iter.user_data = index

    def _get_from_iter(self, iter: Gtk.TreeIter) -> tuple[int, Any]:
        """
        Retrieves the index and object from the iter.
        """
        i = int(iter.user_data)
        return (i, self.data[i])

    # Gtk.TreeModel interface implementation

    def do_get_flags(self) -> Gtk.TreeModelFlags:
        return Gtk.TreeModelFlags.LIST_ONLY

    def do_get_n_columns(self):
        return len(self.types)

    def do_get_column_type(self, index: int) -> GObject.GType:
        return self.types[index][0]

    def do_get_iter(self, treepath: Gtk.TreePath) -> tuple[bool, Gtk.TreeIter]:
        if treepath.get_depth() != 1:
            return (False, self._invalid_treeiter)
        indices = treepath.get_indices()
        try:
            return (True, self._get_iter(indices[0]))
        except IndexError:
            return (False, self._invalid_treeiter)

    def do_get_path(self, iter: Gtk.TreeIter) -> Gtk.TreePath:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        i, _ = self._get_from_iter(iter)
        return Gtk.TreePath.new_from_indices([i])

    def do_get_value(self, iter: Gtk.TreeIter, column: int) -> GObject.Value:
        assert iter.stamp == self.stamp

        index, value = self._get_from_iter(iter)
        ret = self.types[column][1](value)
        if ret is None:
            return GObject.Value(GObject.TYPE_POINTER, ret)
        return ret

    def do_iter_next(self, iter: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        try:
            i, _ = self._get_from_iter(iter)
            return (True, self._get_iter(i + 1))
        except IndexError:
            return (False, self._invalid_treeiter)

    def do_iter_previous(self, iter: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        if iter.stamp != self.stamp:
            return (False, self._invalid_treeiter)

        try:
            i, _ = self._get_from_iter(iter)
            return (True, self._get_iter(i - 1))
        except IndexError:
            return (False, self._invalid_treeiter)

    def do_iter_children(self, iter: Optional[Gtk.TreeIter]
                         ) -> tuple[bool, Gtk.TreeIter]:
        if iter is not None:
            return (False, self._invalid_treeiter)
        return self.do_iter_first()

    def do_iter_has_child(self, iter: Gtk.TreeIter) -> bool:
        return False  # This is a list, not a tree

    def do_iter_n_children(self, iter: Optional[Gtk.TreeIter]) -> int:
        if iter is not None:  # This is a list, not a tree
            return 0
        return len(self.data)

    def do_iter_nth_child(self, parent: Optional[Gtk.TreeIter], n: int
                          ) -> (bool, Gtk.TreeIter):
        if parent is not None:  # This is a list, not a tree
            return (False, self._invalid_treeiter)

        try:
            return (True, self._get_iter(n))
        except IndexError:
            return (False, self._invalid_treeiter)

    def do_iter_parent(self, child: Gtk.TreeIter) -> tuple[bool, Gtk.TreeIter]:
        assert iter.stamp == self.stamp
        return (False, self._invalid_treeiter)  # This is a list, not a tree

    def do_ref_node(self, iter: Gtk.TreeIter):
        pass  # Do nothing

    def do_unref_node(self, iter: Gtk.TreeIter):
        pass  # Do nothing



class TreeStoreDup(Gtk.TreeModel):  # NOT DONE YET, MAY BE REMOVED LATER
    """
    Gtk.TreeModel that duplicates the data from the Gtk.TreeModel
    it imitates into an Gtk.TreeStore, trying to "bypass" python.
    """

    def __init__(self, model: Gtk.TreeModel):
        super().__init__()
        if not isinstance(model, Gtk.TreeModel):
            raise ValueError("Expected Gtk.TreeModel, got %s" % (type(model),))
        self._model = model
        model.connect("row-changed", self._handle_row_changed)
        model.connect("row-deleted", self._handle_row_deleted)
        model.connect("row-has-child-toggled", self._handle_row_has_child_toggled)
        model.connect("row-inserted", self._handle_row_insered)
        model.connect("rows-reordered", self._handle_rows_reordered)

    @GObject.property(type=Gtk.TreeModel)
    def model(self):
        return self._model

    def _translate_path_and_iter(path: Gtk.TreePath,
                                 iter: Optional[Gtk.TreeIter] = None):
        pass

    # Handle signals from TreeModels we use

    def _handle_row_changed(self, tree_model: Gtk.TreeModel,
                            path: Gtk.TreePath, iter: Gtk.TreeIter):
        assert tree_model is self.model
        assert path is not None
        assert iter is not None

        new_path, new_iter = self._translate_path_and_iter(path, iter)
        # self.row_inserted(new_path, new_iter)
        self.insert(new_iter, ...)

    def _handle_row_deleted(self, tree_model: Gtk.TreeModel,
                            path: Gtk.TreePath):
        assert tree_model is self.model
        assert path is not None

        self.remove(self.get_iter(path))

    def _handle_has_child_toggled(self, tree_model: Gtk.TreeModel,
                          path: Gtk.TreePath, iter: Gtk.TreeIter):
        self.has_child_toggled(path, self.get_iter(path))

    def _handle_row_inserted(self, tree_model: Gtk.TreeModel,
                             path: Gtk.TreePath, iter: Gtk.TreeIter):
        assert tree_model is self.model
        assert path is not None
        assert iter is not None

        new_path, new_iter = self._translate_path_and_iter(path, iter)
        self.row_inserted(new_path, new_iter)
        indices = path.get_indices()
        if indices == []:
            return

        new_pos = indices[-1]
        new_path = Gtk.TreePath.new_from_indices(indices[:-1])
        new_iter = self.get_iter(new_path)
        self.insert(new_iter, new_pos, values) # TODO: Fill values

    def _handle_rows_reordered(self, tree_model: Gtk.TreeModel,
                               path: Gtk.TreePath, iter: Gtk.TreeIter,
                               new_order: [int]):
        assert tree_model is self.model
        assert path is not None
        assert new_order is not None

        new_path, new_iter = self._translate_path_and_iter(path, iter)
        self._rows_reordered(new_path, new_iter, new_order)
