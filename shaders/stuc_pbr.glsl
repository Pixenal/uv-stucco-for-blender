/*
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

/*
modify this shader to change how stuc meshes are presented in viewport.
func 'calcLight' is called from 'main' in stuc_frag.glsl,
and tonemapping (Reinhard) is applied straight after.

see https://learnopengl.com/PBR/Theory for a great intro on what's going on in this file.
*/

//note, stuc_utils.glsl is included before this file in stuc_frag.glsl

#define MIN 1.0e-6
#define SPEC_SAMPLE_COUNT 64
#define DIFF_SAMPLE_COUNT 128

//see fresnelSchlick cit,
//referenced also in ue4 presentation cited futher down
float geoSchlickGgx(float nov, float a) {
	float a2 = (a * a) / 2.0f;
	return nov / (nov * (1.0f - a2) + a2);
}

//Smith model,
//https://ieeexplore.ieee.org/document/1138991
// *no accessible source afaik
float geoSmith(float nov, float nol, float a) {
	return geoSchlickGgx(nov, a) * geoSchlickGgx(nol, a);
}

//"An Inexpensive BRDF Model for Physically-based Rendering" Schlick 1994:
//https://onlinelibrary.wiley.com/doi/10.1111/1467-8659.1330233
// *accessible pdf at:
//  https://wiki.jmonkeyengine.org/docs/3.8/tutorials/_attachments/Schlick94.pdf
vec3 fresnelSchlick(vec3 refl, float voh) {
	return refl + (1.0f - refl) * pow(clamp(1.0f - voh, .0f, 1.0f), 5.0f);
}

//Cook-Torrance microfacet model, with D term omitted as we're using ibl only
//"A Reflectance Model For Computer Graphics" Cook, Torrance 1982:
//https://dl.acm.org/doi/epdf/10.1145/357290.357293
vec3 sampleEnvSpec(
	vec3 h,
	vec3 v,
	vec3 l,
	vec3 n,
	vec3 albedo,
	float metal,
	float a2,
	float mip
) {
	float hov = max(dot(h, v), .0f);
	float nol = max(dot(n, l), .0f);
	float nov = max(dot(n, v), .0f);
	float noh = max(dot(n, h), .0f);

	vec3 f0 = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		hov
	);
	float g = geoSmith(nov, nol, a2);
	float denom = 4.0f * noh * nov + MIN;
	vec3 brdf = f0 * g / denom;

	vec3 light = textureLod(envTex, dirToUv(l), mip).xyz * 4.0f;
	return brdf * light * nol;
}

float radicalInvVdc(uint i) {
	i = (i << 16u) | (i >> 16u);
	i = ((i & 0x55555555u) << 1u) | ((i & 0xAAAAAAAAu) >> 1u);
	i = ((i & 0x33333333u) << 2u) | ((i & 0xCCCCCCCCu) >> 2u);
	i = ((i & 0x0F0F0F0Fu) << 4u) | ((i & 0xF0F0F0F0u) >> 4u);
	i = ((i & 0x00FF00FFu) << 8u) | ((i & 0xFF00FF00u) >> 8u);
	return float(i) * 2.3283064365386963e-10;
}

// *see below cit for above func aswell
//Hammersley set, see https://holger.dammertz.org/stuff/notes_HammersleyOnHemisphere.html
vec2 hammersley2d(uint i, uint num) {
	return vec2(float(i) / float(num), radicalInvVdc(i));
}

const float mipTable[11] = float[11](
	0.0f,
	1.0f,
	3.0f,
	4.0f,
	4.0f,
	4.0f,
	5.0f,
	5.0f,
	6.0f,
	6.0f,
	6.0f
);

//based on Brian Karis's 2013 presentation on ue4's pbr shader:
//https://cdn2.unrealengine.com/Resources/files/2013SiggraphPresentationsNotes-26915738.pdf
// *modified to remove prebaked elements
vec3 calcLight(vec3 viewUvw, vec3 v, mat3 tbn, vec3 n, vec3 albedo, float metal, float a) {
	mat3 nMat = matrixForN(tbn[0], tbn[1], n);
	vec3 light = vec3(.0f);
	vec3 rand = randFromVec(abs(viewUvw + v));
	a = clamp(a, .01f, .99f);
	float a2 = a * a;

	const int ia = int(a * 10.0f);
	const float mip = mix(mipTable[ia], mipTable[ia + 1], a * 10.0f - float(ia));
    
	vec3 specSum = vec3(.0f);
    vec3 diffSum = vec3(.0f);
	for (int i = 0; i < SPEC_SAMPLE_COUNT; ++i) {
		vec2 xi = hammersley2d(uint(i + 1), uint(SPEC_SAMPLE_COUNT + 1));
		xi += vec2(rand.x * -.125f, rand.y);
		float phi = (xi.y) * 2.0f * PI;
		const float cosTheta = sqrt((1.0f - xi.x) / (1.0f + (a2 * a2 - 1.0f) * xi.x));
		const float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 h = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		h = nMat * normalize(h);
		const vec3 lSpec = reflect(-v, h);
		specSum += sampleEnvSpec(h, v, lSpec, n, albedo, metal, a2, mip);
	}
	for (int i = 0; i < DIFF_SAMPLE_COUNT; ++i) {
		vec2 xi = hammersley2d(uint(i + 1), uint(DIFF_SAMPLE_COUNT + 1));
		xi += vec2(rand.z * -.125f, rand.x);
		const float phi = (xi.y) * 2.0f * PI;
		const float cosTheta = 1.0f - xi.x;
		const float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 lDiff = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		lDiff = nMat * lDiff;
		const float nol = max(dot(n, lDiff), .0f);
		diffSum += textureLod(envTex, dirToUv(lDiff), 5.0f).xyz * 2.5f * nol;
	}
	return
        diffSum / float(DIFF_SAMPLE_COUNT) * albedo * (1.0f - metal) +
        specSum / float(SPEC_SAMPLE_COUNT);
}