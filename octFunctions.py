# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 11:07:04 2020

Some functions to help processing OCT Raw Files

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""
import zipfile
from bs4 import BeautifulSoup
import lxml
import numpy as np
import math
from scipy import signal
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
#import cv2

# %% Insert Scale
def insertScale(img, scaleSize, xmlDict, fontSize):
    '''
    

    Parameters
    ----------
    img : pillow image
        A pillow image .
    scaleSize : int
        The length of desired scale in um.
    xmlDict : Dictionary
        An Dictionary filled with information about the raw data.
    fontSize : int
        size of the scale annotation.

    Returns
    -------
    img : pillow image
        A pillow image with scale.

    '''

    x = round(69 * img.size[0] / 100)
    y = round(93 * img.size[1] / 100)
  
    lengthOfLine = int(round(scaleSize / (float(xmlDict['imgSizemmX']) * 1000 / img.size[0])))
    
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("fonts/LSANS.TTF", fontSize)
    draw.text((x, y), str(scaleSize) + ' \u00B5m', (255), font = font)
    draw.line((x, y + -10, x + lengthOfLine, y + -10), fill = 255, width=3)    # x1, y1, x2, y2

    return img

# %% Unzip OCT Files
def unzipOCTData(path):
    """
    Uses zipfile to unzip the data. Read Only.

    Parameters
    ----------
    path : str
        A posix Path to the archive location.

    Returns
    -------
    archive
        A unzipped archive with contents in buffer.

    """
    archive = zipfile.ZipFile(path, 'r') 
    return archive

#%%

def getXMLvalue(path: str, value: str)-> str:
    '''
    Returns the OCT data type as documented in the Header.xml. RawSpectral,
    Processed, Both

    Parameters
    ----------
    path : str
        Path to file.
    value : str
        Name of the value.
    Returns
    -------
    str
        Data type as string.

    '''
    return getXMLAttributes(readXMLContent(unzipOCTData(path), 'Header.xml', 'xml'))[value]


# %% Read XML Content
def readXMLContent(archive, nameOfXMLFile, fileExtension):
    """
    Reads XML Contents into buffer.

    Parameters
    ----------
    archive : bufferedZipArchive
        A archive unzipped with zipfile.
    nameOfXMLFile : TYPE
        Name of the xml File.
    fileExtension : Type
        FIle extension of the xml file

    Returns
    -------
    Contents of XML File.

    """
    xmlData = archive.read(nameOfXMLFile)
    xmlContent = BeautifulSoup(xmlData, fileExtension)
    return xmlContent


