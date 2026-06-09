#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from app.logic.shared import oct_functions as octF
from scipy import ndimage
from PIL import Image, ImageTk
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors
from app.view.shared.instruction_renderer import InstructionRenderer
from app.logic.rexview.image_service import ImageService
from app.logic.rexview.models import ImageDisplayConfig
from app.view.rexview.gui_adapters import image_display_config_from_gui_state

class imagePanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("rex_image")
        self.treeView = self.context.get_panel("tree")
        self.globalSettingsFrame = self.context.get_panel("global_settings")
        self.customSettingsFrame = self.context.get_panel("custom_settings")
        
        # Initialize ImageService for pure logic operations
        self.image_service = ImageService()
        self.rawImage = None

        # Configure frame grid 
        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(3, weight=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=0)

        #self.canvas = ResizingCanvas(self.frame, width=1024, height=342, highlightthickness=0, bg='red')
        self.canvas = tk.Canvas(self.frame, width=1024, height=342, highlightthickness=0, bg='#505050')
        self.canvas.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.canvas.bind("<Configure>", self.onResize)

        # Initialize instruction renderer for this canvas
        from app.logic.shared.paths import resource_path
        self.instruction_renderer = InstructionRenderer(self.canvas)
        self.instruction_renderer.set_logo(resource_path("icons/WBM_UL_RGB_digital_Path.png"))
        
        # Show initial instructions
        self.instructionText()

        self.scaleValue = tk.StringVar()
        # Insert a Scale to select current slice
        self.scale = ttk.Scale(self.frame, from_=0, to=2, orient='horizontal',
                               bootstyle="warning")
        self.scale.set(1)
        self.scale.grid(row=3, column=0, columnspan=2, sticky="ew")

        self.scaleValueLabel = ttk.Label(self.frame, text="text", textvariable=self.scaleValue)
        self.scaleValueLabel.grid(row=3, column=2, sticky=tk.E)
        Tooltip(self.scale, text='Move the slider to display a different slice.', wraplength=200)

    def instructionText(self):
        """
        Display instruction text and logo when no image is loaded.
        Shows comprehensive getting started guide for RexView module.
        """
        # Render comprehensive guide from JSON data
        self.instruction_renderer.render('rexview_getting_started')


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

    def _collect_display_config(self) -> ImageDisplayConfig:
        """
        Gather current UI state into ImageDisplayConfig object.
        
        This method collects all display-related settings from the UI widgets
        and returns a configuration object for the ImageService.
        """
        return image_display_config_from_gui_state(
            slice_index=max(0, int(self.scale.get() - 1)),
            slice_direction=self.treeView.getValue(column='Img. Slice Dir.'),
            db_min=self.treeView.getValue(column='dB min'),
            db_max=self.treeView.getValue(column='dB max'),
            resize_state=self.globalSettingsFrame.getResizeState(),
            refractive_index=self.treeView.getValue(column='Refr. Ind.'),
            scale_state=self.globalSettingsFrame.ScaleBox.state(),
            scale_length=self.globalSettingsFrame.scaleEntry.get(),
            scale_font_size=self.globalSettingsFrame.scaleTextSizeEntry.get(),
            data_type=self.treeView.getValue(column='Data Type'),
            averaging=self.globalSettingsFrame.averagingMenu.get(),
            tukey_size=self.globalSettingsFrame.getTukeyWinSize(),
            advanced_filter_state=self.globalSettingsFrame.getAdvancedFilter(),
            dispersion=self.customSettingsFrame.getDispersion(),
            canvas_width=self.canvas.winfo_width(),
            canvas_height=self.canvas.winfo_height(),
        )

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
            file_path = self.treeView.getValue(column='Path')

            # Use ImageService to load OCT file and extract metadata
            self.image_service.load_oct_file(file_path)

            self.treeView.setValue('Status', 'displayed')

            # Reconfigure the existing slice scale for this stack
            self.scale.configure(from_=0, to=self.image_service.total_slices)
            self.scale.set(self.image_service.get_middle_slice_index())
            # Clear any bindings from a previous load before re-binding below
            for sequence in ("<ButtonRelease-1>", "<Left>", "<Right>", "<Up>", "<Down>"):
                self.scale.unbind(sequence)

            # if oct file is in processed format, load the entire stack into memory
            # to avoid loading it every time the user wants to display another slice
            if self.treeView.getValue(column='Data Type') == 'Processed':
                config = self._collect_display_config()
                self.rawImage = self.image_service.load_processed_stack(config)
            else:
                self.rawImage = None

            self.scale.bind("<ButtonRelease-1>",
                            lambda event, scalePosition=int(self.scale.get()-1): [self.scale.focus_set(),
                                                                                  self.showImage(scalePosition, self.rawImage)])

            self.scale.grid(row=3, column=0, columnspan=2, sticky=tk.E + tk.W + tk.N + tk.S)
            self.scale.focus_set()

            self.scale.bind("<Left>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Right>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Up>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])
            self.scale.bind("<Down>", lambda e: [self.scale.set(int(self.scale.get())), self.showImage(int(self.scale.get()), self.rawImage)])

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
        # Update scale value label
        self.scaleValue.set(str(int(self.scale.get())))
        self.canvas.delete("all")
        
        # Collect current display configuration from UI
        config = self._collect_display_config()
        
        # Use ImageService to process the preview image
        if config.data_type == 'Processed':
            # Use pre-loaded stack for processed data
            pil_img, x_position = self.image_service.process_preview_image(
                config, image_stack=self.rawImage
            )
        else:
            # For raw data, service creates slice on demand
            pil_img, x_position = self.image_service.process_preview_image(config)
        
        # Convert to PhotoImage and display on canvas (UI-only operations)
        self.finImg = ImageTk.PhotoImage(pil_img)
        self.canvas.create_image(x_position, 0, image=self.finImg, anchor='nw')

