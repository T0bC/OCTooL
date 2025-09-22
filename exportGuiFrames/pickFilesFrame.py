#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
from toolTip import Tooltip
from tkinter import filedialog
from pathlib import Path
import os
import glob
from fnmatch import fnmatch
import octFunctions as octF
from concurrent import futures


class pickFilesPanel:
    def __init__(self, root, frame, treeView):
        self.root = root
        self.frame = frame
        self.treeView = treeView

        # Add buttons and instructions here

        self.pickFolderBtn = ttk.Button(self.frame, text='Select Folder', width=14,
                                       command=lambda: self.globalPickerThread(1))
        self.pickFolderBtn.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.pickFolderToolTip = 'Choose a folder whichs contains at least one OCT file. ' \
            'All OCT Files inside this folder and subfolders are detected and added to the queue. \n\n' \
            'If you supply a plain text file within a OCT-File directory [*.txt] with information about export range ' \
            'and equidistant slices, those parameters are imported. \n\n' \
            'Format example: \n 33-444 \n 25'
        Tooltip(self.pickFolderBtn, text=self.pickFolderToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.pickFileBtn = ttk.Button(self.frame, text='Select File', width=14,
                                       command=lambda: self.globalPickerThread(0))
        self.pickFileBtn.grid(row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.pickFileToolTip = 'Choose a single OCT file.'
        Tooltip(self.pickFileBtn, text=self.pickFileToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid( row=0, column=3, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.deleteEntryBtn = ttk.Button(self.frame, text='Delete Entry(s)', width=14,
                                       command=self.treeView.deleteEntry)
        self.deleteEntryBtn.grid(row=0, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.deleteFileToolTip = 'Delete one or more selected items in the queue.'
        Tooltip(self.deleteEntryBtn, text=self.deleteFileToolTip , wraplength=200)
    
        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid( row=0, column=5, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        #%% folder/file Picker

    def globalPickerThread(self, var):
        '''
        To prevent GUII from freezing during a loop or time consuming function
        call, we need to set up threads.
        In this thread we call the mainRoutines.

        Returns
        -------
        None.

        '''
        #print('starting')
        self.running = 0
        # create a thread to keep UI responsive
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.globalPicker(var))


    def globalPicker(self, isFolder: bool):
        '''
        Uses file open or ask directory dialog to list oct file(s) in the
        directory.

        Parameters
        ----------
        isFolder : bool
            1 if one chooses a folder
            0 if one chooses a file.

        Returns
        -------
        None

        '''
        
        global dir
        if isFolder == 1:
            self.folderPath = Path(filedialog.askdirectory(initialdir=dir,
                                                           title='Select the Folder Containing Your OCT Files!'))
                       
            tmpPathList = []
            for path, subdirs, files in os.walk(Path(self.folderPath)):
                for file in files:
                    if fnmatch(file, '*.oct'):
                        tmpPathList += [os.path.join(path, file)]


                        
            # create a new list containing name, first, last, status and path
            self.tmpFileList = []
            
            # Create a Progressbar
            self.popup = tk.Toplevel(self.root)
            tk.Label(self.popup, text="Searching for OCT files in selected folder. This might take a while.").grid(row=0,column=0)
            self.progress = 0
            self.progress_var = tk.DoubleVar()
            self.progressBar = ttk.Progressbar(self.popup, 
                                               variable=self.progress_var, 
                                               maximum=len(tmpPathList), 
                                               orient='horizontal', 
                                               mode='determinate', 
                                               length=280)
            self.progressBar.grid(row=1, column=0)
            self.cancelButton = ttk.Button(self.popup, text='Cancel!', command=self.breakAll)
            self.cancelButton.grid(column=0, row=2, padx=10, pady=10, sticky=tk.E)
            self.popup.pack_slaves()
                       
            for j, (path) in enumerate(tmpPathList, start=0):
                firstS, lastS, summS = self.checkForMetaDataFile(Path(tmpPathList[j]))
                if octF.getXMLvalue(Path(tmpPathList[j]), 'Serialnumber') == 'M00427924':
                    self.dispCoeff = '-100'
                else:
                    self.dispCoeff = '20'
    
                self.tmpFileList += [[os.path.splitext(os.path.basename(Path(tmpPathList[j])))[0],   # file name
                                      firstS,                                                        # first slice to export
                                      lastS,                                                         # last slice to export
                                      '20' if octF.getXMLvalue(Path(tmpPathList[j]), 
                                                               'dataType') == 'Processed' else '30', # min dB value
                                      '80' if octF.getXMLvalue(Path(tmpPathList[j]), 
                                                               'dataType') == 'Processed' else '100',# max dB value
                                      summS,                                                         # number of Slices to export
                                      self.dispCoeff,                                                # Dispersion Coefficient
                                      octF.getXMLvalue(Path(tmpPathList[j]), 'dataType'),            # Processed or Spectral Data (or both)
                                      'in queue',                                                    # current state
                                      Path(tmpPathList[j])]]                                         # full path to file
                self.popup.update()
                self.progress += 1
                self.progress_var.set(self.progress)
                if self.running == 1:
                    self.popup.destroy()
                    break
            self.popup.destroy()

        else:
            self.filePath = Path(filedialog.askopenfilename(initialdir=dir,
                                                              title='Select One OCT File!',
                                                              filetypes=(('All Files', '*.*'),
                                                                         ('OCT Files', '*.oct'))))
            firstS, lastS, summS = self.checkForMetaDataFile(self.filePath)

            if octF.getXMLvalue(self.filePath, 'Serialnumber') == 'M00427924':
                self.dispCoeff = '-100'
            else:
                self.dispCoeff = '20'
            
            # create a list object which contains the filename and other things
            self.tmpFileList = [[os.path.splitext(os.path.basename(Path(self.filePath)))[0],         # file name
                                 firstS,                                                             # first slice to export
                                 lastS,                                                              # last slice to export
                                '20' if octF.getXMLvalue(Path(self.filePath), 
                                                         'dataType') == 'Processed' else '30',       # min dB value
                                '80' if octF.getXMLvalue(Path(self.filePath), 
                                                         'dataType') == 'Processed' else '100',      # max dB value
                                 summS,                                                              # number of Slices to export
                                 self.dispCoeff,                                                     # Dispersion Coefficient  
                                 octF.getXMLvalue(Path(self.filePath), 'dataType'),                  # Processed or Spectral Data (or both)
                                 'in queue',                                                         # current state
                                 Path(self.filePath)]]                                               # full path to file

        self.treeView.setMultipleValues(self.tmpFileList)
        self.root.destroy
        

    #%%
    def getBoundedNumLines(self, k: int, infile)->int:
        '''
        Returns the number of non empty lines in a file.
        min(K, number of lines in infile).
    
        Max running time is proportional to K rather than total file length,
        similar to /usr/bin/head -K.

        Parameters
        ----------
        k : int
            Maximum lines to read from file.
        infile : TYPE
            A file to read.

        Returns
        -------
        i : int
            Number of lines detected.

        '''
        try:
            for i in range(k + 1):
                next(infile)
        except StopIteration:
            pass
        infile.close()
        return i
    
    def metaDataFileError(self, pathToFile, errno: int):
        '''
        Displays an error message.

        Parameters
        ----------
        pathToFile : TYPE
            DESCRIPTION.
        errno : int
            DESCRIPTION.

        Returns
        -------
        Tk message box.

        '''
        if errno == 0:
            tk.messagebox.showwarning(title = str('Metadata file corrupted! ERRNO:' + str(errno)), 
                                      message = 'The txt file for OCT Scan \n\n' +  
                                      pathToFile + 
                                      ' \n\nhas to many lines.'+
                                      ' \nThis file should look like this example:'+
                                      ' \n\n'+
                                      ' First-Last\n' +
                                      ' aequidistant Slices (Optional)\n'+
                                      ' Offset (Optional)'+
                                      ' \n\n'+
                                      ' Fix the file or insert first and last slice manually!')
        if errno == 1:
            tk.messagebox.showwarning(title = str('Metadata file corrupted! ERRNO:' + str(errno)), 
                                      message = 'The Value for the last Slice in the txt file for OCT Scan \n\n' +  
                                      pathToFile + 
                                      ' \n\n is greater then the available OCT B-Scans'+
                                      ' \nThis file should look like this example:'+
                                      ' \n\n'+
                                      ' First-Last\n' +
                                      ' aequidistant Slices (Optional)\n'+
                                      ' Offset (Optional)'+
                                      ' \n\n'+
                                      ' Fix the file or insert first and last slice manually!')
                    
    def checkForMetaDataFile(self, pathToFile)->int:
        '''
        Checks if there is a metadata file with first and last slice to be
        exported. If no file exists or if file has more than 4 lines, the 
        standard values are used.

        Parameters
        ----------
        pathToFile : pathlib Path Object 
            The path to *.oct File.

        Returns
        -------
        int
            returns:
            firstS = first Slice to export 
            lastS = last Slice to export
            summS = sum of images to export
            offsett = corrects image shift from time series

        '''
        # check if there is txt file in the folder containing first and last slice
        # the ammount of aequidistant slices
        # and the offset

        os.chdir(pathToFile.parent)
        #for file in os.listdir(pathToFile.parent):
        txtFileList = glob.glob("*.txt")
        
        if len(txtFileList) > 0:
            if self.getBoundedNumLines(4, open(os.path.join(pathToFile.parent, txtFileList[0]))) == 3: 
                # if the file has 3 lines, get first, last, aequidist & offset
                splitlist = open(os.path.join(Path(pathToFile.parent,  txtFileList[0]))).read().splitlines()
                firstS, lastS = splitlist[0].split(sep='-')
                if not splitlist[1]:
                    # if second line is empty calculate the range of images
                    summS = str(1 + int(lastS) - int(firstS))
                else:
                    # sumS is the value in the second line of the textfile
                    summS = splitlist[1]
                if not splitlist[1]:
                    offset = 0
                else:
                    offset = splitlist[2]
                firstS, lastS = int(firstS) + int(offset), int(lastS) + int(offset)
            elif self.getBoundedNumLines(4, open(os.path.join(pathToFile.parent,  txtFileList[0]))) == 2: 
                # if the file hast 2 lines, get first, last & aequidist
                splitlist = open(os.path.join(Path(pathToFile.parent,  txtFileList[0]))).read().splitlines()
                firstS, lastS = splitlist[0].split(sep='-')
                if not splitlist[1]:
                    # if the 2. line is still empty throw error
                    self.metaDataFileError(pathToFile=str(pathToFile), errno=0)
                else:
                    summS = splitlist[1]
                offset = 0
            elif self.getBoundedNumLines(4, open(os.path.join(pathToFile.parent,  txtFileList[0]))) == 1:
                firstS, lastS = open(os.path.join(Path(pathToFile.parent,  txtFileList[0]))).read().split(sep = '-')
                summS = str(1 + int(lastS) - int(firstS))
            else:
                # error output here with info text here
                self.metaDataFileError(pathToFile=str(pathToFile))
    
                firstS = '1'
                lastS = octF.getXMLvalue(pathToFile, 'dimY')
                summS = octF.getXMLvalue(pathToFile, 'dimY')
        else:
            firstS = '1'
            lastS = octF.getXMLvalue(pathToFile, 'dimY')
            summS = octF.getXMLvalue(pathToFile, 'dimY')
        
        if int(lastS) > int(octF.getXMLvalue(pathToFile, 'dimY')):
            self.metaDataFileError(pathToFile=str(pathToFile), errno=1)
   
        return firstS, lastS, summS
    
    def breakAll(self):
        '''
        Var for MainRoutine to break the export cycle.

        Returns
        -------
        None.

        '''
        self.running = 1
        self.popup.destroy()