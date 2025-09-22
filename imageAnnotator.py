# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 09:47:54 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import numpy as np
from scipy.interpolate import splprep, splev
import csv
import os

class ImageAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Annotator")

        self.canvas = tk.Canvas(root, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.points = []
        self.image = None
        self.image_path = None
        self.spline_line = None

        self.root.bind("<KeyPress-a>", lambda e: self.save_annotation("A"))
        self.root.bind("<KeyPress-e>", lambda e: self.save_annotation("E"))
        self.canvas.bind("<Button-1>", self.add_point)

        self.menu = tk.Menu(root)
        self.menu.add_command(label="Load Image", command=self.load_image)
        root.config(menu=self.menu)

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.tiff")])
        if not file_path:
            return

        self.image_path = file_path
        pil_image = Image.open(file_path)
        self.tk_image = ImageTk.PhotoImage(pil_image)
        self.canvas.config(width=self.tk_image.width(), height=self.tk_image.height())
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.points.clear()
        self.canvas.delete("line")

    def add_point(self, event):
        x, y = event.x, event.y
        self.points.append((x, y))
        self.canvas.create_oval(x-2, y-2, x+2, y+2, fill="red", outline="red")
        self.draw_spline()

    def draw_spline(self):
        if len(self.points) < 2:
            return
        self.canvas.delete("line")
        pts = np.array(self.points)
        tck, _ = splprep([pts[:,0], pts[:,1]], s=0)
        u = np.linspace(0, 1, 500)
        x_new, y_new = splev(u, tck)
        coords = list(zip(x_new, y_new))
        for i in range(len(coords)-1):
            self.canvas.create_line(*coords[i], *coords[i+1], fill="blue", tags="line")

    def calculate_length(self):
        if len(self.points) < 2:
            return 0
        pts = np.array(self.points)
        tck, _ = splprep([pts[:,0], pts[:,1]], s=0)
        u = np.linspace(0, 1, 1000)
        x_new, y_new = splev(u, tck)
        length = np.sum(np.sqrt(np.diff(x_new)**2 + np.diff(y_new)**2))
        return length

    def save_annotation(self, label):
        length = self.calculate_length()
        if length == 0 or not self.image_path:
            return

        csv_path = os.path.splitext(self.image_path)[0] + "_annotations.csv"
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Label", "Length (pixels)"])
            writer.writerow([label, round(length, 2)])

        print(f"Saved annotation '{label}' with length {round(length, 2)} pixels.")
        self.points.clear()
        self.canvas.delete("line")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAnnotator(root)
    root.mainloop()