# %% Get MetaInfo from XML File
def getXMLAttributes(xmlContent):
    '''
    Collect Meta-Data from the XML Header file.

    Parameters
    ----------
    xmlContent : bs4
        A beautifullSoup4 buffered file.

    Returns
    -------
    xmlDict : Dict
        A dictionary with the Meta Info.

    '''
    # Get Information About the Stored Files (Processed or Raw Data)
    xmlDataType = xmlContent.find('Image').attrs
    dataType = str(xmlDataType['Type'])

    # get OCT Type
    #serialNum = str(xmlContent.find('Serial').getText())

    # Get mm Dimensions
    xmlPixelInfo = xmlContent.find('SizeReal').getText()
    # z = depth, x = horizontal, y = slices
    imgSizemmZ = round(np.float64(xmlPixelInfo.split('\n')[1]),2)
    imgSizemmX = round(np.float64(xmlPixelInfo.split('\n')[2]),2)
    imgSizemmY = round(np.float64(xmlPixelInfo.split('\n')[3]),2)

    # Get Pixel Dimensions
    pixelDimensions = xmlContent.find('SizePixel').getText()
    # z = depth, x = horizontal, y = slices
    dimZ = int(pixelDimensions.split('\n')[1])
    dimX = int(pixelDimensions.split('\n')[2])
    dimY = int(pixelDimensions.split('\n')[3]) # stacksize
    imgSize = (dimX, dimY)

    # Get Pixel Spacing in um
    pixelSpacing = xmlContent.find('PixelSpacing').getText()
    spacingZ = np.float64(pixelSpacing.split('\n')[1])*1000
    spacingX = np.float64(pixelSpacing.split('\n')[2])*1000
    spacingY = np.float64(pixelSpacing.split('\n')[3])*1000

    # Get z Pixel Size
    xmlPixelInfo = xmlContent.find('SizeReal').getText()
    pixSizeZ = float((xmlPixelInfo.split('\n')[1]))

    # Get some Meta-Info
    studyName = str(xmlContent.find('Study').getText()).replace(' ', '_')
    expNumber = int(xmlContent.find('ExperimentNumber').getText())
    aScanAv = int(xmlContent.find('IntensityAveraging').find('AScans').getText())
    imgResizeFactor = round(np.float64(spacingX) / np.float64(spacingZ), 2)

    Nline = int(xmlContent.find('SpectrometerElements').getText())
    Napo = ""
    Nx = ""
    offsScale = ""


    thorModel = xmlContent.find('Model').getText()
    thorSerial = xmlContent.find('Serial').getText()
    try:
        thorSens = xmlContent.find('DevicePresetDescription').getText().split('(')[1].split(' ')[0] + ' kHz'
    except:
        thorSens = 'notAvail-Old_OCT_Version'
            
    thorProbe = xmlContent.find('Probe').getText()
    thorCentrWaveLen = xmlContent.find('CentralWavelength').getText().split('.')[0]
    thorDateTime = str(datetime.fromtimestamp(int(xmlContent.find('Timestamp').getText())))
    thorScanTime = float(xmlContent.find('ScanTime').getText())
    
    try:
        thorSoftVers = xmlContent.find('OriginalSoftwareVer').getText()
    except:
        thorSoftVers = 'notAvail-Old_OCT_Version'

    if dataType != 'Processed':
        Nline = int(xmlContent.find('SpectrometerElements').getText())
        Napo = int(xmlContent.Ocity.DataFiles.find_all('DataFile')[6].get('ApoRegionEnd0')) # [6] is the 6th child/Entry of <DataFile>
        Nx = int(xmlContent.Ocity.DataFiles.find_all('DataFile')[6].get('ScanRegionEnd0')) - int(xmlContent.Ocity.DataFiles.find_all('DataFile')[6].get('ScanRegionStart0'))
        offsScale = np.float64(xmlContent.find('BinaryToElectronCountScaling').getText())

    xmlDict = {'xmlDataType': xmlDataType,
               'dataType': dataType,
               'xmlPixelInfo': xmlPixelInfo,
               'imgSizemmZ': imgSizemmZ,
               'imgSizemmX': imgSizemmX,
               'imgSizemmY': imgSizemmY,
               'pixelDimensions': pixelDimensions,
               'dimZ': dimZ,
               'dimX': dimX,
               'dimY': dimY,
               'imgSize': imgSize,
               'pixSizeZ': pixSizeZ,
               'studyName': studyName,
               'expNumber': expNumber,
               'Nline': Nline,
               'Napo': Napo,
               'Nx': Nx,
               'offsScale': offsScale,
               'aScanAv': aScanAv,
               'imgResizeFactor': imgResizeFactor,
               'spacingZ': spacingZ,
               'spacingX': spacingX,
               'spacingY': spacingY,
               'Modell':  thorModel,
               'Serialnumber': thorSerial,
               'Sensitivity': thorSens,
               'Probe_Name': thorProbe,
               'Wavelength': thorCentrWaveLen,
               'Acquisition_DateTime': thorDateTime,
               'Scan_Duration': thorScanTime,
               'Software_Version': thorSoftVers,
               }
    return xmlDict

# legacy 
           #'serialNum': serialNum,

# %% Smooth function from Matlab

