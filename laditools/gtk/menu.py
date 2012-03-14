#!/usr/bin/python
# LADITools - Linux Audio Desktop Integration Tools
# Copyright (C) 2011-2012 Alessio Treglia <quadrispro@ubuntu.com>
# Copyright (C) 2007-2010:
# * Marc-Olivier Barre <marco@marcochapeau.org>
# * Nedko Arnaudov <nedko@arnaudov.name>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import subprocess
from gi.repository import Gtk
from gi.repository import GObject
from .. import _gettext_domain
from .. import LadiConfiguration
from .. import JackConfigProxy
from .. import JackController
from .. import A2jController
from .. import LadishProxy
from .. import LadiManager

# Default launcher menu :
menu_default = {"Logs": "ladilog"}

class LadiMenu(LadiManager):
    def __init__(self, menu_config_array, jack_autostart = False):
        LadiManager.__init__(self, jack_autostart)
        # Handle the configuration and grab custom menu items
        self.menu_array = menu_config_array
        # Add some defaults if we don't already have a menu
        if not self.menu_array:
            self.menu_array = menu_default

        if jack_autostart:
            self.jack_start ()

    def set_diagnose_text(self, text):
        self.diagnose_text = text

    def clear_diagnose_text(self):
        self.diagnose_text = ""

    def name_dialog(self, title, label, text):
        dlg = Gtk.Dialog(
            title,
            None,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dlg.add_buttons (Gtk.STOCK_CANCEL,
                         Gtk.ResponseType.REJECT,
                         Gtk.STOCK_OK,
                         Gtk.ResponseType.ACCEPT)

        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(label), True, True, 0)
        entry = Gtk.Entry()
        entry.set_text(text)
        hbox.pack_start(entry, True, True, 0)
        dlg.vbox.pack_start(hbox, True, True, 0)
        dlg.show_all()
        #entry.set_activates_default(True)
        #dlg.set_default_response(Gtk.ResponseType.OK)
        ret = dlg.run()
        new_text = entry.get_text()
        dlg.destroy()
        if ret == Gtk.ResponseType.ACCEPT:
            return True, new_text
        else:
            return False, text

    def studio_new(self):
        accept, name = self.name_dialog(_("New studio"), _("Studio name"), "")
        if accept:
            LadiManager.studio_new(self, name=name)

    def studio_rename(self):
        accept, name = self.name_dialog(_("Rename studio"),
                                        _("Studio name"),
                                        self.get_ladish_controller().studio_name())
        if accept:
            LadiManager.studio_rename(self, name=name)

    def studio_delete(self, item, event, studio):
        dlg = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.YES_NO, "")
        dlg.set_markup(_("<b><big>Confirm studio delete</big></b>"))
        dlg.format_secondary_text(_("Studio \"%s\" will be deleted. Are you sure?") % studio)
        ret = dlg.run()
        dlg.destroy()
        if ret == Gtk.ResponseType.YES:
            LadiManager.studio_delete(self, studio=studio)

    def on_menu_show_diagnose(self, widget, data=None):
        dlg = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, self.diagnose_text)
        dlg.set_title(_("Cannot communicate JACK D-Bus"))
        dlg.run()
        dlg.destroy()

    def on_menu_command(self, widget, function):
        try:
            function()
        except Exception, e:
            error = Gtk.MessageDialog(None,
                                      Gtk.DialogFlags.MODAL,
                                      Gtk.MessageType.ERROR,
                                      Gtk.ButtonsType.OK,
                                      _("Error executing ") +
                                      repr(function) +
                                      _("Unexpected error\n\n") + repr(e))
            error.run()
            error.destroy()

    def on_menu_launcher(self, widget, command):
        LadiManager.launcher_exec(self, command.split())

    def menu_clear(self, menu):
        menu.foreach(lambda item,none: menu.remove(item), None)

    def studio_configure(self, item, event, module):
        LadiManager.launcher_exec(self, ['ladiconf', '-m', module])

    def configure_list_fill(self, widget, function):
        menu = widget.get_submenu()
        self.menu_clear(menu)
        try:
            jack = self.get_jack_configure()
            # 'engine' item
            item = Gtk.MenuItem(_("JACK engine"))
            item.show()
            menu.append(item)
            item.connect("button-release-event", function, "engine")
            # 'params' item
            item = Gtk.MenuItem(_('JACK "%s" driver') % jack.get_selected_driver())
            item.show()
            menu.append(item)
            item.connect("button-release-event", function, "params")
            for internal in jack.read_container(['internals']):
                module = str(internal)
                item = Gtk.MenuItem(_('JACK "%s"') % module)
                item.show()
                menu.append(item)
                item.connect("button-release-event", function, module)
        except Exception, err:
            print str(err)
        if not menu.get_children():
            item = Gtk.MenuItem(_("Empty config list"))
            item.set_sensitive(False)
            item.show()
            menu.append(item)

    def studio_list_fill(self, widget, function):
        menu = widget.get_submenu()
        self.menu_clear(menu)
        try:
            for studio in self.studio_list():
                item = Gtk.MenuItem(studio)
                item.show()
                menu.append(item)
                item.connect("button-release-event", function, studio) # "activate" is not used because of focus bug in pygtk
        except Exception, e:
            self.menu_clear(menu)
            item = Gtk.MenuItem(_("Error obtaining studio list"))
            item.set_sensitive(False)
            item.show()
            menu.append(item)
        if not menu.get_children():
            item = Gtk.MenuItem(_("Empty studio list"))
            item.set_sensitive(False)
            item.show()
            menu.append(item)

    def create_menu(self):
        menu_items = []

        if self.diagnose_text:
            menu_items.append((Gtk.ImageMenuItem(_("Diagnose")), self.on_menu_show_diagnose, None))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))

        if self.ladish_is_available():
            menu_items.append((Gtk.ImageMenuItem(_("Start gladish")), self.on_menu_launcher, "gladish"))

        menu_items.append((Gtk.ImageMenuItem("Configure ..."), self.configure_list_fill, self.studio_configure))
        # Add the laucher entries at the beginning of the menu
        for item in self.menu_array:
            # Replace "Configure" static item with the new sub-menu
            if item == 'configure':
                continue
            menu_label = item.capitalize() + "..."
            path = self.menu_array[item]
            menu_items.append((Gtk.ImageMenuItem(menu_label), self.on_menu_launcher, path))

        menu = Gtk.Menu()
        menu_items.append((Gtk.SeparatorMenuItem.new(),))
        if self.ladish_is_available():
            menu_items.append((Gtk.ImageMenuItem(_("New studio...")), self.on_menu_command, self.studio_new))
            menu_items.append((Gtk.ImageMenuItem(_("Load studio")), self.studio_list_fill, self.studio_load))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))
            if self.studio_is_loaded():
                if self.studio_is_started():
                    menu_items.append((Gtk.ImageMenuItem(_("Stop studio")), self.on_menu_command, self.studio_stop))
                else:
                    menu_items.append((Gtk.ImageMenuItem(_("Start studio")), self.on_menu_command, self.studio_start))
            else:
                menu_items.append((Gtk.ImageMenuItem(_("Start automatic studio")), self.on_menu_command, self.jack_start))
            if self.studio_is_loaded():
                menu_items.append((Gtk.ImageMenuItem(_("Rename studio...")), self.on_menu_command, self.studio_rename))
                menu_items.append((Gtk.ImageMenuItem(_("Save studio")), self.on_menu_command, self.studio_save))
                menu_items.append((Gtk.ImageMenuItem(_("Unload studio")), self.on_menu_command, self.studio_unload))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))
            menu_items.append((Gtk.ImageMenuItem(_("Delete studio")), self.studio_list_fill, self.studio_delete))
            menu_items.append((Gtk.ImageMenuItem(_("Reactivate ladishd")), self.on_menu_command, self.ladish_reactivate))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))
        if self.jack_is_available():
            if not self.jack_is_started():
                if not self.ladish_is_available():
                    menu_items.append((Gtk.ImageMenuItem(_("Start JACK server")), self.on_menu_command, self.jack_start))
            else:
                menu_items.append((Gtk.ImageMenuItem(_("Reset Xruns")), self.on_menu_command, self.jack_reset_xruns))
                if not self.ladish_is_available():
                    menu_items.append((Gtk.ImageMenuItem(_("Stop JACK server")), self.on_menu_command, self.jack_stop))
            menu_items.append((Gtk.ImageMenuItem(_("Reactivate JACK")), self.on_menu_command, self.jack_reactivate))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))
        if self.a2j_is_available():
            # when a2jmidid is used in used with ladish, a2j script should be used
            # for managing bridge "active" lifetime
            if not self.ladish_is_available():
                if not self.a2j_is_started():
                    menu_items.append((Gtk.ImageMenuItem(_("Start A2J bridge")), self.on_menu_command, self.a2j_start))
                else:
                    menu_items.append((Gtk.ImageMenuItem(_("Stop A2J bridge")), self.on_menu_command, self.a2j_stop))
            menu_items.append((Gtk.ImageMenuItem(_("Reactivate A2J")), self.on_menu_command, self.a2j_reactivate))
            menu_items.append((Gtk.SeparatorMenuItem.new(), None, None))
        if hasattr(self, 'on_about'):
            menu_items.append((Gtk.ImageMenuItem(_("About")), self.on_about, None))
        menu_items.append((Gtk.ImageMenuItem(_("Quit")), self.on_menu_command, Gtk.main_quit))

        for menu_tuple in menu_items:
            item = menu_tuple[0]
            if len(menu_tuple) > 1:
                callback = menu_tuple[1]
                exec_path = menu_tuple[2]
            menu.append(item)
            if type(item) is not Gtk.SeparatorMenuItem:
                if callback in (self.studio_list_fill, self.configure_list_fill):
                    item.set_submenu(Gtk.Menu())
                item.connect("activate", callback, exec_path)
        menu.show_all()
        return menu

    def menu_activate(self):
        menu = self.create_menu()
        menu.popup(parent_menu_shell=None,
                   parent_menu_item=None,
                   func=None,
                   data=None,
                   button=3,
                   activate_time=0)
        menu.reposition()
