#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk


class treeViewPanel:
    def __init__(self, root, frame):
        self.root = root
        self.frame = frame

        # canvas Frame and its contens
        self.cols = ('Nr.', 'Name', 'First', 'Last', 'dB min', 'dB max', 'NumSlices','Disp. Coeff', 'Data Type', 'Status', 'Path')
        self.treeView = ttk.Treeview(self.frame, columns=self.cols, show='headings')
        self.treeView.grid(row=1, column = 1, sticky = tk.E + tk.W + tk.N + tk.S)
        self.treeView.columnconfigure(1, weight = 1)
        
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.treeView.yview)
        self.scrollbar.grid(row=0, column = 3, sticky = 'ns') 
        self.treeView.configure(yscrollcommand=self.scrollbar.set)

        
        
        for col in self.cols:
            self.treeView.heading(col, text = col)
        
        # define col sizes
        self.treeView.grid(row=0, column = 1, columnspan = 2, rowspan=2)
        self.treeView.column('Nr.', width = 25) 
        self.treeView.column('Name', width = 200) 
        self.treeView.column('First', width = 50) 
        self.treeView.column('Last', width = 50) 
        self.treeView.column('dB min', width = 50)
        self.treeView.column('dB max', width = 50)
        self.treeView.column('NumSlices', width = 63)
        self.treeView.column('Disp. Coeff', width = 70)
        self.treeView.column('Data Type', width = 70) 
        self.treeView.column('Status', width = 70) 
        self.treeView.column('Path', width = 35)
        #self.treeView.bind('<ButtonRelease-1>', self.selectRow) # what was the purpose here? Delete Button was setup differently
 
        self.treeView.bind('<Double-1>', self.set_cell_value)


       # %% Test for Input
    def set_cell_value(self, event):
        for item in self.treeView.selection():
            item_text = self.treeView.item(item, "values")
            column = self.treeView.identify_column(event.x)
            row = self.treeView.identify_row(event.y)
        cn = int(str(column).replace('#', ''))
        rn = int(str(row).replace('I', ''))
        entryedit = tk.Text(self.frame, width = 10 + (cn - 1) * 16, height = 1)
        entryedit.insert(0.0, self.treeView.set(item, column))
        entryedit.place(x=16 + (cn - 1) * 130, y=6 + rn * 20)

    
        def saveedit():
            self.treeView.set(item, column=column, value=entryedit.get("1.0","end-1c"))
            entryedit.destroy()
            okb.destroy()
    
        okb = ttk.Button(self.frame, text='OK', width=4, command=saveedit)
        okb.place(x=90 + (cn - 1) * 242, y=2 + rn * 20)  
 
        #%% Maybe we can use this someday, this lets you select row and col by mouse
    def selectRow(self, event):
        '''
        Not used: this lets you select row and col by mouse

        Parameters
        ----------
        event : TYPE
            Mouse click event.

        Returns
        -------
        row and column.

        '''
        self.curItem = self.treeView.item(self.treeView.focus())
        self.row = self.treeView.identify_row(event.y)
        self.col = self.treeView.identify_column(event.x)

        
        #%% deleteEntry
        
    def deleteEntry(self):
        '''
        Deletes the current selection from treeView table

        Returns
        -------
        None.

        '''
        self.selectedItemList = self.treeView.selection()
        for item in self.selectedItemList:
            self.treeView.delete(item)
            
        #addSliceToQueu,pass an instance of the treeView Table to the function when calling
    def addSliceToQueue(self, firstEntry: int, lastEntry: int, resetState: bool):
        '''
        Change the parameter for first and fast Slice in the TreeView-Table

        Parameters
        ----------
        firstEntry : int
            Value from user input field.
        lastEntry : int 
            Value from user input field.
        resetStat : bool
            if resize button is used calcculate numOfSlices differently

        Returns
        -------
        None.

        '''
        self.firstEntry = firstEntry
        self.lastEntry = lastEntry
        if resetState == False:
            self.numOfSlices = int(lastEntry) - int(firstEntry)
        else:
            self.numOfSlices = int(lastEntry) - int(firstEntry) + 1
        
        self.treeView.set(self.treeView.focus(), 'First', value=(str(self.firstEntry))) 
        self.treeView.set(self.treeView.focus(), 'Last', value=(str(self.lastEntry)))
        self.treeView.set(self.treeView.focus(), 'NumSlices', value=(str(self.numOfSlices)))
        
    #setdBVal
        
    def setdBVal(self, mdB: int, adB: int):
        '''
        Sets the dBValue according to the sliders.

        Parameters
        ----------
        mdB : int
            Current value (state) of scale.
        adB : int
            Current value (state) of scale.

        Returns
        -------
        None.

        '''
        self.scaleMdB = mdB
        self.scaleAdB = adB
        
        if self.treeView.focus() == '':
            pass
        else:
            self.treeView.set(self.treeView.focus(), 'dB min', value=(str(self.scaleMdB)))
            self.treeView.set(self.treeView.focus(), 'dB max', value=(str(self.scaleAdB))) 
              
    def getChildren(self)->list:
        '''
        Returns a (ID) list of all entry in the Treeview

        Returns: List of ID's'
        -------
        TYPE
            List.

        '''
        return self.treeView.get_children()
    
    def setValue(self, column: str, value: str):
        '''
        Sets value in given row and column in the treeFrame

        Parameters
        ----------
        column : str
            Column name.
        value : str
            Value to be set.

        Returns
        -------
        None.

        '''
        self.treeView.set(self.treeView.focus(), column, value=value)
    
    def getFocus(self)-> int:
        '''
        Returns the current selected Row ID of TreeView

        Returns
        -------
        int
            position of row.

        '''
        return self.treeView.focus()
    
    def getValue(self, column: int)-> str:
        '''
        Returns the value of specified column

        Parameters
        ----------
        column : int
            column number 1st col = 0.

        Returns
        -------
        str: 
            Value in Column as string .

        '''
        return self.treeView.set(self.treeView.focus(), column)
    
    def getValueFromRow(self, item, column: int)-> str:
        '''
        Returns from a given row (Child)

        Parameters
        ----------
        item : TYPE
            DESCRIPTION.
        column : int
            DESCRIPTION.

        Returns
        -------
        str
            DESCRIPTION.

        '''
        return self.treeView.set(item, column)
    
    def setValueFromRow(self, item, column: str, value: str):
        '''
        Sets value in given row and column in the treeFrame

        Parameters
        ----------
        column : str
            Column name.
        value : str
            Value to be set.

        Returns
        -------
        None.

        '''
        self.treeView.set(item, column, value=value)
        
    def setMultipleValues(self, tmpFileList: list):
        '''
        Sets multiple Values from a given list into the treeView table

        Parameters
        ----------
        tmpFileList : list
            A list containing values generated by file/folder Picker.
                : i = increment (int)
                : name = name of file
                : first = first slice to be exportet (standard = 1)
                : last = last slice to be exportet (standard = end)
                : dB = Dezibel values (standard = 20 - 80)
                : status = status of export
                : path = Path to file

        Returns
        -------
        None.

        '''
        for i ,(name, first, last, dBMin, dBMax, NumSlices, DispCoeff, dataType, status, path) in enumerate(tmpFileList, start=1):
            self.treeView.insert('','end', values=(i, name, first, last, dBMin, dBMax, NumSlices, DispCoeff, dataType, status, path)) 
            
    def addequiDistToQueue(self, numSlices: str, allFiles: bool):
        '''
        Add equidistant Slice number to treeView Tablet

        Parameters
        ----------
        numSlices : str
            Number of equidistant slices.
        allFiles : bool
            False = Set only to current selection
            True = Set to all loaded oct files.

        Returns
        -------
        None.

        '''
        if allFiles == False:
            if int(numSlices) > (int(self.getValue(column = 'Last')) - int(self.getValue(column = 'First'))):
                tk.messagebox.showerror(title = ' Value Error 1', 
                                        message = 'The input value for column "NumSlices" [' + 
                                        str(numSlices) + '] is larger then the chosen export range [' 
                                        + str(int(self.getValue(column = 'Last')) - int(self.getValue(column = 'First'))) +
                                        ']!\n\nPlease consider adapting the export range (First & Last) \nor the number of slices!')
            else:
                self.treeView.set(self.treeView.focus(), 'NumSlices', value=numSlices)
            
            
        else:
            for item in enumerate(self.treeView.get_children()):
                self.treeView.set(item[1], 'NumSlices', value=numSlices)
                
    def addToMultipleColsnRows(self, colNames: list, values: list):
        '''
        Add values to multiple columns to all rows. Provide a list of coumn names 
        and in the same order a list of values to add.

        Parameters
        ----------
        colNames : list
            List of column names.
        value : list
            List of values in order.

        '''
        for item in enumerate(self.treeView.get_children()):
            for name in enumerate(colNames):
                self.treeView.set(item[1], str(name[1]), values[name[0]])