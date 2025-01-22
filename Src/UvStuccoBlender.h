#pragma once
#include <stdint.h>

#include <UvStucco.h>

#ifdef PLATFORM_LINUX
    #define STUC_BLENDER_EXPORT
#endif
#ifdef PLATFORM_WINDOWS
	#define STUC_BLENDER_EXPORT __declspec(dllexport)
#endif

STUC_BLENDER_EXPORT
void stucBlenderInit();
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileExport(const char *pName, int32_t objCount,
                                    StucObject* pObjArr, int32_t usgCount,
                                    StucUsg* pUsgArr,
                                    StucAttribIndexedArr indexedAttribs);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, StucObject **ppObjArr,
                                         int32_t *pUsgCount, StucUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, StucObject **ppFlatCutoffArr,
                                         StucAttribIndexedArr *pIndexedAttribs);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileLoad(char *pFilePath);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileUnload(char *pFilePath);
STUC_BLENDER_EXPORT
int32_t stucBlenderMapToMesh(char *pFilePath,
                             StucMesh *pMesh,
                             StucMesh *pWorkMesh,
							 StucCommonAttribList *pCommonAttribs, float wScale);
STUC_BLENDER_EXPORT
void stucBlenderQueryCommonAttribs(StucMesh *pMesh,
								   char *pMapName,
								   StucCommonAttribList *pCommonAttribs);
STUC_BLENDER_EXPORT
void stucBlenderDestroyCommonAttribs(StucCommonAttribList *pCommonAttribs);
STUC_BLENDER_EXPORT
void stucBlenderCopyMeshCore(StucMesh *stucMesh,
                             StucMesh *workMesh);
STUC_BLENDER_EXPORT
void stucBlenderCopyMeshAttribs(StucMesh *stucMesh,
                                StucMesh *workMesh);
STUC_BLENDER_EXPORT
StucResult stucBlenderObjArrDestroy(int32_t objCount, StucObject *pObjArr);
STUC_BLENDER_EXPORT
StucResult stucBlenderUsgArrDestroy(int32_t count, StucUsg *pUsgArr);
STUC_BLENDER_EXPORT 
void stucBlenderMeshDestroy(StucMesh *pWorkMesh);
STUC_BLENDER_EXPORT
int32_t stucBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res,
                                          float *pImage);
STUC_BLENDER_EXPORT
void stucBlenderMapMatsGet(char *pFilePath,
                           StucAttribIndexed **ppMats);
STUC_BLENDER_EXPORT
void stucBlenderDestroy();