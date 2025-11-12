#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated UI Test for Module Tracking

This script programmatically exercises all UI elements to ensure
complete module usage tracking. It can be used standalone or integrated
with track_module_usage.py for comprehensive testing.

Usage:
    python automated_ui_test.py
    
Or integrate with module tracking:
    python track_module_usage.py
    (then manually run this script in another terminal)

Author: Auto-generated for OCTexVIEW optimization
"""

import tkinter as tk
from tkinter import ttk
import time
import sys
import os


class AutomatedUITester:
    """Automates UI interaction for comprehensive module tracking."""
    
    def __init__(self, main_gui):
        self.main_gui = main_gui
        self.test_log = []
        self.errors = []
        self.widgets_tested = 0
        
    def log(self, message, level="INFO"):
        """Log a test action with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.test_log.append(log_entry)
    
    def safe_invoke(self, widget, widget_type, action_name):
        """Safely invoke a widget action with error handling."""
        try:
            if hasattr(widget, 'invoke'):
                widget.invoke()
            elif hasattr(widget, 'event_generate'):
                widget.event_generate('<Button-1>')
            self.widgets_tested += 1
            self.log(f"✓ {widget_type}: {action_name}", "SUCCESS")
            return True
        except tk.TclError as e:
            # Expected for some widgets (e.g., file dialogs without selection)
            self.log(f"⚠ {widget_type}: {action_name} - {str(e)[:50]}", "EXPECTED")
            return False
        except Exception as e:
            # Unexpected errors
            self.errors.append((widget_type, action_name, str(e)))
            self.log(f"✗ {widget_type}: {action_name} - {str(e)[:50]}", "ERROR")
            return False
    
    def test_all_tabs(self):
        """Switch through all tabs to trigger tab-specific imports."""
        self.log("=" * 60)
        self.log("Testing all tabs...")
        self.log("=" * 60)
        
        tab_names = ['Export', 'Analyze', 'CarlQuant']
        for i, tab_name in enumerate(tab_names):
            try:
                self.main_gui.switch_tab(i)
                self.main_gui.mainWin.update()
                time.sleep(0.3)
                self.log(f"Switched to {tab_name} tab")
            except Exception as e:
                self.log(f"Error switching to {tab_name}: {e}", "ERROR")
    
    def test_buttons(self, frame, parent_name=""):
        """Recursively find and test all buttons in a frame."""
        for widget in frame.winfo_children():
            try:
                widget_class = widget.winfo_class()
                
                if isinstance(widget, (ttk.Button, tk.Button)):
                    # Get button text for identification
                    try:
                        text = widget.cget('text') or 'unnamed'
                    except:
                        text = 'unnamed'
                    
                    widget_id = f"{parent_name}.{text}" if parent_name else text
                    
                    # Skip certain buttons that might cause issues
                    skip_buttons = ['Quit', 'Exit', 'Close']
                    if any(skip in text for skip in skip_buttons):
                        self.log(f"Skipping button: {text}", "SKIP")
                        continue
                    
                    self.safe_invoke(widget, "Button", widget_id)
                    self.main_gui.mainWin.update()
                    time.sleep(0.1)
                
                # Recurse into child widgets
                if hasattr(widget, 'winfo_children'):
                    child_name = f"{parent_name}.{widget_class}" if parent_name else widget_class
                    self.test_buttons(widget, child_name)
                    
            except Exception as e:
                self.log(f"Error processing widget: {e}", "ERROR")
    
    def test_checkboxes(self, frame, parent_name=""):
        """Recursively find and test all checkboxes."""
        for widget in frame.winfo_children():
            try:
                if isinstance(widget, (ttk.Checkbutton, tk.Checkbutton)):
                    try:
                        text = widget.cget('text') or 'unnamed'
                    except:
                        text = 'unnamed'
                    
                    widget_id = f"{parent_name}.{text}" if parent_name else text
                    
                    # Toggle checkbox twice (on and off)
                    self.safe_invoke(widget, "Checkbox", f"{widget_id} [ON]")
                    self.main_gui.mainWin.update()
                    time.sleep(0.05)
                    
                    self.safe_invoke(widget, "Checkbox", f"{widget_id} [OFF]")
                    self.main_gui.mainWin.update()
                    time.sleep(0.05)
                
                if hasattr(widget, 'winfo_children'):
                    widget_class = widget.winfo_class()
                    child_name = f"{parent_name}.{widget_class}" if parent_name else widget_class
                    self.test_checkboxes(widget, child_name)
                    
            except Exception as e:
                self.log(f"Error processing checkbox: {e}", "ERROR")
    
    def test_comboboxes(self, frame, parent_name=""):
        """Recursively find and test all dropdown menus."""
        for widget in frame.winfo_children():
            try:
                if isinstance(widget, ttk.Combobox):
                    try:
                        values = widget['values']
                        if values and len(values) > 0:
                            # Test first and last value
                            widget.current(0)
                            widget.event_generate('<<ComboboxSelected>>')
                            self.main_gui.mainWin.update()
                            self.log(f"Combobox: {parent_name} -> {values[0]}")
                            time.sleep(0.1)
                            
                            if len(values) > 1:
                                widget.current(len(values) - 1)
                                widget.event_generate('<<ComboboxSelected>>')
                                self.main_gui.mainWin.update()
                                time.sleep(0.1)
                            
                            self.widgets_tested += 1
                    except Exception as e:
                        self.log(f"Error with combobox: {e}", "EXPECTED")
                
                if hasattr(widget, 'winfo_children'):
                    widget_class = widget.winfo_class()
                    child_name = f"{parent_name}.{widget_class}" if parent_name else widget_class
                    self.test_comboboxes(widget, child_name)
                    
            except Exception as e:
                self.log(f"Error processing combobox: {e}", "ERROR")
    
    def test_menu_items(self):
        """Test menu items if any exist."""
        try:
            menu = self.main_gui.mainWin.cget('menu')
            if menu:
                self.log("Testing menu items...")
                # Menu testing would go here
                # This is complex and might trigger unwanted actions
                self.log("Menu testing skipped (manual testing recommended)")
        except:
            pass
    
    def test_dialogs(self):
        """Test Help and About dialogs."""
        self.log("=" * 60)
        self.log("Testing dialogs...")
        self.log("=" * 60)
        
        # Test Help dialog
        try:
            self.main_gui.onHelp()
            self.main_gui.mainWin.update()
            time.sleep(0.5)
            self.log("✓ Help dialog opened")
            
            # Try to close it
            for widget in self.main_gui.mainWin.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()
                    break
        except Exception as e:
            self.log(f"Help dialog error: {e}", "ERROR")
        
        # Test About dialog
        try:
            self.main_gui.onAbout()
            self.main_gui.mainWin.update()
            time.sleep(0.5)
            self.log("✓ About dialog opened")
            
            # Try to close it
            for widget in self.main_gui.mainWin.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()
                    break
        except Exception as e:
            self.log(f"About dialog error: {e}", "ERROR")
    
    def get_current_tab_frame(self):
        """Get the frame of the currently selected tab."""
        try:
            return self.main_gui.tabParent.nametowidget(
                self.main_gui.tabParent.select()
            )
        except:
            return None
    
    def run_comprehensive_test(self):
        """Run all automated tests."""
        start_time = time.time()
        
        print("\n")
        self.log("=" * 70)
        self.log("AUTOMATED UI TEST - STARTED")
        self.log("=" * 70)
        self.log("This will exercise all UI elements to ensure complete module tracking")
        self.log("")
        
        # Test all tabs first
        self.test_all_tabs()
        time.sleep(0.5)
        
        # Test each tab's content
        tab_names = ['Export', 'Analyze', 'CarlQuant']
        for i, tab_name in enumerate(tab_names):
            self.log("")
            self.log("=" * 60)
            self.log(f"Testing {tab_name} tab content...")
            self.log("=" * 60)
            
            try:
                self.main_gui.switch_tab(i)
                self.main_gui.mainWin.update()
                time.sleep(0.3)
                
                current_frame = self.get_current_tab_frame()
                if current_frame:
                    # Test all widget types in this tab
                    self.log(f"Testing buttons in {tab_name}...")
                    self.test_buttons(current_frame, tab_name)
                    
                    self.log(f"Testing checkboxes in {tab_name}...")
                    self.test_checkboxes(current_frame, tab_name)
                    
                    self.log(f"Testing comboboxes in {tab_name}...")
                    self.test_comboboxes(current_frame, tab_name)
                else:
                    self.log(f"Could not get frame for {tab_name}", "WARNING")
                    
            except Exception as e:
                self.log(f"Error testing {tab_name} tab: {e}", "ERROR")
        
        # Test dialogs
        time.sleep(0.5)
        self.test_dialogs()
        
        # Print summary
        elapsed = time.time() - start_time
        
        print("\n")
        self.log("=" * 70)
        self.log("AUTOMATED UI TEST - COMPLETED")
        self.log("=" * 70)
        self.log(f"Duration: {elapsed:.1f} seconds")
        self.log(f"Widgets tested: {self.widgets_tested}")
        self.log(f"Errors encountered: {len(self.errors)}")
        
        if self.errors:
            self.log("")
            self.log("UNEXPECTED ERRORS:")
            for widget_type, action, error in self.errors[:10]:
                self.log(f"  - {widget_type} ({action}): {error[:60]}")
            if len(self.errors) > 10:
                self.log(f"  ... and {len(self.errors) - 10} more")
        
        self.log("")
        self.log("NEXT STEPS:")
        self.log("  1. Manually test any features not covered by automation")
        self.log("  2. Load sample data files if available")
        self.log("  3. Perform actual operations (export, analyze, etc.)")
        self.log("  4. Press Ctrl+C to finish module tracking")
        self.log("=" * 70)
        
        return self.test_log


