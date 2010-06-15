# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Gettings Things Gnome! - a personal organizer for the GNOME desktop
# Copyright (c) 2008-2009 - Lionel Dricot & Bertrand Rousseau
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
"""
This is the TaskEditor

It's the window you see when you double-click on a Task
The main text widget is a home-made TextView called TaskView (see taskview.py)
The rest is the logic of the widget : date changing widgets, buttons, ...
"""
import time

try:
    import pygtk
    pygtk.require("2.0")
except: # pylint: disable-msg=W0702
    raise SystemExit(1)
try:
    import gtk
    from gtk import gdk
except: # pylint: disable-msg=W0702
    raise SystemExit(1)

from GTG                     import _
from GTG                     import ngettext
from GTG                     import PLUGIN_DIR
from GTG                     import DATA_DIR
from GTG.gtk.editor          import GnomeConfig
from GTG.gtk.editor.taskview import TaskView
from GTG.core.plugins.engine import PluginEngine
from GTG.core.plugins.api    import PluginAPI
from GTG.core.task           import Task
from GTG.tools               import dates


date_separator = "-"


class TaskEditor:
    #req is the requester
    #vmanager is the view manager
    #taskconfig is a ConfigObj dic to save infos about tasks
    #thisisnew is True when a new task is created and opened
    def __init__(self, 
                 requester, 
                 vmanager, 
                 task, 
                 plugins,
                 taskconfig = None,
                 plugin_apis = None,
                 thisisnew = False,
                 clipboard = None) :
        self.req = requester
        self.vmanager = vmanager
        self.config = taskconfig
        self.p_apis = plugin_apis
        self.time = None
        self.clipboard = clipboard
        self.builder = gtk.Builder() 
        self.builder.add_from_file(GnomeConfig.GLADE_FILE)
        self.donebutton = self.builder.get_object("mark_as_done_editor")
        self.dismissbutton = self.builder.get_object("dismiss_editor")
        self.deletebutton = self.builder.get_object("delete_editor")
        self.deletebutton.set_tooltip_text(GnomeConfig.DELETE_TOOLTIP)
        self.subtask_button = self.builder.get_object("insert_subtask")
        self.subtask_button.set_tooltip_text(GnomeConfig.SUBTASK_TOOLTIP)
        self.inserttag_button = self.builder.get_object("inserttag")
        self.inserttag_button.set_tooltip_text(GnomeConfig.TAG_TOOLTIP)
        #Create our dictionary and connect it
        dic = {
                "mark_as_done_clicked"  : self.change_status,
                "on_dismiss"            : self.dismiss,
                "delete_clicked"        : self.delete_task,
                "on_duedate_pressed"    : (self.on_date_pressed,"due"),
                "on_startdate_pressed"    : (self.on_date_pressed,"start"),
                "on_closeddate_pressed"   : (self.on_date_pressed, "closed"),
                "close_clicked"         : self.close,
                "startingdate_changed" : (self.date_changed,"start"),
                "duedate_changed" : (self.date_changed,"due"),
                "closeddate_changed"    : (self.date_changed, "closed"),
                "on_insert_subtask_clicked" : self.insert_subtask,
                "on_inserttag_clicked" : self.inserttag_clicked,
                "on_move" : self.on_move,
                "on_nodate"             : self.nodate_pressed,
                "on_set_fuzzydate_now"  : self.set_fuzzydate_now,
                "on_set_fuzzydate_soon" : self.set_fuzzydate_soon,
                "on_set_fuzzydate_later": self.set_fuzzydate_later,
        }
        self.builder.connect_signals(dic)
        self.window         = self.builder.get_object("TaskEditor")
        #Removing the Normal textview to replace it by our own
        #So don't try to change anything with glade, this is a home-made widget
        textview = self.builder.get_object("textview")
        scrolled = self.builder.get_object("scrolledtask")
        scrolled.remove(textview)
        self.textview   = TaskView(self.req,self.clipboard)
        self.textview.show()
        self.textview.set_subtask_callback(self.new_subtask)
        self.textview.open_task_callback(self.vmanager.open_task)
        self.textview.set_left_margin(7)
        self.textview.set_right_margin(5)
        scrolled.add(self.textview)
        #Voila! it's done
        self.calendar       = self.builder.get_object("calendar")
        self.cal_widget       = self.builder.get_object("calendar1")
        self.calendar_fuzzydate_btns       = self.builder.get_object("fuzzydate_btns")
        #self.cal_widget.set_property("no-month-change",True)
        self.sigid = None
        self.sigid_month = None
        #Do we have to close the calendar when date is changed ?
        #This is a ugly hack to close the calendar on the first click
        self.close_when_changed = True
        self.duedate_widget = self.builder.get_object("duedate_entry")
        self.startdate_widget = self.builder.get_object("startdate_entry")
        self.closeddate_widget = self.builder.get_object("closeddate_entry")
        self.dayleft_label  = self.builder.get_object("dayleft")
        self.tasksidebar = self.builder.get_object("tasksidebar")
        #We will keep the name of the opened calendar
        #Empty means that no calendar is opened
        self.__opened_date = ''
        
        # Define accelerator keys
        self.init_accelerators()
        
        self.task = task
        tags = task.get_tags()
        self.textview.subtasks_callback(task.get_children)
        self.textview.removesubtask_callback(task.remove_child)
        self.textview.set_get_tagslist_callback(task.get_tags_name)
        self.textview.set_add_tag_callback(task.add_tag)
        self.textview.set_remove_tag_callback(task.remove_tag)
        self.textview.save_task_callback(self.light_save)

        texte = self.task.get_text()
        title = self.task.get_title()
        #the first line is the title
        self.textview.set_text("%s\n"%title)
        #we insert the rest of the task
        if texte :
            self.textview.insert("%s"%texte)
        else :
            #If not text, we insert tags
            if tags :
                for t in tags :
                    self.textview.insert_text("%s, "%t.get_name())
                self.textview.insert_text("\n")
            #If we don't have text, we still need to insert subtasks if any
            subtasks = task.get_children()
            if subtasks :
                self.textview.insert_subtasks(subtasks)
        #We select the title if it's a new task
        if thisisnew :
            self.textview.select_title()
        else :
            self.task.set_to_keep()
        self.textview.modified(full=True)
        self.window.connect("destroy", self.destruction)
        
        # plugins
        self.plugins = plugins
        self.pengine = PluginEngine(PLUGIN_DIR)
        self.te_plugin_api = PluginAPI(window = self.window,
                                       config = None,
                                       data_dir = DATA_DIR,
                                       builder = self.builder, 
                                       requester = self.req,
                                       tagpopup = None,
                                       tagview = None,
                                       task = task, 
                                       view_manager = None,
                                       texteditor = self)
        self.p_apis.append(self.te_plugin_api)
        self.pengine.onTaskLoad(self.plugins)
        
        #Putting the refresh callback at the end make the start a lot faster
        self.textview.refresh_callback(self.refresh_editor)
        self.refresh_editor()
        self.textview.grab_focus()
        
        #restoring size and position, spatial tasks
        if self.config :
            tid = self.task.get_id()
            if tid in self.config:
                if "position" in self.config[tid]:
                    pos = self.config[tid]["position"]
                    self.move(pos[0],pos[1])
                    #print "restoring position %s %s" %(pos[0],pos[1])
                if "size" in self.config[tid]:
                    size = self.config[tid]["size"]
                    #print "size %s - %s" %(str(size[0]),str(size[1]))
                    #this eval(str()) is a hack to accept both int and str
                    self.window.resize(eval(str(size[0])),eval(str(size[1])))

        self.window.show()
        self.textview.set_editable(True)
        
        #Connection for the update
        self.req.connect('task-modified',self.task_modified)
        
    #FIXME: avoid to update to many time when we modify from the editor itself
    def task_modified(self,sender,tid):
        self.refresh_editor(refreshtext=True)

    # Define accelerator-keys for this dialog
    # TODO: undo/redo
    def init_accelerators(self):
        agr = gtk.AccelGroup()
        self.window.add_accel_group(agr)
        
        # Escape and Ctrl-W close the dialog. It's faster to call close
        # directly, rather than use the close button widget
        key, modifier = gtk.accelerator_parse('Escape')
        agr.connect_group(key, modifier, gtk.ACCEL_VISIBLE, self.close)
        
        key, modifier = gtk.accelerator_parse('<Control>w')
        agr.connect_group(key, modifier, gtk.ACCEL_VISIBLE, self.close)
        
        # Ctrl-N creates a new task
        key, modifier = gtk.accelerator_parse('<Control>n')
        agr.connect_group(key, modifier, gtk.ACCEL_VISIBLE, self.new_task)
        
        # Ctrl-Shift-N creates a new subtask
        insert_subtask = self.builder.get_object("insert_subtask")
        key, mod       = gtk.accelerator_parse("<Control><Shift>n")
        insert_subtask.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)
        
        # Ctrl-D marks task as done
        mark_as_done_editor = self.builder.get_object('mark_as_done_editor')
        key, mod = gtk.accelerator_parse('<Control>d')
        mark_as_done_editor.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)
        
        # Ctrl-I marks task as dismissed
        dismiss_editor = self.builder.get_object('dismiss_editor')
        key, mod = gtk.accelerator_parse('<Control>i')
        dismiss_editor.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)
        
    
    #Can be called at any time to reflect the status of the Task
    #Refresh should never interfere with the TaskView.
    #If a title is passed as a parameter, it will become
    #the new window title. If not, we will look for the task title.
    #Refreshtext is whether or not we should refresh the TaskView
    #(doing it all the time is dangerous if the task is empty)
    def refresh_editor(self, title=None, refreshtext=False):
        if self.window == None:
            return
        to_save = False
        #title of the window 
        if title :
            self.window.set_title(title)
            to_save = True
        else :
            self.window.set_title(self.task.get_title())
           
        status = self.task.get_status() 
        if status == Task.STA_DISMISSED:
            self.donebutton.set_label(GnomeConfig.MARK_DONE)
            self.donebutton.set_tooltip_text(GnomeConfig.MARK_DONE_TOOLTIP)
            self.donebutton.set_icon_name("gtg-task-done")
            self.dismissbutton.set_label(GnomeConfig.MARK_UNDISMISS)
            self.dismissbutton.set_tooltip_text(GnomeConfig.MARK_UNDISMISS_TOOLTIP)
            self.dismissbutton.set_icon_name("gtg-task-undismiss")
        elif status == Task.STA_DONE:
            self.donebutton.set_label(GnomeConfig.MARK_UNDONE)
            self.donebutton.set_tooltip_text(GnomeConfig.MARK_UNDONE_TOOLTIP)
            self.donebutton.set_icon_name("gtg-task-undone")
            self.dismissbutton.set_label(GnomeConfig.MARK_DISMISS)
            self.dismissbutton.set_tooltip_text(GnomeConfig.MARK_DISMISS_TOOLTIP)
            self.dismissbutton.set_icon_name("gtg-task-dismiss")
        else:
            self.donebutton.set_label(GnomeConfig.MARK_DONE)
            self.donebutton.set_tooltip_text(GnomeConfig.MARK_DONE_TOOLTIP)
            self.donebutton.set_icon_name("gtg-task-done")
            self.dismissbutton.set_label(GnomeConfig.MARK_DISMISS)
            self.dismissbutton.set_tooltip_text(GnomeConfig.MARK_DISMISS_TOOLTIP)
            self.dismissbutton.set_icon_name("gtg-task-dismiss")
            
        self.donebutton.show()
        self.tasksidebar.show()
        
        #Refreshing the status bar labels and date boxes
        if status in [Task.STA_DISMISSED, Task.STA_DONE]:
            self.builder.get_object("label2").hide()
            self.builder.get_object("hbox1").hide()
            self.builder.get_object("label4").show()
            self.builder.get_object("hbox4").show()
        else:
            self.builder.get_object("label4").hide()
            self.builder.get_object("hbox4").hide()
            self.builder.get_object("label2").show() 
            self.builder.get_object("hbox1").show()
             
        #refreshing the due date field
        duedate = self.task.get_due_date()
        prevdate = dates.strtodate(self.duedate_widget.get_text())
        if duedate != prevdate or type(duedate) is not type(prevdate):
            zedate = str(duedate).replace("-", date_separator)
            self.duedate_widget.set_text(zedate)
        # refreshing the closed date field
        closeddate = self.task.get_closed_date()
        prevcldate = dates.strtodate(self.closeddate_widget.get_text())
        if closeddate != prevcldate or type(closeddate) is not type(prevcldate):
            zecldate = str(closeddate).replace("-", date_separator)
            self.closeddate_widget.set_text(zecldate)
        #refreshing the day left label
        #If the task is marked as done, we display the delay between the 
        #due date and the actual closing date. If the task isn't marked 
        #as done, we display the number of days left.
        if status in [Task.STA_DISMISSED, Task.STA_DONE]:
            delay = self.task.get_days_late()
            if delay is None:
                txt = ""
            elif delay == 0:
                txt = "Completed on time"
            elif delay >= 1:
                txt = ngettext("Completed %(days)d day late", "Completed %(days)d days late", delay) % {'days': delay}
            elif delay <= -1:
                abs_delay = abs(delay)
                txt = ngettext("Completed %(days)d day early", "Completed %(days)d days early", abs_delay) % {'days': abs_delay}
        else:
            result = self.task.get_days_left()
            if result is None:
                txt = ""
            elif result > 0:
                txt = ngettext("Due tomorrow!", "%(days)d days left", result) % {'days': result}
            elif result == 0:
                txt = _("Due today!")
            elif result < 0:
                abs_result = abs(result)
                txt = ngettext("Due yesterday!", "Was %(days)d days ago", abs_result) % {'days': abs_result}
        window_style = self.window.get_style()
        color = str(window_style.text[gtk.STATE_INSENSITIVE])
        self.dayleft_label.set_markup("<span color='"+color+"'>"+txt+"</span>")

        startdate = self.task.get_start_date()
        prevdate = dates.strtodate(self.startdate_widget.get_text())
        if startdate != prevdate or type(startdate) is not type(prevdate):
            zedate = str(startdate).replace("-",date_separator)
            self.startdate_widget.set_text(zedate) 
        #Refreshing the tag list in the insert tag button
        taglist = self.req.get_used_tags()
        menu = gtk.Menu()
        tag_count = 0
        for t in taglist :
            if not self.task.has_tags(tag_list=[t]) :
                tag_count += 1
                mi = gtk.MenuItem(label=t, use_underline=False)
                mi.connect("activate",self.inserttag,t)
                mi.show()
                menu.append(mi)
        if tag_count > 0 :
            self.inserttag_button.set_menu(menu)

        if refreshtext:
            self.textview.modified(refresheditor=False)            
        if to_save:
            self.light_save()
            
        
    def date_changed(self,widget,data):
        text = widget.get_text()
        validdate = False
        if not text :
            validdate = True
            datetoset = dates.no_date
        else :
            datetoset = dates.strtodate(text)
            if datetoset :
                validdate = True
                
        if validdate :
            #If the date is valid, we write with default color in the widget
            # "none" will set the default color.
            widget.modify_text(gtk.STATE_NORMAL, None)
            widget.modify_base(gtk.STATE_NORMAL, None)
            if data == "start" :
                self.task.set_start_date(datetoset)
            elif data == "due" :
                self.task.set_due_date(datetoset)
            elif data == "closed" :
                self.task.set_closed_date(datetoset)
        else :
            #We should write in red in the entry if the date is not valid
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse("#F00"))
            widget.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("#F88"))

    def _mark_today_in_bold(self):
        today = dates.date_today()
        #selected is a tuple containing (year, month, day)
        selected = self.cal_widget.get_date()
        #the following "-1" is because in pygtk calendar the month is 0-based,
        # in gtg (and datetime.date) is 1-based.
        if selected[1] == today.month() - 1 and selected[0] == today.year():
            self.cal_widget.mark_day(today.day())
        else:
            self.cal_widget.unmark_day(today.day())
        
        
    def on_date_pressed(self, widget,data): 
        """Called when the due button is clicked."""
        
        self.__opened_date = data
        if self.__opened_date == "due" :
            toset = self.task.get_due_date()
            self.calendar_fuzzydate_btns.show()
        elif self.__opened_date == "start" :
            toset = self.task.get_start_date()
            self.calendar_fuzzydate_btns.hide()
        elif self.__opened_date == "closed" :
            toset = self.task.get_closed_date()
            self.calendar_fuzzydate_btns.hide()
        
        rect = widget.get_allocation()
        x, y = widget.window.get_origin()
        cal_width, cal_height = self.calendar.get_size()
        self.calendar.move((x + rect.x - cal_width + rect.width)
                                            , (y + rect.y - cal_height))
        self.calendar.show()
        """Because some window managers ignore move before you show a window."""
        self.calendar.move((x + rect.x - cal_width + rect.width)
                                            , (y + rect.y - cal_height))
        
        self.calendar.grab_add()
        #We grab the pointer in the calendar
        gdk.pointer_grab(self.calendar.window, True,gdk.BUTTON1_MASK|gdk.MOD2_MASK)
        #we will close the calendar if the user clicks outside
        
        if not isinstance(toset, dates.FuzzyDate):
            if not toset:
                # we set the widget to today's date if there is not a date defined
                toset = dates.date_today()

            y = toset.year()
            m = toset.month()
            d = int(toset.day())
            
            #We have to select the day first. If not, we might ask for
            #February while still being on 31 -> error !
            self.cal_widget.select_day(d)
            self.cal_widget.select_month(int(m)-1,int(y))

        self._mark_today_in_bold()
            
        self.calendar.connect('button-press-event', self.__focus_out)
        self.sigid = self.cal_widget.connect("day-selected",self.day_selected)
        self.sigid_month = self.cal_widget.connect("month-changed",self.month_changed)

    def day_selected(self,widget) :
        y,m,d = widget.get_date()
        if self.__opened_date == "due" :
            self.task.set_due_date(dates.strtodate("%s-%s-%s"%(y,m+1,d)))
        elif self.__opened_date == "start" :
            self.task.set_start_date(dates.strtodate("%s-%s-%s"%(y,m+1,d)))
        elif self.__opened_date == "closed" :
            self.task.set_closed_date(dates.strtodate("%s-%s-%s"%(y,m+1,d)))
        if self.close_when_changed :
            #When we select a day, we connect the mouse release to the
            #closing of the calendar.
            self.mouse_sigid = self.cal_widget.connect('event',self.__mouse_release)
        else :
            self.close_when_changed = True
        self.refresh_editor()
        
    def __mouse_release(self,widget,event):
        if event.type == gtk.gdk.BUTTON_RELEASE:
            self.__close_calendar()
            self.cal_widget.disconnect(self.mouse_sigid)
        
    def month_changed(self,widget) :
        #This is a ugly hack to close the calendar on the first click
        self.close_when_changed = False
        self._mark_today_in_bold()

    def set_opened_date(self, date):
        if self.__opened_date == "due" :
            self.task.set_due_date(date)
        elif self.__opened_date == "start" :
            self.task.set_start_date(date)
        elif self.__opened_date == "closed" :
            self.task.set_closed_date(date)
        self.refresh_editor()
        self.__close_calendar()
        
    def nodate_pressed(self,widget) : #pylint: disable-msg=W0613
        self.set_opened_date(dates.no_date)
        
    def set_fuzzydate_now(self, widget) : #pylint: disable-msg=W0613
        self.set_opened_date(dates.NOW)
        
    def set_fuzzydate_soon(self, widget) : #pylint: disable-msg=W0613
        self.set_opened_date(dates.SOON)
        
    def set_fuzzydate_later(self, widget) : #pylint: disable-msg=W0613
        self.set_opened_date(dates.LATER)
        
    def dismiss(self,widget) : #pylint: disable-msg=W0613
        stat = self.task.get_status()
        if stat == "Dismiss":
            self.task.set_status("Active")
            self.refresh_editor()
        else:
            self.task.set_status("Dismiss")
            self.close(None)
    
    def change_status(self,widget) : #pylint: disable-msg=W0613
        stat = self.task.get_status()
        if stat == "Done":
            self.task.set_status("Active")
            self.refresh_editor()
        else:
            self.task.set_status("Done")
            self.close(None)
    
    def delete_task(self, widget) :
        #this triggers the closing of the window in the view manager
        self.vmanager.ask_delete_tasks([self.task.get_id()])
    
    #Take the title as argument and return the subtask ID
    def new_subtask(self,title=None,tid=None) :
        if tid:
            self.task.add_child(tid)
        elif title:
            subt = self.task.new_subtask()
            subt.set_title(title)
            tid = subt.get_id()
        return tid

    # Create a new task
    def new_task(self, *args):
        task = self.req.new_task(newtask=True)
        task_id = task.get_id()
        self.vmanager.open_task(task_id)
        
    def insert_subtask(self,widget) : #pylint: disable-msg=W0613
        self.textview.insert_newtask()
        self.textview.grab_focus()
        
    def inserttag_clicked(self,widget) : #pylint: disable-msg=W0613
        itera = self.textview.get_insert()
        if itera.starts_line() :
            self.textview.insert_text("@",itera)
        else :
            self.textview.insert_text(" @",itera)
        self.textview.grab_focus()
        
    def inserttag(self,widget,tag) : #pylint: disable-msg=W0613
        self.textview.insert_tags([tag])
        self.textview.grab_focus()
    
    def save(self) :
        self.task.set_title(self.textview.get_title())
        self.task.set_text(self.textview.get_text()) 
        self.task.sync()
        if self.config != None:
            self.config.write()
        self.time = time.time()
    #light_save save the task without refreshing every 30seconds
    #We will reduce the time when the get_text will be in another thread
    def light_save(self) :
        #if self.time is none, we never called any save
        if self.time:
            diff = time.time() - self.time
            tosave = diff > GnomeConfig.SAVETIME
        else:
            #we don't want to save a task while opening it
            tosave = self.textview.get_editable()
            diff = None
        if tosave:
            self.save()
        
        
    #This will bring the Task Editor to front    
    def present(self):
        self.window.present()
    def move(self,x,y):
        try:
            xx=int(x)
            yy=int(y)
            self.window.move(xx,yy)
        except:
            pass
    def get_position(self):
        return self.window.get_position()
        
    def on_move(self,widget,event):
        #saving the position
        if self.config != None:
            tid = self.task.get_id()
            if not tid in self.config :
                self.config[tid] = dict()
            #print "saving task position %s" %str(self.get_position())
            self.config[tid]["position"] = self.get_position()
            self.config[tid]["size"] = self.window.get_size()
        
    #We define dummy variable for when close is called from a callback
    def close(self,window=None,a=None,b=None,c=None): #pylint: disable-msg=W0613
        #We should also destroy the whole taskeditor object.
        if self.window:
            self.window.destroy()
            self.window = None
    
    #The destroy signal is linked to the "close" button. So if we call
    #destroy in the close function, this will cause the close to be called twice
    #To solve that, close will just call "destroy" and the destroy signal
    #Will be linked to this destruction method that will save the task
    def destruction(self,a=None) :#pylint: disable-msg=W0613
        #Save should be also called when buffer is modified
        self.pengine.onTaskClose(self.plugins, self.te_plugin_api)
        self.p_apis.remove(self.te_plugin_api)
        tid = self.task.get_id()
        if self.task.is_new():
            self.req.delete_task(tid)
        else:
            self.save()
            for i in self.task.get_subtasks():
                if i:
                    i.set_to_keep()
        self.vmanager.close_task(tid)
        
############# Private functions #################
        
    
    def __focus_out(self,w=None,e=None) : #pylint: disable-msg=W0613
        #We should only close if the pointer click is out of the calendar !
        p = self.calendar.window.get_pointer()
        s = self.calendar.get_size()
        if  not(0 <= p[0] <= s[0] and 0 <= p[1] <= s[1]) :
            self.__close_calendar()
        
    
    def __close_calendar(self,widget=None,e=None) : #pylint: disable-msg=W0613
        self.calendar.hide()
        self.__opened_date = ''
        gtk.gdk.pointer_ungrab()
        self.calendar.grab_remove()
        if self.sigid :
            self.cal_widget.disconnect(self.sigid)
            self.sigid = None
        if self.sigid_month :
            self.cal_widget.disconnect(self.sigid_month)
            self.sigid_month = None
