
# Implementation of the org.gnome.GTG.Tasks interface

from gi.repository import GLib
from GTG.core.logger import log
from GTG.core.search import parse_search_query, InvalidQuery
from GTG.core.dates import Date
from .dbus import DBusInterfaceImplService, DBusReturnError


def _task_to_dict(task):
    d = {
        "id": task.get_id(),
        "status": task.get_status(),
        "title": task.get_title(),
        "duedate": str(task.get_due_date()), # TODO: Check if str(Date) is correct
        "startdate": str(task.get_start_date()), # TODO: Check if str(Date) is correct
        "donedate": str(task.get_closed_date()), # TODO: Check if str(Date) is correct
        "tags": task.get_tags_name(),
        "text": task.get_text(),
        "subtasks": task.get_children(),
        "parents": task.get_parents(),
    }
    return d

_task_dict_to_variant_type = {
    "id": 's',
    "status": 's',
    "title": 's',
    "duedate": 's',
    "startdate": 's',
    "donedate": 's',
    "tags": 'as',
    "text": 's',
    "subtasks": 'as',
    "parents": 'as',
}

def _task_dict_to_variant(task_dict):
    """Convert an task dict to a variant dict to be submitted over DBus"""
    d = dict(task_dict)
    for name, vtype in _task_dict_to_variant_type.items():
        if name in task_dict:
            d[name] = GLib.Variant(vtype, task_dict[name])
    return d # Not GLib.Variant("a{sv}", d) because it'll break later
    # return GLib.Variant("a{sv}", d)

def _task_to_variant(task):
    """Convert an task object to a variant dict to be submitted over DBus"""
    return _task_dict_to_variant(_task_to_dict(task))

def _variant_to_task_dict(task_variant):
    """Convert an variant dict to a task"""
    return task_variant.unpack()


class DBusImplTasks(DBusInterfaceImplService):
    INTERFACE_NAME = 'org.gnome.GTG.Tasks'

    def __init__(self, req):
        super().__init__()
        self.req = req

        tree = req.get_main_view()
        # TODO: Register signals
        # tree.register_cllbck('node-added', lambda tid, _:
        #                           self.TaskAdded(tid))
        # tree.register_cllbck('node-modified', lambda tid, _:
        #                           self.TaskModified(tid))
        # tree.register_cllbck('node-deleted', lambda tid, _:
        #                           self.TaskDeleted(tid))

    def GetTasks(self, tids):
        log.debug(f"Doing GetTasks({tids})")
        # TODO: Improve on better error message on missing tasks or something
        # Current: Fehler: GDBus.Error:python.AttributeError: 'NoneType' object has no attribute 'get_id'
        return [_task_to_variant(self.req.get_task(tid)) for tid in tids]

    def GetActiveTasks(self):
        log.debug(f"Doing GetActiveTasks()")
        return self.GetTasksFiltered(['active', 'workable'])

    def GetTaskIdsFiltered(self, filters):
        log.debug(f"Doing GetTasksFiltered({filters})")
        tree = self.req.get_tasks_tree().get_basetree()
        view = tree.get_viewtree()
        for filter in filters:
            if filter[0] == '!':
                view.apply_filter(filter[1:], parameters={'negate': 1})
            else:
                view.apply_filter(filter)
        return view.get_all_nodes() # TODO: Check what it returns (type-wise)

    def GetTasksFiltered(self, filters):
        log.debug(f"Doing GetTasksFiltered({filters})")
        return self.GetTasks(self.GetTaskIdsFiltered(filters))

    def SearchTaskIds(self, query):
        log.debug(f"Doing SearchTaskIds({query})")
        tree = self.req.get_tasks_tree().get_basetree()
        view = tree.get_viewtree()
        try:
            search = parse_search_query(query)
            view.apply_filter('search', parameters=search)
            tasks = view.get_all_nodes()
            if tasks:
                return tasks
        except InvalidQuery:
            raise DBusReturnError("gtg.InvalidQuery", "Invalid Query: " + str(query))
        return []

    def SearchTasks(self, query):
        log.debug(f"Doing SearchTasks({query})")
        return self.GetTasks(self.SearchTaskIds(query))

    def HasTasks(self, tids):
        log.debug(f"Doing HasTasks({tids})")
        return {tid: self.req.has_task(tid) for tid in tids}

    def DeleteTasks(self, tids):
        log.debug(f"Doing DeleteTasks({tids})")
        d = {}
        for tid in tids:
            if self.req.has_task(tid):
                self.req.delete_task(tid)
                d[tid] = True
            else:
                d[tid] = False
        return d

    def NewTasks(self, tasks):
        log.debug(f"Doing NewTasks({tasks})")
        return [] # TODO: Implement this

    def ModifyTasks(self, patches):
        log.debug(f"Doing ModifyTasks({patches})")
        r = []
        for patch in patches:
            r.append(_task_to_variant(self._modify_task(patch)))
        return r

    def _modify_task(self, patch):
        """Modify a single task and return it"""
        task = self.req.get_task(patch["id"])
        if "title" in patch:
            task.set_title(patch["task"])
        if "text" in patch:
            task.set_text(patch["text"])
        if "duedate" in patch:
            task.set_due_date(Date.parse(patch["due_date"]))
        if "startdate" in patch:
            task.set_start_date(Date.parse(patch["start_date"]))
        if "donedate" in patch:
            pass # TODO
        if "tags" in patch:
            pass # TODO
        if "childrens" in patch:
            pass # TODO
        if "parents" in patch:
            pass # TODO
        return task

