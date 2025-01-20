#pragma once
#include <stdint.h>

#include <RUVM.h>

#ifdef PLATFORM_LINUX
    #define RUVM_BLENDER_EXPORT
#endif
#ifdef PLATFORM_WINDOWS
	#define RUVM_BLENDER_EXPORT __declspec(dllexport)
#endif

RUVM_BLENDER_EXPORT
void ruvmBlenderInit();
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderMapFileExport(const char *pName, int32_t objCount,
                                    RuvmObject* pObjArr, int32_t usgCount,
                                    RuvmUsg* pUsgArr,
                                    RuvmAttribIndexedArr indexedAttribs);
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, RuvmObject **ppObjArr,
                                         int32_t *pUsgCount, RuvmUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, RuvmObject **ppFlatCutoffArr,
                                         RuvmAttribIndexedArr *pIndexedAttribs);
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderMapFileLoad(char *pFilePath);
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderMapFileUnload(char *pFilePath);
RUVM_BLENDER_EXPORT
int32_t ruvmBlenderMapToMesh(char *pFilePath,
                             RuvmMesh *pMesh,
                             RuvmMesh *pWorkMesh,
							 RuvmCommonAttribList *pCommonAttribs, float wScale);
RUVM_BLENDER_EXPORT
void ruvmBlenderQueryCommonAttribs(RuvmMesh *pMesh,
								   char *pMapName,
								   RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void ruvmBlenderDestroyCommonAttribs(RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void ruvmBlenderCopyMeshCore(RuvmMesh *ruvmMesh,
                             RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT
void ruvmBlenderCopyMeshAttribs(RuvmMesh *ruvmMesh,
                                RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderObjArrDestroy(int32_t objCount, RuvmObject *pObjArr);
RUVM_BLENDER_EXPORT
RuvmResult ruvmBlenderUsgArrDestroy(int32_t count, RuvmUsg *pUsgArr);
RUVM_BLENDER_EXPORT 
void ruvmBlenderMeshDestroy(RuvmMesh *pWorkMesh);
RUVM_BLENDER_EXPORT
int32_t ruvmBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res,
                                          float *pImage);
RUVM_BLENDER_EXPORT
void ruvmBlenderMapMatsGet(char *pFilePath,
                           RuvmAttribIndexed **ppMats);