# %% Create Image Spectral
def createImageFromRaw(xmlDict: dict, archive: None, dBmin: int, dBmax: int, selDataType: str, averaging: str, spectral: int, prefRaw: bool, resizeState: str, tukeySize: float, advancedFilter: str, dispersion):
    '''
    Returns an uint8 (0-255) numpy array with the correct image dimensions in 
    X, Y and Z. Can handle OCT Spectral raw data and processed oct files.
    

    Parameters
    ----------
    xmlDict : dict
        A dict with informations about the oct file. see function: getXMLAttributes()
    archive : zipfile
        A zipfile buffer object ('r' -mode).
    dBmin : int
        Minimun dB Value (Dynamic Range).
    dBmax : int
        Maximum dB Value (Dynamic Range)..
    selDataType : str
        Processed or RawData (or both).
    averaging : str
        Averaging type: coherent, incoherent, none.
    spectral : int
        Current slice number selected by the tk.skale undernath the image.
    prefRaw : bool
        Boolean expression if raw data is to be prefered when exporting. (Not enabled yet)
    resizeState : str
        Resize the image in X-Dimension. (Anisotropic pixels)
    tukeySize : float
        Size of the Tukey Window r = 0.5 default (tapered cosine),
        r = 1 hann, r = 0 rectangle
    advancedFilter : str
        Switch to enable advanced local filtering of outliers 

    Returns
    -------
    uint8 numpy array (3D)
        A uint8 numpy array containing the image stack or slice.

    '''   
    if selDataType == 'Processed':

        rawData = archive.read('data/Intensity.data')
        # read the raw data into an string
        img_arr = np.frombuffer(rawData, np.int32)
        img = np.reshape(img_arr, (xmlDict['dimY'], xmlDict['dimX'], xmlDict['dimZ']))
        img = np.rot90(img, k=-1, axes = (0,2))

        # Set dB Value according to settings
        dBstart = (1119000000-1105000000)/(80-20) * dBmin + (1105000000 - ((1119000000-1105000000)/(80-20)*20))
        dBend = (1119000000-1105000000)/(80-20) * dBmax + (1105000000 - ((1119000000-1105000000)/(80-20)*20))
        img = np.clip(img, dBstart, dBend)
        img = (255 * ((img - dBstart) / (dBend - dBstart))).astype(np.uint8)

        if resizeState == 'selected':
            # stretch image here to maintain aspect ratio
            img = np.repeat(img, round(xmlDict['imgResizeFactor']), axis=1)
        
        
        return img

    else:
        # Raw Spectral Data        
        # Dispersion correctur 
        # 3.78e-4 empircal determined to get a percentage ratio
        if (dispersion[0] == 'Quadratic'):
            dispersionCoefficient = int(dispersion[1])* 3.78e-4
        else:
            dispersionCoefficient = 0
            
        ref_scale = int(7e4)
        #m = np.arange(1,int(xmlDict['Nline']),1)[np.newaxis,...]
        zRange = np.rot90(np.arange(0, xmlDict['Nline']/2,1, dtype=np.float16)[..., np.newaxis])
        #AScans = np.rot90(np.arange(1, xmlDict['Nx'], 1)[..., np.newaxis])
        #BScans = np.rot90(np.arange(1, xmlDict['dimY'],1)[..., np.newaxis])
        
        offsetErrorDataRaw = archive.read('data/OffsetErrors.data')
        offsetErrorData = np.frombuffer(offsetErrorDataRaw, np.float32)
        off0 = smooth(offsetErrorData/xmlDict['offsScale'], int(xmlDict['Nline']/32)-1)[...,np.newaxis]

        chirpDataRaw = archive.read('data/Chirp.data')
        chirpData = np.frombuffer(chirpDataRaw, np.float32)[..., np.newaxis]    

        # Crazy stuff happening here
        dispersionCorrection = np.exp(1j *(dispersionCoefficient * np.transpose(chirpData) **2 /  xmlDict['Nline']))

        [K, M] = np.meshgrid(chirpData, zRange) 
        nftm = np.exp(np.float64(2) * math.pi * 1j * np.float64(M) * np.float64(K) / xmlDict['Nline'])

        spectralDataRaw = archive.read('data/Spectral' + str(spectral) + '.data')
        spectralData = np.frombuffer(spectralDataRaw, np.int16) 
        spectralData = np.rot90(np.fliplr(np.reshape(spectralData, (xmlDict['Napo'] + xmlDict['Nx'], xmlDict['Nline']))))
        apo0 = np.mean(spectralData[:,0:xmlDict['Napo']],1)
        raw0 = spectralData[:,:]

        #Apodization Window
        apoWin0 = (np.sqrt(smooth(apo0, (int(xmlDict['Nline']/32))-1)) / ref_scale)
        
        # create a Tukey window (Tapered Cosine)
        # create window: r=0.5 default (tapered cosine), r=1 hann, r=0 rectangle 
        win = np.float64(signal.tukey(xmlDict['Nline'], tukeySize))[..., np.newaxis]
        window0 = np.divide(win, np.sum(win.sum(axis=0))) / apoWin0[..., np.newaxis]

        cBScan0 = (nftm @ ((window0 * (raw0 - apo0[..., np.newaxis] - off0)) * np.transpose(np.conjugate(dispersionCorrection)))) 
        cBScan0 = cBScan0[:,(xmlDict['Napo']):cBScan0.shape[1]]

        # Initialize the image with the desired dimensions, either with A-Scan Averaging or not
        if averaging == 'none':
            imageInit = np.zeros(shape=(int(xmlDict['Nline']/2), int(xmlDict['Nx'])), dtype=np.uint8) 
        else:
            imageInit = np.zeros(shape=(int(xmlDict['Nline']/2), int((xmlDict['Nx'])/xmlDict['aScanAv'])), dtype=np.uint8) 

        img = np.zeros(shape=(int(xmlDict['dimZ']), int(xmlDict['dimX'])))

        # Manage averaging settings here
        # wenn incoherent oder coherent
        if averaging != 'none':
            cbScan0Av = np.zeros(shape=(int(xmlDict['Nline']/2), int((xmlDict['Nx'])/xmlDict['aScanAv']), xmlDict['aScanAv']), dtype=np.complex128)
            for av in range(xmlDict['aScanAv']):
                cbScan0Av[:,:,av] = cBScan0[:,av:xmlDict['Nx']:xmlDict['aScanAv']]

            if averaging == 'incoherent':
                imageInit[:,:] = octToGV(np.mean(abs(cbScan0Av), axis=2), dBmin, dBmax, advancedFilter)

            elif averaging == 'coherent':
                imageInit[:,:] = octToGV(np.mean(cbScan0Av, axis=2), dBmin, dBmax, advancedFilter)
        else: # averaging is 'none'
            imageInit = octToGV(cBScan0[:, range(0, np.shape(cBScan0)[1], xmlDict['aScanAv'])], dBmin, dBmax, advancedFilter)

        img[:,:] = imageInit
       
        if resizeState == 'selected':
            # stretch image to maintain physical aspect ratio
            img = np.array(Image.fromarray(img).resize(size=(int(xmlDict['dimX'] * xmlDict['imgResizeFactor']), 
                                                             xmlDict['dimZ']),
                                                       resample=0), 
                           dtype=np.uint8)
        else:
            img = np.array(Image.fromarray(img), dtype=np.uint8)
                
            
    return img

