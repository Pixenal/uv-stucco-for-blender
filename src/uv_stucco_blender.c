/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define HANDLE_TABLE_SIZE 64
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

#include <uv_stucco_blender.h>


typedef struct HandleEntry {
	struct HandleEntry *pNext;
	StucMap handle;
	char *pName;
} HandleEntry;
static HandleEntry handleTable[HANDLE_TABLE_SIZE];

static StucContext pStucCtx;

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
int32_t getHandle(HandleEntry **pEntry, HandleEntry **pPrevEntry, const char *pName) {
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

static
void mapFileDestroy(const char *pName) {
	HandleEntry *pEntry, *pPrevEntry;
	getHandle(&pEntry, &pPrevEntry, pName);
	stucMapFileUnload(pStucCtx, pEntry->handle);
	if (pEntry->pName) {
		free(pEntry->pName);
		pEntry->pName = NULL;
	}
	if (!pPrevEntry) {
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
		free(pEntry);
	}
}

static
StucErr handleTableDestroy() {
	for (int32_t i = 0; i < HANDLE_TABLE_SIZE; ++i) {
		HandleEntry *pEntry = handleTable + i;
		if (pEntry->handle) {
			stucMapFileUnload(pStucCtx, pEntry->handle);
		}
		pEntry = pEntry->pNext;
		while (pEntry) {
			if (pEntry->handle) {
				stucMapFileUnload(pStucCtx, pEntry->handle);
			}
			HandleEntry *pNext = pEntry->pNext;
			free(pEntry);
			pEntry = pNext;
		};
	}
	return PIX_ERR_SUCCESS;
}

void stucBlenderInit() {
	stucContextInit(&pStucCtx, NULL, NULL, NULL, NULL, NULL);
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

StucErr stucBlenderMapFileExport(
	const char *pFilepath,
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
		pStucCtx,
		pFilepath,
		objCount,
		pObjArr,
		usgCount,
		pUsgArr,
		pIndexedAttribs
	);
}
StucErr stucBlenderMapFileLoadForEdit(
	const char *pName,
	int32_t *pObjCount,
	StucObject **ppObjArr,
	int32_t *pUsgCount,
	StucUsg **ppUsgArr,
	int32_t *pFlatCutoffCount,
	StucObject **ppFlatCutoffArr,
	StucAttribIndexedArr *pIndexedAttribs
) {
	return stucMapFileLoadForEdit(
		pStucCtx,
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

StucErr stucBlenderMapFileLoad(const char *pFilepath, const char *pName) {
	HandleEntry *pEntry = NULL;
	HandleEntry *pPrevEntry = NULL;
	int32_t result = getHandle(&pEntry, &pPrevEntry, pName);
	switch (result) {
		case 1: {
			pEntry = pEntry->pNext = (HandleEntry *)calloc(1, sizeof(HandleEntry));
			break;
		}
		case 2: {
			printf("Handle table entry has valid filepath, but invalid handle\n");
			return PIX_ERR_ERROR;
		}
		case 3: {
			printf("No match in handle table\n");
			return PIX_ERR_ERROR;
		}
	}
	if (!pEntry) {
		return PIX_ERR_ERROR;
	}
	StucErr err = stucMapFileLoad(pStucCtx, &pEntry->handle, pFilepath);
	if (err != PIX_ERR_SUCCESS) {
		return err;
	}
	int32_t nameLength = (int32_t)strlen(pName) + 1;
	pEntry->pName = (char *)calloc(nameLength, 1);
	memcpy(pEntry->pName, pName, nameLength);
	return PIX_ERR_SUCCESS;
}

StucErr stucBlenderMapFileUnload(const char *pName) {
	HandleEntry *pEntry = NULL;
	HandleEntry *pPrevEntry = NULL;
	int32_t result = getHandle(&pEntry, &pPrevEntry, pName);
	switch (result) {
	case 1: {
		pEntry = pEntry->pNext = (HandleEntry *)calloc(1, sizeof(HandleEntry));
		break;
	}
	case 2: {
		printf("Handle table entry has valid filepath, but invalid handle\n");
		return PIX_ERR_ERROR;
	}
	case 3: {
		printf("No match in handle table\n");
		return PIX_ERR_ERROR;
	}
	}
	if (!pEntry) {
		return PIX_ERR_ERROR;
	}
	return stucMapFileUnload(pStucCtx, pEntry->handle);
}

void stucBlenderQueryCommonAttribs(
	StucMesh *pMesh,
	const char *pMap,
	StucCommonAttribList *pCommonAttribs
) {
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pMap) != 4) {
		return;
	}
	stucQueryCommonAttribs(pStucCtx, pEntry->handle, pMesh, pCommonAttribs);
}

static
int32_t makeMapArr(StucBlenderMapArr *pBlendMapArr, StucMapArr *pMapArr) {
	if (!pBlendMapArr->count) {
		return 1;
	}
	pMapArr->size = pBlendMapArr->count;
	pMapArr->count = pBlendMapArr->count;
	pMapArr->pMatArr = pBlendMapArr->pMatIdxArr;
	pMapArr->ppArr = calloc(pMapArr->size, sizeof(void *));
	for (int32_t i = 0; i < pMapArr->count; ++i) {
		HandleEntry *pEntry, *pPrevEntry;
		if (getHandle(&pEntry, &pPrevEntry, pBlendMapArr->ppArr[i]) != 4) {
			return 1;
		}
		pMapArr->ppArr[i] = pEntry->handle;
	}
	pMapArr->pCommonAttribArr = pBlendMapArr->pCommonAttribArr;
	return 0;
}

int32_t stucBlenderMapToMesh(
	void **ppJobHandle,
	StucBlenderMapArr *pMapArrPy,
	StucMesh *pMesh,
	StucAttribIndexedArr *pInIndexedAttribs,
	StucMesh *pOutMesh,
	StucAttribIndexedArr *pOutIndexedAttribs,
	float wScale,
	float receiveLen
) {
	StucMapArr *pMapArr = calloc(1, sizeof(StucMapArr));
	int32_t err = makeMapArr(pMapArrPy, pMapArr);
	if (err) {
		return 2;
	}
	StucErr result = stucQueueMapToMesh(
		pStucCtx,
		ppJobHandle,
		pMapArr,
		pMesh,
		pInIndexedAttribs,
		pOutMesh,
		pOutIndexedAttribs,
		wScale,
		receiveLen
	);
	return result != PIX_ERR_SUCCESS;
}

void stucBlenderDestroyCommonAttribs(StucCommonAttribList *pCommonAttribs) {
	stucDestroyCommonAttribs(pStucCtx, pCommonAttribs);
}

void stucBlenderCopyMeshCore(StucMesh *stucMesh, StucMesh *workMesh) {
	memcpy(stucMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
	       (stucMesh->faceCount + 1));
	memcpy(stucMesh->pCorners, workMesh->pCorners, sizeof(int32_t) *
	       stucMesh->cornerCount);
	memcpy(stucMesh->vertAttribs.pArr[0].core.pData,
	       workMesh->vertAttribs.pArr[0].core.pData,
	       sizeof(Stuc_V3_F32) * stucMesh->vertCount);
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
		stucGetAttribSize(&pA->pArr[i].core, &attribSize);
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

StucErr stucBlenderObjArrDestroy(int32_t objCount, StucObject *pObjArr) {
	return stucObjArrDestroy(pStucCtx, objCount, pObjArr);
}

StucErr stucBlenderUsgArrDestroy(int32_t count, StucUsg *pUsgArr) {
	return stucUsgArrDestroy(pStucCtx, count, pUsgArr);
}

void stucBlenderMeshDestroy(StucMesh *pMesh) {
	stucMeshDestroy(pStucCtx, pMesh);
}

int32_t stucBlenderMapMatsGet(StucBlenderMapArr *pMapArr, StucAttribIndexedArr *pMats) {
	StucMapArr mapArr;
	int32_t err = makeMapArr(pMapArr, &mapArr);
	if (err) {
		return err;
	}
	for (int32_t i = 0; i < mapArr.count; ++i) {
		StucAttribIndexedArr indexedAttribs = {0};
		stucMapIndexedAttribsGet(pStucCtx, mapArr.ppArr[i], &indexedAttribs);
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
	StucErr err = stucWaitForJobs(pStucCtx, count, ppJobHandles, wait, pDone);
	if (err != PIX_ERR_SUCCESS) {
		return 1;
	}
	if (wait || *pDone) {
		err = stucJobGetErrs(pStucCtx, count, &ppJobHandles);
		stucJobDestroyHandles(pStucCtx, count, ppJobHandles);
		if (err != PIX_ERR_SUCCESS) {
			return 1;
		}
	}
	return 0;
}

void stucBlenderDestroy() {
	handleTableDestroy();
	stucContextDestroy(pStucCtx);
	return;
}
