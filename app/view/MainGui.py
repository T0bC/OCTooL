#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main GUI.

Top-level application window orchestrator. Creates the themed Tkinter root,
installs global exception handling, sets up the custom coloured tab bar, and
assembles the three main tabs (RexView, AnnoLyze, CarlQuant). Also hosts the
shared status bar and silent background update checker.

Key contents:
- MainGui: Root window builder and tab orchestrator.
- __init__: Builds the root, style, tab container, status bar, and all tabs.
- create_colored_tab_buttons / switch_tab: Custom tab-bar UI with theme-aware colours.
- _setup_tab_styles / _apply_tab_colors: ttkbootstrap style overrides.
- _on_update_available: Callback that shows the update-available notification.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""


import tkinter as tk
from tkinter import ttk
import webbrowser
from ttkbootstrap import Style
from app.view.rexview import rexViewTab
from app.view.annolyze import annoLyzeTab
from app.view.carlquant import carlQuantTab
from app.view.shared.app_context import AppContext
from app.logic.shared.paths import resource_path
from app.view.shared.status_bar import StatusBar
from app.view.shared.error_handler import handle_errors, install_tk_exception_handler
from app.view.shared.help_dialog import HelpDialog
from app.view.shared.about_dialog import AboutDialog
from app.logic.shared.app_config import VERSION_DISPLAY, SERVER_BASE_URL
from app.logic.shared.update_checker import check_for_updates_async, check_for_updates_sync


