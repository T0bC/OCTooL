# -*- coding: utf-8 -*-
"""
Created on Tue May 25 10:40:52 2021

@author: Tobias Meissner
"""

from PIL import Image



filename = r'icons\thumb_4.png'

img = Image.open(filename)
icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (255, 255)]
img.save('icons/thumb_4.ico')