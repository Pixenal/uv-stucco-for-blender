#define HANDLE_TABLE_SIZE 64
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

#include <UvStuccoBlender.h>


typedef struct HandleEntry {
	struct HandleEntry *pNext;
	StucMap handle;
	char *pFilePath;
} HandleEntry;
static HandleEntry handleTable[HANDLE_TABLE_SIZE];

StucContext pStucContext;

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

void stucBlenderInit() {
	stucContextInit(&pStucContext, NULL, NULL, NULL, NULL, NULL);
}

StucResult stucBlenderMapFileExport(const char *pName, int32_t objCount,
                                    StucObject* pObjArr, int32_t usgCount,
                                    StucUsg* pUsgArr,
                                    StucAttribIndexedArr indexedAttribs,
                                    StucBlenderMatTableArr *pMatTable) {
	for (int32_t i = 0; i < objCount; ++i) {
		StucMesh *pMesh = (StucMesh *)pObjArr[i].pData;
		StucAttrib *pAttrib = NULL;
		stucGetAttrib("StucMaterialIndices", &pMesh->faceAttribs, &pAttrib);
		if (!pAttrib) {
			continue;
		}
		int8_t *pIndices = pAttrib->pData;
		for (int32_t j = 0; j < pMesh->faceCount; ++j) {
			pIndices[j] = pMatTable->pArr[i].pArr[pIndices[j]];
		}
	}
	return stucMapFileExport(pStucContext, pName, objCount, pObjArr, usgCount,
	                         pUsgArr, indexedAttribs);
}
StucResult stucBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, StucObject **ppObjArr,
                                         int32_t *pUsgCount, StucUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, StucObject **ppFlatCutoffArr,
                                         StucAttribIndexedArr *pIndexedAttribs) {
	return stucMapFileLoadForEdit(pStucContext, pFilePath, pObjCount, ppObjArr,
	                              pUsgCount, ppUsgArr, pFlatCutoffCount, ppFlatCutoffArr,
	                              pIndexedAttribs);
}

StucResult stucBlenderMapFileLoad(char *pFilePath) {
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
	return stucMapFileLoad(pStucContext, &pEntry->handle, pFilePath);
}

StucResult stucBlenderMapFileUnload(char *pFilePath) {
	HandleEntry *pEntry, *pPrevEntry;
	getHandle(&pEntry, &pPrevEntry, pFilePath);
	stucMapFileUnload(pStucContext, pEntry->handle);
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
	return STUC_SUCCESS;
}

void stucBlenderQueryCommonAttribs(StucMesh *pMesh, char *pMap,
								   StucCommonAttribList *pCommonAttribs) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pMap) != 4) {
		printf("Stuc query common attribs failed, specified map not loaded\n");
		return;
	}
	stucQueryCommonAttribs(pStucContext, pEntry->handle, pMesh, pCommonAttribs);
}

int32_t stucBlenderMapToMesh(char *pFilePath, StucMesh *pMesh, StucMesh *pWorkMesh,
                             StucCommonAttribList *pCommonAttribs, float wScale) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Stuc blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	//TODO if multiple objects are selected, see if dispatching them all at once on multiple threads
	// improves perf. Probably not a good idea for high res meshes or maps, given the memory use.
	// maybe selectivly do it based on the mesh and map res?
	StucResult result = stucMapToMesh(pStucContext, pEntry->handle, pMesh, pWorkMesh, pCommonAttribs, wScale);
	return result == STUC_ERROR;
}

void stucBlenderDestroyCommonAttribs(StucCommonAttribList *pCommonAttribs) {
	stucDestroyCommonAttribs(pStucContext, pCommonAttribs);
}

void stucBlenderCopyMeshCore(StucMesh *stucMesh, StucMesh *workMesh) {
	memcpy(stucMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
	       (stucMesh->faceCount + 1));
	memcpy(stucMesh->pCorners, workMesh->pCorners, sizeof(int32_t) *
	       stucMesh->cornerCount);
	memcpy(stucMesh->vertAttribs.pArr[0].pData, workMesh->vertAttribs.pArr[0].pData, sizeof(StucVec3) *
	       stucMesh->vertCount);
	//memcpy(stucMesh->pEdges, workMesh->pEdges, sizeof(int32_t) *
	//       stucMesh->cornerCount);
}

static void copyAttribs(StucAttribArray *pA, StucAttribArray *pB,
                        int32_t dataLen) {
	if (!pA || !pB) {
		return;
	}
	for (int32_t i = 0; i < pA->count; ++i) {
		StucAttrib* pBEntry;
		stucGetAttrib(pA->pArr[i].name, pB, &pBEntry);
		if (!pBEntry) {
			printf("Mismatch in workmesh and stucmesh attribs\n");
			abort();
		}
		int32_t attribSize;
		stucGetAttribSize(pA->pArr + i, &attribSize);
		printf("attrib Size == %d\n", attribSize);
		memcpy(pBEntry->pData, pA->pArr[i].pData, attribSize * dataLen);
	}
}

void stucBlenderCopyMeshAttribs(StucMesh *stucMesh, StucMesh *workMesh) {
	//copyAttribs(workMesh->pMeshAttribs, stucMesh->pMeshAttribs,
	//            workMesh->meshAttribCount, 1);
	copyAttribs(&workMesh->faceAttribs, &stucMesh->faceAttribs,
	            workMesh->faceCount);
	copyAttribs(&workMesh->cornerAttribs, &stucMesh->cornerAttribs,
	            workMesh->cornerCount);
	//copyAttribs(workMesh->pEdgeAttribs, stucMesh->pEdgeAttribs,
	//            workMesh->edgeAttribCount, workMesh->edgeCount);
	//copyAttribs(workMesh->pVertAttribs, stucMesh->pVertAttribs,
	//            workMesh->vertAttribCount, workMesh->vertCount);
}

StucResult stucBlenderObjArrDestroy(int32_t objCount, StucObject *pObjArr) {
	return stucObjArrDestroy(pStucContext, objCount, pObjArr);
}

StucResult stucBlenderUsgArrDestroy(int32_t count, StucUsg *pUsgArr) {
	return stucUsgArrDestroy(pStucContext, count, pUsgArr);
}

void stucBlenderMeshDestroy(StucMesh *pMesh) {
	stucMeshDestroy(pStucContext, pMesh);
}

int32_t stucBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res, float *pImage) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Stuc blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	StucImage image = {.res = res, .type = STUC_IMAGE_F32};
	stucMapFileGenPreviewImage(pStucContext, pEntry->handle, &image);
	memcpy(pImage, image.pData, res * res * 4 * sizeof(float));
	return 0;
}

void stucBlenderMapMatsGet(char *pFilePath,
                           StucAttribIndexed **ppMats) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Stuc blender map to mesh failed, specified map not loaded\n");
		return;
	}
	StucAttribIndexedArr indexedAttribs = {0};
	stucMapIndexedAttribsGet(pStucContext, pEntry->handle, &indexedAttribs);
	for (int32_t i = 0; i < indexedAttribs.count; ++i) {
		StucAttribIndexed *pAttrib = indexedAttribs.pArr + i;
		if (!strncmp("StucMaterials", pAttrib->name, STUC_ATTRIB_NAME_MAX_LEN)) {
			*ppMats = pAttrib;
			return;
		}
	}
}

void stucBlenderDestroy() {
	//TODO implement this
	return;
}