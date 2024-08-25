#define HANDLE_TABLE_SIZE 64
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

#include <RuvmBlender.h>


typedef struct HandleEntry {
	struct HandleEntry *pNext;
	RuvmMap handle;
	char *pFilePath;
} HandleEntry;
static HandleEntry handleTable[HANDLE_TABLE_SIZE];

RuvmContext pRuvmContext;

uint32_t fnvHash(unsigned char *value, int32_t valueSize, uint32_t size) {
	uint32_t hash = 2166136261;
	for (int32_t i = 0; i < valueSize; ++i) {
		hash ^= value[i];
		hash *= 16777619;
	}
	hash %= size;
	return hash;
}

static int32_t getHandle(HandleEntry **pEntry, HandleEntry **pPrevEntry,
                            char *pFilePath) {
	int32_t pathLength = strlen(pFilePath);
	int32_t hash = fnvHash((unsigned char *)pFilePath, pathLength,
			HANDLE_TABLE_SIZE);
	*pEntry = handleTable + hash;
	*pPrevEntry = NULL;
	do {
		if (!(*pEntry)->pFilePath) {
			return 0;
		}
		int32_t samePath = !strcmp(pFilePath, (*pEntry)->pFilePath);
		if (samePath) {
			if ((*pEntry)->handle == NULL) {
				return 2;
			}
			return 4;
			break;
		}
		if (!(*pEntry)->pNext) {
			return 1;
		}
		*pPrevEntry = *pEntry;
		*pEntry = (*pEntry)->pNext;
	} while(1);
	return 3;
}

void ruvmBlenderInit() {
	RuvmTypeDefaultConfig typeDefaultConfig = {0};
	ruvmContextInit(&pRuvmContext, NULL, NULL, NULL, &typeDefaultConfig, NULL);
}

RuvmResult ruvmBlenderMapFileExport(const char *pName, int32_t objCount,
                                    RuvmObject* pObjArr, int32_t usgCount,
                                    RuvmUsg* pUsgArr,
                                    RuvmAttribIndexedArr indexedAttribs) {
	return ruvmMapFileExport(pRuvmContext, pName, objCount, pObjArr, usgCount,
	                         pUsgArr, indexedAttribs);
}
RuvmResult ruvmBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, RuvmObject **ppObjArr,
                                         int32_t *pUsgCount, RuvmUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, RuvmObject **ppFlatCutoffArr,
                                         RuvmAttribIndexedArr *pIndexedAttribs) {
	return ruvmMapFileLoadForEdit(pRuvmContext, pFilePath, pObjCount, ppObjArr,
	                              pUsgCount, ppUsgArr, pFlatCutoffCount, ppFlatCutoffArr,
	                              pIndexedAttribs);
}

RuvmResult ruvmBlenderMapFileLoad(char *pFilePath) {
	HandleEntry *pEntry, *pPrevEntry;
	int32_t result = getHandle(&pEntry, &pPrevEntry, pFilePath);
	switch (result) {
		case 1: {
			pEntry = pEntry->pNext = calloc(1, sizeof(HandleEntry));
			break;
		}
		case 2: {
			printf("Handle table entry has valid filepath, but invalid handle\n");
			abort();
		}
		case 3: {
			printf("No match in handle table\n");
			abort();
		}
	}
	int32_t pathLength = strlen(pFilePath) + 1;
	pEntry->pFilePath = malloc(pathLength);
	memcpy(pEntry->pFilePath, pFilePath, pathLength);
	return ruvmMapFileLoad(pRuvmContext, &pEntry->handle, pFilePath);
}

void ruvmBlenderUnloadRuvmFile(char *pFilePath) {
	HandleEntry *pEntry, *pPrevEntry;
	getHandle(&pEntry, &pPrevEntry, pFilePath);
	ruvmMapFileUnload(pRuvmContext, pEntry->handle);
	if (!pPrevEntry && pEntry->pNext) {
		HandleEntry *pNext = pEntry->pNext;
		*pEntry = *pEntry->pNext;
		free(pNext);
	}
	else {
		pPrevEntry->pNext = pEntry->pNext;
		free(pEntry->pFilePath);
		free(pEntry);
	}
}

void ruvmBlenderQueryCommonAttribs(RuvmMesh *pMesh, char *pMap,
								   RuvmCommonAttribList *pCommonAttribs) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pMap) != 4) {
		printf("Ruvm query common attribs failed, specified map not loaded\n");
		return;
	}
	ruvmQueryCommonAttribs(pRuvmContext, pEntry->handle, pMesh, pCommonAttribs);
}

