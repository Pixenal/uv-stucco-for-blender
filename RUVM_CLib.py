import ctypes
import sys

if sys.platform == "win32":
    ruvmLibPath = "T:/workshop_folders/RUVM_Blender/Build/WinRelease/Debug/RUVMBlender.dll"
elif sys.platform == "linux" or "linux2":
    ruvmLibPath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_Blender/Build/Debug/libRUVMBlender.so"
ruvmLib = ctypes.cdll.LoadLibrary(ruvmLibPath)
