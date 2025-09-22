#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 19:47:52 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import MainGui as mainGui
import traceback
import tkinter as tk
from tkinter import messagebox

def show_error_popup(title="Unexpected Error", exception=None):
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    error_message = f"{str(exception)}\n\nTraceback:\n{traceback.format_exc()}"
    messagebox.showerror(title, error_message)
    root.destroy()

try:
    myWindow = mainGui.MainGui()
    myWindow.start()
except Exception as e:
    show_error_popup(exception=e)