# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os, sys, re, tempfile, time, png

# An IPython shell to use in the terminal.
try:
    from IPython.terminal.embed import InteractiveShellEmbed
except ImportError:
    from IPython.frontend.terminal.embed import InteractiveShellEmbed
InteractiveShellEmbed.readline_use = False
InteractiveShellEmbed.autoindent = False
# Temporary hack to enable colors without readline.
# IPython says this will be removed in the future.
InteractiveShellEmbed.colors_force = True

import snappy
from snappy.tkterminal import TkTerm
from snappy.app_menus import dirichlet_menus, horoball_menus, really_disable_menu_items
from snappy.app_menus import togl_save_image, add_menu, scut, SnapPy_help
from snappy import filedialog
from snappy import SnapPeaFatalError
from snappy.polyviewer import PolyhedronViewer
from snappy.horoviewer import HoroballViewer
from snappy.browser import Browser
from snappy.SnapPy import SnapPea_interrupt, msg_stream
from snappy.preferences import Preferences, PreferenceDialog
from snappy.infodialog import about_snappy
from snappy.phone_home import update_needed
try:
    import Tkinter as Tk_
    import tkMessageBox
    from tkMessageBox import askyesno
    from tkFont import Font

except ImportError: # Python 3
    import tkinter as Tk_
    import tkinter.messagebox as tkMessageBox
    from tkinter.messagebox import askyesno 
    from tkinter.font import Font

from plink import LinkEditor
from plink.smooth import Smoother

class ListedInstance(object):

    def to_front(self):
        self.window_master.update_window_menu()
        self.window.lift()
        self.window.focus_force()
        self.focus(event=None)

    def focus(self, event):
        self.focus_var.set(1)

    def unfocus(self, event):
        self.focus_var.set(0)

