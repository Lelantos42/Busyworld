class_name Agent
extends Node2D
# One AI citizen's body in the world. Visuals + movement; the "mind" lives in the
# Python brain. Y-sorted by its own position (origin at the feet).

signal arrived(agent: Agent)

const FRAME_W := 48
const FRAME_H := 68

var id := ""
var agent_name := ""
var title := ""
var role := ""
var personality := ""
var home_name := ""
var workplace_name := ""

var speed := 64.0
var facing := "down"
var current_action := "idle"
var mood := "content"
var energy := 100.0

var _path: PackedVector2Array = PackedVector2Array()
var _path_i := 0
var _moving := false
var _final_target := Vector2.ZERO

var world                              # set by World on spawn (for pathfinding)
var _spr: AnimatedSprite2D
var _name_lbl: Label
var _bubble: Panel
var _bubble_lbl: Label
var _bubble_timer := 0.0
var _think_cooldown := 0.0             # set by World decision pacing

func setup(data: Dictionary, sheet: Texture2D, move_speed: float) -> void:
	id = data.get("id", "")
	agent_name = data.get("name", "Citizen")
	title = data.get("title", "")
	role = data.get("role", "")
	personality = data.get("personality", "")
	home_name = data.get("home", "")
	workplace_name = data.get("workplace", "")
	speed = move_speed
	_build_visual(sheet)

func _build_visual(sheet: Texture2D) -> void:
	_spr = AnimatedSprite2D.new()
	_spr.sprite_frames = CharacterFrames.build(sheet)
	_spr.centered = false
	_spr.offset = Vector2(-FRAME_W / 2.0, -FRAME_H + 4)   # feet ~ at origin
	add_child(_spr)
	_play("idle")

	# nameplate
	_name_lbl = Label.new()
	_name_lbl.text = agent_name
	_name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_name_lbl.position = Vector2(-70, -84)
	_name_lbl.size = Vector2(140, 16)
	_name_lbl.add_theme_font_size_override("font_size", 11)
	_name_lbl.add_theme_color_override("font_color", Color(1, 1, 1))
	_name_lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_name_lbl.add_theme_constant_override("outline_size", 5)
	add_child(_name_lbl)

	# speech bubble (hidden until speak())
	_bubble = Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.99, 0.98, 0.93, 0.97)
	sb.set_corner_radius_all(7)
	sb.set_border_width_all(2)
	sb.border_color = Color(0.2, 0.2, 0.25, 0.9)
	sb.set_content_margin_all(6)
	_bubble.add_theme_stylebox_override("panel", sb)
	_bubble.position = Vector2(-78, -150)
	_bubble.size = Vector2(156, 54)
	_bubble.visible = false
	add_child(_bubble)
	_bubble_lbl = Label.new()
	_bubble_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_bubble_lbl.size = Vector2(144, 42)
	_bubble_lbl.position = Vector2(6, 5)
	_bubble_lbl.add_theme_font_size_override("font_size", 11)
	_bubble_lbl.add_theme_color_override("font_color", Color(0.12, 0.12, 0.16))
	_bubble.add_child(_bubble_lbl)

func _process(dt: float) -> void:
	if _think_cooldown > 0.0:
		_think_cooldown -= dt
	if _bubble_timer > 0.0:
		_bubble_timer -= dt
		if _bubble_timer <= 0.0:
			_bubble.visible = false
	if _moving:
		_advance(dt)
	energy = max(0.0, energy - dt * 0.15)

func _advance(dt: float) -> void:
	if _path_i >= _path.size():
		_stop_moving()
		return
	var target: Vector2 = _path[_path_i]
	var to := target - position
	var dist := to.length()
	var step := speed * dt
	if dist <= step:
		position = target
		_path_i += 1
		if _path_i >= _path.size():
			_stop_moving()
	else:
		var dir := to / dist
		position += dir * step
		_update_facing(dir)
		_play("walk")

func _stop_moving() -> void:
	_moving = false
	current_action = "idle"
	_play("idle")
	emit_signal("arrived", self)

func _update_facing(dir: Vector2) -> void:
	if abs(dir.x) > abs(dir.y):
		facing = "right" if dir.x > 0 else "left"
	else:
		facing = "down" if dir.y > 0 else "up"

func _play(base: String) -> void:
	var anim := base + "_" + facing
	if _spr.sprite_frames.has_animation(anim) and _spr.animation != anim:
		_spr.play(anim)
	elif not _spr.is_playing():
		_spr.play(anim)

# ---- public API used by World --------------------------------------------
func go_to(target: Vector2) -> void:
	_final_target = target
	if world == null:
		return
	var p: PackedVector2Array = world.find_path(position, target)
	if p.size() <= 1:
		# already there / no route: just face the target and idle
		_stop_moving()
		return
	_path = p
	_path_i = 1   # skip the start cell
	_moving = true
	current_action = "walking"

func stop() -> void:
	_path = PackedVector2Array()
	_moving = false
	current_action = "idle"
	_play("idle")

func face_point(p: Vector2) -> void:
	var d := p - position
	if d.length() > 1.0:
		_update_facing(d.normalized())
		_play("idle")

func speak(text: String, seconds: float = 5.0) -> void:
	if text.strip_edges() == "":
		return
	_bubble_lbl.text = text
	_bubble.visible = true
	_bubble_timer = seconds

func set_mood(m: String) -> void:
	mood = m

func is_moving() -> bool:
	return _moving

func can_think() -> bool:
	return _think_cooldown <= 0.0

func set_think_cooldown(s: float) -> void:
	_think_cooldown = s
