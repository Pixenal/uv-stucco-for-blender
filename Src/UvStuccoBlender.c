#define HANDLE_TABLE_SIZE 64
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

#include <UvStuccoBlender.h>


typedef struct HandleEntry {
	struct HandleEntry *pNext;
	StucMap handle;
	char *pName;
} HandleEntry;
static HandleEntry handleTable[HANDLE_TABLE_SIZE];

StucContext pStucContext;

static
uint32_t fnvHash(unsigned char *value, int32_t valueSize, uint32_t size) {
	uint32_t hash = 2166136261;
	for (int32_t i = 0; i < valueSize; ++i) {
		hash ^= value[i];
		hash *= 16777619;
	}
	hash %= size;
	return hash;
}

static
int32_t getHandle(HandleEntry **pEntry, HandleEntry **pPrevEntry, char *pName) {
	int32_t pathLength = (int32_t)strlen(pName);
	int32_t hash = fnvHash((unsigned char *)pName, pathLength, HANDLE_TABLE_SIZE);
	*pEntry = handleTable + hash;
	*pPrevEntry = NULL;
	do {
		if (!(*pEntry)->pName) {
			return 0;
		}
		int32_t samePath = !strcmp(pName, (*pEntry)->pName);
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

static
void correctMatIndices(
	int32_t objCount,
	StucObject *pObjArr,
	StucBlenderMatTableArr *pMatTable
) {
	for (int32_t i = 0; i < objCount; ++i) {
		StucMesh *pMesh = (StucMesh *)pObjArr[i].pData;
		StucAttrib *pAttrib = NULL;
		stucGetAttrib("StucMaterialIndices", &pMesh->faceAttribs, &pAttrib);
		if (!pAttrib) {
			continue;
		}
		int8_t *pIndices = pAttrib->core.pData;
		for (int32_t j = 0; j < pMesh->faceCount; ++j) {
			pIndices[j] = pMatTable->pArr[i].pArr[pIndices[j]];
		}
	}
}

StucResult stucBlenderMapFileExport(
	char *pFilepath,
	int32_t objCount,
	StucObject *pObjArr,
	int32_t usgCount,
	StucUsg *pUsgArr,
	StucAttribIndexedArr *pIndexedAttribs,
	StucBlenderMatTableArr *pMatTable
) {
	StucAttribIndexed *pAttrib = NULL;
	if (pIndexedAttribs->count) {
		stucGetAttribIndexed("StucMaterials", pIndexedAttribs, &pAttrib);
	}
	if (pAttrib) {
		correctMatIndices(objCount, pObjArr, pMatTable);
	}
	return stucMapFileExport(
		pStucContext,
		pFilepath,
		objCount,
		pObjArr,
		usgCount,
		pUsgArr,
		pIndexedAttribs
	);
}
StucResult stucBlenderMapFileLoadForEdit(
	char *pName,
	int32_t *pObjCount,
	StucObject **ppObjArr,
	int32_t *pUsgCount,
	StucUsg **ppUsgArr,
	int32_t *pFlatCutoffCount,
	StucObject **ppFlatCutoffArr,
	StucAttribIndexedArr *pIndexedAttribs
) {
	return stucMapFileLoadForEdit(
		pStucContext,
		pName,
		pObjCount,
		ppObjArr,
		pUsgCount,
		ppUsgArr,
		pFlatCutoffCount,
		ppFlatCutoffArr,
		pIndexedAttribs
	);
}

StucResult stucBlenderMapFileLoad(char *pFilepath, char *pName) {
	StucResult err = STUC_SUCCESS;
	HandleEntry *pEntry = NULL;
	HandleEntry *pPrevEntry = NULL;
	int32_t result = getHandle(&pEntry, &pPrevEntry, pName);
	switch (result) {
		case 1: {
			pEntry = pEntry->pNext = calloc(1, sizeof(HandleEntry));
			break;
		}
		case 2: {
			printf("Handle table entry has valid filepath, but invalid handle\n");
			err = STUC_ERROR;
			break;
		}
		case 3: {
			printf("No match in handle table\n");
			err = STUC_ERROR;
			break;
		}
	}
	if (pEntry) {
		int32_t nameLength = (int32_t)strlen(pName) + 1;
		pEntry->pName = malloc(nameLength);
		memcpy(pEntry->pName, pName, nameLength);
		return stucMapFileLoad(pStucContext, &pEntry->handle, pFilepath);
	}
	else {
		err = STUC_ERROR;
	}
	return err;
}

StucResult stucBlenderMapFileUnload(char *pName) {
	HandleEntry *pEntry, *pPrevEntry;
	getHandle(&pEntry, &pPrevEntry, pName);
	stucMapFileUnload(pStucContext, pEntry->handle);
	if (!pPrevEntry) {
		free(pEntry->pName);
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
		free(pEntry->pName);
		free(pEntry);
	}
	return STUC_SUCCESS;
}

void stucBlenderQueryCommonAttribs(
	StucMesh *pMesh,
	char *pMap,
	StucCommonAttribList *pCommonAttribs
) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pMap) != 4) {
		printf("Stuc query common attribs failed, specified map not loaded\n");
		return;
	}
	stucQueryCommonAttribs(pStucContext, pEntry->handle, pMesh, pCommonAttribs);
}

