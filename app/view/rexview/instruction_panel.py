#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RexView Instruction Panel.

Simple introductory label panel displayed at the top of the RexView tab before
any files are loaded. Provides a brief hint to the user on how to begin.

Key contents:
- instructionPanel: Lightweight label panel with introductory text.

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
from tkinter import ttk as ttk

class instructionPanel:
    def __init__(self, root, frame):
        self.root = root
        self.frame = frame
        
        # text Frame and its contents
        
        self.introLabel = ttk.Label(self.frame, 
                                   text = 'Select a folder to process or choose single files!')
        self.introLabel.grid(row=0, column=0, sticky=tk.W + tk.W + tk.N + tk.S, pady=3)
        
        # more instructions possible