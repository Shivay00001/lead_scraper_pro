"""
Lead Scraper Pro - Main Entry Point
Run the application from here.
"""

import sys
import os

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.cli import LeadScraperCLI

def launch_gui():
    """Launch the modern GUI."""
    try:
        from ui.app import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"[ERROR] GUI requirements not met (PySide6). Error: {e}")
        print("Install with: pip install PySide6")
        sys.exit(1)

def main():
    """Determine mode and launch."""
    args = sys.argv[1:]
    
    # Check for GUI request or no args (default to GUI in future, currently explicit)
    if not args or 'gui' in args:
        launch_gui()
    else:
        # Launch CLI
        cli = LeadScraperCLI()
        cli.run()

if __name__ == '__main__':
    main()
