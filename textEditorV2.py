"""
TODO
edit_menu.add_command(label="Find [Here]", accelerator="Ctrl+F", command=self.find_cmd)
        edit_menu.add_command(label="Replace [Here]", accelerator="Ctrl+R", command=self.replace_cmd)
        edit_menu.add_command(label="Find [3 Files]", accelerator="Ctrl+Shift+F", command=self.all_file_find_cmd)
        edit_menu.add_command(label="Replace [3 Files]", accelerator="Ctrl+Shift+R", command=self.all_file_replace_cmd)
        edit_menu.add_command(label="Goto Line...", accelerator="Ctrl+G", command=self.goto_cmd)
"""

from collections import deque
import sys
import json
import re
import webbrowser
from pathlib import Path
from urllib.parse import quote

from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QTabWidget, QFileDialog, QMessageBox, QMenu, QInputDialog
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtCore import QTimer, Qt

class TextEditor(QMainWindow):
    APP_TITLE = "TextEditor"
    DEFAULT_FILENAME = "Untitled"
    MAX_VISIBLE_RECENT_FILES = 10
    MAX_RECENT_FILES = 100

    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            self.app_location = Path(sys.executable).parent
        else:
            self.app_location = Path(__file__).parent
        
        self.setWindowTitle(self.APP_TITLE)
        self.resize(800, 600)

        self.tabs = {}  # widget -> {file, saved}, order should be preserved when moving tabs
        self.closed_this_session = [] # order is not important, as its already session scoped
        self.recent_files = [] # chronologically ordered, multi-session context
        self.current_zoom = 100
        self.autosave_enabled = False

        self.font = QFont("Consolas", 12)

        # Central widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(True)  
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tab_widget)

        self.typing_timer = QTimer()
        self.typing_timer.setSingleShot(True)
        self.typing_timer.timeout.connect(self.on_typing_stopped)

        self.create_menus()
        self.load_app_data()
        self.rebuild_recent_files()

    # =========================
    # TAB SYSTEM
    # =========================
    def maybe_save_editor(self, editor):
        data = self.tabs[editor]

        if data["saved"]:
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"Save changes to {data['file'].name if data['file'] else 'Untitled'}?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Save:
            return self.save_editor(editor)
        elif reply == QMessageBox.StandardButton.Cancel:
            return False

        return True
    
    def close_current_tab(self):
        editor = self.get_current_editor()
        if not editor:
            return

        if not self.maybe_save_editor(editor):
            return

        index = self.tab_widget.indexOf(editor)
        self.tab_widget.removeTab(index)
        
        if self.tabs[editor]['file'] in self.closed_this_session:
            self.closed_this_session.remove(self.tabs[editor]['file'])
        self.closed_this_session.append(self.tabs[editor]['file'])
        
        del self.tabs[editor]

        if self.tab_widget.count() == 0:
            self.create_new_tab()
        self.rebuild_recent_files()
    
    def close_all_tabs(self):
        editors = list(self.tabs.keys())
        not_saved = [editor for editor in editors if not self.tabs[editor]["saved"]]

        if not_saved:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {len(not_saved)} file{'' if len(not_saved) == 1 else 's'}?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return False

            if reply == QMessageBox.StandardButton.Save:
                for editor in not_saved:
                    if not self.save_editor(editor):
                        return False  # user canceled save dialog

        for editor in editors:
            index = self.tab_widget.indexOf(editor)
            self.tab_widget.removeTab(index)
            
            if self.tabs[editor]['file'] in self.closed_this_session:
                self.closed_this_session.remove(self.tabs[editor]['file'])
            self.closed_this_session.append(self.tabs[editor]['file'])
            
            del self.tabs[editor]

        self.create_new_tab()
        self.rebuild_recent_files()
        return True
    
    def close_tab(self, index):
        editor = self.tab_widget.widget(index)
        data = self.tabs[editor]

        if not data["saved"]:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {data['file'].name if data['file'] else 'Untitled'}?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                if not self.save_editor(editor):
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        file = data['file']
        self.tab_widget.removeTab(index)
        del self.tabs[editor]

        # Only track real files
        if file:
            if file in self.closed_this_session:
                self.closed_this_session.remove(file)
            self.closed_this_session.append(file)
            # Remove from recent temporarily (we want it under "reopen closed" until reopened)
            if file in self.recent_files:
                self.recent_files.remove(file)

        if self.tab_widget.count() == 0:
            self.create_new_tab()

        self.rebuild_recent_files()
    
    def create_new_tab(self, content="", file=None):
        if any(file == tab["file"] for tab in self.tabs.values()):
            return
        
        editor = QTextEdit()
        editor.setFont(self.font)
        editor.setPlainText(content)

        index = self.tab_widget.addTab(editor, file.name if file else self.DEFAULT_FILENAME)
        self.tab_widget.setCurrentIndex(index)

        self.tabs[editor] = {
            "file": file,
            "saved": True
        }

        editor.textChanged.connect(lambda e=editor: self.on_text_changed(e))
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        editor.customContextMenuRequested.connect(self.show_context_menu)
        
        # File is now open → remove from closed_this_session if present
        if file:
            if file in self.closed_this_session:
                self.closed_this_session.remove(file)
            self.push_recent_file(file)
            self.truncate_recent_files()
        
        self.rebuild_recent_files()

    def get_current_editor(self):
        return self.tab_widget.currentWidget()

    def get_current_data(self):
        editor = self.get_current_editor()
        return self.tabs.get(editor)

    def update_tab_title(self, editor):
        index = self.tab_widget.indexOf(editor)
        data = self.tabs[editor]

        name = data["file"].name if data["file"] else self.DEFAULT_FILENAME
        if not data["saved"]:
            name += " ●"

        self.tab_widget.setTabText(index, name)

    # =========================
    # EVENTS
    # =========================
    def on_text_changed(self, editor):
        data = self.tabs[editor]
        data["saved"] = False
        self.update_tab_title(editor)

        self.typing_timer.start(1000)

    def on_typing_stopped(self):
        if not self.autosave_enabled:
            return

        editor = self.get_current_editor()
        data = self.tabs[editor]

        if data["file"]:
            self.save_editor(editor)

    # =========================
    # MENUS
    # =========================
    def create_menus(self):
        menubar = self.menuBar()

        self.file_menu = menubar.addMenu("File")

        self.file_menu.addAction(self.create_action("New", self.new_file, "Ctrl+N"))
        
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.create_action("Open...", self.open_file, "Ctrl+O"))
        self.recent_file_menu = QMenu("Open Recent", self)
        self.file_menu.addMenu(self.recent_file_menu)
        
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.create_action("Save", self.save_file, "Ctrl+S"))
        self.file_menu.addAction(self.create_action("Save As...", self.save_file_as, "Ctrl+Alt+S"))
        self.file_menu.addAction(self.create_action("Save All", self.save_all_files, "Ctrl+Shift+S"))
        
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.create_action("Close Tab", self.close_current_tab, "Ctrl+T"))
        self.file_menu.addAction(self.create_action("Close All", self.close_all_tabs, "Ctrl+Shift+T"))
        
        self.file_menu.addSeparator()
        autosave_action = QAction("Auto Save", self)
        autosave_action.setCheckable(True)
        autosave_action.triggered.connect(self.toggle_autosave)
        self.file_menu.addAction(autosave_action)

        self.file_menu.addSeparator()
        self.file_menu.addAction(self.create_action("Exit", self.close, "Alt+F4"))

        self.edit_menu = menubar.addMenu("Edit")
        self.edit_menu.addAction(self.create_action("Cut", lambda: self.get_current_editor().cut(), "Ctrl+X"))
        self.edit_menu.addAction(self.create_action("Copy", lambda: self.get_current_editor().copy(), "Ctrl+C"))
        self.edit_menu.addAction(self.create_action("Paste", lambda: self.get_current_editor().paste(), "Ctrl+V"))

        self.view_menu = menubar.addMenu("View")
        self.view_menu.addAction(self.create_action("Zoom In", self.zoom_in, "Ctrl++"))
        self.view_menu.addAction(self.create_action("Zoom Out", self.zoom_out, "Ctrl+-"))
        self.view_menu.addAction(self.create_action("Reset Zoom", self.reset_zoom, "Ctrl+0"))

        self.tools_menu = menubar.addMenu("Tools")
        self.tools_menu.addAction(self.create_action("Word Count", self.word_count, "Ctrl+W"))
        self.tools_menu.addAction(self.create_action("Web Search", self.web_search, "Ctrl+/"))

    def create_action(self, name, func, shortcut=None):
        action = QAction(name, self)
        action.triggered.connect(func)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    # =========================
    # RECENT FILE MENU
    # =========================
    
    # rebuild_recent_files: always show closed first, then recent
    def rebuild_recent_files(self):
        self.recent_file_menu.clear()
        
        self.recent_file_menu.addAction(
            self.create_action("Reopen Closed This Session", self.reopen_closed_this_session)
        )
        self.recent_file_menu.addSeparator()
        
        # closed files menu
        for file in self.closed_this_session:
            self.recent_file_menu.addAction(
                self.create_action(file.name, lambda _, f=file: self.headless_open_file(f))
            )

        self.recent_file_menu.addSeparator()
        
        # recent files menu
        for file in self.recent_files[:self.MAX_VISIBLE_RECENT_FILES]:
            if file in self.closed_this_session:
                continue
            self.recent_file_menu.addAction(
                self.create_action(file.name, lambda _, f=file: self.headless_open_file(f))
            )
        
        self.recent_file_menu.addSeparator()
        self.recent_file_menu.addAction(self.create_action("Show More", self.show_more_recent))
        self.recent_file_menu.addSeparator()
        self.recent_file_menu.addAction(self.create_action("Clear Previous Files...", self.clear_recent))

    def reopen_closed_this_session(self):
        # sort for predictable order if needed
        files_to_reopen = list(self.closed_this_session)
        for file in files_to_reopen:
            try:
                content = file.read_text(encoding="utf-8")
                self.create_new_tab(content, file)
            except Exception:
                pass
            if file in self.closed_this_session:
                self.closed_this_session.remove(file)
            self.push_recent_file(file)
        self.truncate_recent_files()
        self.rebuild_recent_files()
    
    def show_more_recent(self):
        pass
    
    def clear_recent(self):
        self.recent_files.clear()
        self.rebuild_recent_files()

    # =========================
    # FILE OPS
    # =========================
    def push_recent_file(self, file):
        if file in self.recent_files:
            self.recent_files.remove(file)
        self.recent_files.insert(0, file)
        
    def truncate_recent_files(self):
        self.recent_files = self.recent_files[:self.MAX_RECENT_FILES]
    
    def headless_open_file(self, file):
        content = file.read_text(encoding="utf-8")
        self.create_new_tab(content, file)

        self.push_recent_file(file)
        self.truncate_recent_files()
    
    def new_file(self):
        self.create_new_tab()
    
    def open_file(self):
        files, _ = QFileDialog.getOpenFileNames(self)

        for path in files:
            file = Path(path)
            content = file.read_text(encoding="utf-8")
            self.create_new_tab(content, file)
            
            self.push_recent_file(file)
        self.truncate_recent_files()
        self.rebuild_recent_files()

    def save_file(self):
        editor = self.get_current_editor()
        self.save_editor(editor)

    def save_editor(self, editor):
        data = self.tabs[editor]
        if data["saved"]:
            return True

        if not data["file"]:
            path, _ = QFileDialog.getSaveFileName(self)
            if not path:
                return False 
            data["file"] = Path(path)

        data["file"].write_text(editor.toPlainText(), encoding="utf-8")
        data["saved"] = True
        self.update_tab_title(editor)
        return True
    
    def save_all_editors(self):
        for editor in self.tabs.keys():
            if not self.save_editor(editor):
                # User cancelled → stop saving further
                return False
        return True
    
    def save_all_files(self):
        self.save_all_editors()

    def save_file_as(self):
        editor = self.get_current_editor()
        data = self.tabs[editor]

        path, _ = QFileDialog.getSaveFileName(self)
        if not path:
            return

        data["file"] = Path(path)
        self.save_editor(editor)

    # =========================
    # CONTEXT MENU
    # =========================
    def show_context_menu(self, pos):
        editor = self.get_current_editor()
        menu = QMenu()

        menu.addAction("Cut", editor.cut, "Ctrl+X")
        menu.addAction("Copy", editor.copy, "Ctrl+C")
        menu.addAction("Paste", editor.paste, "Ctrl+V")
        menu.addSeparator()
        menu.addAction("Web Search", self.web_search)

        menu.exec(editor.mapToGlobal(pos))
    
    # =========================
    # TOOLS
    # =========================
    def web_search(self):
        editor = self.get_current_editor()
        selected = editor.textCursor().selectedText()

        if not selected.strip():
            return

        query = quote(selected[:1900])
        url = f"https://google.com/search?q={query}"

        if QMessageBox.question(self, "Search", f"Search for: {selected[:30]}"):
            webbrowser.open(url)

    def word_count(self):
        editor = self.get_current_editor()
        text = editor.toPlainText()
        
        def count_words(text):
            # Matches any sequence of letters/numbers. 
            # This keeps 'Redpandas' and '007BFF' but ignores '###'
            return len(re.findall(r'\w+', text))
        
        # Document stats
        lines = text.count('\n') + (1 if text else 0)
        words = count_words(text)
        chars = len(text)
        chars_ws = chars - sum(1 for char in text if char.isspace())

        # Selection stats
        try:
            selected = editor.textCursor().selectedText()
            sel_lines = selected.count('\n') + (1 if selected else 0)
            sel_words = count_words(selected)
            sel_chars = len(selected)
            sel_chars_ws = sel_chars - sum(1 for char in selected if char.isspace())
        except Exception:
            sel_lines = sel_words = sel_chars = sel_chars_ws = 0
        
        QMessageBox.information(self, "Word Count", (
                f"       Document  Selected\n"
                f"Lines  {lines:8}  {sel_lines:8}\n"
                f"Words  {words:8}  {sel_words:8}\n"
                f"Chars  {chars_ws:8}  {sel_chars_ws:8}\n"
                f"Total  {chars:8}  {sel_chars:8}\n"
            )
        )

    # =========================
    # ZOOM
    # =========================
    def update_zoom(self):
        size = int(12 * self.current_zoom / 100)
        self.font.setPointSize(size)

        for editor in self.tabs:
            editor.setFont(self.font)

    def zoom_in(self):
        self.current_zoom += 10
        self.update_zoom()

    def zoom_out(self):
        self.current_zoom -= 10
        self.update_zoom()

    def reset_zoom(self):
        self.current_zoom = 100
        self.update_zoom()

    # =========================
    # SYSTEM
    # =========================
    def closeEvent(self, event):
        for editor, data in list(self.tabs.items()):
            if not data["saved"]:
                self.tab_widget.setCurrentWidget(editor)

                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Save changes to {data['file'].name if data['file'] else 'Untitled'}?",
                    QMessageBox.StandardButton.Save |
                    QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Save:
                    if not self.save_editor(editor):
                        event.ignore()
                        return
                elif reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                # Discard → continue

        self.save_app_data()
        event.accept()
    
    def toggle_autosave(self, state):
        self.autosave_enabled = state
    
    def load_app_data(self):
        try:
            app_data_path = self.app_location / 'data' / 'data.json'
            app_data = json.loads(app_data_path.read_text(encoding="utf-8")) if app_data_path.exists() else {}
            
            self.autosave_enabled = app_data.get("autosave enabled", False)
            
            open_files = [Path(f) for f in app_data.get("open files", [])]
            recent_files = [Path(f) for f in app_data.get("recent files", [])]
            closed_this_session = [Path(f) for f in app_data.get("prev open files", [])]

            all_existing = {p for p in {*open_files, *recent_files, *closed_this_session} if p.exists()}
            
            open_files = [p for p in open_files if p in all_existing]
            self.recent_files = [p for p in recent_files if p in all_existing]
            self.closed_this_session = [p for p in closed_this_session if p in all_existing]
            
        except Exception as e:
            print(f"Error loading data: {e}")
            open_files, self.recent_files, self.closed_this_session = [], [], []
        
        if not open_files:
            self.create_new_tab()
        else:
            for file in open_files:
                try:
                    self.create_new_tab(file.read_text(encoding="utf-8"), file)
                except Exception:
                    pass
        
    def save_app_data(self):
        try:
            app_data_path = self.app_location / 'data' / 'data.json'
            app_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            app_data = {
                "autosave enabled": self.autosave_enabled,
                "open files": [str(tab['file']) for tab in self.tabs.values()],
                "recent files": [str(file) for file in self.recent_files],
                "prev open files": [str(file) for file in self.closed_this_session]
            }
            
            app_data_path.write_text(json.dumps(app_data, indent=2), encoding="utf-8")
            
        except Exception:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = TextEditor()
    editor.show()
    sys.exit(app.exec())