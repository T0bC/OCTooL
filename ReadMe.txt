# Literatur: Some information regarding OCT raw files
# OCTexVIEW_1.0: Python Source code
	# dist: compiled software ready for distribution

# E-Mail: tobias.meissner@medizin.uni-leipzig.de
# This Software was developed using an conda virtual environment 
# to edit the source code follow these instructions
# Install miniconda
# in anaconda promt (CMD) type

conda create -n octDev python=3.9 spyder numpy matplotlib beautifulsoup4 scipy pillow opencv

# this creates an invironment with all on conda aviable packages used in this project
# two packages need to be installed via pip

pip install ttkthemes
pip install lxml


# We are using a customized ttktheme 'equilux'
# copy the file OCTexVIEW_X.X\icons\equilux.tcl into the environment folder
# C:\Users\YourUserName\.conda\envs\yourEnvName\Lib\site-packages\ttkthemes\png\equilux
# now all packages are installed
# type 'spyder' in the anaconda promt to open the IDE spyder
# select those *.py files which are of interest of you
# exportGuiFrames contains all window tiles / frames for the OCT export routine including their functions
# analyzeGuiFrames is still under developement
# octFunctions contais the routines to read, process, export OCT RawImages

#####################
#### Compilation ####
#####################

# To Compile the software to an executable for your OS do the following
# if not allready, install miniconda
# create a seperate compiling environment using the anaconda promt

conda create -n compileEnv python=3.8.5

# the rest of the packages are installed via pip, since anaconda library seems to 
# make the executable uneccesarily larger

pip install pyinstaller
pip install numpy
pip install matplotlib
pip install beautifulsoup4
pip install scipy
pip install pillow 
pip install opencv-python
pip install ttkthemes
pip install lxml

# We are using a customized ttktheme 'equilux'
# copy the file OCTexVIEW_X.X\icons\equilux.tcl into the environment folder
# C:\Users\YourUserName\.conda\envs\yourEnvName\Lib\site-packages\ttkthemes\png\equilux
# activate the compiling environment

conda activate compileEnv

# change the directory to the sourcefile *.py location (OCTexVIEW.py)
# e.g. cd "C:\Path\To\OCTExport\OCTexVIEW_1.0"

# make shure the icon/thumbnail for the software is in the *.ico format
# http://www.rw-designer.com/image-to-icon this webiste creates those
# be shure to supply as well larger icons (16,32, 64, 128, 256)
# save the ico file into the "icons" folder where the source code is
# or use the python script: png_to_ico_script.py

# run the following command to compile the software into a folder with a provided thumbnail

pyinstaller --onedir --clean --noconsole --icon "icons/thumb_4.ico" OCTexVIEW.py

# after the compilation copy the icon folder into the "dist" folder where all the other source files 
# are lokated. Done

#### Hint ####
# If no new packages/librarys are included during the developement, you only need to copy & replace 
# the OCTexView.exe to update an existing installation of the software.