class SnapPyTerm(TkTerm, ListedInstance):

    def __init__(self, the_shell):
        self.window_master = self
        self.window_list=[self]
        self.menu_title = 'SnapPy Shell'
        TkTerm.__init__(self, the_shell, name='SnapPy Command Shell')
        self.prefs = SnapPyPreferences(self)
        self.start_interaction()
        self.edit_config(None)
        if sys.platform == 'darwin':
            assert str(self.window) == "."
            # Under OS X, the main window shouldn't be closable.
            self.window.protocol('WM_DELETE_WINDOW', lambda : self.window.iconify())
            self.window.createcommand("::tk::mac::OpenDocument",
                                  self.OSX_open_filelist)
            really_disable_menu_items(self.menubar)
        else:
            self.window.tk.call('namespace', 'import', '::tk::dialog::file::')
            self.window.tk.call('set', '::tk::dialog::file::showHiddenBtn',  '1')
            self.window.tk.call('set', '::tk::dialog::file::showHiddenVar',  '0')

    def add_bindings(self):
        self.text.bind_all('<ButtonRelease-1>', self.edit_config)
        self.window.bind('<FocusIn>', self.focus)
        self.window.bind('<FocusOut>', self.unfocus)
        self.focus_var = Tk_.IntVar(value=1)

    def build_menus(self):
        self.menubar = menubar = Tk_.Menu(self.window)
        Python_menu = Tk_.Menu(menubar, name="apple")
        Python_menu.add_command(label='About SnapPy...',
                                command=lambda : about_snappy(self.window))
        Python_menu.add_separator()
        Python_menu.add_command(label='SnapPy Preferences...',
                                command=self.edit_prefs)
        if sys.platform in ('linux2', 'win32'):
            Python_menu.add_separator()
            Python_menu.add_command(label='Quit SnapPy', command=self.close)
        menubar.add_cascade(label='SnapPy', menu=Python_menu)
        File_menu = Tk_.Menu(menubar, name='file')
        add_menu(self.window, File_menu, 'Open...', self.open_file)
        add_menu(self.window, File_menu, 'Open link...', self.open_link_file)
        add_menu(self.window, File_menu, 'Save', self.save_file, state='disabled')
        add_menu(self.window, File_menu, 'Save as...', self.save_file_as)
        menubar.add_cascade(label='File', menu=File_menu)
        Edit_menu = Tk_.Menu(menubar, name='edit')
        add_menu(self.window, Edit_menu, 'Cut', 
                 lambda event=None: self.text.event_generate('<<Cut>>'))
        add_menu(self.window, Edit_menu, 'Copy',
                 lambda event=None: self.text.event_generate('<<Copy>>'))
        add_menu(self.window, Edit_menu, 'Paste',
                 lambda event=None: self.text.event_generate('<<Paste>>'))
        add_menu(self.window, Edit_menu, 'Delete',
                 lambda event=None: self.text.event_generate('<<Clear>>')) 
        menubar.add_cascade(label='Edit', menu=Edit_menu)
        self.window_menu = window_menu = Tk_.Menu(menubar, name='window')
        menubar.add_cascade(label='Window', menu=window_menu)
        self.update_window_menu()
        Help_menu = Tk_.Menu(menubar, name="help")
        Help_menu.add_command(label='Help on SnapPy...', command=SnapPy_help)
        menubar.add_cascade(label='Help', menu=Help_menu)

    def update_window_menu(self):
        if sys.platform == 'darwin':
            return
        self.window_menu.delete(0,'end')
        for instance in self.window_list:
            self.window_menu.add_command(
                label=instance.menu_title,
                command=instance.to_front)

    def add_listed_instance(self, instance):
        self.window_list.append(instance)

    def delete_listed_instance(self, instance):
        self.window_list.remove(instance)

    def edit_prefs(self):
        apple_menu = self.menubar.children['apple']
        apple_menu.entryconfig(2, state='disabled')
        dialog = PreferenceDialog(self.window, self.prefs)
        if dialog.okay:
            answer = askyesno('Save?',
                              'Do you want to save these settings?')
            if answer:
                self.prefs.write_prefs()
        apple_menu.entryconfig(2, state='active')

    def edit_config(self, event):
        edit_menu = self.menubar.children['edit']
        if sys.platform == 'darwin':
            activate, deactivate, rest = [2], [], [0, 1, 3]
        else:
            activate, deactivate, rest = [], [0, 3], [1, 2]
        try:
            self.text.get(Tk_.SEL_FIRST, Tk_.SEL_LAST)
            activate += rest
        except Tk_.TclError:
            deactivate += rest

        for i in activate:
            edit_menu.entryconfig(i, state='active')
        for i in deactivate:
            edit_menu.entryconfig(i, state='disabled')

    def OSX_open_filelist(self, *args):
        for arg in args:
            sys.stderr.write(repr(arg)+'\n')

    def open_file(self, event=None):
        openfile = filedialog.askopenfile(
            title='Run Saved Transcript In Current Namespace',
            defaultextension='.py',
            filetypes = [
                ("Python and text files", "*.py *.ipy *.txt", "TEXT"),
                ("All text files", "", "TEXT"),
                ("All files", "")])
        if openfile:
            lines = openfile.readlines()
            openfile.close()
            if re.search("%\s*[lL]ink\s*[Pp]rojection", lines[0]):
                tkMessageBox.showwarning('Bad file',
                                         'This is a SnapPea link projection file, not a session transcript.')
            elif re.search("%\s*[tT]riangulation", lines[0]):
                tkMessageBox.showwarning('Bad file',
                                         'This is a SnapPea triangulation file, not a session transcript.')
            elif re.search("%\s*Generators", lines[0]):
                tkMessageBox.showwarning('Bad file',
                                         'This is a SnapPea generator file, not a session transcript.')
            else:
                for line in lines:
                    if line.startswith('#') or len(line) == 1:
                        continue
                    self.write(line)
                    self.interact_handle_input(line)
                    self.interact_prompt()

    def open_link_file(self):
        openfile = filedialog.askopenfile(
            title='Load Link Projection File',
            defaultextension='.lnk',
            filetypes = [
                ("Link and text files", "*.lnk *.txt", "TEXT"),
                ("All text files", "", "TEXT"),
                ("All files", "")])
        if openfile:
            if not re.search("%\s*[lL]ink\s*[Pp]rojection", openfile.readline()):
                tkMessageBox.showwarning('Bad file',
                                         'This is not a SnapPea link projection file')
                openfile.close()
            else:
                name = openfile.name
                openfile.close()
                line = "Manifold()\n"
                self.write(line)
                self.interact_handle_input(line)
                self.interact_prompt()
                M = self.IP.user_ns['_']
                M.LE.load(file_name=name)

    def save_file_as(self, event=None):
        savefile = filedialog.asksaveasfile(
            mode='w',
            title='Save Transcript as a Python script',
            defaultextension='.py',
            filetypes = [
                ("Python and text files", "*.py *.ipy *.txt", "TEXT"),
                ("All text files", "", "TEXT"),
                ("All files", "")])
        if savefile:
            savefile.write("""\
#!/usr/bin/env/python
# This script was saved by SnapPy on %s.
"""%time.asctime())
            inputs = self.IP.history_manager.input_hist_raw
            results = self.IP.history_manager.output_hist
            for n in range(1,len(inputs)):
                savefile.write('\n'+re.sub('\n+','\n',inputs[n]) +'\n')
                try:
                    output = repr(results[n]).split('\n')
                except KeyError:
                    continue
                for line in output:
                    savefile.write('#' + line + '\n')
            savefile.close()

    def save_file(self, event=None):
        self.window.bell()
        self.write2('Save As\n')

