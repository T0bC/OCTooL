#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:54:41 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk

class instructionPanel:
    def __init__(self, root, frame):
        self.root = root
        self.frame = frame
        
        # text Frame and its contents
        
        self.introLabel = tk.Label(self.frame, 
                                   text = 'This feauture is currently not activated!')
        self.introLabel.grid(row=0, column=0, sticky=tk.W + tk.W + tk.N + tk.S, pady=3)
        
        self.introLabel = tk.Label(self.frame, 
                                   text = 'Future releases may unlock this!')
        self.introLabel.grid(row=1, column=0, sticky=tk.W + tk.W + tk.N + tk.S, pady=3)
        # more instructions possible