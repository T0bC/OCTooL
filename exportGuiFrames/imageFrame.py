#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
import octFunctions as octF
import cv2
from PIL import Image, ImageTk
from toolTip import Tooltip


class imagePanel:
    def __init__(self, root, frame, treeView, globalSettingsFrame, customSettingsFrame, pickFrame):
        self.root = root
        self.frame = frame
        self.treeView = treeView
        self.globalSettingsFrame = globalSettingsFrame
        self.customSettingsFrame = customSettingsFrame
        self.pickFrame = pickFrame
            
        
        # Image Frame
        # displayed in pickFilesFrame
        self.showBtn = ttk.Button(self.pickFrame, text='Show', width=14, command = self.dispImageInCanvas)
        self.showBtn.grid(row=0, column=6, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.showBtnToolTip = 'Select a OCT-Scan from the queue and display it.'
        Tooltip(self.showBtn, text=self.showBtnToolTip , wraplength=200)
        
        #self.canvas = ResizingCanvas(self.frame, width=1024, height=342, highlightthickness=0, bg='red')
        self.canvas = tk.Canvas(self.frame, width=1024, height=342, highlightthickness=0, bg='#505050')
        self.canvas.grid(row=1, column=0, columnspan=2, sticky=tk.E + tk.W + tk.N + tk.S)
        self.canvas.bind("<Configure>", self.onResize)
            
        self.instructionText()
        
        self.scaleValue = tk.StringVar()
        # Insert a Scale to select current slice
        self.scale = ttk.Scale(self.frame, from_=0, to=2, orient='horizontal')
        self.scale.set(1)
        self.scale.grid(row=3, column = 0, sticky=tk.E + tk.W + tk.N + tk.S)
        
        self.scaleValueLabel = ttk.Label(self.frame, text="text", textvariable=self.scaleValue)
        self.scaleValueLabel.grid(row=3, column = 1, sticky=tk.E)

    def instructionText(self):
        '''
        Display some instructions.

        Returns
        -------
        None.

        '''
        self.canvas.update()
        self.cwidth = self.canvas.winfo_width()
        self.cheight = self.canvas.winfo_height()        
        
        #self.medFakPhoto = "icons/Logo_Med_Fak_unigrau_transparent.png"
        self.ULPhoto = "icons/WBM_UL_RGB_digital_Path.png"
        
        # Med Fakultaet Image
        #self.medImage = Image.open(self.medFakPhoto)
        #self.medImage = self.medImage.resize((217,50), Image.ANTIALIAS)
        #self.medImage = ImageTk.PhotoImage(self.medImage)
        #self.canvas.create_image(self.cwidth-(217/2)-7, 25, image=self.medImage)
        
        self.ULImage = Image.open(self.ULPhoto)
        self.ULImage = self.ULImage.resize((217,76), Image.ANTIALIAS)
        self.ULImage = ImageTk.PhotoImage(self.ULImage)
        self.canvas.create_image(self.cwidth-(217/2)-7, 45, image=self.ULImage)
        
        self.canvas.create_text(70,10,fill="#D0D0D0",font="Sans 15 bold",disabledfill="black",
                                text="Short Manual", justify=tk.RIGHT, tags = "Text")
        
        self.content1 = "- Select a folder with OCT files (subfolders are searched)\n" \
            "- You can add single files as well via 'Select Files'\n" \
            "- To view a dataset select it in the 'Queue' then click show\n" \
            "- 'Global Settings' applys to all data sets in the queue\n \n" \
            "Custom Settings\n" \
            "- 'Exp. Range: First and Last Slice to export \n" \
            "- 'Equidist. Slices'': Amount of equidistant slices in Exp. Range\n" \
            "- 'Dyn. Range [dB]': Adjust the 'Contrast' of the image\n" \
            "- 'Dispersion Correction': Adjust for 'sharp' edges\n\n" \
            "Additional Meta Information\n" \
            "If you supply a *.txt in the same folder as the OCT File " \
            "with the following structure, the provided parameters are imported:\n\n" \
            "First Line: First-Last Slice to export\n" \
            "Second Line: Number of equidistant slices\n" \
            "Third Line: Offset for time series"
        # x, y
        self.canvas.create_text(405,180,fill="#D0D0D0",font="Sans 11", justify=tk.LEFT,
                                text=self.content1)

    def onResize(self, event):
        '''
        If the user changes the canvas size the image inside is resized.

        Parameters
        ----------
        event : event
            Either clickin and dragging or tapping on maximize or any method
            to resize a window.

        Returns
        -------
        None.

        '''        
        # define what you want to do with the canvas here.
        self.width = event.width
        self.height = event.height
        # if there is no image then don't run show image
        # but if there is text resize the canvas
        if len(self.canvas.find_all()) > 0:
            if(len(self.canvas.find_withtag("Text")) > 0):
                self.canvas.delete("all")
                self.instructionText()
                return
            self.dispImageInCanvas()

        
        # %% Functions
        
        # dispImageInCanvas
    def dispImageInCanvas(self):
        '''
        Read selected OCT File, extract XML-Data, create a Scale according to
        stack size. By default the first image to be shown is in the middle of
        the stack. If scale is moved the new image is created.

        Returns
        -------
        None.

        '''
        if len(self.treeView.getFocus()) != 0:
            self.file = self.treeView.getValue(column = 'Path')
            
            # Unzip Data and read XML Header to Buffer
            # open zipfile without unpacking                  
            self.archive = octF.unzipOCTData(self.file)
        
            # Read the XML Data to Buffer use BS for read of XML 
            self.xmlContent = octF.readXMLContent(self.archive, 'Header.xml', 'xml')
                      
            self.treeView.setValue('Status', 'displayed')
            
            #  Get MetaInfo from XML File
            self.xmlDict = octF.getXMLAttributes(self.xmlContent)
          
            self.dBmin = int(self.treeView.getValue(column='dB min'))
            self.dBmax = int(self.treeView.getValue(column='dB max'))

            # Insert a Scale to select current slice
            self.scale = ttk.Scale(self.frame,
                                   from_= 0, 
                                   to = self.xmlDict['dimY'], 
                                   orient = 'horizontal')
            self.scale.set(round(self.xmlDict['dimY']/2))
            
            # if oct file is in processed format, load the entire stack into memmory
            # to avoid loading it every time the user wants to display another slice
            if  self.treeView.getValue(column='Data Type') == 'Processed':
                self.rawImage = octF.createImageFromRaw(xmlDict = self.xmlDict,
                                                        archive = self.archive, 
                                                        dBmin = int(self.treeView.getValue(column='dB min')), 
                                                        dBmax = int(self.treeView.getValue(column='dB max')), 
                                                        selDataType = self.treeView.getValue(column='Data Type'), 
                                                        averaging = self.globalSettingsFrame.averagingMenu.get(), 
                                                        spectral = int(self.scale.get()-1),
                                                        prefRaw = 'doesnt matter', #self.globalSettingsFrame.getPrefRawState()[0]
                                                        resizeState = self.globalSettingsFrame.getResizeState(),
                                                        tukeySize = float(self.globalSettingsFrame.getTukeyWinSize()),
                                                        advancedFilter = self.globalSettingsFrame.getAdvancedFilter(),
                                                        dispersion = self.customSettingsFrame.getDispersion())
            else:
                 self.rawImage = 0   
            
            self.scale.bind("<ButtonRelease-1>", 
                            lambda event, scalePosition=int(self.scale.get()-1): [self.scale.focus_set(), 
                                                                                  self.showImage(scalePosition, self.rawImage)])
            
            self.scale.grid(row=3, column = 0, sticky=tk.E + tk.W + tk.N + tk.S)
            self.scale.focus_set()
            
            self.scale.bind("<Left>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Right>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Up>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Down>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scaleToolTip = 'Move the slider to display a different slice. '
            Tooltip(self.scale, text=self.scaleToolTip , wraplength=200)
            
            self.showImage(int(self.scale.get()-1), self.rawImage)

    
    def showImage(self, scaleState: int, rawImage):
        '''
        Displays the selected OCT File in a Canvas. Everytime one of the sliders
        of the dB value is moved the image is computed again.

        Parameters
        ----------
        scaleState : int
            Current position of scale, not used since we handle events different.

        Returns
        -------
        Image in Canvas.

        '''
        
        if  self.treeView.getValue(column='Data Type') == 'Processed':
            # this is pretty slow, needs to be improved
            self.scaleValue.set(str(int(self.scale.get())))
            self.canvas.delete("all")

            self.finImg = rawImage
            self.imgShape0 = self.finImg.shape[0]
            self.imgShape1 = self.finImg.shape[1]
            
            if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
                self.finImg = octF.insertScale(img = Image.fromarray(self.finImg[:,:,int(self.scale.get()-1)]), 
                                               scaleSize = int(self.globalSettingsFrame.scaleEntry.get()),
                                               xmlDict = self.xmlDict,
                                               fontSize = int(self.globalSettingsFrame.scaleTextSizeEntry.get()))
            else:
                self.finImg =Image.fromarray(self.finImg[:,:,int(self.scale.get()-1)])
                    
                
            self.finImg = self.finImg.resize((int(self.canvas.winfo_height() * self.finImg.size[0] / self.finImg.size[1]), 
                                             int(self.canvas.winfo_height())), Image.LANCZOS)            

            self.finImg = ImageTk.PhotoImage(self.finImg)            
            self.canvas.create_image(int(self.canvas.winfo_width()/2)-round(int(self.finImg.width())/2),0, image = self.finImg, anchor='nw')
            
        else:
            self.scaleValue.set(str(int(self.scale.get())))
            self.canvas.delete("all")
            self.finImg = octF.createImageFromRaw(xmlDict = self.xmlDict, 
                                                  archive = self.archive, 
                                                  dBmin = int(self.treeView.getValue(column='dB min')), 
                                                  dBmax = int(self.treeView.getValue(column='dB max')), 
                                                  selDataType = self.treeView.getValue(column='Data Type'), 
                                                  averaging = self.globalSettingsFrame.averagingMenu.get(), 
                                                  spectral = int(self.scale.get()-1),
                                                  prefRaw = 'doesnt matter', #self.globalSettingsFrame.getPrefRawState()[0]
                                                  resizeState = self.globalSettingsFrame.getResizeState(),
                                                  tukeySize = float(self.globalSettingsFrame.getTukeyWinSize()),
                                                  advancedFilter = self.globalSettingsFrame.getAdvancedFilter(),
                                                  dispersion = self.customSettingsFrame.getDispersion())
            
            if self.globalSettingsFrame.ScaleBox.state() == ('selected',):  
                self.finImg = octF.insertScale(img = Image.fromarray(self.finImg), 
                                               scaleSize = int(self.globalSettingsFrame.scaleEntry.get()),
                                               xmlDict = self.xmlDict,
                                               fontSize = int(self.globalSettingsFrame.scaleTextSizeEntry.get()))
            else:
                self.finImg = Image.fromarray(self.finImg)

            self.finImg = self.finImg.resize((int(self.canvas.winfo_height() * self.finImg.size[0] / self.finImg.size[1]), 
                                              int(self.canvas.winfo_height())), Image.LANCZOS)            
            
            self.finImg = ImageTk.PhotoImage(self.finImg)
            
            self.canvas.create_image(int(self.canvas.winfo_width()/2)-round(int(self.finImg.width())/2), 
                                     0, 
                                     image = self.finImg, 
                                     anchor='nw')