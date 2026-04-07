import json
from pathlib import Path
import re
import webbrowser
import sys
import tkinter as tk
from tkinter import Widget, filedialog, ttk, messagebox
from tkinter import font
from tkinter import simpledialog

import urllib
import urllib.parse

class TextEditor():
    APP_TITLE = "TextEditor"
    DEFAULT_FILENAME = "Untitled"
    ZOOM_RATE = 10
    MIN_ZOOM = 10
    MAX_ZOOM = 500
    DEFAULT_ZOOM = 100
    MAX_RECENT_FILES = 10
    MAX_OPEN_FILES = 10

    def __init__(self):
        self.app_path = None
        self.current_zoom = self.DEFAULT_ZOOM
        self.tabs = {}
        self.drag_data = {"index": None}
        self.recent_files = []
        self.context_menu = None
        self.tab_menu = None
        self.typing_timer = None
        
        self.root = tk.Tk(className=self.APP_TITLE)
        
        self.autosave = tk.BooleanVar()
        self.current_font = font.Font(family="Consolas", size=12)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        self.notebook.bind("<Button-1>", self.on_tab_click)
        self.notebook.bind("<B1-Motion>", self.reorder_tabs)
        
        self.set_app_size()
        self.set_app_title()
        self.set_menubar()
        self.set_context_menu()
        self.set_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close_cmd)

    # =========================
    # CORE TAB SYSTEM
    # =========================
    def on_tab_click(self, event):
        """Store the index of the tab where the user first clicked."""
        try:
            self.drag_data["index"] = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            self.drag_data["index"] = None

    def reorder_tabs(self, event):
        """Move the tab only if it's dragged over a neighbor."""
        if self.drag_data["index"] is None:
            return

        try:
            # Get the index of the tab currently under the mouse
            over_index = self.notebook.index(f"@{event.x},{event.y}")
            
            # Only move if the mouse has moved to a different tab position
            if over_index != self.drag_data["index"]:
                # notebook.tabs() returns a list of internal widget names
                child_id = self.notebook.tabs()[self.drag_data["index"]]
                self.notebook.insert(over_index, child_id)
                
                # Update our tracker to the new position
                self.drag_data["index"] = over_index
        except tk.TclError:
            pass
    
    def on_key_release(self, event):
        # Cancel the previous timer
        if self.typing_timer:
            self.root.after_cancel(self.typing_timer)
        
        # Pass the widget that triggered the event to the stopped handler
        self.typing_timer = self.root.after(1000, lambda: self.on_typing_stopped(event.widget))

    def on_typing_stopped(self, text_widget):
        self.typing_timer = None 
        
        if self.autosave.get():
            # Find which tab this text_widget belongs to
            for frame, data in self.tabs.items():
                if data["text_widget"] == text_widget:
                    # Only auto-save if a file path already exists
                    if data["file"]:
                        self.perform_autosave(frame)
                    break
    
    def create_new_tab(self, content: str = "", file: Path = None) -> None:
        if any(tab['file'] == file for tab in self.tabs.values()):
            return
        
        filename = file.name if file else self.DEFAULT_FILENAME

        frame = tk.Frame(self.notebook)
        
        frame.bind("<Button-3>")
        
        text_widget = tk.Text(frame, wrap="word", undo=True, font=self.current_font)
        text_widget.pack(expand=True, fill="both")
        
        #text_widget.bind("<Button-3>", self.show_tab_menu)
        text_widget.bind("<KeyRelease>", self.on_key_release)

        # Step 1: Insert content
        text_widget.insert("1.0", content)

        # Step 2: Reset modified flag
        text_widget.edit_modified(False)

        # Step 3: Track tab info
        self.tabs[frame] = {
            "text_widget": text_widget,
            "file": file,
            "saved": True
        }

        self.notebook.add(frame, text=filename)
        self.update_tab_title(frame)
        
        self.notebook.select(frame)

        # Step 4: Bind modification handler
        def on_modified(event, f=frame, w=text_widget):
            if w.edit_modified():
                # 1. Update UI state
                tab_data = self.tabs[f]
                tab_data["saved"] = False
                self.update_tab_title(f)

                # 2. Handle Debouncing (Stopped Typing)
                if self.typing_timer:
                    self.root.after_cancel(self.typing_timer)
                
                # Start timer to trigger on_typing_stopped
                self.typing_timer = self.root.after(1000, lambda: self.on_typing_stopped(w))

                # Reset flag
                w.edit_modified(False)

        text_widget.bind("<<Modified>>", on_modified)

    def update_tab_title(self, frame: Widget) -> None:
        tab_info = self.tabs[frame]
        title = tab_info["file"].name if tab_info["file"] else self.DEFAULT_FILENAME
        if not tab_info.get("saved", True):
            title += " *"
        self.notebook.tab(frame, text=title)

    def on_text_modified(self, frame: Widget) -> None:
        self.tabs[frame]["saved"] = False
        self.update_tab_title(frame)
        # reset modified flag
        self.tabs[frame]["text_widget"].edit_modified(False)

    def get_current_tab(self) -> tk.Frame:
        return self.notebook.nametowidget(self.notebook.select())

    def get_current_text_widget(self) -> None:
        tab = self.get_current_tab()
        return self.tabs[tab]["text_widget"]
    
    def get_current_filepath(self) -> Path:
        tab = self.get_current_tab()
        return self.tabs[tab]["file"]

    def set_app_size(self) -> None:
        self.root.geometry("600x400")
        self.root.minsize(200, 200)

    def set_app_title(self) -> None:
        self.root.title(self.APP_TITLE)

    # =========================
    # MENUS
    # =========================
    def toggle_autosave_cmd(self, event=None):
        if self.autosave.get():
            self.save_all_files_cmd()
            #print("Auto-save enabled: All files saved.")
    
    def set_menubar(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New...", accelerator="Ctrl+N", command=self.new_file_cmd)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file_cmd)
        
        self.recent_file_submenu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_file_submenu)
        
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file_cmd)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_file_as_cmd)
        file_menu.add_command(label="Save All", accelerator="Ctrl+Alt+S", command=self.save_all_files_cmd)
        file_menu.add_command(label="Close Tab", command=self.close_tab_cmd)
        file_menu.add_command(label="Close All Tabs", command=self.close_all_tabs_cmd)
        file_menu.add_separator()
        file_menu.add_checkbutton(label="Auto Save", variable=self.autosave, command=self.toggle_autosave_cmd)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Esc", command=self.close_cmd)

        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut_cmd)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_cmd)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste_cmd)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all_cmd)

        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Zoom In", accelerator="Ctrl+Plus", command=self.zoom_in_cmd)
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+Minus", command=self.zoom_out_cmd)
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.reset_zoom_cmd)
        view_menu.add_separator()
        view_menu.add_command(label="Goto Line", command=self.scroll_to_cmd)
        view_menu.add_command(label="Goto Top", accelerator="Ctrl+Home", command=self.scroll_top_cmd)
        view_menu.add_command(label="Goto End", accelerator="Ctrl+End", command=self.scroll_end_cmd)

        menubar.add_cascade(label="View", menu=view_menu)
        
        insert_menu = tk.Menu(menubar, tearoff=0)
        insert_menu.add_command(label="Table", command=None)
        insert_menu.add_command(label="Seperator", command=None)
        insert_menu.add_command(label="Hyperlink", command=None)
        insert_menu.add_command(label="Date", command=None)
        insert_menu.add_command(label="Time", command=None)
        
        menubar.add_cascade(label="Insert", menu=insert_menu)
        
        format_menu = tk.Menu(menubar, tearoff=0)
        format_menu.add_command(label="Heading 1", command=None)
        format_menu.add_command(label="Heading 2", command=None)
        format_menu.add_command(label="Heading 3", command=None)
        format_menu.add_separator()
        format_menu.add_command(label="Bold", accelerator="Ctrl+B", command=self.insert_bold_cmd)
        format_menu.add_command(label="Italic", accelerator="Ctrl+I", command=self.insert_italic_cmd)
        format_menu.add_command(label="Underline", accelerator="Ctrl+U", command=None)
        format_menu.add_command(label="Strikethrough", command=None)
        
        menubar.add_cascade(label="Format", menu=format_menu)

        tool_menu = tk.Menu(menubar, tearoff=0)
        tool_menu.add_command(label="Word Count", accelerator="Ctrl+W", command=self.word_count_cmd)
        tool_menu.add_command(label="Web Search", accelerator="Ctrl+/", command=self.web_cmd)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About TextEditor", command=None)

        menubar.add_cascade(label="Tool", menu=tool_menu)
        
        self.root.config(menu=menubar)

    def set_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut_cmd)
        self.context_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_cmd)
        self.context_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste_cmd)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Web Search", accelerator="Ctrl+/", command=self.web_cmd)
        
    def show_context_menu(self, event):
        event.widget.focus_set()
        text = self.get_current_text_widget()
        has_selection = text.tag_ranges("sel")
        
        state = "normal" if has_selection else "disabled"
        
        self.context_menu.entryconfigure("Cut", state=state)
        self.context_menu.entryconfigure("Copy", state=state)
        self.context_menu.entryconfigure("Web Search", state=state)
        
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
            
    def set_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut_cmd)
        self.context_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_cmd)
        self.context_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste_cmd)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Web Search", accelerator="Ctrl+/", command=self.web_cmd)        

    # =========================
    # HOTKEYS
    # =========================
    def set_hotkeys(self) -> None:
        self.root.bind("<Control-n>", self.new_file_cmd)
        self.root.bind("<Control-o>", self.open_file_cmd)
        self.root.bind("<Control-Shift-O>", self.reopen_files_cmd)
        self.root.bind("<Control-s>", self.save_file_cmd)
        self.root.bind("<Control-Shift-S>", self.save_file_as_cmd)
        self.root.bind("<Control-Alt-s>", self.save_all_files_cmd)
        self.root.bind("<Control-w>", self.word_count_cmd)

        self.root.bind("<Control-a>", self.select_all_cmd)

        self.root.bind("<Control-slash>", self.web_cmd)
        self.root.bind("<Control-minus>", self.zoom_out_cmd)
        self.root.bind("<Control-equal>", self.zoom_in_cmd)
        self.root.bind("<Control-0>", self.reset_zoom_cmd)
        self.root.bind("<Control-MouseWheel>", self.scroll_zoom_cmd)

        self.root.bind("<Control-Prior>", self.tab_left_cmd)
        self.root.bind("<Control-Next>", self.tab_right_cmd)

        self.root.bind("<Control-l>", self.scroll_to_cmd)
        self.root.bind("<Control-Home>", self.scroll_top_cmd)
        self.root.bind("<Control-End>", self.scroll_end_cmd)

        self.root.bind("<Control-b>", self.insert_bold_cmd)
        self.root.bind_all("<Control-i>", self.insert_italic_cmd)

        self.root.bind("<Escape>", self.close_cmd)

    # =========================
    # INSERT COMMANDS
    # =========================

    def insert_italic_cmd(self, event=None) -> None:
        file = self.get_current_filepath()
        widget = self.get_current_text_widget()
        
        # 1. Define tags based on file type
        if file.suffix in ('.html', '.ejs'):
            prefix, suffix = "<em>", "</em>"
        else:
            prefix, suffix = "*", "*"

        try:
            start = widget.index("sel.first")
            end = widget.index("sel.last")
            
            # 2. Get the actual selected text
            selection = widget.get(start, end)

            # 3. CASE A: Tags are INSIDE the selection (e.g., "*text*" is highlighted)
            if selection.startswith(prefix) and selection.endswith(suffix):
                unwrapped = selection[len(prefix) : -len(suffix)]
                widget.delete(start, end)
                widget.insert(start, unwrapped)
                
            else:
                # 4. CASE B: Check if tags are OUTSIDE the selection (e.g., "text" is highlighted)
                current_pre = widget.get(f"{start}-{len(prefix)}c", start)
                current_suf = widget.get(end, f"{end}+{len(suffix)}c")

                if current_pre == prefix and current_suf == suffix:
                    widget.delete(end, f"{end}+{len(suffix)}c")
                    widget.delete(f"{start}-{len(prefix)}c", start)
                else:
                    # 5. CASE C: Not wrapped at all, so add them
                    widget.insert(end, suffix)
                    widget.insert(start, prefix)

        except tk.TclError:
            print("No text selected")
            
        return "break"

    def insert_bold_cmd(self, event=None) -> None:
        file = self.get_current_filepath()
        widget = self.get_current_text_widget()
        
        # 1. Define tags based on file type
        if file.suffix in ('.html', '.ejs'):
            prefix, suffix = "<strong>", "</strong>"
        else:
            prefix, suffix = "**", "**"

        try:
            start = widget.index("sel.first")
            end = widget.index("sel.last")
            
            # 2. Get the actual selected text
            selection = widget.get(start, end)

            # 3. CASE A: Tags are INSIDE the selection (e.g., "**text**" is highlighted)
            if selection.startswith(prefix) and selection.endswith(suffix):
                unwrapped = selection[len(prefix) : -len(suffix)]
                widget.delete(start, end)
                widget.insert(start, unwrapped)
                
            else:
                # 4. CASE B: Check if tags are OUTSIDE the selection (e.g., "text" is highlighted)
                current_pre = widget.get(f"{start}-{len(prefix)}c", start)
                current_suf = widget.get(end, f"{end}+{len(suffix)}c")

                if current_pre == prefix and current_suf == suffix:
                    widget.delete(end, f"{end}+{len(suffix)}c")
                    widget.delete(f"{start}-{len(prefix)}c", start)
                else:
                    # 5. CASE C: Not wrapped at all, so add them
                    widget.insert(end, suffix)
                    widget.insert(start, prefix)

        except tk.TclError:
            print("No text selected")
            
        return "break"

    # =========================
    # FILE COMMANDS
    # =========================
    def perform_autosave(self, frame: tk.Frame) -> None:
        tab_data = self.tabs[frame]
        file = tab_data["file"]
        text_widget = tab_data["text_widget"]
        
        # Auto-save only works if the file has been saved at least once before
        if not file:
            return
            
        try:
            # Get all text from start to end (minus the trailing newline Tkinter adds)
            content = text_widget.get("1.0", "end-1c")
            file.write_text(content, encoding='utf-8')
            
            # Update state and UI
            tab_data["saved"] = True
            self.update_tab_title(frame)
            #print(f"Auto-saved: {file}")
        except Exception as e:
            messagebox.showerror("Auto-save Error", f"Could not auto-save to {file}:\n{e}")
    
    def new_file_cmd(self, event=None) -> None:
        self.create_new_tab()

    def open_file_cmd(self, event=None) -> None:
        for raw_filepath in filedialog.askopenfilenames():
            file = Path(raw_filepath)
            content = file.read_text(encoding="utf-8")
            self.create_new_tab(content, file)

            # Update session
            if file in self.recent_files:
                self.recent_files.remove(file)
            self.recent_files.insert(0, file)

            if len(self.recent_files) > self.MAX_RECENT_FILES:
                self.recent_files.pop()
                
        # Move this OUTSIDE the loop so the menu only rebuilds once
        self.rebuild_recent_file_submenu()
    
    def reopen_files_cmd(self) -> None:
        for file in self.recent_files:
            content = file.read_text(encoding="utf-8")
            self.create_new_tab(content, file)
    
    def clear_recent_files(self) -> None:
        self.recent_files.clear()
        self.rebuild_recent_file_submenu()

    def rebuild_recent_file_submenu(self) -> None:
        self.recent_file_submenu.delete(0, "end")
        
        def open_file(file):
            content = file.read_text(encoding="utf-8")
            self.create_new_tab(content, file)
        
        state = state = "normal" if len(self.recent_files) > 0 else "disabled"
        
        self.recent_file_submenu.add_command(label="Reopen Recent...", command=self.reopen_files_cmd, state=state)  
        self.recent_file_submenu.add_separator()
        
        for file in self.recent_files:
            self.recent_file_submenu.add_command(label=str(file), command=lambda f=file: open_file(f))      
            
        self.recent_file_submenu.add_separator()
        self.recent_file_submenu.add_command(label="Clear Recent...", command=self.clear_recent_files, state=state)         

    def save_all_files_cmd(self, event=None) -> None:
        for tab in self.tabs.keys():
            text_widget = self.tabs[tab]["text_widget"]
            file = self.tabs[tab]["file"]

            text = text_widget.get("1.0", tk.END)

            # If no file assigned, use Save As
            if not file:
                raw_filepath = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[
                        ("Text Document", "*.txt"),
                        ("Markdown", "*.md"),
                        ("All Files", "*.*")
                    ]
                )
                if not raw_filepath:  # user canceled
                    return
                file = Path(raw_filepath)
                self.tabs[tab]["file"] = file

            # Save the file
            file.write_text(text, encoding="utf-8")

            # Mark as saved and update tab title
            self.tabs[tab]["saved"] = True
            self.update_tab_title(tab)

    def save_file_cmd(self, event=None) -> None:
        tab = self.get_current_tab()
        text_widget = self.tabs[tab]["text_widget"]
        file = self.tabs[tab]["file"]

        text = text_widget.get("1.0", tk.END)

        # If no file assigned, use Save As
        if not file:
            raw_filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Text Document", "*.txt"),
                    ("Markdown", "*.md"),
                    ("All Files", "*.*")
                ]
            )
            if not raw_filepath:  # user canceled
                return
            file = Path(raw_filepath)
            self.tabs[tab]["file"] = file

        # Save the file
        file.write_text(text, encoding="utf-8")

        # Mark as saved and update tab title
        self.tabs[tab]["saved"] = True
        self.update_tab_title(tab)
            
    def save_file_as_cmd(self, event=None) -> None:
        tab = self.get_current_tab()
        text_widget = self.tabs[tab]["text_widget"]
        text = text_widget.get("1.0", tk.END)

        raw_filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text Document", "*.txt"),
                ("Markdown", "*.md"),
                ("All Files", "*.*")
            ]
        )
        if not raw_filepath:  # user canceled
            return

        file = Path(raw_filepath)
        self.tabs[tab]["file"] = file
        file.write_text(text, encoding="utf-8")

        # Mark as saved and update tab title
        self.tabs[tab]["saved"] = True
        self.update_tab_title(tab)

    def close_tab_cmd(self, event=None) -> None:
        tab = self.get_current_tab()
        if not tab:
            return

        # check unsaved changes
        if not self.tabs[tab].get("saved", True):
            if not messagebox.askyesno("Unsaved Changes", "This tab has unsaved changes. Close anyway?"):
                return

        self.notebook.forget(tab)
        tab.destroy()
        self.tabs.pop(tab, None)

        # Select next tab if exists, otherwise create new
        if len(self.tabs) == 0:
            self.create_new_tab()
        else:
            # select the first remaining tab
            first_tab = list(self.tabs.keys())[0]
            self.notebook.select(first_tab)

    def close_all_tabs_cmd(self, event=None) -> None:
        for tab_id in self.notebook.tabs():
            tab_widget = self.notebook.nametowidget(tab_id)
            # check unsaved changes
            if not self.tabs[tab_widget].get("saved", True):
                if not messagebox.askyesno("Unsaved Changes", "Some tabs have unsaved changes. Close anyway?"):
                    return
        for tab_id in self.notebook.tabs():
            tab_widget = self.notebook.nametowidget(tab_id)
            self.notebook.forget(tab_widget)
            tab_widget.destroy()
        self.tabs.clear()
        self.create_new_tab()

    # =========================
    # EDIT COMMANDS
    # =========================
    # These just straightup don't work regardless of how I code them
    
    def cut_cmd(self, event=None) -> str:
        widget = self.get_current_text_widget()
        widget.event_generate("<<Cut>>")
        widget.update()

    def copy_cmd(self, event=None) -> str:
        widget = self.get_current_text_widget()
        widget.event_generate("<<Copy>>")
        widget.update()

    def paste_cmd(self, event=None) -> str:
        widget = self.get_current_text_widget()
        widget.event_generate("<<Paste>>")
        widget.update()

    def select_all_cmd(self, event=None) -> None:
        pass
    

    # =========================
    # VIEW
    # =========================
    def web_cmd(self, event=None) -> None:
        text_widget = self.get_current_text_widget()
    
        try:
            selected = text_widget.selection_get()
            if not selected.strip():
                return
        except Exception:
            # No text selected, just exit
            return

        # URL encode the selection to handle spaces/special characters safely
        query = urllib.parse.quote(selected[:1900])
        search_url = f"https://google.com/search?q={query}"

        if messagebox.askokcancel("Web Search", f"Search for: {selected[:30]}", icon="question"):
            try:
                webbrowser.open_new_tab(search_url)
            except Exception:
                messagebox.showerror("Web Search", "Could not open your default web browser.")
    
    def word_count_cmd(self, event=None) -> None:
        text_widget = self.get_current_text_widget()
        content = text_widget.get("1.0", "end-1c")

        def count_words(text):
            # Matches any sequence of letters/numbers. 
            # This keeps 'Redpandas' and '007BFF' but ignores '###'
            return len(re.findall(r'\w+', text))

        # Document stats
        lines = content.count('\n') + (1 if content else 0)
        words = count_words(content)
        chars = len(content)
        chars_ws = chars - sum(1 for char in content if char.isspace())

        # Selection stats
        try:
            selected = text_widget.get("sel.first", "sel.last")
            sel_lines = selected.count('\n') + (1 if selected else 0)
            sel_words = count_words(selected)
            sel_chars = len(selected)
            sel_chars_ws = sel_chars - sum(1 for char in selected if char.isspace())
        except tk.TclError:
            sel_lines = sel_words = sel_chars = sel_chars_ws = 0

        messagebox.showinfo(
            title="Word Count",
            message=(
                f"Document\n"
                f"• Lines: {lines}\n"
                f"• Words: {words}\n"
                f"• Chars: {chars_ws}\n"
                f"• Total: {chars}\n\n"
                f"Selected\n"
                f"• Lines: {sel_lines}\n"
                f"• Words: {sel_words}\n"
                f"• Chars: {sel_chars_ws}\n"
                f"• Total: {sel_chars}"
            )
        )

    def update_zoom(self) -> None:
        size = int(12 * self.current_zoom / 100)  # base font 12
        self.current_font.configure(size=size)

    def zoom_in_cmd(self, event=None) -> None:
        self.current_zoom = min(self.current_zoom + self.ZOOM_RATE, self.MAX_ZOOM)
        self.update_zoom()

    def zoom_out_cmd(self, event=None) -> None:
        self.current_zoom = max(self.MIN_ZOOM, self.current_zoom - self.ZOOM_RATE)
        self.update_zoom()

    def reset_zoom_cmd(self, event=None) -> None:
        self.current_zoom = self.DEFAULT_ZOOM
        self.update_zoom()

    def scroll_to_cmd(self, event=None) -> None:
        text_widget = self.get_current_text_widget()
        last_line = int(text_widget.index("end-1c").split(".")[0])
        
        line_num = simpledialog.askinteger(
            "Go to Line", 
            f"Enter line number (1-{last_line}):", 
            minvalue=1, 
            maxvalue=last_line
        )
        
        if line_num is None:
            return
        
        target_index = f"{line_num}.0"
        text_widget.mark_set("insert", target_index)
        text_widget.see(target_index)
        text_widget.focus_set()  

    def scroll_top_cmd(self, event=None) -> None:
        text_widget = self.get_current_text_widget()
        text_widget.see("1.0")
        # Set insertion cursor to the top as well
        text_widget.mark_set("insert", "1.0")
    
    def scroll_end_cmd(self, event=None) -> None:
        text_widget = self.get_current_text_widget()
        text_widget.see("end")
        # Set insertion cursor to the end
        text_widget.mark_set("insert", "end")

    def scroll_zoom_cmd(self, event) -> None:
        if event.delta > 0:
            self.zoom_in_cmd()
        else:
            self.zoom_out_cmd()
            
    def tab_left_cmd(self, event=None) -> None:
        current_index = self.notebook.index("current")
        if current_index > 0:
            self.notebook.select(current_index - 1)
    
    def tab_right_cmd(self, event) -> None:
        current_index = self.notebook.index("current")
        if current_index < self.notebook.index("end") - 1:
            self.notebook.select(current_index + 1)
    
    # =========================
    # SYSTEM
    # =========================
    def close_cmd(self, event=None) -> None:
        #TODO check for unsaved changes
        
        
        self.save_app_data()
        self.root.destroy()
        
    def save_app_data(self):
        try:
            app_data_path = self.app_path / 'data' / 'data.json'
            app_data_path.parent.mkdir(parents=True, exist_ok=True)
            save_data = {
                "AUTOSAVE_ENABLED": self.autosave.get(),
                "OPEN_FILES": [str(tab['file']) for tab in self.tabs.values()],
                "RECENT_FILES": [str(file) for file in self.recent_files]
            }
            app_data_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def launch(self) -> None:
        if getattr(sys, 'frozen', False):
            self.app_path = Path(sys.executable).parent
        else:
            self.app_path = Path(__file__).parent
        
        app_data_path = self.app_path / 'data' / 'data.json'
        
        try:
            app_data = json.loads(app_data_path.read_text(encoding="utf-8"))
            
            #"AUTOSAVE_ENABLED": self.autosave.get(),
            self.autosave.initialize(app_data.get("AUTOSAVE_ENABLED", False))
            
            raw = app_data.get("OPEN_FILES", [])
            filtered = filter(Path.exists, map(Path, raw))
            open_files = list(filtered)
            
            raw = app_data.get("RECENT_FILES", [])
            filtered = filter(Path.exists, map(Path, raw))
            self.recent_files = list(filtered)[:self.MAX_RECENT_FILES]
            
        except (FileNotFoundError, json.JSONDecodeError):
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
            
        self.rebuild_recent_file_submenu()

        self.root.mainloop()

textEditor = TextEditor()
textEditor.launch()