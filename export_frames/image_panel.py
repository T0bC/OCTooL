#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils import oct_functions as octF
from scipy import ndimage
from PIL import Image, ImageTk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors

class imagePanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("image")
        self.treeView = self.context.get_panel("tree")
        self.globalSettingsFrame = self.context.get_panel("global_settings")
        self.customSettingsFrame = self.context.get_panel("custom_settings")
        self.pickFrame = self.context.get_frame("pick_files")


        # Image Frame
        # displayed in pickFilesFrame
        self.showBtn = ttk.Button(self.pickFrame,
                                  text='Show',
                                  width=14,
                                  command = self.dispImageInCanvas,
                                  bootstyle = "success")
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
        self.scale = ttk.Scale(self.frame, from_=0, to=2, orient='horizontal',
                               bootstyle="warning")
        self.scale.set(1)
        self.scale.grid(row=3, column = 0, sticky=tk.E + tk.W + tk.N + tk.S)

        self.scaleValueLabel = ttk.Label(self.frame, text="text", textvariable=self.scaleValue)
        self.scaleValueLabel.grid(row=3, column = 1, sticky=tk.E)

    def instructionText(self):
        self.canvas.delete("all")

        self.cwidth = self.canvas.winfo_width()
        self.cheight = self.canvas.winfo_height()

        # Draw logo in top-right corner
        try:
            self.ULPhoto = "icons/WBM_UL_RGB_digital_Path.png"
            self.ULImage = Image.open(self.ULPhoto)
            self.ULImage = self.ULImage.resize((217,76), Image.Resampling.LANCZOS)
            self.ULImage = ImageTk.PhotoImage(self.ULImage)
            self.canvas.create_image(self.cwidth - 217 // 2 - 7, 45, image=self.ULImage)
        except Exception as e:
            print(f"Failed to load logo: {e}")

        header_y = 10
        text_y_start = 5
        line_spacing = 20
        max_line_width = 80  # Adjust based on canvas width

        instructions = [
            "- Select a folder with OCT files (subfolders searched automatically)",
            "- Add single files via 'Select File'",
            "- Select dataset in 'Queue' and click 'Show'",
            "- 'Global Settings' apply to all datasets",

            "",
            "Custom Settings",
            "- 'Exp. Range': First and last slice to export",
            "- 'Equidist. Slices': Number of slices to export",
            "- 'Dyn. Range [dB]': Adjust image contrast",
            "- 'Dispersion Correction': Enhance edge sharpness",

            "",
            "Sidecar Metadata File ('same name as oct file'.txt)",
            "- Format: <VIEW>:<START-END>:<numberOfAequidistSlices>:<refractiveIndex>",
            "  Example: ",
            "           XZ:20-80:20:1.5",
            "           YZ:15-90:10:1",
            "           XY:1-50:25",
            "- If file is missing or malformed, defaults are used."
        ]

        y_offset = text_y_start
        for line in instructions:
            if line == "":
                y_offset += line_spacing // 2
                continue
            self.canvas.create_text(10, y_offset, fill="#D0D0D0", font="Sans 11",
                                    text=line, anchor=tk.NW, tags="Text")
            y_offset += line_spacing


    @handle_errors("imagePanel")
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
    @handle_errors("imagePanel")
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
                                   orient = 'horizontal',
                                   bootstyle="warning")
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
                                                        #resizeState = self.globalSettingsFrame.getResizeState(),
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

    @handle_errors("imagePanel")
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

        if self.treeView.getValue(column='Data Type') == 'Processed':
            self.scaleValue.set(str(int(self.scale.get())))
            self.canvas.delete("all")

            # Extract the selected slice
            img2D = self.rawImage[int(self.scale.get() - 1), :, :]

            # Apply resizing and refractive index correction
            imgSliceDir = self.treeView.getValue(column='Img. Slice Dir.')
            if imgSliceDir == 'XZ':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    img2D = ndimage.zoom(img2D, zoom=(1, self.xmlDict['imgResizeFactorX']), order=0)
                if self.treeView.getValue(column='Refr. Ind.') != 1:
                    img2D = ndimage.zoom(img2D, zoom=(float(self.treeView.getValue(column='Refr. Ind.')), 1), order=0)

            elif imgSliceDir == 'YZ':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    img2D = ndimage.zoom(img2D, zoom=(1, self.xmlDict['imgResizeFactorY']), order=0)
                if self.treeView.getValue(column='Refr. Ind.') != 1:
                    img2D = ndimage.zoom(img2D, zoom=(float(self.treeView.getValue(column='Refr. Ind.')), 1), order=0)

            elif imgSliceDir == 'XY':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    img2D = ndimage.zoom(img2D,
                                         zoom=(self.xmlDict['imgResizeFactorY'], self.xmlDict['imgResizeFactorX']),
                                         order=0)

            # Add scale bar if selected
            if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
                self.finImg = octF.insertScale(
                    img=Image.fromarray(img2D),
                    scaleSize=int(self.globalSettingsFrame.scaleEntry.get()),
                    xmlDict=self.xmlDict,
                    fontSize=int(self.globalSettingsFrame.scaleTextSizeEntry.get()),
                    imgSliceDir=imgSliceDir
                )
            else:
                self.finImg = Image.fromarray(img2D)

            # Resize to fit canvas
            self.finImg = self.finImg.resize(
                (int(self.canvas.winfo_height() * self.finImg.size[0] / self.finImg.size[1]),
                 int(self.canvas.winfo_height())),
                Image.LANCZOS
            )

            self.finImg = ImageTk.PhotoImage(self.finImg)
            self.canvas.create_image(int(self.canvas.winfo_width() / 2) - round(int(self.finImg.width()) / 2),
                                     0,
                                     image=self.finImg,
                                     anchor='nw')


        else:
            self.imgSliceDir = self.treeView.getValue(column = 'Img. Slice Dir.')
            self.scaleValue.set(str(int(self.scale.get())))
            self.canvas.delete("all")
            self.finImg = octF.createImageFromRaw(xmlDict = self.xmlDict,
                                                  archive = self.archive,
                                                  dBmin = int(self.treeView.getValue(column='dB min')),
                                                  dBmax = int(self.treeView.getValue(column='dB max')),
                                                  selDataType = self.treeView.getValue(column='Data Type'),
                                                  averaging = self.globalSettingsFrame.averagingMenu.get(),
                                                  spectral = int(self.scale.get()-1),
                                                  prefRaw = 'doesnt matter',
                                                  tukeySize = float(self.globalSettingsFrame.getTukeyWinSize()),
                                                  advancedFilter = self.globalSettingsFrame.getAdvancedFilter(),
                                                  dispersion = self.customSettingsFrame.getDispersion())

            # Extract 2D image from stack based on slice direction
            if self.imgSliceDir == 'XZ':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    self.finImg = ndimage.zoom(self.finImg, zoom=(1, self.xmlDict['imgResizeFactorX']), order=0)
                # refractive index
                if self.treeView.getValue(column = 'Refr. Ind.') != 1:
                    self.finImg = ndimage.zoom(self.finImg, zoom=(float(self.treeView.getValue(column = 'Refr. Ind.')),1), order=0)

            elif self.imgSliceDir == 'YZ':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    self.finImg = ndimage.zoom(self.finImg, zoom=(1, self.xmlDict['imgResizeFactorY']), order=0)
                # refractive index
                if self.treeView.getValue(column = 'Refr. Ind.') != 1:
                        self.finImg = ndimage.zoom(self.finImg, zoom=(float(self.treeView.getValue(column = 'Refr. Ind.')),1), order=0)

            elif self.imgSliceDir == 'XY':
                if self.globalSettingsFrame.getResizeState() == 'selected':
                    self.finImg = ndimage.zoom(self.finImg,
                                            zoom=(self.xmlDict['imgResizeFactorY'], self.xmlDict['imgResizeFactorX']),
                                            order=0)

            # Add scale bar if selected
            if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
                self.finImg = octF.insertScale(
                    img=Image.fromarray(self.finImg),
                    scaleSize=int(self.globalSettingsFrame.scaleEntry.get()),
                    xmlDict=self.xmlDict,
                    fontSize=int(self.globalSettingsFrame.scaleTextSizeEntry.get()),
                    imgSliceDir=self.imgSliceDir
                )
            else:
                self.finImg = Image.fromarray(self.finImg)

            self.finImg = self.finImg.resize((int(self.canvas.winfo_height() * self.finImg.size[0] / self.finImg.size[1]),
                                              int(self.canvas.winfo_height())), Image.LANCZOS)

            self.finImg = ImageTk.PhotoImage(self.finImg)

            self.canvas.create_image(int(self.canvas.winfo_width()/2)-round(int(self.finImg.width())/2),
                                     0,
                                     image = self.finImg,
                                     anchor='nw')

