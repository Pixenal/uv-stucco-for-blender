#define PI 3.14159265359
#define MIN 1.0e-6
#define SPEC_SAMPLES 64

float geoSchlickGgx(float nov, float a) {
	float a2 = (a * a) / 2.0f;
	return nov / (nov * (1.0f - a2) + a2);
}

float geoSmith(float nov, float nol, float a) {
	return geoSchlickGgx(nov, a) * geoSchlickGgx(nol, a);
}

vec3 fresnelSchlick(vec3 refl, float voh) {
	return refl + (1.0f - refl) * pow(clamp(1.0f - voh, .0f, 1.0f), 5.0f);
}

vec2 dirToUv(vec3 dir) {
	return vec2(-atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
}

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

//hammersley set, see https://holger.dammertz.org/stuff/notes_HammersleyOnHemisphere.html
vec2 hammersley2d(uint i, uint num) {
	return vec2(float(i) / float(num), radicalInvVdc(i));
}

uint fnvHash(uint value, uint size) {
	uint hash = 2166136261;
	for (int i = 0; i < 4; ++i) {
		uint byte = (value >> 8 * i) & 0xFF;
		hash ^= byte;
		hash *= 16777619;
	}
	return hash % size;
}

float randFromDir(vec3 dir) {
	vec3 dirAbs = abs(dir);
	const uint iSize= 1048583u;
	const float fSize = float(iSize);
	uint iRand =
		fnvHash(uint(dirAbs.x * fSize) * iSize, iSize) +
		fnvHash(uint(dirAbs.y * fSize) * iSize, iSize) +
		fnvHash(uint(dirAbs.z * fSize) * iSize, iSize);
	return float(iRand % iSize) / fSize * 2.0f * float(PI);
}

mat3 matrixForN(vec3 t, vec3 b, vec3 n) {
	vec3 left = cross(t == n ? b : t, n);
	vec3 right = cross(left, n);
	return mat3(right, left, n);
}

vec3 calcLights(vec3 v, mat3 tbn, vec3 n, vec3 albedo, float metal, float a) {
	vec3 r = reflect(-v, n);
	mat3 nMat = matrixForN(tbn[0], tbn[1], n);
	vec3 light = vec3(.0f);
	float halfPi = PI / 2.0f;
	float rand = randFromDir(r);
	float a2 = a * a;

	float mip = a >= 1.0f ? 100.0f : -2.0f / log(a) - 1.0f;
	mip = clamp(mip, .0f, 6.0f);
	mip = .0f;

	vec3 fDiff = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		max(dot(n, v), .0f)
	);

	for (int i = 0; i < SPEC_SAMPLES; ++i) {
		vec2 xi = hammersley2d(i + 1, SPEC_SAMPLES + 1);
		float phi = xi.y * 2.0f * PI + rand;

		float cosTheta = sqrt((1.0f - xi.x) / (1.0f + (a2 * a2 - 1.0f) * xi.x));
		float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 h = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		h = nMat * normalize(h);
		vec3 lSpec = reflect(-v, h);

		cosTheta = 1.0f - xi.x;
		sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 lDiff = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		lDiff = nMat * normalize(lDiff);

		vec3 spec = sampleEnvSpec(h, v, lSpec, n, albedo, metal, a2, mip);
		vec3 diff = textureLod(envTex, dirToUv(lDiff), mip).xyz * 4.0f * max(dot(n, lDiff), .0f);
		diff = diff * albedo * (1.0f - metal);
		light += spec + diff;
	}
	return light / float(SPEC_SAMPLES);
}

vec3 v3SwizzleChannel(vec4 vec, int channel) {
	if (channel == -1) {
		return vec.xyz;
	}
	if (channel >= 0 && channel <= 3) {
		return vec3(vec[channel]);
	}
	return vec3(1.0f, .0f, 1.0f);
}

float fSwizzleChannel(vec4 vec, int channel) {
	if (channel == -1) {
		return vec.x;
	}
	if (channel >= 0 && channel <= 3) {
		return vec[channel];
	}
	return 1.0f;
}

vec3 normalizeToRange(vec3 col, float min, float max) {
	return (col - min) / (max - min);
}

vec3 denormalizeFromRange(vec3 col, float min, float max) {
	return col * (max - min) + min;
}

void main() {
	vec3 v = normalize(v_viewPos - v_pos);

	vec3 albedo = v3SwizzleChannel(texture(albedoTex, v_uv), int(matInfo.albedoChannel));
	albedo = mix(matInfo.albedoUniform, albedo, matInfo.albedoUseTex);
	vec3 normal = texture(normalTex, v_uv).xyz;
	//normal.y = 1.0f - normal.y;
	normal = mix(vec3(.5f, .5f, 1.0f), normal, matInfo.normalUseTex);
	normal = normal * 2.0f - 1.0f;
	normal = m_tbn * normal;
	float metal = fSwizzleChannel(texture(metalTex, v_uv), int(matInfo.metalChannel));
	metal = mix(matInfo.metalUniform, metal, matInfo.metalUseTex);
	float rough = fSwizzleChannel(texture(roughTex, v_uv), int(matInfo.roughChannel));
	rough = mix(matInfo.roughUniform, rough, matInfo.roughUseTex);

	vec3 col = calcLights(v, m_tbn, normal, albedo, metal, rough);

	//col = normalizeToRange(log2(col / .18), -10, 15);
	//col = texture(tmLut, col).xyz;
	//col = pow(col, vec3(2.4f));
	col = col / (col + vec3(1.0f));
	FragColor = vec4(vec3(col), 1.0f);
}