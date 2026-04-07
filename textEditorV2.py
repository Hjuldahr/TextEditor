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

    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            self.app_location = Path(sys.executable).parent
        else:
            self.app_location = Path(__file__).parent
        
        self.setWindowTitle(self.APP_TITLE)
        self.resize(800, 600)

        self.tabs = {}  # widget -> {file, saved}
        self.recent_files = []
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

    # =========================
    # TAB SYSTEM
    # =========================
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

        self.tab_widget.removeTab(index)
        del self.tabs[editor]

        if self.tab_widget.count() == 0:
            self.create_new_tab()
    
    def create_new_tab(self, content="", file=None):
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

        file_menu = menubar.addMenu("File")

        file_menu.addAction(self.create_action("New", self.new_file, "Ctrl+N"))
        file_menu.addAction(self.create_action("Open", self.open_file, "Ctrl+O"))
        file_menu.addAction(self.create_action("Save", self.save_file, "Ctrl+S"))
        file_menu.addAction(self.create_action("Save As", self.save_file_as, "Ctrl+Alt+S"))
        file_menu.addAction(self.create_action("Save All", self.save_all_files, "Ctrl+Shift+S"))
        file_menu.addSeparator()

        autosave_action = QAction("Auto Save", self)
        autosave_action.setCheckable(True)
        autosave_action.triggered.connect(self.toggle_autosave)
        file_menu.addAction(autosave_action)

        file_menu.addSeparator()
        file_menu.addAction(self.create_action("Exit", self.close))

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.create_action("Cut", lambda: self.get_current_editor().cut(), "Ctrl+X"))
        edit_menu.addAction(self.create_action("Copy", lambda: self.get_current_editor().copy(), "Ctrl+C"))
        edit_menu.addAction(self.create_action("Paste", lambda: self.get_current_editor().paste(), "Ctrl+V"))

        view_menu = menubar.addMenu("View")
        view_menu.addAction(self.create_action("Zoom In", self.zoom_in, "Ctrl++"))
        view_menu.addAction(self.create_action("Zoom Out", self.zoom_out, "Ctrl+-"))
        view_menu.addAction(self.create_action("Reset Zoom", self.reset_zoom, "Ctrl+0"))

        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self.create_action("Word Count", self.word_count, "Ctrl+W"))
        tools_menu.addAction(self.create_action("Web Search", self.web_search, "Ctrl+/"))

    def create_action(self, name, func, shortcut=None):
        action = QAction(name, self)
        action.triggered.connect(func)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    # =========================
    # FILE OPS
    # =========================
    def new_file(self):
        self.create_new_tab()

    def open_file(self):
        files, _ = QFileDialog.getOpenFileNames(self)

        for path in files:
            file = Path(path)
            content = file.read_text(encoding="utf-8")
            self.create_new_tab(content, file)

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

        menu.addAction("Cut", editor.cut)
        menu.addAction("Copy", editor.copy)
        menu.addAction("Paste", editor.paste)
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
            
            raw = app_data.get("open files", [])
            filtered = filter(Path.exists, map(Path, raw))
            open_files = list(filtered)
            
            raw = app_data.get("recent files", [])
            filtered = filter(Path.exists, map(Path, raw))
            self.recent_files = list(filtered)
            
        except Exception as e:
            print(e)
            open_files = []
            self.recent_files = []
        
        if len(open_files) == 0:
            # New Session
            self.create_new_tab()
        else:
            # Restore Old Session
            for file in open_files:
                content = file.read_text(encoding="utf-8")
                self.create_new_tab(content, file)
            
        #self.rebuild_recent_file_submenu()
        
    def save_app_data(self):
        try:
            app_data_path = self.app_location / 'data' / 'data.json'
            app_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            app_data = {
                "autosave enabled": self.autosave_enabled,
                "open files": [str(tab['file']) for tab in self.tabs.values()],
                "recent files": [str(file) for file in self.recent_files]
            }
            
            app_data_path.write_text(json.dumps(app_data, indent=2), encoding="utf-8")
            
        except Exception:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = TextEditor()
    editor.show()
    sys.exit(app.exec())