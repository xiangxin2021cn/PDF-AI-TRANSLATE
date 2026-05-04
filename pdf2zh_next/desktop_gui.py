"""
PDF2ZH-Next Desktop GUI
Native Windows desktop application using tkinter
"""

import asyncio
import logging
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from pdf2zh_next import __version__
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA
from pdf2zh_next.high_level import TranslationError, do_translate_async_stream
from pdf2zh_next.markdown_translator import translate_markdown_file

logger = logging.getLogger(__name__)


class PDF2ZHDesktopApp:
    """Main desktop application class"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"PDF2ZH-Next v{__version__} - PDF Math Translation Tool")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Set application icon (if available)
        try:
            icon_path = Path(__file__).parent / "assets" / "app_icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass  # Icon not available, continue without it
        
        # Initialize configuration
        self.config_manager = ConfigManager()
        self.settings = None
        self.translation_thread = None
        self.is_translating = False
        
        # Language mappings
        self.lang_map = {
            "English": "en",
            "Simplified Chinese": "zh-CN", 
            "Traditional Chinese - Hong Kong": "zh-HK",
            "Traditional Chinese - Taiwan": "zh-TW",
            "Japanese": "ja",
            "Korean": "ko",
            "Polish": "pl",
            "Russian": "ru",
            "Spanish": "es",
            "Portuguese": "pt",
            "Brazilian Portuguese": "pt-BR",
            "French": "fr",
            "Malay": "ms",
            "Indonesian": "id",
        }
        
        self.setup_menu()
        self.setup_ui()
        self.load_settings()

    def setup_menu(self):
        """Setup the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open File...", command=self.browse_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear Log", command=self.clear_log)
        tools_menu.add_command(label="Open Output Directory", command=self.open_output_dir)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        # Bind keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_file())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    def setup_ui(self):
        """Setup the user interface"""
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="PDF2ZH-Next - PDF Math Translation Tool", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # File selection
        ttk.Label(main_frame, text="Input File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(main_frame, textvariable=self.file_path_var, width=50)
        file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        
        browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_file)
        browse_btn.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # Translation engine selection
        ttk.Label(main_frame, text="Translation Engine:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.engine_var = tk.StringVar()
        engine_combo = ttk.Combobox(main_frame, textvariable=self.engine_var, 
                                   values=list(TRANSLATION_ENGINE_METADATA.keys()),
                                   state="readonly")
        engine_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        engine_combo.set("SiliconFlowFree")  # Default
        
        # Language selection
        ttk.Label(main_frame, text="Source Language:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.source_lang_var = tk.StringVar()
        source_lang_combo = ttk.Combobox(main_frame, textvariable=self.source_lang_var,
                                        values=list(self.lang_map.keys()), state="readonly")
        source_lang_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        source_lang_combo.set("English")  # Default
        
        ttk.Label(main_frame, text="Target Language:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.target_lang_var = tk.StringVar()
        target_lang_combo = ttk.Combobox(main_frame, textvariable=self.target_lang_var,
                                        values=list(self.lang_map.keys()), state="readonly")
        target_lang_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        target_lang_combo.set("Simplified Chinese")  # Default
        
        # Output directory
        ttk.Label(main_frame, text="Output Directory:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.output_dir_var = tk.StringVar()
        self.output_dir_var.set(str(Path.cwd() / "pdf2zh_files"))
        output_entry = ttk.Entry(main_frame, textvariable=self.output_dir_var, width=50)
        output_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        
        output_browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_output_dir)
        output_browse_btn.grid(row=5, column=2, padx=(5, 0), pady=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="5")
        options_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(1, weight=1)

        # Dual language output option
        self.dual_output_var = tk.BooleanVar(value=False)
        dual_check = ttk.Checkbutton(options_frame, text="Dual language output",
                                    variable=self.dual_output_var)
        dual_check.grid(row=0, column=0, sticky=tk.W, padx=5)

        # Keep original formatting option
        self.keep_format_var = tk.BooleanVar(value=True)
        format_check = ttk.Checkbutton(options_frame, text="Keep original formatting",
                                      variable=self.keep_format_var)
        format_check.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Translate button
        self.translate_btn = ttk.Button(main_frame, text="Start Translation",
                                       command=self.start_translation)
        self.translate_btn.grid(row=7, column=0, columnspan=3, pady=20)
        
        # Progress bar
        self.progress_var = tk.StringVar()
        self.progress_var.set("Ready")
        progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        progress_label.grid(row=8, column=0, columnspan=3, pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Log output
        ttk.Label(main_frame, text="Log Output:").grid(row=10, column=0, sticky=tk.W, pady=(20, 5))
        self.log_text = scrolledtext.ScrolledText(main_frame, height=10, width=80)
        self.log_text.grid(row=11, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Configure grid weights for resizing
        main_frame.rowconfigure(11, weight=1)
        
        # Setup logging handler
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging to display in the text widget"""
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                self.text_widget.after(0, append)
        
        # Add handler to root logger
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(text_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def load_settings(self):
        """Load application settings"""
        try:
            self.settings = self.config_manager.load_settings()
            logger.info("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            # Create default settings
            self.settings = SettingsModel()
    
    def browse_file(self):
        """Browse for input file"""
        filetypes = [
            ("PDF files", "*.pdf"),
            ("Markdown files", "*.md"),
            ("All files", "*.*")
        ]
        filename = filedialog.askopenfilename(
            title="Select input file",
            filetypes=filetypes
        )
        if filename:
            self.file_path_var.set(filename)
    
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(
            title="Select output directory"
        )
        if directory:
            self.output_dir_var.set(directory)
    
    def start_translation(self):
        """Start the translation process"""
        if self.is_translating:
            messagebox.showwarning("Warning", "Translation is already in progress!")
            return
        
        # Validate inputs
        input_file = self.file_path_var.get().strip()
        if not input_file:
            messagebox.showerror("Error", "Please select an input file!")
            return
        
        if not os.path.exists(input_file):
            messagebox.showerror("Error", "Input file does not exist!")
            return
        
        # Update UI
        self.is_translating = True
        self.translate_btn.config(text="Translating...", state="disabled")
        self.progress_var.set("Starting translation...")
        self.progress_bar.start()
        
        # Start translation in separate thread
        self.translation_thread = threading.Thread(target=self.run_translation)
        self.translation_thread.daemon = True
        self.translation_thread.start()
    
    def run_translation(self):
        """Run translation in background thread"""
        try:
            # Update settings with current UI values
            self.settings.basic.input_files = [self.file_path_var.get()]
            self.settings.translation.output = self.output_dir_var.get()
            self.settings.translation.lang_in = self.lang_map[self.source_lang_var.get()]
            self.settings.translation.lang_out = self.lang_map[self.target_lang_var.get()]
            self.settings.translation.engine = self.engine_var.get()

            # Apply UI options
            self.settings.pdf.no_dual = not self.dual_output_var.get()
            # Note: keep_format_var could be used for future formatting options
            
            # Create output directory if it doesn't exist
            os.makedirs(self.settings.translation.output, exist_ok=True)
            
            logger.info(f"Starting translation of: {self.settings.basic.input_files[0]}")
            logger.info(f"Engine: {self.settings.translation.engine}")
            logger.info(f"From {self.source_lang_var.get()} to {self.target_lang_var.get()}")
            
            # Run translation
            if self.settings.basic.input_files[0].lower().endswith('.md'):
                # Markdown translation
                asyncio.run(self.translate_markdown())
            else:
                # PDF translation
                asyncio.run(self.translate_pdf())
            
            # Translation completed successfully
            self.root.after(0, self.translation_completed)
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            self.root.after(0, lambda: self.translation_failed(str(e)))
    
    async def translate_pdf(self):
        """Translate PDF file"""
        async for progress in do_translate_async_stream(self.settings):
            if hasattr(progress, 'message'):
                self.root.after(0, lambda: self.progress_var.set(progress.message))
    
    async def translate_markdown(self):
        """Translate Markdown file"""
        input_file = Path(self.settings.basic.input_files[0])
        output_file = Path(self.settings.translation.output) / f"{input_file.stem}_translated.md"
        
        await translate_markdown_file(
            input_file=input_file,
            output_file=output_file,
            settings=self.settings
        )
    
    def translation_completed(self):
        """Handle successful translation completion"""
        self.is_translating = False
        self.translate_btn.config(text="Start Translation", state="normal")
        self.progress_bar.stop()
        self.progress_var.set("Translation completed successfully!")
        
        logger.info("Translation completed successfully!")
        
        # Ask if user wants to open output directory
        if messagebox.askyesno("Translation Complete", 
                              "Translation completed successfully!\n\nWould you like to open the output directory?"):
            try:
                os.startfile(self.output_dir_var.get())
            except Exception as e:
                logger.error(f"Failed to open output directory: {e}")
    
    def translation_failed(self, error_msg):
        """Handle translation failure"""
        self.is_translating = False
        self.translate_btn.config(text="Start Translation", state="normal")
        self.progress_bar.stop()
        self.progress_var.set("Translation failed!")
        
        messagebox.showerror("Translation Failed", f"Translation failed with error:\n\n{error_msg}")
    
    def clear_log(self):
        """Clear the log output"""
        self.log_text.delete(1.0, tk.END)

    def open_output_dir(self):
        """Open the output directory"""
        output_dir = self.output_dir_var.get()
        if os.path.exists(output_dir):
            try:
                os.startfile(output_dir)
            except Exception as e:
                logger.error(f"Failed to open output directory: {e}")
                messagebox.showerror("Error", f"Failed to open output directory:\n{e}")
        else:
            messagebox.showwarning("Warning", "Output directory does not exist!")

    def show_about(self):
        """Show about dialog"""
        about_text = f"""PDF2ZH-Next Desktop v{__version__}

PDF Math Translation Tool

A desktop application for translating PDF documents and Markdown files
while preserving mathematical formulas and formatting.

Features:
• PDF translation with math formula preservation
• Markdown file translation
• Multiple translation engines support
• Dual language output option
• Native Windows desktop interface

Visit: https://github.com/PDFMathTranslate/PDFMathTranslate-next"""

        messagebox.showinfo("About PDF2ZH-Next", about_text)

    def run(self):
        """Start the application"""
        logger.info(f"PDF2ZH-Next Desktop v{__version__} started")
        self.root.mainloop()


def setup_desktop_gui():
    """Setup and run the desktop GUI"""
    app = PDF2ZHDesktopApp()
    app.run()


if __name__ == "__main__":
    setup_desktop_gui()
