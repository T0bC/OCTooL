#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:54:41 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
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