class MainGui:
    @handle_errors("MainGui.init")
    def __init__(self):
        # ========================================
        # DISTRIBUTION CONFIGURATION
        # Set to True to enable each section, False to hide
        # ========================================
        self.ENABLE_REXVIEW = True
        self.ENABLE_ANNOLYZE = True
        self.ENABLE_CARLQUANT = True
        # ========================================

        self.mainWin = tk.Tk()
        self.mainWin.withdraw()

        # Route every uncaught Tk callback exception to a user-visible popup + log,
        # so the app never fails silently (critical for windowed PyInstaller builds).
        install_tk_exception_handler(self.mainWin)

        self.context = AppContext()
        self.context.root = self.mainWin

        self.version = VERSION_DISPLAY
        self.mainWin.title(str('OCTooL' + self.version))
        self.pathToFolder = None
        self.mainWin['padx'] = 5
        self.mainWin['pady'] = 5

        # seetings for resizing of the window
        self.mainWin.columnconfigure(0, weight = 1)
        self.mainWin.rowconfigure(0, weight = 1)  # Main content row
        self.mainWin.rowconfigure(1, weight = 0)  # Status bar row

        # set a custom icon
        try:
            icon_path = resource_path("icons/thumb_6.ico")
            self.mainWin.iconbitmap(icon_path)
        except Exception as e:
            print(f"Warning: Could not set icon: {e}")

        self.style = Style(theme="darkly")
        self.context.style = self.style  # Store style in context for access by panels

        # Create custom tab styles with different colors
        self._setup_tab_styles()


        # %% Create custom colored tab system
        # Create container for custom tab system
        self.tabContainer = ttk.Frame(self.mainWin)
        self.tabContainer.grid(row = 0, column = 0, sticky = tk.E + tk.W + tk.N + tk.S)
        self.tabContainer.columnconfigure(0, weight=1)
        self.tabContainer.rowconfigure(1, weight=1)

        # Create custom tab bar with colored buttons
        self.tabBar = ttk.Frame(self.tabContainer)
        self.tabBar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))

        # Create colored tab buttons
        self.create_colored_tab_buttons()

        # Create content area (using notebook without visible tabs)
        self.tabParent = ttk.Notebook(self.tabContainer)
        self.tabParent.grid(row = 1, column = 0, sticky = tk.E + tk.W + tk.N + tk.S)

        # Hide the notebook tabs after creation
        self.tabParent.configure(style="Hidden.TNotebook")
        # make the window resizeable
        self.tabParent.columnconfigure(0, weight = 1)
        self.tabParent.rowconfigure(0, weight = 1)

        # Shared status bar container
        self.statusFrame = ttk.Frame(self.mainWin)
        self.statusFrame.grid(row = 1, column = 0, sticky = tk.E + tk.W, pady = (5, 0))
        self.statusFrame.columnconfigure(0, weight = 1)

        self.statusBar = StatusBar(self.statusFrame)
        self.statusBar.frame.grid(row = 0, column = 0, sticky = "ew")

        # %% EXPORT TAB
        # create a frame holding the contents for the tab
        if self.ENABLE_REXVIEW:
            self.rexViewTabFrame = ttk.Frame(self.tabParent)
            self.tabParent.add(self.rexViewTabFrame, text = 'RexView')
            # Fill the tab with content defined in rexViewTab.py
            rexViewTab.addContent(self, self.rexViewTabFrame)


        # %% Anylyzing Tab
        if self.ENABLE_ANNOLYZE:
            self.annoLyzeFrame = ttk.Frame(self.tabParent)
            self.tabParent.add(self.annoLyzeFrame, text = 'AnnoLyze')
            annoLyzeTab.addContent(self, self.annoLyzeFrame)

        # %% Carl Quant
        if self.ENABLE_CARLQUANT:
            self.carlQuantTabFrame = ttk.Frame(self.tabParent)
            self.tabParent.add(self.carlQuantTabFrame, text='CarlQuant')
            carlQuantTab.addContent(self, self.carlQuantTabFrame)

        # Apply custom styles to individual tabs after all tabs are created
        self._apply_tab_colors()

        # Select first available tab after everything is created
        if self.tab_buttons and self.tabParent.index("end") > 0:
            self.switch_tab(0)

        self.mainWin.update_idletasks()  # Ensure layout is processed
        self.mainWin.deiconify()

        # Silent background update check: only prompts if a newer version exists.
        check_for_updates_async(self.mainWin, self._on_update_available)

    @handle_errors("MainGui.setup_tab_styles")
    def _setup_tab_styles(self):
        """Setup custom styles for colored tab buttons."""
        # Hide the default notebook tabs completely by modifying the layout
        self.style.layout("Hidden.TNotebook", [
            ("Notebook.client", {"sticky": "nswe"})
        ])  # Only keep the client area, remove tab area

        # Alternative: Set tab height to 0
        self.style.configure(
            "Hidden.TNotebook.Tab",
            padding=[0, 0, 0, 0],  # No padding at all
            borderwidth=0,         # No border
            focuscolor="none",
            relief="flat"
        )

        # Make tabs invisible by setting their size to 0
        self.style.map(
            "Hidden.TNotebook.Tab",
            expand=[("selected", [0, 0, 0, 0])],  # No expansion
            background=[("selected", ""), ("active", ""), ("!active", "")],
            foreground=[("selected", ""), ("active", ""), ("!active", "")]
        )

        # Create colored button styles for each tab
        # RexView tab - Blue/Primary
        self.style.configure(
            "RexView.TButton",
            background=self.style.colors.primary,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[20, 10]
        )

        # AnnoLyze tab - Green/Success
        self.style.configure(
            "AnnoLyze.TButton",
            background=self.style.colors.success,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[20, 10]
        )

        # CarlQuant tab - Orange/Warning
        self.style.configure(
            "CarlQuant.TButton",
            background=self.style.colors.warning,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[20, 10]
        )

        # Header tool buttons (Updates / Help / About) - consistent emoji font
        # so the glyphs all render at the same, larger size.
        self.style.configure(
            "Header.secondary.TButton",
            font=("Segoe UI Emoji", 11),
            padding=[12, 5]
        )

    @handle_errors("MainGui.create_colored_tab_buttons")
    def create_colored_tab_buttons(self):
        """Create colored buttons that act as tabs, plus Help and About buttons."""
        self.tab_buttons = []
        self.current_tab = 0
        
        # Configure tabBar to have space between tab buttons and help buttons
        self.tabBar.columnconfigure(0, weight=0)  # Tab buttons
        self.tabBar.columnconfigure(1, weight=1)  # Spacer
        self.tabBar.columnconfigure(2, weight=0)  # Help buttons
        
        # Container for tab buttons (left side)
        tab_button_container = ttk.Frame(self.tabBar)
        tab_button_container.grid(row=0, column=0, sticky="w")

        # Track column position for dynamic button placement
        col_index = 0
        
        # RexView button
        if self.ENABLE_REXVIEW:
            export_btn = ttk.Button(
                tab_button_container,
                text="RexView", #📊
                style="RexView.TButton",
                command=lambda idx=col_index: self.switch_tab(idx),
                takefocus=False  # Prevent button from taking focus
            )
            export_btn.grid(row=0, column=col_index, padx=(0 if col_index == 0 else 2, 2 if self.ENABLE_ANNOLYZE or self.ENABLE_CARLQUANT else 0))
            self.tab_buttons.append(export_btn)
            col_index += 1

        # AnnoLyze button
        if self.ENABLE_ANNOLYZE:
            analyze_btn = ttk.Button(
                tab_button_container,
                text="AnnoLyze", #🔬
                style="AnnoLyze.TButton",
                command=lambda idx=col_index: self.switch_tab(idx),
                takefocus=False  # Prevent button from taking focus
            )
            analyze_btn.grid(row=0, column=col_index, padx=(0 if col_index == 0 else 2, 2 if self.ENABLE_CARLQUANT else 0))
            self.tab_buttons.append(analyze_btn)
            col_index += 1

        # CarlQuant button
        if self.ENABLE_CARLQUANT:
            carlquant_btn = ttk.Button(
                tab_button_container,
                text="CarlQuant", #⚡
                style="CarlQuant.TButton",
                command=lambda idx=col_index: self.switch_tab(idx),
                takefocus=False  # Prevent button from taking focus
            )
            carlquant_btn.grid(row=0, column=col_index, padx=(0 if col_index == 0 else 2, 0))
            self.tab_buttons.append(carlquant_btn)
            col_index += 1
        
        # Container for Help and About buttons (right side)
        help_button_container = ttk.Frame(self.tabBar)
        help_button_container.grid(row=0, column=2, sticky="e")
        
        # Check for updates button
        update_btn = ttk.Button(
            help_button_container,
            text="🔄 Check for updates",
            style="Header.secondary.TButton",
            command=self.onCheckForUpdates,
            takefocus=False
        )
        update_btn.grid(row=0, column=0, padx=(0, 2))

        # Help button
        help_btn = ttk.Button(
            help_button_container,
            text="❓ Help",
            style="Header.secondary.TButton",
            command=self.onHelp,
            takefocus=False
        )
        help_btn.grid(row=0, column=1, padx=2)
        
        # About button
        about_btn = ttk.Button(
            help_button_container,
            text="ℹ️ About",
            style="Header.secondary.TButton",
            command=self.onAbout,
            takefocus=False
        )
        about_btn.grid(row=0, column=2, padx=(2, 0))

    @handle_errors("MainGui.switch_tab")
    def switch_tab(self, tab_index):
        """Switch to the specified tab."""
        # Safeguard: Check if tab_index is valid
        num_tabs = self.tabParent.index("end")
        if num_tabs == 0:
            # No tabs available, do nothing
            return
        
        if tab_index >= num_tabs:
            # Tab index out of bounds, do nothing
            return
        
        # Force the button to lose focus immediately
        self.mainWin.focus_set()

        # Switch to the tab
        self.tabParent.select(tab_index)
        self.current_tab = tab_index

        # Force an immediate update of the display
        self.tabParent.update_idletasks()

        # Update button appearances (optional: make selected button darker)
        for i, btn in enumerate(self.tab_buttons):
            # Remove focus from all buttons
            btn.state(['!pressed', '!active'])

            if i == tab_index:
                # Make selected button slightly darker
                if i == 0:  # RexView
                    btn.configure(style="RexView.TButton")
                elif i == 1:  # AnnoLyze
                    btn.configure(style="AnnoLyze.TButton")
                elif i == 2:  # CarlQuant
                    btn.configure(style="CarlQuant.TButton")

    @handle_errors("MainGui.apply_tab_colors")
    def _apply_tab_colors(self):
        """Apply the hidden style to notebook tabs."""
        # Hide the default notebook tabs since we're using custom buttons
        try:
            for i in range(self.tabParent.index("end")):
                self.tabParent.tab(i, text="")  # Remove text from hidden tabs
        except tk.TclError:
            pass

    @handle_errors("MainGui.start")
    def start(self):
        self.mainWin.mainloop() #start monitoring and updating the GUI

    @handle_errors("MainGui.onHelp")
    def onHelp(self):
        """Show context-aware help based on the currently active tab."""
        # Build mapping of tab indices to tab types based on enabled tabs
        tab_type_map = []
        if self.ENABLE_REXVIEW:
            tab_type_map.append(0)  # RexView
        if self.ENABLE_ANNOLYZE:
            tab_type_map.append(1)  # AnnoLyze
        if self.ENABLE_CARLQUANT:
            tab_type_map.append(2)  # CarlQuant
        
        # Get the actual tab type for the current tab index
        if self.current_tab < len(tab_type_map):
            actual_tab_type = tab_type_map[self.current_tab]
        else:
            # Fallback to first available tab type
            actual_tab_type = tab_type_map[0] if tab_type_map else 0
        
        help_dialog = HelpDialog(self.mainWin, self.style, actual_tab_type)
        help_dialog.show()

    @handle_errors("MainGui.onAbout")
    def onAbout(self):
        """Show About dialog with dark theme."""
        about_dialog = AboutDialog(self.mainWin, self.style, self.version)
        about_dialog.show()

    @handle_errors("MainGui.onCheckForUpdates")
    def onCheckForUpdates(self):
        """Manual update check: always gives feedback (newer / up-to-date / error)."""
        info = check_for_updates_sync()
        if info.available:
            self._on_update_available(info)
        elif info.error:
            tk.messagebox.showwarning(
                title='Update Check Failed',
                message='Could not check for updates.\n\n'
                        f'{info.error}\n\nCheck your internet connection.'
            )
        else:
            tk.messagebox.showinfo(
                title='No Updates',
                message=f'OCTooL{self.version} is up to date.'
            )

    @handle_errors("MainGui.on_update_available")
    def _on_update_available(self, info):
        """Show an 'update available' dialog and optionally open the download."""
        message = (
            f'A newer version of OCTooL is available.\n\n'
            f'Installed:{self.version}\n'
            f'Available:  [v. {info.latest_version}]\n'
        )
        if info.notes:
            message += f'\n{info.notes}\n'
        message += (
            '\nInstallation: Download the zip, extract it, close OCTooL and\n'
            'replace the old folder (or overwrite the existing one).\n'
            'Create a new desktop shortcut from OCTooL.exe if necessary.\n\n'
            'Open the download page now?'
        )

        if tk.messagebox.askyesno(title='Update Available', message=message):
            if info.download_url:
                webbrowser.open(info.download_url)
            else:
                webbrowser.open(SERVER_BASE_URL)

    @handle_errors("MainGui.attach_status_bar")
    def attach_status_bar(self, context):
        """Attach the shared status bar to a given context."""
        if hasattr(self, "statusBar") and self.statusBar:
            self.statusBar.attach_context(context)
        else:
            raise RuntimeError("StatusBar not initialized in MainGui")
