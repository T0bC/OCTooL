# -*- coding: utf-8 -*-
"""
Created on Tue Sep 28 15:49:29 2021

@author: meissnerto
"""

import octFunctions as octF
import cv2
from PIL import Image, ImageTk
import matplotlib.pyplot as plt


file = "C:/Users/meissnerto/Desktop/ausrichtung/02_1500nm_raw/02_1500nm_raw_0001_Mode3D.oct"
#file = "C:/Users/meissnerto/Desktop/ausrichtung/05_1300_raw/05_1300_raw_0001_Mode3D.oct"
#file = "C:/Users/meissnerto/Desktop/ausrichtung/xx/T4.2_0001_Mode3D.oct"

archive = octF.unzipOCTData(file)

# Read the XML Data to Buffer use BS for read of XML 
xmlContent = octF.readXMLContent(archive, 'Header.xml', 'xml')

#  Get MetaInfo from XML File
xmlDict = octF.getXMLAttributes(xmlContent)
dattype = xmlDict['xmlDataType']


# if oct file is in processed format, load the entire stack into memmory
# to avoid loading it every time the user wants to display another slice
rawImage = octF.createImageFromRaw(xmlDict = xmlDict, 
                                   archive = archive, 
                                   dBmin = 20, 
                                   dBmax = 80, 
                                   selDataType = dattype, 
                                   averaging = 1, 
                                   spectral = 50,
                                   prefRaw = 'doesnt matter', #globalSettingsFrame.getPrefRawState()[0]
                                   resizeState = True,
                                   tukeySize = 0.9,
                                   advancedFilter = False,
                                   dispersion = str(-50))


#plt.imshow(rawImage)


#finImg = Image.fromarray(rawImage)

#finImg.show()