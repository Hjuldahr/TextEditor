#TODO time opened tracking for recent files

from contextlib import contextmanager
from datetime import datetime
import sys
import json
import re
import webbrowser
from pathlib import Path
from urllib.parse import quote

from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QPushButton, QTextEdit, QTabWidget, QFileDialog, QMessageBox, QMenu, QVBoxLayout
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QTextCharFormat, QTextCursor, QTextDocument
from PyQt6.QtCore import QEvent, QTimer, Qt
import timeago

class FileAccessData():
    def __init__(self, file: Path, access_timestamp: float = None):
        self.file = file
        self.access_timestamp = access_timestamp or datetime.now().astimezone().timestamp()

class TabData:
    def __init__(self, editor: QTextEdit, file: Path, saved: bool=True):
        """TabData

        Args:
            editor (QTextEdit): PyQt6 object
            file (Path): PathLib object
            saved (bool, optional): saved status. Defaults to True.
        """
        self.editor = editor
        self.file = file
        self.saved = saved
        self.search_state = SearchState()

class TabsData:
    def __init__(self):
        self.data = dict()

    def __getitem__(self, key):
        return self.data[id(key)]

    def __setitem__(self, key, value):
        self.data[id(key)] = value

    def __delitem__(self, key):
        del self.data[id(key)]

    def __contains__(self, key):
        return id(key) in self.data

    def __iter__(self):
        return iter(self.data.values())

    def ids(self):
        return self.data.keys()

    def values(self):
        return self.data.values()
    
    def items(self):
        return self.data.items()

class SearchState:
    DEFAULT_TEXT = ""
    DEFAULT_RESULTS = []
    DEFAULT_INDEX = -1
    DEFAULT_SUPPRESS = False
    
    def __init__(self):
        self.text = self.DEFAULT_TEXT
        self.results = self.DEFAULT_RESULTS
        self.index = self.DEFAULT_INDEX
        self.suppress_search_refresh = self.DEFAULT_SUPPRESS
        
    def clear(self):
        self.text = self.DEFAULT_TEXT
        self.results = self.DEFAULT_RESULTS
        self.index = self.DEFAULT_INDEX
        self.suppress_search_refresh = self.DEFAULT_SUPPRESS

class FindBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.trigger_search)
        
        self.setFixedWidth(400)
        self.setFixedHeight(95) # Enough height for two rows + margins

        self.setStyleSheet("""
            QFrame { 
                background-color: #ffffff; 
                border: 1px solid #c0c0c0;
            }
        """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)

        # --- Row 1: Find ---
        find_layout = QHBoxLayout()
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("Find text...")
        # Re-add: Live search on text change
        self.input.textEdited.connect(lambda: self.timer.start(150))
        # Re-add: Enter key moves to next result
        self.input.returnPressed.connect(self.do_find_next)

        self.count = QLabel("0 of 0")

        self.btn_prev = QPushButton("🡡")
        self.btn_prev.clicked.connect(self.do_find_prev) # Re-add
        
        self.btn_next = QPushButton("🡣")
        self.btn_next.clicked.connect(self.do_find_next) # Re-add
        
        self.btn_select_only = QPushButton("⬚")
        self.btn_select_only.setCheckable(True)
        self.btn_select_only.clicked.connect(self.trigger_search) # Re-add
        
        self.btn_close = QPushButton("X")
        self.btn_close.clicked.connect(self.close) # Re-add

        # Styling & Focus
        for btn in [self.btn_prev, self.btn_next, self.btn_select_only, self.btn_close]:
            btn.setFixedWidth(30)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        find_layout.addWidget(self.input)
        find_layout.addWidget(self.count)
        find_layout.addWidget(self.btn_prev)
        find_layout.addWidget(self.btn_next)
        find_layout.addWidget(self.btn_select_only)
        find_layout.addWidget(self.btn_close)

        # --- Row 2: Replace ---
        replace_layout = QHBoxLayout()
        
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")
        # Re-add: Enter key in replace box triggers single replacement
        self.replace_input.returnPressed.connect(self.do_replace)

        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.do_replace) # Re-add

        self.btn_replace_all = QPushButton("All")
        self.btn_replace_all.clicked.connect(self.do_replace_all) # Re-add

        # Styling & Focus
        for btn in [self.btn_replace, self.btn_replace_all]:
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        replace_layout.addWidget(self.replace_input)
        replace_layout.addWidget(self.btn_replace)
        replace_layout.addWidget(self.btn_replace_all)

        # Assemble
        main_layout.addLayout(find_layout)
        main_layout.addLayout(replace_layout)
        
        self.hide()
        self._drag_pos = None
        
    def close(self):
        self.parent().clear_search()
        self.hide()

    def do_find_next(self):
        text = self.input.text()
        #self.parent().smart_search(text)
        self.parent().search_next()
        
    def do_find_prev(self):
        text = self.input.text()
        #self.parent().smart_search(text)
        self.parent().search_prev()

    def show_bar(self):
        # Position at top right of the editor
        self.move(self.parent().width() - self.width() - 20, 10)
        self.show()
        self.input.setFocus()
        self.trigger_search()
        
    def mousePressEvent(self, event):
        # Capture the initial click position within the widget
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        # Move the widget based on the mouse delta
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            # We move it relative to the parent (the main window)
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            
            # Optional: Constrain it so it doesn't leave the main window
            parent_rect = self.parent().rect()
            if parent_rect.contains(new_pos):
                self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        
    def trigger_search(self):
        text = self.input.text()
        self.parent().search(text)
        
    def do_replace(self):
        # Calls the parent TextEditor method
        self.parent().replace_current(self.replace_input.text())

    def do_replace_all(self):
        # Calls the parent TextEditor method
        self.parent().replace_all(self.replace_input.text())

    def do_find_next(self):
        self.parent().search_next()
        
    def do_find_prev(self):
        self.parent().search_prev()

    def trigger_search(self):
        self.parent().search(self.input.text())

