import ctypes
import sys

if sys.platform == "win32":
    ruvmLibPath = "T:/workshop_folders/RUVM_Blender/Build/WinMd/Debug/RuvmBlender.dll"
elif sys.platform == "darwin":
    ruvmLibPath = "/Users/calebdawson/Repos/RUVM_Blender/build/macosShared/libRUVMBlender.dylib"
elif sys.platform == "linux" or "linux2":
    ruvmLibPath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_Blender/Build/Debug/libRuvmBlender.so"
ruvmLib = ctypes.cdll.LoadLibrary(ruvmLibPath)
