void main() {
	v_pos = position;
	v_normal = normal;
	v_uv = uv;
	v_viewPos = viewPos;

	//vec3 viewDir = normalize(v_viewPos - v_pos);
	gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);
}