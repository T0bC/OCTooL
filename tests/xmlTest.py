# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 20:51:58 2020

@author: TMPC
"""

import octFunctions as octF
from pathlib import Path
import numpy as np
from matplotlib import pylab as plt
from PIL import Image
#from scipy.misc import imsave
from tifffile import imsave
import scipy.io as sio
from scipy import signal as ssig
from datetime import datetime
import open3d as o3d

#### load an '.oct' file and display it ####


file =  Path('C:/Users/meissnerto/Desktop/Julia_Oberflächen/03_Original_Data/CD5_T0_cavitron.oct')

for file in Path('C:/Users/meissnerto/Desktop/Julia_Oberflächen/03_Original_Data/').glob('*.oct'):
    print(file.stem)
    
    archive = archive = octF.unzipOCTData(Path(file))
    xmlContent = octF.readXMLContent(archive, 'Header.xml', 'xml')
    xmlDict = octF.getXMLAttributes(xmlContent)
    
    #surface3d = np.empty(shape=(int(xmlDict['dimX'] * xmlDict['imgResizeFactor']), 
    #                            xmlDict['dimZ'], 
    #                            xmlDict['dimY']))
    
    
    
    if xmlDict['dataType'] != 'Processed':
        surface2d = np.empty(shape=(int(xmlDict['dimX'] * xmlDict['imgResizeFactor']), xmlDict['dimY']))
        for Bscan in range(xmlDict['dimY']):
            print(Bscan)
            img = octF.createImageFromRaw(xmlDict = xmlDict,
                                          archive = archive, 
                                          dBmin = 20, 
                                          dBmax = 80, 
                                          selDataType =  xmlDict['dataType'], 
                                          averaging = 'none', 
                                          spectral = Bscan,
                                          prefRaw = 'selected',
                                          resizeState = 'selected',
                                          tukeySize = 0.5,
                                          advancedFilter = '!selected',
                                          dispersion = 'Quadratic')
            
            medImg = ssig.medfilt2d(img, kernel_size=9)
            for Ascan in range(np.shape(medImg)[1]):
                deri = np.argmax(np.gradient(medImg[:,Ascan]))
                #surface3d[Ascan,deri,Bscan] = 255
                surface2d[Ascan,Bscan] = (deri * xmlDict['pixSizeZ']) / 1000
                
    else:
        img = octF.createImageFromRaw(xmlDict = xmlDict,
                                      archive = archive, 
                                      dBmin = 20, 
                                      dBmax = 80, 
                                      selDataType =  xmlDict['dataType'], 
                                      averaging = 'none', 
                                      spectral = Bscan,
                                      prefRaw = 'Processed',
                                      resizeState = 'selected',
                                      tukeySize = 0.5,
                                      advancedFilter = '!selected',
                                      dispersion = 'Quadratic')
        surface2d = np.empty(shape=(np.shape(img)[1], xmlDict['dimY']))
        for Bscan in range(xmlDict['dimY']):
            medImg = ssig.medfilt2d(img[:,:,Bscan], kernel_size=9)
            for Ascan in range(np.shape(medImg)[1]):
                deri = np.argmax(np.gradient(medImg[:,Ascan]))
                #surface3d[Ascan,deri,Bscan] = 255
                surface2d[Ascan,Bscan] = (deri * xmlDict['pixSizeZ']) / 1000

    np.savetxt(Path('C:/Users/meissnerto/Desktop/Julia_Oberflächen/04_TXT_Surface_From_Tobias', (str(file.stem) + '_surface' + '.txt')), surface2d, fmt='%1.6g')
            

np.shape(img)[1]

#### get an A-Scan and plot it ####
medImg = ssig.medfilt2d(img, kernel_size=9)

# iterate over whole image
surface = np.empty(np.shape(medImg))

for Ascan in range(np.shape(medImg)[1]):
    line = medImg[:,Ascan]
    deri = np.argmax(np.gradient(line))
    surface[deri,Ascan] = 255

plt.imshow(surface, cmap=plt.cm.gray)

Ascan = medImg[:,750]
plt.plot(Ascan)

deri = np.gradient(Ascan)
np.argmax(deri)
plt.plot(deri)



####################

#### load an '.oct' file and display it ####

file = Path('G:/OCT/t_3 (12 M)/P10_Fiedler, Ingrid/P10/22/P10_22.oct')
archive = archive = octF.unzipOCTData(Path(file))
xmlContent = octF.readXMLContent(archive, 'Header.xml', 'xml')
xmlDict = octF.getXMLAttributes(xmlContent)

imageSlice = 109

for Bscan in range(xmlDict['dimY']):
    img = octF.createImageFromRaw(xmlDict = xmlDict,
                                  archive = archive, 
                                  dBmin = 20, 
                                  dBmax = 80, 
                                  selDataType = 'RawSpectraAndProcessedIntensity', 
                                  averaging = 'none', 
                                  spectral = Bscan,
                                  prefRaw = 'doesnt matter',
                                  resizeState = 'selected',
                                  tukeySize = 0.5,
                                  advancedFilter = '!selected',
                                  dispersion = 'Quadratic')

# original image
plt.imshow(img, cmap=plt.cm.gray)

#### get an A-Scan and plot it ####
medImg = ssig.medfilt2d(img, kernel_size=9)
plt.imshow(medImg) #, cmap=plt.cm.gray

# iterate over whole image
surface = np.empty(np.shape(medImg))

for Ascan in range(np.shape(medImg)[1]):
    line = medImg[:,Ascan]
    deri = np.argmax(np.gradient(line))
    surface[deri,Ascan] = 255

plt.imshow(surface)

Ascan = medImg[:,750]
plt.plot(Ascan)

deri = np.gradient(Ascan)
np.argmax(deri)
plt.plot(deri)



####################
#C:\Users\meissnerto\Desktop\OCTExport\01_Data\A1_E_48_REM\A1_IPS e.maxCAD_48_REM_o\A1_IPS e.maxCAD_48_REM_o

#%% Load File
#file = Path("C:/Users/TMPC/Desktop/OCT-Export_2/01_Data/A1_IPS e.maxCAD_48_REM_o/A1_IPS e.maxCAD_48_REM_o" / Path("A1_IPS e.maxCAD_48_REM_o_0001_Mode3D.oct"))
#file = Path("C:/Users/meissnerto/Desktop/OCTExport/01_Data/A1_E_48_REM/A1_IPS e.maxCAD_48_REM_o/A1_IPS e.maxCAD_48_REM_o" / Path("A1_IPS e.maxCAD_48_REM_o_0001_Mode3D.oct"))

file = Path("C:/Users/meissnerto/Desktop/OCTExport/01_Data/av_test_5" / Path("av_test_5_0002_Mode3D.oct"))

file = Path("C:/Users/meissnerto/Desktop/OCT_TestFiles/01_1500nm_proc" / Path("01_1500nm_proc_0001_Mode3D.oct"))
file = Path("D:/OCT_TestFiles/xx" / Path("T4.2_0001_Mode3D.oct"))

#C:\Users\meissnerto\Desktop\OCTExport\01_Data\av_test_5

archive = octF.unzipOCTData(Path(file))
xmlContent = octF.readXMLContent(archive, 'Header.xml', 'xml')
xmlDict = octF.getXMLAttributes(xmlContent)
spectralDataRaw = archive.read('data/Spectral' + str(50) + '.data')


img = octF.createImageFromRaw(xmlDict = xmlDict,
                              archive = archive, 
                              dBmin = 20, 
                              dBmax = 80, 
                              selDataType = 'Processed', 
                              averaging = 'none', 
                              spectral = 20,
                              prefRaw = 'doesnt matter',
                              resizeState = 'selected',
                              tukeySize = 0.5,
                              advancedFilter = '!selected',
                              dispersion = 'Quadratic')

finImg = Image.fromarray((img*1).astype(np.uint8))

np.amin(img)

exif = finImg.getexif()

exif[36864] = '0230'
exif[37510] = "sadas"
exif[41987] = '7'
exif[36867] = 'dd'

dpi = (round(np.shape(img)[1] / (xmlDict['imgSizemmX'] / 100)), 
       round(np.shape(img)[0] / (xmlDict['imgSizemmZ'] / 100)))


img.save(Path("D:/OCT_TestFiles/xx/test" / Path('test2.tif')),
            dpi = (round(np.shape(img)[1] / (xmlDict['imgSizemmX'] / 25.4)), 
                   round(np.shape(img)[1] / (xmlDict['imgSizemmZ'] / 25.4)))
            )

Image

im = Image.open(Path("C:/Users/meissnerto/Desktop/OCT_TestFiles/02_1500nm_raw" / Path('TestExp') / Path('test2.tif')))

XPComment = 0x9C9C
XPKeywords = 0x9C9E

exdat = im.getexif()

exdat[XPComment] = 'tasdasd'.encode('utf16')
exdat[XPKeywords] = 'asjjjj'.encode('utf16')
                                    
im.save(Path("C:/Users/meissnerto/Desktop/OCT_TestFiles/02_1500nm_raw" / Path('TestExp') / Path('test3.jpg')),
           exif = exdat)                                    



exdat = im.getexif()

im.info.keys()

type(exdat)
dict(exdat)

finImg = img[20]

fig = plt.figure(frameon=False, clear=True)
ax = plt.Axes(fig, [0., 0., 1., 1.])
ax.set_axis_off()
fig.add_axes(ax)
plt.imshow(finImg, cmap=plt.cm.gray)



#####################

#%% create image
finImg = octF.createImageFromRaw(xmlDict=xmlDict, 
                                 archive=archive, 
                                 dBmin=20, 
                                 dBmax=90, 
                                 selDataType='RawSpectra', 
                                 averaging='coherent', 
                                 spectral=50,
                                 prefRaw=True,
                                 tukeySize = 0.9,
                                 resizeState='selected',
                                 advancedFilter='!selected',
                                 dispersion=test)

finImg = Image.fromarray(finImg)

print(finImg.info)

finImg.save('C:/Users/meissnerto/Desktop/OCTExport/test3.png', format='png')
finImg.save('C:/Users/meissnerto/Desktop/OCTExport/tes42.tiff', format='png', dpi = (round(np.shape(finImg)[1] / xmlDict['imgSizemmX']), round(np.shape(finImg)[1] / xmlDict['imgSizemmX'])))

#%% Save Image / Plot Image
finImg = np.uint8(finImg[:,:,0])
imsave('test01.tif', finImg)

Image.fromarray(finImg).save('diffDP.tiff')

plt.imsave('test02.tiff',
           arr=finImg,
           cmap=plt.cm.gray)

imageInit = np.uint8(imageInit)
imsave('test_coh2_med_filter.tif', imageInit)

#  Create image without white space
fig = plt.figure(frameon=False, clear=True)
ax = plt.Axes(fig, [0., 0., 1., 1.])
ax.set_axis_off()
fig.add_axes(ax)
plt.imshow(finImg, cmap=plt.cm.gray)

plt.imshow(imageInit, cmap=plt.cm.gray)