# These classes assume that the global variable "terminal" exists

class SnapPyBrowser(Browser, ListedInstance):
    def __init__(self, manifold):
        Browser.__init__(self, manifold, terminal.window)
        self.prefs = terminal.prefs
        self.menu_title = self.window.title()
        self.focus_var = Tk_.IntVar(self.window)
        self.window_master = terminal
        self.window_master.add_listed_instance(self)
        self.window_master.update_window_menu()
        self.window.bind('<FocusIn>', self.focus)
        self.window.bind('<FocusOut>', self.unfocus)
        if sys.platform=='darwin':
            really_disable_menu_items(self.menubar)

    def close(self, event=None):
        window_list = self.window_master.window_list
        if self in window_list:
                window_list.remove(self)
        self.window_master.update_window_menu()
        self.window.destroy()

class SnapPyLinkEditor(LinkEditor, ListedInstance):
    def __init__(self, root=None, no_arcs=False, callback=None, cb_menu='',
                 manifold=None, file_name=None):
        self.manifold = manifold
        self.focus_var = Tk_.IntVar()
        self.window_master = terminal
        LinkEditor.__init__(self, root=terminal.window, no_arcs=no_arcs,
                            callback=callback, cb_menu=cb_menu,
                            manifold=manifold, file_name=file_name)
        self.set_title()
        self.window_master.add_listed_instance(self)
        self.window_master.update_window_menu()
        self.window.bind('<FocusIn>', self.focus)
        self.window.bind('<FocusOut>', self.unfocus)
        self.window.focus_set()
        self.window.update_idletasks()
        if sys.platform == 'darwin':
            really_disable_menu_items(self.menubar)
        self.window.after_idle(self.set_title)

    def set_title(self):
        # Try to determine the variable associated to the manifold:
        title = 'Plink Editor'
        if self.IP:
            ns = self.IP.user_ns
            names = [name for name in ns
                     if ns[name] is self.manifold]
            if names:
                names.sort(key=lambda x : '}'+x if x.startswith('_') else x)
                title += ' - %s' % names[0]
            else:
                count = self.IP.execution_count
                if ns['_'] is self.manifold:
                    title += ' - Out[%d]'%count
        self.window.title(title)
        self.menu_title = title

    def focus(self, event):
        self.focus_in(event)
        ListedInstance.focus(self, event)

    def unfocus(self, event):
        self.focus_out(event)
        ListedInstance.unfocus(self, event)

    def build_menus(self):
        self.menubar = menubar = Tk_.Menu(self.window)
        Python_menu = Tk_.Menu(menubar, name="apple")
        Python_menu.add_command(label='About PLink...', command=self.about)
        Python_menu.add_separator()
        Python_menu.add_command(label='Preferences...', state='disabled')
        Python_menu.add_separator()
        if sys.platform == 'linux2':
            Python_menu.add_command(label='Quit SnapPy', command=terminal.close)
        menubar.add_cascade(label='SnapPy', menu=Python_menu)
        File_menu = Tk_.Menu(menubar, name='file')
        add_menu(self.window, File_menu, 'Open...', self.load)
        add_menu(self.window, File_menu, 'Save as...', self.save)
        self.build_save_image_menu(menubar, File_menu) # Add image save menu
        File_menu.add_separator()
        if self.callback:
            add_menu(self.window, File_menu, 'Close', self.done)
        else:
            add_menu(self.window, File_menu, 'Exit', self.done)
        menubar.add_cascade(label='File', menu=File_menu)

        Edit_menu = Tk_.Menu(menubar, name='edit')

        add_menu(self.window, Edit_menu, 'Cut', None, state='disabled')
        add_menu(self.window, Edit_menu, 'Copy', None, state='disabled')
        add_menu(self.window, Edit_menu, 'Paste', None, state='disabled')
        add_menu(self.window, Edit_menu, 'Delete', None, state='disabled')
        menubar.add_cascade(label='Edit', menu=Edit_menu)
        self.build_plink_menus() # Application Specific Menus
        Window_menu = self.window_master.menubar.children['window']
        menubar.add_cascade(label='Window', menu=Window_menu)
        Help_menu = Tk_.Menu(menubar, name="help")
        Help_menu.add_command(label='Help on PLink ...', command=SnapPy_help)
        menubar.add_cascade(label='Help', menu=Help_menu)
        self.window.config(menu=menubar)

    def to_front(self):
        self.set_title()
        ListedInstance.to_front(self)

    def copy_info(self):
        if not self.infotext.selection_present():
           self.infotext.selection_range(0, Tk_.END)
        self.infotext.focus()
        self.infotext.event_generate('<<Copy>>')

    def load(self, event=None, file_name=None):
        LinkEditor.load(self, file_name)

    def save(self, event=None):
        LinkEditor.save(self)

