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

void uvsBlenderInit() {
	RuvmTypeDefaultConfig typeDefaultConfig = {0};
	uvsContextInit(&pRuvmContext, NULL, NULL, NULL, &typeDefaultConfig, NULL);
}

RuvmResult uvsBlenderMapFileExport(const char *pName, int32_t objCount,
                                    RuvmObject* pObjArr, int32_t usgCount,
                                    RuvmUsg* pUsgArr,
                                    RuvmAttribIndexedArr indexedAttribs) {
	return uvsMapFileExport(pRuvmContext, pName, objCount, pObjArr, usgCount,
	                         pUsgArr, indexedAttribs);
}
RuvmResult uvsBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, RuvmObject **ppObjArr,
                                         int32_t *pUsgCount, RuvmUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, RuvmObject **ppFlatCutoffArr,
                                         RuvmAttribIndexedArr *pIndexedAttribs) {
	return uvsMapFileLoadForEdit(pRuvmContext, pFilePath, pObjCount, ppObjArr,
	                              pUsgCount, ppUsgArr, pFlatCutoffCount, ppFlatCutoffArr,
	                              pIndexedAttribs);
}

RuvmResult uvsBlenderMapFileLoad(char *pFilePath) {
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
	return uvsMapFileLoad(pRuvmContext, &pEntry->handle, pFilePath);
}

RuvmResult uvsBlenderMapFileUnload(char *pFilePath) {
	HandleEntry *pEntry, *pPrevEntry;
	getHandle(&pEntry, &pPrevEntry, pFilePath);
	uvsMapFileUnload(pRuvmContext, pEntry->handle);
	if (!pPrevEntry) {
		free(pEntry->pFilePath);
		if (pEntry->pNext) {
			HandleEntry *pNext = pEntry->pNext;
			*pEntry = *pNext;
			free(pNext);
		}
		else {
			HandleEntry empty = {0};
			*pEntry = empty;
		}
	}
	else {
		pPrevEntry->pNext = pEntry->pNext;
		free(pEntry->pFilePath);
		free(pEntry);
	}
	return RUVM_SUCCESS;
}

void uvsBlenderQueryCommonAttribs(RuvmMesh *pMesh, char *pMap,
								   RuvmCommonAttribList *pCommonAttribs) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pMap) != 4) {
		printf("Ruvm query common attribs failed, specified map not loaded\n");
		return;
	}
	uvsQueryCommonAttribs(pRuvmContext, pEntry->handle, pMesh, pCommonAttribs);
}

int32_t uvsBlenderMapToMesh(char *pFilePath, RuvmMesh *pMesh, RuvmMesh *pWorkMesh,
                             RuvmCommonAttribList *pCommonAttribs, float wScale) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	RuvmResult result = uvsMapToMesh(pRuvmContext, pEntry->handle, pMesh, pWorkMesh, pCommonAttribs, wScale);
	return result == RUVM_ERROR;
}

void uvsBlenderDestroyCommonAttribs(RuvmCommonAttribList *pCommonAttribs) {
	uvsDestroyCommonAttribs(pRuvmContext, pCommonAttribs);
}

void uvsBlenderCopyMeshCore(RuvmMesh *uvsMesh, RuvmMesh *workMesh) {
	memcpy(uvsMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
	       (uvsMesh->faceCount + 1));
	memcpy(uvsMesh->pCorners, workMesh->pCorners, sizeof(int32_t) *
	       uvsMesh->cornerCount);
	memcpy(uvsMesh->vertAttribs.pArr[0].pData, workMesh->vertAttribs.pArr[0].pData, sizeof(RuvmVec3) *
	       uvsMesh->vertCount);
	//memcpy(uvsMesh->pEdges, workMesh->pEdges, sizeof(int32_t) *
	//       uvsMesh->cornerCount);
}

static void copyAttribs(RuvmAttribArray *pA, RuvmAttribArray *pB,
                        int32_t dataLen) {
	if (!pA || !pB) {
		return;
	}
	for (int32_t i = 0; i < pA->count; ++i) {
		RuvmAttrib* pBEntry;
		uvsGetAttrib(pA->pArr[i].name, pB, &pBEntry);
		if (!pBEntry) {
			printf("Mismatch in workmesh and uvsmesh attribs\n");
			abort();
		}
		int32_t attribSize;
		uvsGetAttribSize(pA->pArr + i, &attribSize);
		printf("attrib Size == %d\n", attribSize);
		memcpy(pBEntry->pData, pA->pArr[i].pData, attribSize * dataLen);
	}
}

void uvsBlenderCopyMeshAttribs(RuvmMesh *uvsMesh, RuvmMesh *workMesh) {
	//copyAttribs(workMesh->pMeshAttribs, uvsMesh->pMeshAttribs,
	//            workMesh->meshAttribCount, 1);
	copyAttribs(&workMesh->faceAttribs, &uvsMesh->faceAttribs,
	            workMesh->faceCount);
	copyAttribs(&workMesh->cornerAttribs, &uvsMesh->cornerAttribs,
	            workMesh->cornerCount);
	//copyAttribs(workMesh->pEdgeAttribs, uvsMesh->pEdgeAttribs,
	//            workMesh->edgeAttribCount, workMesh->edgeCount);
	//copyAttribs(workMesh->pVertAttribs, uvsMesh->pVertAttribs,
	//            workMesh->vertAttribCount, workMesh->vertCount);
}

RuvmResult uvsBlenderObjArrDestroy(int32_t objCount, RuvmObject *pObjArr) {
	return uvsObjArrDestroy(pRuvmContext, objCount, pObjArr);
}

RuvmResult uvsBlenderUsgArrDestroy(int32_t count, RuvmUsg *pUsgArr) {
	return uvsUsgArrDestroy(pRuvmContext, count, pUsgArr);
}

void uvsBlenderMeshDestroy(RuvmMesh *pMesh) {
	uvsMeshDestroy(pRuvmContext, pMesh);
}

int32_t uvsBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res, float *pImage) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	RuvmImage image = {.res = res, .type = RUVM_IMAGE_F32};
	uvsMapFileGenPreviewImage(pRuvmContext, pEntry->handle, &image);
	memcpy(pImage, image.pData, res * res * 4 * sizeof(float));
	return 0;
}

void uvsBlenderMapMatsGet(char *pFilePath,
                           RuvmAttribIndexed **ppMats) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return;
	}
	RuvmAttribIndexedArr indexedAttribs = {0};
	uvsMapIndexedAttribsGet(pRuvmContext, pEntry->handle, &indexedAttribs);
	for (int32_t i = 0; i < indexedAttribs.count; ++i) {
		RuvmAttribIndexed *pAttrib = indexedAttribs.pArr + i;
		if (!strncmp("RuvmMaterials", pAttrib->name, RUVM_ATTRIB_NAME_MAX_LEN)) {
			*ppMats = pAttrib;
			return;
		}
	}
}

void uvsBlenderDestroy() {
	//TODO implement this
	return;
}