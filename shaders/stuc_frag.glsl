#define PI 3.14159265359
#define MIN 1.0e-6
#define SPEC_SAMPLES 128

float trowbridgeReitzGgx(float a, vec3 n, vec3 h) {
	float a2 = a * a;
	float noh = max(dot(n, h), .0f);
	float base = noh * noh * (a2 - 1.0f) + 1.0f;
	float denom = PI * base * base;
	return a2 / denom;
}

float geoSchlickGgx(float nov, float a) {
	float aP1 = a + 1.0f;
	float a2 = (aP1 * aP1) / 8.0f;
	return nov / (nov * (1.0f - a2) + a2);
}

float geoSmith(float hov, float a) {
	float geo = geoSchlickGgx(hov, a);
	return 1.0f / (1.0f + geo * geo);
}

vec3 fresnelSchlick(vec3 refl, float voh) {
	return refl + (1.0f - refl) * pow(clamp(1.0f - voh, .0f, 1.0f), 5.0f);
}

vec2 dirToUv(vec3 dir) {
	return vec2(-atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
}

vec3 sampleEnvSpec(
	vec3 v,
	vec3 l,
	vec3 n,
	vec3 albedo,
	float metal,
	float a
) {
	float a2 = a * a;
	a2 = a; //<- testing without a2
	vec3 h = normalize(l + v);
	float hov = max(dot(h, v), .0f);

	float d = trowbridgeReitzGgx(a2, h, l);
	vec3 f0 = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		hov
	);
	float g = geoSmith(hov, a2);

	float nol = max(dot(n, l), .0f);
	float nov = max(dot(n, v), .0f);
	float noh = max(dot(n, h), .0f);

	float denom = 4.0f * nol * nov + MIN;
	vec3 brdf = d * f0 * g / denom;

	float pdf = d * noh / (4.0f * hov) + MIN;

	float mip = a >= 1.0f ? 100.0f : -2.0f / log(a) - 1.0f;
	mip = clamp(mip, .0f, 6.0f);
	vec3 lightCol = textureLod(envTex, dirToUv(l), mip).xyz;

	return dot(n, l) >= .0f ? brdf / pdf * lightCol * nol : vec3(.0f);
}

vec3 calcAmbient(vec3 v, vec3 normal, vec3 albedo, float metal, float rough, vec3 spec) {
	vec3 f0 = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		max(dot(normal, v), .0f)
	);
	vec3 irr = texture(envTexConv, dirToUv(normal)).xyz;
	return (1.0f - f0 * spec) * irr * albedo * (1.0f - metal);
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

vec3 calcLights(vec3 v, vec3 n, vec3 albedo, float metal, float a) {
	mat3 rMat;
	vec3 r = reflect(-v, n);
	{
		vec3 up = vec3(.0f, .0f, 1.0f);
		up = up == r ? normalize(vec3(.5f, .0f, .5f)) : up;
		vec3 right = normalize(cross(up, r));
		up = normalize(cross(r, right));
		rMat = mat3(right, up, r);
	}
	a = max(a * 1.5f, .01);
	vec3 light = vec3(.0f);
	float halfPi = PI / 2.0f;
	float rand = randFromDir(r);
	for (int i = 0; i < SPEC_SAMPLES; ++i) {
		vec2 sampleUv = hammersley2d(i + 1, SPEC_SAMPLES + 1);
		float phi = 2.0f * PI * sampleUv.x + rand;
		float a2 = a * a;
		float cosTheta = sqrt((1.0f - sampleUv.y) / (1.0f + (a2 * a2 - 1.0f) * sampleUv.y));
		float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 l = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		l = rMat * normalize(l);

		vec3 spec = sampleEnvSpec(v, l, n, albedo, metal, a);
		light += spec;
	}
	return light / float(SPEC_SAMPLES);
}

void main() {
	vec3 v = normalize(v_viewPos - v_pos);

	vec3 albedo = texture(albedoTex, v_uv).xyz;
	albedo = mix(matInfo.albedoUniform, albedo, matInfo.albedoUseTex);
	float metal = texture(metalTex, v_uv).x;
	metal = mix(matInfo.metalUniform, metal, matInfo.metalUseTex);
	float rough = texture(roughTex, v_uv).x;
	rough = mix(matInfo.roughUniform, rough, matInfo.roughUseTex);

	vec3 light = calcLights(v, v_normal, albedo, metal, rough);
	vec3 ambient = calcAmbient(v, v_normal, albedo, metal, rough, light);

	vec3 col = light + ambient;
	col = col / (col + vec3(1.0f));
	FragColor = vec4(col, 1.0f);
}