class SnapPyPolyhedronViewer(PolyhedronViewer, ListedInstance):
    def __init__(self, facedicts, root=None, title='Polyhedron Viewer'):
        self.focus_var = Tk_.IntVar()
        self.window_master = terminal
        PolyhedronViewer.__init__(self, facedicts, root=terminal.window,
                                  title=title)
        self.menu_title = self.window.title()
        self.window_master.add_listed_instance(self)
        self.window_master.update_window_menu()
        self.window.bind('<FocusIn>', self.focus)
        self.window.bind('<FocusOut>', self.unfocus)
        if sys.platform=='darwin':
            really_disable_menu_items(self.menubar)

    def add_help(self):
        pass

    build_menus = dirichlet_menus

    def close(self):
        self.polyhedron.destroy()
        self.window_master.window_list.remove(self)
        self.window_master.update_window_menu()
        self.window.destroy()

    def save_image(self):
        togl_save_image(self)

class SnapPyHoroballViewer(HoroballViewer, ListedInstance):
    def __init__(self, nbhd, which_cusp=0, cutoff=None,
                 root=None, title='Horoball Viewer'):
        self.focus_var = Tk_.IntVar()
        self.window_master = terminal
        HoroballViewer.__init__(self, nbhd, which_cusp=which_cusp,
                                cutoff=cutoff, root=terminal.window,
                                title=title, prefs = terminal.prefs)
        self.menu_title = self.window.title()
        self.window_master.add_listed_instance(self)
        self.window_master.update_window_menu()
        self.window.bind('<FocusIn>', self.focus)
        self.window.bind('<FocusOut>', self.unfocus)
        self.view_check()
        if sys.platform=='darwin':
            really_disable_menu_items(self.menubar)

    build_menus = horoball_menus

    def close(self):
        self.widget.activate()
        self.scene.destroy()
        self.window_master.window_list.remove(self)
        self.window_master.update_window_menu()
        self.window.destroy()

    def save_image(self):
        togl_save_image(self)

