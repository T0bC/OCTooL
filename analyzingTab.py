# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 15:14:14 2021

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from analyzeGuiFrames.analyzingInstructionFrame import instructionPanel as instruction

def addContent(self, frame):
    self.analyzingTabFrame = frame
    # adapt this to your liking
    self.analyzingTabFrame.columnconfigure(0, weight=1)
    self.analyzingTabFrame.columnconfigure(1, weight=1)
    #self.analyzingTabFrame.rowconfigure(0, weight=0)
    #self.analyzingTabFrame.rowconfigure(5, weight=1)
    

    # %% Create Frames for Content here  
    
    # INSTRUCTIONS
    self.instrFrame = ttk.LabelFrame(self.analyzingTabFrame, text="Outlook...", relief=tk.RIDGE)
    self.instrFrame.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    
    
    # %% Fill Content Frames with widgets here        
    # create content (Panel) inside the frames / Create Instances of each class
    self.instrPanel = instruction(self.analyzingTabFrame, self.instrFrame)