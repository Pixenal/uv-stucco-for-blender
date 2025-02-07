#pragma once
#include <stdint.h>

#include <UvStucco.h>

#ifdef PLATFORM_LINUX
    #define STUC_BLENDER_EXPORT
#endif
#ifdef PLATFORM_WINDOWS
	#define STUC_BLENDER_EXPORT __declspec(dllexport)
#endif

//TODO replace these mat structs with a generic per obj offset table for all indexedAttribs,
//rather than just having an adhoc solution for materials
//Though really this is only being done to avoid iterating over faces in python,
//so this should be a non-issue for dcc's with c api's

typedef struct {
    char **ppArr;
    char *pMatIdxArr;
    int8_t count;
} StucBlenderMapArr;

typedef struct {
    int8_t *pArr;
    int32_t count;
} StucBlenderMatTable;

typedef struct {
    StucBlenderMatTable *pArr;
    int32_t count;
} StucBlenderMatTableArr;

STUC_BLENDER_EXPORT
void stucBlenderInit();
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileExport(char *pFilepath, int32_t objCount,
                                    StucObject* pObjArr, int32_t usgCount,
                                    StucUsg* pUsgArr,
                                    StucAttribIndexedArr indexedAttribs,
                                    StucBlenderMatTableArr *pMatTable);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileLoadForEdit(char *pFilepath,
                                         int32_t *pObjCount, StucObject **ppObjArr,
                                         int32_t *pUsgCount, StucUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, StucObject **ppFlatCutoffArr,
                                         StucAttribIndexedArr *pIndexedAttribs);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileLoad(char *pFilepath, char *pName);
STUC_BLENDER_EXPORT
StucResult stucBlenderMapFileUnload(char *pName);
STUC_BLENDER_EXPORT
int32_t stucBlenderMapToMesh(StucBlenderMapArr *pMapArr, StucMesh *pMesh,
                             StucMesh *pWorkMesh, StucCommonAttribList *pCommonAttribs,
                             float wScale);
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
int32_t stucBlenderMapFileGenPreviewImage(char *pName, int32_t res,
                                          float *pImage);
STUC_BLENDER_EXPORT
int32_t stucBlenderMapMatsGet(StucBlenderMapArr *pMapArr,
                              StucAttribIndexedArr *pMats);
STUC_BLENDER_EXPORT
void stucBlenderDestroy();