int32_t ruvmBlenderMapToMesh(char *pFilePath, RuvmMesh *pMesh, RuvmMesh *pWorkMesh,
                             RuvmCommonAttribList *pCommonAttribs, float wScale) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	RuvmResult result = ruvmMapToMesh(pRuvmContext, pEntry->handle, pMesh, pWorkMesh, pCommonAttribs, wScale);
	return result == RUVM_ERROR;
}

void ruvmBlenderDestroyCommonAttribs(RuvmCommonAttribList *pCommonAttribs) {
	ruvmDestroyCommonAttribs(pRuvmContext, pCommonAttribs);
}

void ruvmBlenderCopyMeshCore(RuvmMesh *ruvmMesh, RuvmMesh *workMesh) {
	memcpy(ruvmMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
	       (ruvmMesh->faceCount + 1));
	memcpy(ruvmMesh->pLoops, workMesh->pLoops, sizeof(int32_t) *
	       ruvmMesh->loopCount);
	memcpy(ruvmMesh->vertAttribs.pArr[0].pData, workMesh->vertAttribs.pArr[0].pData, sizeof(RuvmVec3) *
	       ruvmMesh->vertCount);
	//memcpy(ruvmMesh->pEdges, workMesh->pEdges, sizeof(int32_t) *
	//       ruvmMesh->loopCount);
}

static void copyAttribs(RuvmAttribArray *pA, RuvmAttribArray *pB,
                        int32_t dataLen) {
	if (!pA || !pB) {
		return;
	}
	for (int32_t i = 0; i < pA->count; ++i) {
		RuvmAttrib* pBEntry;
		ruvmGetAttrib(pA->pArr[i].name, pB, &pBEntry);
		if (!pBEntry) {
			printf("Mismatch in workmesh and ruvmmesh attribs\n");
			abort();
		}
		int32_t attribSize;
		ruvmGetAttribSize(pA->pArr + i, &attribSize);
		printf("attrib Size == %d\n", attribSize);
		memcpy(pBEntry->pData, pA->pArr[i].pData, attribSize * dataLen);
	}
}

void ruvmBlenderCopyMeshAttribs(RuvmMesh *ruvmMesh, RuvmMesh *workMesh) {
	//copyAttribs(workMesh->pMeshAttribs, ruvmMesh->pMeshAttribs,
	//            workMesh->meshAttribCount, 1);
	copyAttribs(&workMesh->faceAttribs, &ruvmMesh->faceAttribs,
	            workMesh->faceCount);
	copyAttribs(&workMesh->loopAttribs, &ruvmMesh->loopAttribs,
	            workMesh->loopCount);
	//copyAttribs(workMesh->pEdgeAttribs, ruvmMesh->pEdgeAttribs,
	//            workMesh->edgeAttribCount, workMesh->edgeCount);
	//copyAttribs(workMesh->pVertAttribs, ruvmMesh->pVertAttribs,
	//            workMesh->vertAttribCount, workMesh->vertCount);
}

RuvmResult ruvmBlenderObjArrDestroy(int32_t objCount, RuvmObject *pObjArr) {
	return ruvmObjArrDestroy(pRuvmContext, objCount, pObjArr);
}

RuvmResult ruvmBlenderUsgArrDestroy(int32_t count, RuvmUsg *pUsgArr) {
	return ruvmUsgArrDestroy(pRuvmContext, count, pUsgArr);
}

void ruvmBlenderMeshDestroy(RuvmMesh *pMesh) {
	ruvmMeshDestroy(pRuvmContext, pMesh);
}

int32_t ruvmBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res, float *pImage) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	RuvmImage image = {.res = res, .type = RUVM_IMAGE_F32};
	ruvmMapFileGenPreviewImage(pRuvmContext, pEntry->handle, &image);
	memcpy(pImage, image.pData, res * res * 4 * sizeof(float));
	return 0;
}

void ruvmBlenderMapMatsGet(char *pFilePath,
                           RuvmAttribIndexed **ppMats) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return;
	}
	RuvmAttribIndexedArr indexedAttribs = {0};
	ruvmMapIndexedAttribsGet(pRuvmContext, pEntry->handle, &indexedAttribs);
	for (int32_t i = 0; i < indexedAttribs.count; ++i) {
		RuvmAttribIndexed *pAttrib = indexedAttribs.pArr + i;
		if (!strncmp("RuvmMaterials", pAttrib->name, RUVM_ATTRIB_NAME_MAX_LEN)) {
			*ppMats = pAttrib;
			return;
		}
	}
}