class TextEditor(QMainWindow):
    APP_TITLE = "TextEditor"
    DEFAULT_FILENAME = "Untitled"
    MAX_VISIBLE_RECENT_FILES = 10
    MAX_RECENT_FILES = 100
    
    MIN_ZOOM = 10
    MAX_ZOOM = 500
    ZOOM_STEP_SIZE = 10
    DEFAULT_ZOOM = 100
    BASE_FONT_SIZE = 12

    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            self.app_location = Path(sys.executable).parent
        else:
            self.app_location = Path(__file__).parent
        
        self.setWindowTitle(self.APP_TITLE)
        self.resize(800, 600)

        self.tabs = TabsData()  # widget -> {file, saved}, order should be preserved when moving tabs
        self.closed_this_session = {} # order is not important, as its already session scoped
        self.recent_files = {} # chronologically ordered, multi-session context
        self.current_zoom = self.DEFAULT_ZOOM
        self.readonly_enabled = False
        self.autosave_enabled = False
        
        self.status = self.statusBar()
        self.cursor_status = QLabel()
        self.status.addPermanentWidget(self.cursor_status)
        
        self.zoom_status = QLabel()
        self.zoom_status.setText("100%")
        self.status.addPermanentWidget(self.zoom_status)
        
        self.filesize_status = QLabel()
        self.status.addPermanentWidget(self.filesize_status)

        self.font = QFont("Consolas", self.BASE_FONT_SIZE)

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
        
        # Child Widgets
        self.find_bar = FindBar(self)
        self.clear_search_position_label()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.on_tab_changed(None)

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    # =========================
    # TAB SYSTEM
    # =========================
    def maybe_save_editor(self, editor):
        data = self.tabs[editor]

        if data.saved:
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"Save changes to {data.file.name if data.file else 'Untitled'}?",
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
        
        file = self.tabs[editor].file
        self.closed_this_session[file] = FileAccessData(file)
        
        del self.tabs[editor]

        if self.tab_widget.count() == 0:
            self.create_new_tab()
        self.rebuild_recent_files()
    
    def close_all_tabs(self):
        data = self.tabs.values()
        not_saved = [tab_data for tab_data in data if not tab_data.saved]

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

        for tab_data in data:
            index = self.tab_widget.indexOf(tab_data.editor)
            self.tab_widget.removeTab(index)
            
            self.closed_this_session[tab_data.file] = FileAccessData(tab_data.file)
            
            del self.tabs[tab_data.editor]

        self.create_new_tab()
        self.rebuild_recent_files()
        return True
    
    def close_tab(self, index):
        editor = self.tab_widget.widget(index)
        data = self.tabs[editor]

        if not data.saved:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {data.file.name if data.file else 'Untitled'}?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                if not self.save_editor(editor):
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        file = data.file
        self.tab_widget.removeTab(index)
        del self.tabs[editor]

        # Only track real files
        if file:
            self.closed_this_session[file] = FileAccessData(file)
            
            if file in self.open_files:
                self.open_files.remove(file)
            
            # Remove from recent temporarily (we want it under "reopen closed" until reopened)
            if file in self.recent_files:
                #self.recent_files.remove(file)
                self.recent_files.pop(file, None)

        if self.tab_widget.count() == 0:
            self.create_new_tab()

        self.rebuild_recent_files()
    
    def create_new_tab(self, content="", file=None):
        if any(file == tab.file for tab in self.tabs.values()):
            return
        
        editor = QTextEdit()
        editor.setFont(self.font)
        editor.viewport().installEventFilter(self)
        editor.setPlainText(content)

        index = self.tab_widget.addTab(editor, file.name if file else self.DEFAULT_FILENAME)
        self.tab_widget.setCurrentIndex(index)

        self.tabs[editor] = TabData(editor, file)

        editor.textChanged.connect(lambda e=editor: self.on_text_changed(e))
        editor.cursorPositionChanged.connect(lambda e=editor: self.on_cursor_moved(e))
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        editor.customContextMenuRequested.connect(self.show_context_menu)
        
        # File is now open → remove from closed_this_session if present
        if file:
            self.closed_this_session.pop(file, None)
                
            if file not in self.open_files:    
                self.open_files.append(file)
                
            self.push_recent_file(file)
            self.truncate_recent_files()
        
        self.rebuild_recent_files()

    def get_search_state(self):
        editor = self.get_current_editor()
        if not editor:
            return None
        return self.tabs[editor].search_state

    def get_current_editor(self):
        return self.tab_widget.currentWidget()

    def get_current_file(self):
        editor = self.tab_widget.currentWidget()
        return self.tabs[editor].file

    def update_tab_title(self, editor):
        index = self.tab_widget.indexOf(editor)
        data = self.tabs[editor]

        name = data.file.name if data.file else self.DEFAULT_FILENAME
        if not data.saved:
            name += " ●"

        self.tab_widget.setTabText(index, name)

    # =========================
    # EVENTS
    # =========================
    def eventFilter(self, obj, event):
        # Turns out my mouse wheel button is dead and its not pyt6... damn it
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                self.reset_zoom()
                return True
        
        if event.type() == QEvent.Type.Wheel:
            # Check if Control is held
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                return True
                
        return super().eventFilter(obj, event)
    
    def on_tab_changed(self, index):
        editor = self.get_current_editor()
        if not editor or editor not in self.tabs:
            return
        
        text = self.find_bar.input.text()
        if text:
            self.search(text)
            
        self.on_cursor_moved(editor) # moved across files
        self.update_filesize_status(self.tabs[editor])
    
    def on_cursor_moved(self, editor):
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        sel = len(cursor.selectedText())
        
        status_text = f"Ln {line}, Col {col}"
        if sel > 0:
            status_text += f", Selected {sel}"
        
        self.cursor_status.setText(status_text)
        
        if (
            not self.get_search_state().suppress_search_refresh and
            self.find_bar.isVisible() and
            self.find_bar.btn_select_only.isChecked() and
            self.find_bar.input.text()
        ):
            self.find_bar.timer.start(100)
    
    def on_text_changed(self, editor):
        data = self.tabs[editor]
        data.saved = False
        self.update_tab_title(editor)

        self.typing_timer.start(1000)

    def on_typing_stopped(self):
        editor = self.get_current_editor()
        data = self.tabs[editor]
        
        self.update_filesize_status(data)
        
        if not self.autosave_enabled:
            return

        if data.file:
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

        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.create_action("Find / Replace", self.find, "Ctrl+F"))
        self.edit_menu.addAction(self.create_action("Find By Selection", self.find_by_selection))
        #self.edit_menu.addAction(self.create_action("Find Across Files", self.all_file_find, "Ctrl+Shift+F"))
        self.edit_menu.addAction(self.create_action("Goto Line", self.goto, "Ctrl+G"))

        self.edit_menu.addSeparator()
        readonly_action = QAction("Readonly", self)
        readonly_action.setCheckable(True)
        readonly_action.setShortcut(QKeySequence("Ctrl+L"))
        readonly_action.triggered.connect(self.toggle_readonly)
        self.edit_menu.addAction(readonly_action)
    
        self.view_menu = menubar.addMenu("View")
        self.view_menu.addAction(self.create_action("Zoom In", self.zoom_in, "Ctrl+="))
        self.view_menu.addAction(self.create_action("Zoom Out", self.zoom_out, "Ctrl+-"))
        self.view_menu.addAction(self.create_action("Reset Zoom", self.reset_zoom, "Ctrl+0"))

        self.insert_menu = menubar.addMenu("Insert")
        self.insert_menu.addAction(self.create_action("Timestamp", self.insert_timestamp))
        self.insert_menu.addAction(self.create_action("Seperator", self.insert_separator))

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
    # INSERTION
    # =========================

    def insert_timestamp(self):
        editor = self.get_current_editor()
        file_path = self.tabs[editor].file
        suffix = file_path.suffix.lower() if file_path else ''
        
        now = datetime.now().astimezone()
        
        # Display formats
        human_readable = now.strftime("%Y-%m-%d %H:%M:%S")
        iso_date = now.strftime("%Y-%m-%d")

        if suffix == '.html':
            text = f'<time datetime="{now.isoformat()}">{human_readable}</time>'
        elif suffix in ('.md', '.markdown'):
            text = iso_date
        else:
            text = human_readable

        editor.insertPlainText(text)
        
    def insert_separator(self):
        editor = self.get_current_editor()
        cursor = editor.textCursor()
        
        file_path = self.tabs[editor].file
        suffix = file_path.suffix.lower() if file_path else ''
        
        if suffix == '.md':
            text = '\n--- \n'
            editor.insertPlainText(text)
        elif suffix == '.html':
            text = '\n<hr>\n'
            editor.insertPlainText(text)
        else:
            line_text = cursor.block().text()
            width = 80
            char = '─'

            if line_text:
                clean_text = line_text.rstrip(f"{char} ")
                formatted = clean_text.ljust(width).replace(' ', char)
                formatted = re.sub(r'(?<=[a-zA-Z0-9])─|─(?=[a-zA-Z0-9])', ' ', formatted)
                cursor.movePosition(cursor.MoveOperation.StartOfBlock)
                cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
                cursor.insertText(formatted+'\n') 
            else:
                cursor.insertText(char * width)

    # =========================
    # FIND / REPLACE
    # =========================

        ##self.edit_menu.addAction(self.create_action("Replace", self.replace, "Ctrl+R"))
        #self.edit_menu.addAction(self.create_action("Find Across Files", self.all_file_find, "Ctrl+Shift+F"))
        #self.edit_menu.addAction(self.create_action("Replace Across Files", self.all_file_replace, "Ctrl+Shift+R"))
        #self.edit_menu.addAction(self.create_action("Goto Line...", self.goto, "Ctrl+G"))

    def goto(self):
        editor = self.get_current_editor()
        cursor = editor.textCursor() 
        
        # Store the current column (relative to start of line)
        current_column = cursor.positionInBlock()
        total_lines = editor.document().blockCount()
        
        line_number, ok = QInputDialog.getInt(
            self, 'Goto Line', f'{total_lines} Total Lines', 
            cursor.blockNumber() + 1, 1, total_lines, 1
        )
        
        if ok:
            block = editor.document().findBlockByNumber(line_number - 1) 
            if block.isValid():
                # Calculate the new target position
                # Use min() to prevent jumping past the end of a shorter line
                new_col = min(current_column, block.length() - 1)
                new_pos = block.position() + new_col
                
                cursor.setPosition(new_pos) 
                editor.setTextCursor(cursor) 
                editor.ensureCursorVisible()

    def find_by_selection(self):
        editor = self.get_current_editor()
        selected = editor.textCursor().selectedText().replace('\u2029', '\n')

        if not selected.strip():
            return
        
        self.find_bar.show_bar()
        self.find_bar.input.setText(selected)
        self.search(selected)

    def find(self):
        self.find_bar.show_bar()
        
    def clear_search(self):
        self.find_bar.input.blockSignals(True)
        self.find_bar.input.clear()
        self.find_bar.input.blockSignals(False)

        for tab in self.tabs.values():
            tab.editor.setExtraSelections([])

        self.clear_search_position_label()
        
    def search(self, text):
        editor = self.get_current_editor()
        if not editor:
            return

        self.get_search_state().text = text

        if not text:
            self.clear_search()
            return

        doc = editor.document()
        results = []

        cursor = editor.textCursor()

        # Selection mode toggle
        if self.find_bar.btn_select_only.isChecked() and cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor = QTextCursor(doc)
            cursor.setPosition(start)

            while True:
                cursor = doc.find(text, cursor)
                if cursor.isNull():
                    break

                s = cursor.selectionStart()
                e = cursor.selectionEnd()

                if s >= end:
                    break

                # only include matches fully inside selection
                if e <= end:
                    results.append((s, e))
        else:
            # normal full-document search
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            while True:
                cursor = doc.find(text, cursor)
                if cursor.isNull():
                    break
                results.append((cursor.selectionStart(), cursor.selectionEnd()))

        self.get_search_state().results = results
        self.get_search_state().index = 0 if results else -1

        self.apply_highlights()

        if results:
            self.update_search_position_label(0, len(results))
        else:
            self.clear_search_position_label()
        
    def search_next(self):
        r = self.get_search_state().results
        if not r:
            return
        self.get_search_state().index = (self.get_search_state().index + 1) % len(r)
        self.jump()

    def search_prev(self):
        r = self.get_search_state().results
        if not r:
            return
        self.get_search_state().index = (self.get_search_state().index - 1) % len(r)
        self.jump()    
    
    @contextmanager
    def suppress_search(self):
        self.get_search_state().suppress_search_refresh = True
        try:
            yield
        finally:
            self.get_search_state().suppress_search_refresh = False
    
    def jump(self):
        editor = self.get_current_editor()
        if not editor:
            return

        r = self.get_search_state().results
        i = self.get_search_state().index

        if i < 0 or i >= len(r):
            return

        start, end = r[i]

        doc = editor.document()
        doc_len = doc.characterCount() - 1

        if start < 0 or end > doc_len:
            return

        cursor = QTextCursor(doc)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        with self.suppress_search():
            editor.setTextCursor(cursor)
    
        editor.ensureCursorVisible()

        self.apply_highlights()
        self.update_search_position_label(i, len(r))
    
    def clear_search_position_label(self):
        self.find_bar.count.setText('No results')
        
    def update_search_position_label(self, i, n):
        self.find_bar.count.setText(f'{i+1} of {n}')
    
    def apply_highlights(self):
        editor = self.get_current_editor()
        if not editor:
            return

        state = self.get_search_state()
        if not state.text or not state.results:
            editor.setExtraSelections([])
            return

        results = state.results
        if not results:
            editor.setExtraSelections([])
            return

        normal = QTextCharFormat()
        normal.setBackground(QColor("yellow"))

        current = QTextCharFormat()
        current.setBackground(QColor("orange"))

        extra = []
        idx = self.get_search_state().index

        doc = editor.document()

        for i, (start, end) in enumerate(results):
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = current if i == idx else normal
            extra.append(sel)

        editor.setExtraSelections(extra)
                
    def replace(self):
        pass
    
    def all_file_find(self):
        pass
    
    def all_file_replace(self):
        pass

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
        # if any(file == file_data for file_data in self.closed_this_session.values()):
        
        now = datetime.now().astimezone()
        
        data = sorted(self.closed_this_session.values(), key=lambda e: e.access_timestamp, reverse=True)
        for file_data in data:
            if any(file_data.file == cts.file for cts in self.closed_this_session.values()):
                continue
            time_str = timeago.format(datetime.fromtimestamp(file_data.access_timestamp, tz=now.tzinfo), now)
            self.recent_file_menu.addAction(
                self.create_action(f'{file_data.file.name} - {time_str}', lambda _, f=file_data.file: self.headless_open_file(f))
            )

        self.recent_file_menu.addSeparator()
        
        # recent files menu
        data = sorted(self.recent_files.values(), key=lambda e: e.access_timestamp, reverse=True)
        for file_data in data:
            if any(file_data.file == cts.file for cts in self.closed_this_session.values()):
                continue
            time_str = timeago.format(datetime.fromtimestamp(file_data.access_timestamp, tz=now.tzinfo), now)
            self.recent_file_menu.addAction(
                self.create_action(f'{file_data.file.name} - {time_str}', lambda _, f=file_data.file: self.headless_open_file(f))
            )
        # datetime.fromtimestamp(file_data.access_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        self.recent_file_menu.addSeparator()
        self.recent_file_menu.addAction(self.create_action("Show More", self.show_more_recent))
        self.recent_file_menu.addSeparator()
        self.recent_file_menu.addAction(self.create_action("Clear Previous Files...", self.clear_recent))

    def reopen_closed_this_session(self):
        # sort for predictable order if needed
        data = self.closed_this_session.values()
        for file_data in data:
            file = file_data.file
            try:
                content = file.read_text(encoding="utf-8")
                self.create_new_tab(content, file)
            except Exception:
                pass
            self.closed_this_session.pop(file, None)
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
        if file in self.recent_files.keys():
            self.recent_files[file] = FileAccessData(file)
        
    def truncate_recent_files(self):
        #self.recent_files = self.recent_files[:self.MAX_RECENT_FILES]
        pass
    
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

    def update_filesize_status(self, data):
        editor = self.get_current_editor()
        if not editor:
            self.filesize_status.setText("0 B")
            return

        ram_size = len(editor.toPlainText().replace('\n', '\r\n').encode("utf-8"))

        if data.file and data.file.exists():
            disk_size = data.file.stat().st_size
        else:
            disk_size = 0

        if not data.saved:
            self.filesize_status.setText(f'{self.format_size(disk_size)} 🡢 {self.format_size(ram_size)}')
        else:
            self.filesize_status.setText(self.format_size(disk_size))

    def save_editor(self, editor):
        data = self.tabs[editor]
        if data.saved:
            return True

        if not data.file:
            path, _ = QFileDialog.getSaveFileName(self)
            if not path:
                return False 
            data.file = Path(path)

        data.file.write_text(editor.toPlainText(), encoding="utf-8")
        data.saved = True
        self.update_tab_title(editor)
        self.update_filesize_status(data)
        return True
    
    def save_all_editors(self):
        for tab in self.tabs.values():
            if not self.save_editor(tab.editor):
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

        data.file = Path(path)
        self.save_editor(editor)

    # =========================
    # CONTEXT MENU
    # =========================
    def show_context_menu(self, pos):
        editor = self.get_current_editor()
        menu = QMenu()

        cursor = editor.textCursor()
        has_selection = cursor.hasSelection()
        clipboard = QApplication.clipboard()
        has_clipboard = bool(clipboard.text())

        find_action = self.create_action("Find by Selection", self.find_by_selection, "Ctrl+F")
        find_action.setEnabled(has_selection)
        menu.addAction(find_action)

        menu.addSeparator()
        cut_action = self.create_action("Cut", editor.cut, "Ctrl+X")
        cut_action.setEnabled(has_selection)
        menu.addAction(cut_action)

        copy_action = self.create_action("Copy", editor.copy, "Ctrl+C")
        copy_action.setEnabled(has_selection)
        menu.addAction(copy_action)

        paste_action = self.create_action("Paste", editor.paste, "Ctrl+V")
        paste_action.setEnabled(has_clipboard)
        menu.addAction(paste_action)

        menu.addSeparator()
        web_search_action = self.create_action("Web Search", self.web_search)
        web_search_action.setEnabled(has_selection)
        
        menu.addAction(web_search_action)

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
                f"       Doc       Sel\n"
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
        size = int(self.BASE_FONT_SIZE * self.current_zoom / 100)
        self.font.setPointSize(size)

        for tab in self.tabs.values():
            tab.editor.setFont(self.font)
            
        self.zoom_status.setText(f'{self.current_zoom}%')

    def zoom_in(self):
        self.current_zoom = min(self.MAX_ZOOM, self.current_zoom + self.ZOOM_STEP_SIZE)
        self.update_zoom()

    def zoom_out(self):
        self.current_zoom = max(self.MIN_ZOOM, self.current_zoom - self.ZOOM_STEP_SIZE)
        self.update_zoom()

    def reset_zoom(self):
        self.current_zoom = self.DEFAULT_ZOOM
        self.update_zoom()

    # =========================
    # SYSTEM
    # =========================
    def closeEvent(self, event):
        for data in list(self.tabs.values()):
            if not data.saved:
                self.tab_widget.setCurrentWidget(data.editor)

                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Save changes to {data.file.name if data.file else 'Untitled'}?",
                    QMessageBox.StandardButton.Save |
                    QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Save:
                    if not self.save_editor(data.editor):
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
        
    def toggle_readonly(self, state):
        self.readonly_enabled = state
    
    def load_app_data(self):
        try:
            app_data_path = self.app_location / 'data' / 'data.json'
            app_data = json.loads(app_data_path.read_text(encoding="utf-8")) if app_data_path.exists() else {}
            
            preferences = app_data.get("preferences", {})
            self.readonly_enabled = preferences.get("readonly", False)
            self.autosave_enabled = preferences.get("autosave", False)
            
            session = app_data.get("session", {})
            self.open_files = [f2 for f2 in [Path(f1) for f1 in session.get("open files", [])] if f2.exists()]
            
            for entry in session.get("recent files", []):
                file = Path(entry.get('file'))
                if file.exists():
                    access_time = entry.get('atime', datetime.now().astimezone().timestamp())

                    self.recent_files[file] = FileAccessData(file, access_time)
                    
            for entry in session.get("closed files", []):
                file = Path(entry.get('file'))
                if file.exists():
                    access_time = entry.get('atime', datetime.now().astimezone().timestamp())

                    self.closed_this_session[file] = FileAccessData(file, access_time)        
            
        except Exception as e:
            print(f"Error loading data: {e}")
            self.open_files = []
            self.recent_files = {}
            self.closed_this_session = {}
        
        # Rehydrate tabs
        if not self.open_files:
            self.create_new_tab()
        else:
            for file in self.open_files:
                try:
                    self.create_new_tab(file.read_text(encoding="utf-8"), file)
                except Exception:
                    pass
        
    def save_app_data(self):
        try:
            app_data_path = self.app_location / 'data' / 'data.json'
            app_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            app_data = {
                "preferences": {
                    "readonly": self.readonly_enabled,
                    "autosave": self.autosave_enabled
                },
                "session": {
                    "open files": [str(tab.file) for tab in self.tabs.values()],
                    
                    "recent files": [{
                        "file": str(data.file),
                        "atime": data.access_timestamp
                    } for data in self.recent_files.values()],
                    
                    "closed files": [{
                        "file": str(data.file),
                        "atime": data.access_timestamp
                    } for data in self.closed_this_session.values()]
                }
            }
            
            app_data_path.write_text(json.dumps(app_data, indent=2), encoding="utf-8")
            
        except Exception:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = TextEditor()
    editor.show()
    sys.exit(app.exec())