void main() {
	v_pos = position;
	v_normal = normal;
	v_uv = uv;
	v_lightDir = lightDir;
	v_viewPos = viewPos;
	v_albedo = vec3(.4, .1, .01);
	s_metal = .0f;
	s_rough = .2f;

	//vec3 viewDir = normalize(v_viewPos - v_pos);
	gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);
}