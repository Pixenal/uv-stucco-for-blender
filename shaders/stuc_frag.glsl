/*
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

//included maunually on shader load
#include "stuc_utils.glsl"
#include "stuc_pbr.glsl"
#include "stuc_tool.glsl"

void main() {
	float time;
#ifdef USE_TIME
	time = matInfo.time;
#else
	{
		float a = atan(m_viewMat[2].y, m_viewMat[2].x);
		float b = atan(m_viewMat[2].y, m_viewMat[2].z);
		time = (sin(a) * sin(b)) * .5f + .5f;
		time *= 60.0f;
	}
#endif

	vec3 v = normalize(v_viewPos - v_pos);
	vec3 viewUvw = vec3(gl_FragCoord.xy / v_viewRes, 1.0f);
	float aspect = v_viewRes.x / v_viewRes.y;
	
	vec4 v4Albedo = texture(albedoTex, v_uv);
	vec3 albedo = v3SwizzleChannel(v4Albedo, int(matInfo.albedoChannel));
	albedo = mix(matInfo.albedoUniform, albedo, matInfo.albedoUseTex);
	vec3 normal = texture(normalTex, v_uv).xyz;
	if (matInfo.flipY == 1.0f) {
		normal.y = 1.0f - normal.y;
	}
	normal = mix(vec3(.5f, .5f, 1.0f), normal, matInfo.normalUseTex);
	normal = m_tbn * (normal * 2.0f - 1.0f);
	normal *= float(gl_FrontFacing) * 2.0f - 1.0f;
	float metal = fSwizzleChannel(texture(metalTex, v_uv), int(matInfo.metalChannel));
	metal = mix(matInfo.metalUniform, metal, matInfo.metalUseTex);
	float rough = fSwizzleChannel(texture(roughTex, v_uv), int(matInfo.roughChannel));
	rough = mix(matInfo.roughUniform, rough, matInfo.roughUseTex);

	vec3 col = .000000001f * (albedo + normal + vec3(metal, rough, .0f) + v);

	bool selFace = matInfo.isEditMode == 1.0f && i_select == 1;

	bool textOuter = false;
	bool textInner = false;
	vec3 errCol = vec3(.0f);
	vec3 crystal = vec3(.0f);
	float sinTimeSlow = sin(time / 45.0f * PI);
	{
		crystal = mod(v_pos + sinTimeSlow, vec3(1.0f));
		vec3 crystalRefl = mod(reflect(normalize(-v), crystal), vec3(.5f)) * 2.0f;
		crystal = normalize(cross(crystal, crystalRefl));
	}
	vec3 sparkles = vec3(.0f);
	vec3 selCol = vec3(227.0f, 62.0f, 191.0f) / vec3(255.0f);
	if (matInfo.error != .0f) {
		sparkles = makeErrMat(v_pos, m_tbn, m_viewMat, v, viewUvw.xy, aspect, time, selFace);
		albedo = vec3(.0f);
		metal = 1.0f;
		rough = .0f;
	}
	switch (i_matParam) {
		case 0:
			col += albedo;
			break;
		case 1:
			normal.y = -normal.y;
			normal = normal * .5f + .5f;
			col += normal;
			break;
		case 2:
			col += vec3(.0f, rough, metal);
			break;
		default:
			if (v4Albedo.w < .5) {
				discard;
			}
			//modify this func in stuc_pbr.glsl to adjust viewport look
			col = calcLight(viewUvw, v, m_tbn, normal, albedo, metal, rough);
			col = tnReinhard(col);
	}
	if (matInfo.error != 0.0f) {
		col += sparkles;
	}
	float luminance = .2126f * sparkles.x + .7152 * sparkles.y + .0722 * sparkles.z;
	col = mix(mix(selCol * .5f, selCol, pow(luminance, .25f)), col, selFace ? .5f : 1.0f);
	FragColor = vec4(col, 1.0f);
}