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
	ruvmContextInit(&pRuvmContext, NULL, NULL, NULL);
}

void ruvmBlenderMapFileExport(RuvmMesh *pMesh, float *pNormals) {
	pMesh->pNormals = (RuvmVec3 *)pNormals;
	ruvmMapFileExport(pRuvmContext, pMesh);
}

void ruvmBlenderMapFileLoad(char *pFilePath) {
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
	ruvmMapFileLoad(pRuvmContext, &pEntry->handle, pFilePath);
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

int32_t ruvmBlenderMapToMesh(char *pFilePath, RuvmMesh *pMesh, int32_t *pEdges,
                          float *pNormals, RuvmMesh *pWorkMesh) {
	pMesh->pNormals = (RuvmVec3 *)pNormals;
	pMesh->pEdges = pEdges;
	HandleEntry *pEntry, *pPrevEntry;
	if (getHandle(&pEntry, &pPrevEntry, pFilePath) != 4) {
		printf("Ruvm blender map to mesh failed, specified map not loaded\n");
		return 1;
	}
	return ruvmMapToMesh(pRuvmContext, pEntry->handle, pMesh, pWorkMesh);
}

void ruvmBlenderUpdateMesh(RuvmMesh *ruvmMesh, RuvmMesh *workMesh, float **ppOutNormals) {
	memcpy(ruvmMesh->pVerts, workMesh->pVerts, sizeof(RuvmVec3) *
			ruvmMesh->vertCount);
	memcpy(ruvmMesh->pLoops, workMesh->pLoops, sizeof(int32_t) *
			ruvmMesh->loopCount);
	memcpy(ruvmMesh->pFaces, workMesh->pFaces, sizeof(int32_t) *
			(ruvmMesh->faceCount + 1));
	*ppOutNormals = (float *)workMesh->pNormals;
}

void ruvmBlenderUpdateMeshUv(RuvmMesh *ruvmMesh, RuvmMesh *workMesh) {
	memcpy(ruvmMesh->pUvs, workMesh->pUvs, sizeof(RuvmVec2) *
			ruvmMesh->loopCount);
}

void ruvmBlenderMeshDestroy(RuvmMesh *pMesh) {
	ruvmMeshDestroy(pRuvmContext, pMesh);
}
