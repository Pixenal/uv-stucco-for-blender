import ctypes
import sys

if sys.platform == "win32":
    uvsLibPath = "T:/workshop_folders/RUVM_Blender/Build/WinMd/Debug/RuvmBlender.dll"
elif sys.platform == "darwin":
    uvsLibPath = "/Users/calebdawson/Repos/RUVM_Blender/build/macosShared/libRUVMBlender.dylib"
elif sys.platform == "linux" or "linux2":
    uvsLibPath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_Blender/Build/Debug/libRuvmBlender.so"
uvsLib = ctypes.cdll.LoadLibrary(uvsLibPath)
