import tkinter as tk
from tkinter import filedialog, ttk

class TextEditor():
    APP_TITLE = "TextEditor"
    DEFAULT_FILENAME = "Untitled"
    ZOOM_RATE = 10
    MIN_ZOOM = 10 #percentage
    MAX_ZOOM = 500
    DEFAULT_ZOOM = 100
    
    def __init__(self):
        self.current_file_name = self.DEFAULT_FILENAME
        self.open_filepaths = []
        self.file_contents = { self.DEFAULT_FILENAME:"" } # filename -> content
        self.current_zoom = self.DEFAULT_ZOOM
        
        self.root = tk.Tk(
            className=self.APP_TITLE
        )
        self.set_app_zize()
        self.set_app_title()
        self.set_menubar()
        self.set_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close_cmd)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        self.tabs = {
            0: {
                "text_widget": tk.Text(tk.Frame(self.notebook), wrap="word", undo=True),
                "filepath": None,
                "filename": self.current_file_name
            }
        }
        
    def set_app_zize(self):
        self.root.geometry("400x200")
        self.root.minsize(10, 100)
        
    def set_app_title(self):
        self.root.title(f"{self.APP_TITLE} - {self.current_file_name}")
        
    def set_menubar(self):
        menubar = tk.Menu(self.root)

        # Create File dropdown
        file_menu = tk.Menu(menubar, tearoff=0)

        # 1. Using 'accelerator' for right-aligned text
        file_menu.add_command(label="New...", accelerator="Ctrl+N", command=self.new_file_cmd)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file_cmd)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file_cmd)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_file_as_cmd)
        file_menu.add_command(label="Rename To...", command=self.rename_file_cmd)
        file_menu.add_separator()
        #file_menu.add_command(label="Page Setup...")
        file_menu.add_command(label="Print...", accelerator="Ctrl+P", command=self.print_cmd)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Esc", command=self.close_cmd)

        menubar.add_cascade(label="File", menu=file_menu)
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo_cmd)
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo_cmd)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut_cmd)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_cmd)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste_cmd)
        edit_menu.add_separator()
        edit_menu.add_command(label="Search with Google", accelerator="Ctrl+/", command=self.web_cmd)
        edit_menu.add_command(label="Find [Here]", accelerator="Ctrl+F", command=self.find_cmd)
        edit_menu.add_command(label="Replace [Here]", accelerator="Ctrl+R", command=self.replace_cmd)
        edit_menu.add_command(label="Find [3 Files]", accelerator="Ctrl+Shift+F", command=self.all_file_find_cmd)
        edit_menu.add_command(label="Replace [3 Files]", accelerator="Ctrl+Shift+R", command=self.all_file_replace_cmd)
        edit_menu.add_command(label="Goto Line...", accelerator="Ctrl+G", command=self.goto_cmd)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all_cmd)
        edit_menu.add_command(label="Insert Seperator", command=self.insert_seperator_cmd)
        edit_menu.add_command(label="Insert Timestamp", command=self.insert_timestamp_cmd)
        
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        
        view_menu.add_command(label="Zoom In", accelerator="Ctrl+Plus", command=self.zoom_in_cmd)
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+Minus", command=self.zoom_out_cmd)
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+Zero", command=self.reset_zoom_cmd)
        view_menu.add_command(label="Word Count", accelerator="Ctrl+W", command=self.word_count_cmd)
        
        menubar.add_cascade(label="View", menu=view_menu)
        
        self.root.config(menu=menubar)
        
    def set_hotkeys(self):
        self.root.bind("<Control-n>", self.new_file_cmd)
        self.root.bind("<Control-o>", self.open_file_cmd)
        self.root.bind("<Control-s>", self.save_file_cmd)
        self.root.bind("<Control-Shift-S>", self.save_file_as_cmd)
        self.root.bind("<Control-p>", self.print_cmd)
        
        self.root.bind("<Control-z>", self.undo_cmd)
        self.root.bind("<Control-y>", self.redo_cmd)
        
        self.root.bind("<Control-x>", self.cut_cmd)
        self.root.bind("<Control-c>", self.copy_cmd)
        self.root.bind("<Control-v>", self.paste_cmd)
        
        self.root.bind("<Control-slash>", self.web_cmd)
        self.root.bind("<Control-f>", self.find_cmd)
        self.root.bind("<Control-r>", self.replace_cmd)
        self.root.bind("<Control-Shift-F>", self.all_file_find_cmd)
        self.root.bind("<Control-Shift-R>", self.all_file_replace_cmd)
        self.root.bind("<Control-w>", self.word_count_cmd)
        
        self.root.bind("<Control-a>", self.select_all_cmd)
        self.root.bind("<Control-g>", self.goto_cmd)
        
        self.root.bind("<Control-minus>", self.zoom_in_cmd)
        self.root.bind("<Control-equal>", self.zoom_out_cmd)
        self.root.bind("<Control-MouseWheel>", self.scroll_zoom_cmd)
        self.root.bind("<Control-0>", self.reset_zoom_cmd)
        
        self.root.bind("<Escape>", self.close_cmd)
        
    def new_file_cmd(self, event=None):
        print("New File")
        
    def open_file_cmd(self, event=None):
        files = filedialog.askopenfilenames(
            title="Open",
            filetypes=[
                ("Text Document", ("*.txt", "*.md")),
                ("Data File", ("*.csv", "*.json")),
                ("All Files", "*")
            ]
        )
        for filepath in files:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            filename = filepath.split("/")[-1]
            self.file_contents[filename] = content
            
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", content)
            
            self.current_file_name = filename
            self.set_app_title()
        
    def save_file_cmd(self, event=None):
        print("Save File")
        
    def save_file_as_cmd(self, event=None):
        print("Save File As")
        
    def print_cmd(self, event=None):
        print("Print")
        
    def redo_cmd(self, event=None):
        print("Redo")
        
    def undo_cmd(self, event=None):
        print("Undo")
        
    def cut_cmd(self, event=None):
        self.copy_cmd()
        self.text_widget.delete("sel.first", "sel.last")
        
    def copy_cmd(self, event=None):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.text_widget.selection_get())
        except tk.TclError:
            pass
        
    def paste_cmd(self, event=None):
        try:
            self.text_widget.insert(tk.INSERT, self.root.clipboard_get())
        except tk.TclError:
            pass
        
    def web_cmd(self, event=None):
        print("Google Search")    
        
    def find_cmd(self, event=None):
        print("Find in current file")  
        
    def replace_cmd(self, event=None):
        print("Replace in current file")    
        
    def all_file_find_cmd(self, event=None):
        print("Find in all files")  
        
    def all_file_replace_cmd(self, event=None):
        print("Replace in all files") 
        
    def goto_cmd(self, event=None):
        print("Goto")    
        
    def insert_seperator_cmd(self, event=None):
        print("Seperator") 
        
    def insert_timestamp_cmd(self, event=None):
        print("Timestamp") 
        
    def select_all_cmd(self, event=None):
        print("Select All") 
        
    def word_count_cmd(self, event=None):
        text = self.text_widget.get("1.0", tk.END)
        words = len(text.split())
        chars = len(text)
        selected_text = self.text_widget.selection_get()
        selected_words = len(text.split())
        selected_chars = len(text)
        #print(f"Words: {words}, Characters: {chars}")
        #TODO popup
        
    def deselect_all_cmd(self, event=None):
        print("Deselect All") 
        
    def zoom_in_cmd(self, event=None):
        self.current_zoom = min(self.current_zoom + self.ZOOM_RATE, self.MAX_ZOOM)

    def zoom_out_cmd(self, event=None):
        self.current_zoom = max(self.MIN_ZOOM, self.current_zoom - self.ZOOM_RATE)    
        
    def reset_zoom_cmd(self, event=None):
        print("Reset Zoom") 
        self.current_zoom = self.DEFAULT_ZOOM
        
    def scroll_zoom_cmd(self, event=None):
        print("Scroll Zoom")    
        if event.delta > 0:
            self.zoom_out_cmd(event)
        elif event.delta < 0:
            self.zoom_in_cmd(event)
        
    def close_cmd(self, event=None):
        print("Quit")
        self.root.destroy()
        
    def rename_file_cmd(self, event=None):
        print("Rename File")
        
    def launch(self):
        self.root.mainloop()
        
textEditor = TextEditor()
textEditor.launch()