def octToGV(cBscan, dBmin: int, dBmax: int, advancedFilter: str):
 
    '''
    Computes greyvalues from complex number of the spectral data.
    The Matlab implementation of 'uint8' uses saturation arithmetic unlike
    python which uses modular arithmetic. Using numpy.clip() is the equivalent.
    
    Advanced local filtering is used to minimize low local noise outliers.
    
    --------------------------------------------------
    Original Matlab implementation.
    GW = uint8(255*(20*log10(abs(cBScan)) - dBmin)/(dBmax - dBmin));

    (https://en.wikipedia.org/wiki/Saturation_arithmetic,
     https://en.wikipedia.org/wiki/Modular_arithmetic)

    Parameters
    ----------
    cBscan : Array of complex128
        2D-Array of complex spectral data.
    dBmin : int
        Minimum Dezibel.
    dBmax : int
        Maximum Dezibel.
    advancedFilter : bool
        Switch for advanced local Filtering of small outliers.

    Returns
    -------
    None.

    '''
    
    temp = 255*(20 * np.log10(abs(cBscan)) - dBmin) / (dBmax - dBmin)
    #temp[0:6, 0:np.shape(temp)[1]] = 25 # one could make the first 6 lines black if desired
    
    if advancedFilter == 'selected':
        outlierList = np.where(temp < 50)
        for value in range(len(outlierList[0])):
            temp[outlierList[0][value],outlierList[1][value]] = np.median(temp[outlierList[0][value] -1 :  outlierList[0][value] + 2 , 
                                                                               outlierList[1][value] -1 : outlierList[1][value] + 2])

    return np.clip(temp, a_min = 0, a_max = 255)

def smooth(a, SPAN):
    '''
    SMOOTH(a,SPAN) smooths data a using SPAN as the number of points used
    to compute each element of Z. As in Matlabs implementation. 
    If an even SPAN is specified, it should reduced by 1.

    Parameters
    ----------
    a : Array / List
        NumPy 1-D array containing the data to be smoothed.
    WSZ : int
        IMPORTANT: Matlabs generates an odd number by substracing -1
        smoothing window size needs, which must be odd number, as in the 
        original MATLAB implementation.

    Returns
    -------
    Array
        Smoothed array according to /SPAN size.

    '''
    out0 = np.convolve(a, np.ones(SPAN, dtype=np.int),'valid')/SPAN    
    r = np.arange(1, SPAN-1,2)
    start = np.cumsum(a[:SPAN-1])[::2]/r
    stop = (np.cumsum(a[:-SPAN:-1])[::2]/r)[::-1]
    return np.concatenate((  start , out0, stop  ))