static
int32_t makeMapArr(StucBlenderMapArr *pBlendMapArr, StucMapArr *pMapArr) {
	pMapArr->size = pBlendMapArr->count;
	pMapArr->count = pBlendMapArr->count;
	pMapArr->pMatArr = pBlendMapArr->pMatIdxArr;
	pMapArr->ppArr = calloc(pMapArr->size, sizeof(void *));
	for (int32_t i = 0; i < pMapArr->count; ++i) {
		HandleEntry *pEntry, *pPrevEntry;
		if (getHandle(&pEntry, &pPrevEntry, pBlendMapArr->ppArr[i]) != 4) {
			printf("Stuc blender map to mesh failed, specified map not loaded\n");
			return 1;
		}
		pMapArr->ppArr[i] = pEntry->handle;
	}
	return 0;
}

int32_t stucBlenderMapToMesh(
	void **ppJobHandle,
	StucBlenderMapArr *pMapArrPy,
	StucMesh *pMesh,
	StucAttribIndexedArr *pInIndexedAttribs,
	StucMesh *pOutMesh,
	StucAttribIndexedArr *pOutIndexedAttribs,
	StucCommonAttribList *pCommonAttribs,
	float wScale
) {
	printf("face attrib 0 name is %s\n", pMesh->faceAttribs.pArr[0].core.name);
	printf("face attrib 1 name is %s\n", pMesh->faceAttribs.pArr[1].core.name);
	StucMapArr *pMapArr = calloc(1, sizeof(StucMapArr));
	int32_t err = makeMapArr(pMapArrPy, pMapArr);
	if (err) {
		return err;
	}
	//TODO if multiple objects are selected, see if dispatching them all at once on multiple threads
	// improves perf. Probably not a good idea for high res meshes or maps, given the memory use.
	// maybe selectivly do it based on the mesh and map res?
	StucResult result = stucQueueMapToMesh(
		pStucContext,
		ppJobHandle,
		pMapArr,
		pMesh,
		pInIndexedAttribs,
		pOutMesh,
		pOutIndexedAttribs,
		pCommonAttribs,
		wScale
	);
	return result != STUC_SUCCESS;
}

void stucBlenderDestroyCommonAttribs(StucCommonAttribList *pCommonAttribs) {
	stucDestroyCommonAttribs(pStucContext, pCommonAttribs);
}

void stucBlenderCopyMeshCore(StucMesh *stucMesh, StucMesh *workMesh) {
	memcpy(stucMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
	       (stucMesh->faceCount + 1));
	memcpy(stucMesh->pCorners, workMesh->pCorners, sizeof(int32_t) *
	       stucMesh->cornerCount);
	memcpy(stucMesh->vertAttribs.pArr[0].core.pData,
	       workMesh->vertAttribs.pArr[0].core.pData,
	       sizeof(StucVec3) * stucMesh->vertCount);
	//memcpy(stucMesh->pEdges, workMesh->pEdges, sizeof(int32_t) *
	//       stucMesh->cornerCount);
}

static
void copyAttribs(StucAttribArray *pA, StucAttribArray *pB, int32_t dataLen) {
	if (!pA || !pB) {
		return;
	}
	for (int32_t i = 0; i < pA->count; ++i) {
		StucAttrib* pBEntry;
		stucGetAttrib(pA->pArr[i].core.name, pB, &pBEntry);
		if (!pBEntry) {
			printf("Mismatch in workmesh and stucmesh attribs\n");
			abort();
		}
		int32_t attribSize;
		stucGetAttribSize(pA->pArr + i, &attribSize);
		printf("attrib Size == %d\n", attribSize);
		memcpy(pBEntry->core.pData, pA->pArr[i].core.pData, attribSize * dataLen);
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

int32_t stucBlenderMapFileGenPreviewImage(char *pName, int32_t res, float *pImage) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pName) != 4) {
		printf("Stuc blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	StucImage image = {.res = res, .type = STUC_IMAGE_F32};
	stucMapFileGenPreviewImage(pStucContext, pEntry->handle, &image);
	memcpy(pImage, image.pData, res * res * 4 * sizeof(float));
	return 0;
}

int32_t stucBlenderMapMatsGet(StucBlenderMapArr *pMapArr, StucAttribIndexedArr *pMats) {
	StucMapArr mapArr;
	int32_t err = makeMapArr(pMapArr, &mapArr);
	if (err) {
		return err;
	}
	for (int32_t i = 0; i < mapArr.count; ++i) {
		StucAttribIndexedArr indexedAttribs = {0};
		stucMapIndexedAttribsGet(pStucContext, mapArr.ppArr[i], &indexedAttribs);
		for (int32_t j = 0; j < indexedAttribs.count; ++j) {
			StucAttribIndexed *pAttrib = indexedAttribs.pArr + j;
			if (!strncmp("StucMaterials", pAttrib->core.name, STUC_ATTRIB_NAME_MAX_LEN)) {
				pMats->pArr[i] = *pAttrib;
				break;
			}
		}
	}
	return err;
}

int32_t stucBlenderWaitForJobs(
	int32_t count,
	void **ppJobHandles,
	bool wait,
	bool *pDone
) {
	StucResult err = stucWaitForJobs(pStucContext, count, ppJobHandles, wait, pDone);
	if (err != STUC_SUCCESS) {
		return 1;
	}
	if (wait || *pDone) {
		err = stucJobGetErrs(pStucContext, count, &ppJobHandles);
		stucJobDestroyHandles(pStucContext, count, ppJobHandles);
		if (err != STUC_SUCCESS) {
			return 1;
		}
	}
	return 0;
}

void stucBlenderDestroy() {
	stucContextDestroy(pStucContext);
	return;
}