def run_automated_test(main_gui, delay_ms=2000):
    """
    Run automated test on a MainGui instance.
    
    Args:
        main_gui: Instance of MainGui
        delay_ms: Delay in milliseconds before starting test
    """
    tester = AutomatedUITester(main_gui)
    # Schedule the test to run after GUI is fully initialized
    main_gui.mainWin.after(delay_ms, tester.run_comprehensive_test)
    return tester


if __name__ == "__main__":
    print("=" * 70)
    print("AUTOMATED UI TESTER")
    print("=" * 70)
    print("\nThis script should be run AFTER starting track_module_usage.py")
    print("\nUsage:")
    print("  1. In terminal 1: python build_tools/track_module_usage.py")
    print("  2. Wait for app to start")
    print("  3. In terminal 2: python build_tools/automated_ui_test.py")
    print("\nAlternatively, the test runs automatically with track_module_usage.py")
    print("=" * 70)
    
    # Add parent directory to path so we can import MainGui
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    
    # Try to import and run with OCTexVIEW
    try:
        import MainGui as mainGui
        
        print("\nStarting OCTexVIEW with automated testing...")
        myWindow = mainGui.MainGui()
        
        # Run automated test after 2 seconds
        tester = run_automated_test(myWindow, delay_ms=2000)
        
        myWindow.start()
        
    except ImportError:
        print("\nError: Could not import MainGui")
        print("Make sure you're running this from the OCTexVIEW directory")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