class SnapPyPreferences(Preferences):
    def __init__(self, terminal):
        self.terminal = terminal
        Preferences.__init__(self, terminal.text)
        self.apply_prefs()

    def apply_prefs(self):
        self.terminal.set_font(self['font'])
        self.terminal.window.update_idletasks()
        changed = self.changed()
        IP = self.terminal.IP
        self.terminal.quiet = True
        if 'autocall' in changed:
            if self.prefs_dict['autocall']:
                IP.magics_manager.magics['line']['autocall'](2)
            else:
                IP.magics_manager.magics['line']['autocall'](0)
        if 'automagic' in changed:
            if self.prefs_dict['automagic']:
                IP.magics_manager.magics['line']['automagic']('on')
            else:
                IP.magics_manager.magics['line']['automagic']('off')
        self.terminal.quiet = False

app_banner = """
 Hi.  It's SnapPy.  
 SnapPy is based on the SnapPea kernel, written by Jeff Weeks.
 Type "Manifold?" to get started.
"""

help_banner = """Type X? for help with X.
Use the Help menu or type help() to view the SnapPy documentation."""

class SnapPyExit:
    """
    Replacement for the IPython ExitAutocall class
    """
    def __repr__(self):
        return 'Please use the SnapPy menu to quit.'
    __str__ = __repr__

    def __call__(self):
        return self

# This hack avoids an unnecessary warning from IPython saying that
# _Helper is not included in the app2py site.py file.
class _Helper(object):
    pass
import site
site._Helper = _Helper

# This will be used for paging by IPython help.
def IPython_pager(self, text):
    terminal.page(text)

# This will be used for paging by pydoc help.
import pydoc

def pydoc_pager(text):
    terminal.page(pydoc.plain(text))

pydoc.getpager() # this call creates the global variable pydoc.pager
pydoc.pager = pydoc_pager

# This sets the "system menu" icon in the title bar to be the SnapPy
# icon (in Windows and ??KDE??)

def set_icon(window):
    if sys.platform == 'win32':
        try:
            ico = os.path.join(os.path.dirname(snappy.__file__), 'SnapPy.ico')
            window.iconbitmap(default=ico)
        except:
            pass

def main():
    global terminal
    the_shell = InteractiveShellEmbed.instance(
        banner1=app_banner + update_needed())
    terminal = SnapPyTerm(the_shell)
    the_shell.tkterm = terminal
    set_icon(terminal.window)
    the_shell.set_hook('show_in_pager', IPython_pager)
    SnapPy_ns = dict([(x, getattr(snappy,x)) for x in snappy.__all__])
    SnapPy_ns['exit'] = SnapPy_ns['quit'] = SnapPyExit()
    SnapPy_ns['pager'] = None
    helper = pydoc.Helper(input=terminal, output=terminal)
    helper.__call__ = lambda x=None : helper.help(x) if x else SnapPy_help()
    helper.__repr__ = lambda : help_banner
    SnapPy_ns['help'] = helper
    the_shell.user_ns.update(SnapPy_ns)
    snappy.browser.window_master = terminal
    LP, HP = snappy.SnapPy, snappy.SnapPyHP
    LP.LinkEditor = HP.LinkEditor = SnapPyLinkEditor
    SnapPyLinkEditor.IP = the_shell
    LP.PolyhedronViewer = HP.PolyhedronViewer = SnapPyPolyhedronViewer
    LP.HoroballViewer = HP.HoroballViewer = SnapPyHoroballViewer
    LP.Browser = HP.Browser = SnapPyBrowser
    LP.msg_stream.write = HP.msg_stream.write = terminal.write2
    LP.UI_callback = terminal.SnapPea_callback
    if not snappy.SnapPy._within_sage:
        snappy.pari.UI_callback = terminal.PARI_callback
    terminal.window.lift()
    terminal.window.mainloop()

if __name__ == "__main__":
    main()
