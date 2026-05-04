"""
PDF2ZH-Next WebView Desktop Application
Wraps the web interface in a native desktop window using webview
"""

import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

try:
    import webview
except ImportError:
    print("Error: pywebview is not installed. Please install it with:")
    print("pip install pywebview")
    sys.exit(1)

from pdf2zh_next import __version__
# Import will be done dynamically to avoid circular imports

logger = logging.getLogger(__name__)


class WebViewDesktopApp:
    """Desktop application using webview to wrap the web interface"""
    
    def __init__(self):
        self.server_port = 7860
        self.server_thread = None
        self.server_url = f"http://localhost:{self.server_port}"
        self.window = None
        
    def start_server(self):
        """Start the web server in a separate thread"""
        def run_server():
            try:
                # Import and start the GUI server
                from pdf2zh_next.gui import setup_gui
                setup_gui(
                    auth_file=None,
                    welcome_page=True,
                    server_port=self.server_port,
                    share=False,
                    debug=False
                )
            except Exception as e:
                logger.error(f"Failed to start server: {e}")
                
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        max_wait = 30  # seconds
        for i in range(max_wait):
            try:
                import urllib.request
                urllib.request.urlopen(self.server_url, timeout=1)
                logger.info(f"Server started successfully on {self.server_url}")
                return True
            except:
                time.sleep(1)
                
        logger.error("Failed to start server within timeout")
        return False
    
    def create_window(self):
        """Create the webview window"""
        try:
            # Set window properties
            window_title = f"PDF2ZH-Next v{__version__} - PDF Math Translation Tool"
            
            # Create the webview window
            self.window = webview.create_window(
                title=window_title,
                url=self.server_url,
                width=1200,
                height=800,
                min_size=(800, 600),
                resizable=True,
                shadow=True,
                on_top=False,
                text_select=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create window: {e}")
            return False
    
    def on_window_loaded(self):
        """Called when the window is loaded"""
        logger.info("WebView window loaded successfully")
        
        # Optional: Inject custom CSS or JavaScript
        try:
            # Hide the Gradio footer or customize appearance
            custom_css = """
            <style>
            .gradio-container {
                max-width: none !important;
            }
            footer {
                display: none !important;
            }
            </style>
            """
            # Note: webview.evaluate_js can be used to inject JavaScript
        except Exception as e:
            logger.warning(f"Failed to inject custom styles: {e}")
    
    def run(self):
        """Start the desktop application"""
        logger.info(f"Starting PDF2ZH-Next Desktop v{__version__}")
        
        # Start the web server
        if not self.start_server():
            print("Failed to start the web server. Exiting.")
            return 1
            
        # Create the webview window
        if not self.create_window():
            print("Failed to create the desktop window. Exiting.")
            return 1
            
        try:
            # Start the webview (this blocks until window is closed)
            webview.start(
                debug=False,
                http_server=False  # We're using our own server
            )
            
            logger.info("Application closed by user")
            return 0
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            print(f"Application error: {e}")
            return 1


def setup_webview_gui():
    """Setup and run the webview desktop GUI"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the application
    app = WebViewDesktopApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(setup_webview_gui())
