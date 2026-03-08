# this script will invoke PyInstaller using a  
# "gry_bundle.spec" specification file, and bundle 
# the Gry command line tool in a standalone distribution

from pathlib import Path
from shutil import copy
import zipfile
import PyInstaller.__main__

HERE = Path(__file__).absolute().parent
BUNDLE_FILES = HERE / 'gry_bundle_files' # some files to be included
SPEC_FILE = HERE / 'gry_bundle.spec'
DEST_DIR = HERE / 'dist' / 'gry'
ZIP_FILE = HERE / 'dist' / 'gry.zip'

def main():
    PyInstaller.__main__.run([str(SPEC_FILE)])
    copy(BUNDLE_FILES / 'cliconverters.py', 
         DEST_DIR / 'cliconverters.py')
    copy(BUNDLE_FILES / 'gryconf.json', 
         DEST_DIR / 'gryconf.json')
    copy(BUNDLE_FILES / 'gryrequest.json', 
         DEST_DIR / 'gryrequest.json')
    copy(BUNDLE_FILES / 'readme.txt', 
         DEST_DIR / 'readme.txt')
    with zipfile.ZipFile(ZIP_FILE, 'w') as zip:
       for root, dirs, files in DEST_DIR.walk():
           for file in files:
               zip.write(root / file, arcname=(root / file).relative_to(DEST_DIR))

if __name__ == '__main__':
    main()
