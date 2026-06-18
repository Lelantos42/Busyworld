extends Node2D
# Busyworld main scene. Authoritative for *physical* world state (space + time).
# The Python brain is authoritative for each citizen's *mind* + economy.

const AGENT_SCRIPT := preload("res://scripts/Agent.gd")
const HUD_SCRIPT := preload("res://scripts/HUD.gd")

var town: Dictionary
var tile := 32
var map_px := Vector2(3328, 2816)
var earshot := 130.0
var move_speed := 64.0

var astar := AStarGrid2D.new()
var entities: Node2D
var camera: Camera2D
var canvas_mod: CanvasModulate
var hud

var agents: Dictionary = {}            # id -> Agent
var meta: Dictionary = {}              # id -> per-agent decision bookkeeping
var places: Array = []
var place_by_name: Dictionary = {}

const DOOR_SCRIPT := preload("res://scripts/DoorNode.gd")
var interiors: Dictionary = {}         # place name -> {bounds, walk, entry, center, door, zoom}
var ext_doors: Dictionary = {}         # place name -> DoorNode (exterior)
var interiors_root: Node2D
var focused_interior := ""
var _town_cam_pos := Vector2.ZERO
var _town_cam_zoom := Vector2.ONE

var vision_ids: Array = []             # citizens whose models can see (from the brain)
var _pov_vp: SubViewport
var _pov_cam: Camera2D

# clock
var hour := 8.0
var day := 1
var day_length := 300.0
var treasury := 500                    # founder's simulated incentive pool

# screenshots
var _shot_accum := 0.0
var _shots_taken := 0
var _life := 0.0

# camera control
var _drag := false

func _ready() -> void:
	randomize()
	town = GameConfig.town
	tile = int(town.get("tile", 32))
	var mp: Array = town.get("map_px", [3328, 2816])
	map_px = Vector2(mp[0], mp[1])
	earshot = float(GameConfig.get_w("earshot_px", 130.0))
	move_speed = float(GameConfig.get_w("move_speed", 64.0))
	day_length = float(GameConfig.get_w("day_length_sec", 300.0))
	hour = float(GameConfig.get_w("start_hour", 8.0))

	_build_places()
	entities = Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	add_child(entities)

	var solids: Array = TownBuilder.build(self, entities, town)
	_build_navgrid(solids)
	_build_interiors()
	_setup_camera()
	_setup_pov()
	_setup_daynight()
	_setup_hud()

	Net.message.connect(_on_net_message)
	Net.connected.connect(_on_brain_connected)
	Net.disconnected.connect(func(): hud.log_line("[brain] disconnected — citizens run on local instinct"))

	_spawn_citizens()
	hud.log_line("Welcome to %s. %d citizens are waking up." % [town.get("town_name", "the town"), agents.size()])
	if not Net.enabled:
		hud.log_line("[autopilot] running without the brain server.")
	if GameConfig.demo_interior != "":
		_demo_interior(GameConfig.demo_interior)
	if GameConfig.povtest != "":
		_run_povtest(GameConfig.povtest)

func _run_povtest(id: String) -> void:
	await get_tree().create_timer(1.5).timeout
	if agents.has(id):
		var b64: String = await _render_pov(agents[id])
		var img := Image.new()
		img.load_png_from_buffer(Marshalls.base64_to_raw(b64))
		var path := GameConfig.screenshot_path if GameConfig.screenshot_path != "" else "user://pov.png"
		img.save_png(path)
		print("[povtest] saved %s POV (%d bytes b64) -> %s" % [id, b64.length(), path])
	get_tree().quit()

func _demo_interior(place: String) -> void:
	for id in agents.keys():
		var a: Agent = agents[id]
		if a.workplace_name == place or a.home_name == place:
			enter_building(a, place)
	focus_interior(place)

# ---------------------------------------------------------------- places
func _build_places() -> void:
	places = town.get("places", [])
	for p in places:
		place_by_name[p.get("name", "")] = p

func place_pos(pname: String) -> Vector2:
	if place_by_name.has(pname):
		var p = place_by_name[pname]
		return Vector2(float(p.x), float(p.y))
	return map_px * 0.5

func nearest_place(pos: Vector2) -> Dictionary:
	var best := {}
	var bd := INF
	for p in places:
		var d := pos.distance_to(Vector2(float(p.x), float(p.y)))
		if d < bd:
			bd = d
			best = p
	return best

# ---------------------------------------------------------------- interiors
func _build_interiors() -> void:
	interiors_root = Node2D.new()
	interiors_root.name = "Interiors"
	interiors_root.y_sort_enabled = true
	add_child(interiors_root)
	var ix0 := map_px.x + 600.0
	var i := 0
	for b in town.get("buildings", []):
		var design := String(b.get("interior", ""))
		var place := String(b.get("place", b.get("name", "")))
		_make_ext_door(place, b)
		if design == "" or not GameConfig.interiors_data.has(design):
			continue
		var info: Dictionary = GameConfig.interiors_data[design]
		var tex := load("res://assets/" + String(info.image)) as Texture2D
		if tex == null:
			continue
		var origin := Vector2(ix0 + float(i % 3) * 900.0, 200.0 + float(i / 3) * 900.0)
		var sz := tex.get_size()
		var room := Node2D.new()
		room.position = origin
		room.z_index = -10
		interiors_root.add_child(room)
		var floor_spr := Sprite2D.new()
		floor_spr.texture = tex
		floor_spr.centered = false
		room.add_child(floor_spr)
		var lbl := Label.new()
		lbl.text = place
		lbl.position = Vector2(6, -24)
		lbl.add_theme_font_size_override("font_size", 16)
		lbl.add_theme_color_override("font_color", Color(1, 0.9, 0.6))
		lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
		lbl.add_theme_constant_override("outline_size", 5)
		room.add_child(lbl)

		# per-room navigation grid from the walkable floor tiles
		var tw := int(info.tw)
		var th := int(info.th)
		var ra := AStarGrid2D.new()
		ra.region = Rect2i(0, 0, tw, th)
		ra.cell_size = Vector2(tile, tile)
		ra.offset = origin + Vector2(tile, tile) * 0.5
		ra.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
		ra.update()
		for ty in range(th):
			for tx in range(tw):
				ra.set_point_solid(Vector2i(tx, ty), true)        # solid by default
		var walk_world: Array = []
		for c in info.walkable:
			var cell := Vector2i(int(c[0]), int(c[1]))
			ra.set_point_solid(cell, false)
			walk_world.append(origin + Vector2(cell) * tile + Vector2(tile, tile) * 0.5)
		var spots: Array = []
		for s in info.spots:
			spots.append(origin + Vector2(float(s[0]), float(s[1])) * tile + Vector2(tile, tile) * 0.5)
		var entry: Vector2 = origin + Vector2(float(info.entry[0]), float(info.entry[1])) * tile + Vector2(tile, tile) * 0.5

		# interior exit door at the bottom-centre threshold
		var idoor: DoorNode = DOOR_SCRIPT.new()
		var dsheet := load("res://assets/doors/door_1.png") as Texture2D
		if dsheet:
			idoor.setup(dsheet)
			idoor.position = origin + Vector2(float(info.door_px[0]), float(info.door_px[1]))
			interiors_root.add_child(idoor)
		interiors[place] = {
			"origin": origin, "astar": ra, "tw": tw, "th": th,
			"center": origin + sz * 0.5, "entry": entry,
			"walk": walk_world, "spots": spots, "door": idoor,
			"zoom": clampf(min(1180.0 / sz.x, 660.0 / sz.y), 0.55, 2.0),
		}
		i += 1

func _make_ext_door(place: String, b: Dictionary) -> void:
	var dtype := String(b.get("door_type", "door_1"))
	var sheet := load("res://assets/doors/%s.png" % dtype) as Texture2D
	if sheet == null:
		sheet = load("res://assets/doors/door_1.png") as Texture2D
	if sheet == null:
		return
	var d: DoorNode = DOOR_SCRIPT.new()
	d.setup(sheet)
	var door: Array = b.get("door", [b.bx, b.by])
	d.position = Vector2(float(door[0]), float(door[1]))
	entities.add_child(d)
	ext_doors[place] = d

func interior_roam_point(place: String) -> Vector2:
	if interiors.has(place):
		var w: Array = interiors[place].walk
		if w.size() > 0:
			return w[randi() % w.size()]
	return Vector2.ZERO

func interior_path(place: String, from_w: Vector2, to_w: Vector2) -> PackedVector2Array:
	if not interiors.has(place):
		return PackedVector2Array([from_w, to_w])
	var info: Dictionary = interiors[place]
	var ra: AStarGrid2D = info.astar
	var o: Vector2 = info.origin
	var a := _room_cell(ra, info, from_w - o)
	var b := _room_cell(ra, info, to_w - o)
	if a == b:
		return PackedVector2Array([from_w, to_w])
	var p := ra.get_point_path(a, b)
	return p if p.size() > 1 else PackedVector2Array([from_w, to_w])

func _room_cell(ra: AStarGrid2D, info: Dictionary, local: Vector2) -> Vector2i:
	var c := Vector2i(int(local.x / tile), int(local.y / tile))
	c = c.clamp(Vector2i.ZERO, Vector2i(int(info.tw) - 1, int(info.th) - 1))
	if not ra.is_point_solid(c):
		return c
	for r in range(1, 6):
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				var n := c + Vector2i(dx, dy)
				if ra.region.has_point(n) and not ra.is_point_solid(n):
					return n
	return c

func enter_building(a: Agent, place: String) -> void:
	if not interiors.has(place):
		return
	if ext_doors.has(place):
		ext_doors[place].open(1.4)
	a.teleport(interiors[place].entry)
	a.inside = place
	a.current_action = "working" if place == a.workplace_name else "resting"
	_roam_inside(a)

func _roam_inside(a: Agent) -> void:
	var tgt := interior_roam_point(a.inside)
	if tgt != Vector2.ZERO:
		a.walk_path(interior_path(a.inside, a.position, tgt))

func exit_building(a: Agent) -> void:
	if a.inside == "":
		return
	var place := a.inside
	a.inside = ""
	if ext_doors.has(place):
		ext_doors[place].open(1.4)
	a.teleport(place_pos(place))

func focus_interior(place: String) -> void:
	if not interiors.has(place):
		return
	if focused_interior == "":
		_town_cam_pos = camera.position
		_town_cam_zoom = camera.zoom
	focused_interior = place
	camera.position = interiors[place].center
	camera.zoom = Vector2(interiors[place].zoom, interiors[place].zoom)
	if interiors[place].door:
		interiors[place].door.open(2.0)
	hud.set_interior_mode(place)

func leave_interior() -> void:
	focused_interior = ""
	camera.position = _town_cam_pos
	camera.zoom = _town_cam_zoom
	hud.clear_interior_mode()

# ---------------------------------------------------------------- navgrid
func _build_navgrid(solids: Array) -> void:
	var cols := int(map_px.x / tile)
	var rows := int(map_px.y / tile)
	astar.region = Rect2i(0, 0, cols, rows)
	astar.cell_size = Vector2(tile, tile)
	astar.offset = Vector2(tile, tile) * 0.5
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	astar.update()
	for c in solids:
		if astar.region.has_point(c):
			astar.set_point_solid(c, true)

func _cell(pos: Vector2) -> Vector2i:
	return Vector2i(int(floor(pos.x / tile)), int(floor(pos.y / tile)))

func _nearest_free(cell: Vector2i) -> Vector2i:
	if not astar.region.has_point(cell):
		cell = cell.clamp(Vector2i.ZERO, astar.region.size - Vector2i.ONE)
	if not astar.is_point_solid(cell):
		return cell
	for r in range(1, 8):
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				var c := cell + Vector2i(dx, dy)
				if astar.region.has_point(c) and not astar.is_point_solid(c):
					return c
	return cell

func find_path(from_px: Vector2, to_px: Vector2) -> PackedVector2Array:
	var a := _nearest_free(_cell(from_px))
	var b := _nearest_free(_cell(to_px))
	if a == b:
		return PackedVector2Array([from_px, to_px])
	return astar.get_point_path(a, b)

func random_walkable(near: Vector2, radius_px: float) -> Vector2:
	for _i in range(12):
		var ang := randf() * TAU
		var r := randf() * radius_px
		var p := near + Vector2(cos(ang), sin(ang)) * r
		p = p.clamp(Vector2(tile, tile), map_px - Vector2(tile, tile))
		if not astar.is_point_solid(_cell(p)):
			return p
	return near

# ---------------------------------------------------------------- camera
func _setup_camera() -> void:
	camera = Camera2D.new()
	camera.position = map_px * 0.5
	camera.zoom = Vector2(0.62, 0.62)
	if GameConfig.overview:
		var vp := get_viewport_rect().size
		var z: float = min(vp.x / map_px.x, vp.y / map_px.y)
		camera.zoom = Vector2(z, z)
	add_child(camera)
	camera.make_current()

func _setup_pov() -> void:
	# an off-screen viewport that shares the town world, used to render a
	# citizen's first-person-ish view for vision-capable models
	_pov_vp = SubViewport.new()
	_pov_vp.size = Vector2i(240, 176)
	_pov_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_pov_vp)
	_pov_vp.world_2d = get_viewport().world_2d
	_pov_cam = Camera2D.new()
	_pov_cam.zoom = Vector2(1.15, 1.15)
	_pov_vp.add_child(_pov_cam)
	_pov_cam.make_current()

func _render_pov(a: Agent) -> String:
	_pov_cam.global_position = a.position - Vector2(0, 20)
	_pov_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	var img := _pov_vp.get_texture().get_image()
	_pov_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	return Marshalls.raw_to_base64(img.save_png_to_buffer())

func _setup_daynight() -> void:
	canvas_mod = CanvasModulate.new()
	add_child(canvas_mod)
	_update_daynight()

func _update_daynight() -> void:
	# warm dawn/dusk, bright noon, deep-blue night
	var c: Color
	if hour < 5.0 or hour >= 21.0:
		c = Color(0.30, 0.34, 0.55)
	elif hour < 7.0:
		c = Color(0.30, 0.34, 0.55).lerp(Color(1, 0.92, 0.82), (hour - 5.0) / 2.0)
	elif hour < 9.0:
		c = Color(1, 0.92, 0.82).lerp(Color(1, 1, 1), (hour - 7.0) / 2.0)
	elif hour < 17.0:
		c = Color(1, 1, 1)
	elif hour < 19.0:
		c = Color(1, 1, 1).lerp(Color(1, 0.85, 0.7), (hour - 17.0) / 2.0)
	elif hour < 21.0:
		c = Color(1, 0.85, 0.7).lerp(Color(0.30, 0.34, 0.55), (hour - 19.0) / 2.0)
	else:
		c = Color(0.30, 0.34, 0.55)
	canvas_mod.color = c

# ---------------------------------------------------------------- HUD
func _setup_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Control.new()
	hud.set_script(HUD_SCRIPT)
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	layer.add_child(hud)
	hud.request_submitted.connect(_on_player_request)
	hud.leave_interior_pressed.connect(leave_interior)
	hud.set_town_name(String(town.get("town_name", "Busyworld")))

# ---------------------------------------------------------------- spawn
func _spawn_citizens() -> void:
	var sheet_dir := "res://assets/characters/"
	for data in GameConfig.starting_citizens():
		var idx := int(data.get("sprite", 1))
		var path := sheet_dir + "Premade_Character_48x48_%02d.png" % idx
		var sheet := load(path) as Texture2D
		if sheet == null:
			push_warning("missing character sheet " + path)
			continue
		var a: Agent = AGENT_SCRIPT.new()
		a.setup(data, sheet, move_speed)
		a.world = self
		var home := place_pos(String(data.get("home", "Town Plaza")))
		a.position = random_walkable(home, 48.0)
		a.arrived.connect(_on_agent_arrived)
		entities.add_child(a)
		agents[a.id] = a
		meta[a.id] = {
			"next_think": _life + randf() * 4.0,
			"awaiting": false,
			"deadline": 0.0,
			"recent": [],
			"thought": "", "goal": String((data.get("goals", ["settle in"]) as Array)[0]),
			"money": 100,
		}
	hud.set_population(agents.size())
	hud.set_treasury(treasury)

# ---------------------------------------------------------------- main loop
func _process(dt: float) -> void:
	_life += dt
	# clock
	hour += (24.0 / day_length) * dt
	if hour >= 24.0:
		hour -= 24.0
		day += 1
	_update_daynight()
	hud.set_clock(_clock_string(), day)

	_decision_loop()
	_screenshot_logic(dt)

	if GameConfig.quit_after > 0.0 and _life >= GameConfig.quit_after:
		get_tree().quit()

func _decision_loop() -> void:
	for id in agents.keys():
		var a: Agent = agents[id]
		var m: Dictionary = meta[id]
		if m.awaiting:
			if _life > m.deadline:
				m.awaiting = false        # brain too slow; allow a fresh think
			else:
				continue
		if a.is_moving():
			continue
		if _life < m.next_think:
			continue
		_request_decision(a, m)

func _request_decision(a: Agent, m: Dictionary) -> void:
	if Net.is_open():
		m.awaiting = true
		m.deadline = _life + 20.0
		var msg := {"type": "decide", "agent_id": a.id}
		if a.id in vision_ids:
			msg["image"] = await _render_pov(a)     # the citizen's eyesight
		msg["perception"] = _build_perception(a, m)
		Net.send(msg)
	else:
		_apply_action(a, _heuristic_decide(a, m), m)

# ---------------------------------------------------------------- perception
func _build_perception(a: Agent, m: Dictionary) -> Dictionary:
	var here := nearest_place(a.position)
	var loc_name := String(here.get("name", "town"))
	var loc_tags: Array = here.get("tags", [])
	if a.inside != "":
		loc_name = "inside the " + a.inside
		if place_by_name.has(a.inside):
			loc_tags = place_by_name[a.inside].get("tags", [])
	var vis: Array = []
	var sorted_places := places.duplicate()
	sorted_places.sort_custom(func(p, q):
		return a.position.distance_to(Vector2(p.x, p.y)) < a.position.distance_to(Vector2(q.x, q.y)))
	for p in sorted_places.slice(0, 6):
		vis.append({
			"name": p.get("name", ""),
			"dir": _compass(a.position, Vector2(float(p.x), float(p.y))),
			"steps": int(a.position.distance_to(Vector2(float(p.x), float(p.y))) / tile),
		})
	var near: Array = []
	for oid in agents.keys():
		if oid == a.id:
			continue
		var o: Agent = agents[oid]
		var d := a.position.distance_to(o.position)
		if d < earshot * 2.2:
			near.append({
				"name": o.agent_name, "role": o.role,
				"steps": int(d / tile), "can_talk": d < earshot,
				"doing": o.current_action,
			})
	return {
		"self": {
			"name": a.agent_name, "title": a.title, "role": a.role,
			"action": a.current_action, "mood": a.mood,
			"energy": int(a.energy), "at": loc_name,
			"goal": m.get("goal", ""), "indoors": a.inside != "",
		},
		"time": _clock_string(), "day": day, "phase": _phase(),
		"location": {"name": loc_name, "feels_like": loc_tags},
		"visible_places": vis,
		"nearby_people": near,
		"recent_events": m.get("recent", []),
	}

func _compass(a: Vector2, b: Vector2) -> String:
	var d := b - a
	if d.length() < 1.0:
		return "here"
	var s := ""
	if d.y < -tile: s += "N"
	elif d.y > tile: s += "S"
	if d.x > tile: s += "E"
	elif d.x < -tile: s += "W"
	return s if s != "" else "here"

func _phase() -> String:
	if hour < 6: return "night"
	elif hour < 11: return "morning"
	elif hour < 14: return "midday"
	elif hour < 18: return "afternoon"
	elif hour < 21: return "evening"
	return "night"

func _clock_string() -> String:
	var h := int(hour) % 24
	var mi := int((hour - int(hour)) * 60.0)
	return "%02d:%02d" % [h, mi]

# ---------------------------------------------------------------- actions
func _apply_action(a: Agent, action: Dictionary, m: Dictionary) -> void:
	m.awaiting = false
	if action.has("thought"):
		m.thought = String(action.thought)
	if action.has("goal"):
		m.goal = String(action.goal)
	if action.has("mood"):
		a.set_mood(String(action.mood))
	if action.has("say"):
		var said := String(action.say)
		if said.strip_edges() != "":
			a.speak(said)
			hud.log_line("%s: %s" % [a.agent_name, said])
			_broadcast_speech(a, said)
	var interval := 6.0
	var act = action.get("action", {})
	var atype := String(act.get("type", "idle")) if typeof(act) == TYPE_DICTIONARY else String(act)
	match atype:
		"move_to", "go_to":
			var tgt: Vector2
			var dest_place := ""
			if act.has("place"):
				dest_place = String(act.place)
				tgt = place_pos(dest_place)
			elif act.has("x"):
				tgt = Vector2(float(act.x), float(act.y))
			else:
				tgt = place_pos("Town Plaza")
			if a.inside != "" and a.inside != dest_place:
				exit_building(a)
			if interiors.has(dest_place):
				a.pending_enter = dest_place
			a.go_to(tgt)
			interval = 5.0
		"work":
			_go_into(a, a.workplace_name)
			interval = 9.0
		"go_home":
			_go_into(a, a.home_name)
			interval = 8.0
		"wander":
			if a.inside != "":
				exit_building(a)
			a.go_to(random_walkable(a.position, 220.0))
			interval = 6.0
		"talk_to":
			if a.inside != "":
				exit_building(a)
			var who := String(act.get("agent", ""))
			var o := _find_agent_by_name(who)
			if o:
				a.go_to(o.position + Vector2(randf_range(-28, 28), 24))
				a.face_point(o.position)
			interval = 6.0
		"idle":
			if a.inside != "":
				_roam_inside(a)
			else:
				a.stop()
			interval = float(act.get("seconds", 5))
		_:
			interval = 6.0
	m.next_think = _life + interval
	a.set_think_cooldown(interval)

func _go_into(a: Agent, place: String) -> void:
	if place == "":
		a.stop(); return
	if a.inside == place:
		_roam_inside(a)                              # already inside; wander the room
		return
	if a.inside != "":
		exit_building(a)
	if interiors.has(place):
		a.pending_enter = place
		a.go_to(place_pos(place))                    # walk to the door, then enter
	else:
		a.go_to(place_pos(place))                    # outdoor workplace (park, plaza)
		a.current_action = "working"

func _find_agent_by_name(n: String) -> Agent:
	for id in agents.keys():
		if String(agents[id].agent_name).to_lower().begins_with(n.to_lower()) or n.to_lower().begins_with(String(agents[id].agent_name).split(" ")[0].to_lower()):
			return agents[id]
	return null

func _broadcast_speech(speaker: Agent, text: String) -> void:
	for id in agents.keys():
		if id == speaker.id:
			continue
		var o: Agent = agents[id]
		if speaker.position.distance_to(o.position) < earshot:
			_push_event(id, "%s said: \"%s\"" % [speaker.agent_name, text])

func _push_event(id: String, text: String) -> void:
	if not meta.has(id):
		return
	var r: Array = meta[id].recent
	r.append(text)
	while r.size() > 6:
		r.pop_front()

# ---------------------------------------------------------------- heuristic brain
func _heuristic_decide(a: Agent, m: Dictionary) -> Dictionary:
	var out := {}
	# greet a nearby citizen sometimes
	for id in agents.keys():
		if id == a.id: continue
		var o: Agent = agents[id]
		if a.position.distance_to(o.position) < earshot and randf() < 0.25:
			out["say"] = _smalltalk(a, o)
			break
	var ph := _phase()
	if ph == "night":
		out["action"] = {"type": "go_home"}
	elif randf() < 0.55:
		out["action"] = {"type": "work"}
	elif randf() < 0.5:
		out["action"] = {"type": "move_to", "place": "Town Plaza"}
	else:
		out["action"] = {"type": "wander"}
	return out

func _smalltalk(a: Agent, o: Agent) -> String:
	var lines := [
		"Morning, %s!" % o.agent_name.split(" ")[0],
		"Busy day ahead at the %s." % a.workplace_name,
		"Have you been to the plaza? The fountain looks lovely.",
		"How's the %s treating you, %s?" % [o.workplace_name, o.agent_name.split(" ")[0]],
		"Good to see you, neighbour.",
	]
	return lines[randi() % lines.size()]

# ---------------------------------------------------------------- events in
func _on_agent_arrived(a: Agent) -> void:
	if a.pending_enter != "":
		var bn := a.pending_enter
		a.pending_enter = ""
		enter_building(a, bn)
		return
	if a.current_action == "working":
		a.face_point(place_pos(a.workplace_name) + Vector2(0, -20))

func _on_brain_connected() -> void:
	hud.log_line("[brain] connected — citizens are thinking for themselves.")
	Net.send({"type": "hello", "world": town.get("town_name", "Busyworld"),
		"active": agents.keys(), "time": _clock_string()})

func _on_net_message(msg: Dictionary) -> void:
	match String(msg.get("type", "")):
		"action":
			var id := String(msg.get("agent_id", ""))
			if agents.has(id):
				_apply_action(agents[id], msg, meta[id])
		"say":
			var id2 := String(msg.get("agent_id", ""))
			if agents.has(id2):
				agents[id2].speak(String(msg.get("text", "")))
				hud.log_line("%s: %s" % [agents[id2].agent_name, msg.get("text", "")])
		"agent_state":
			var id3 := String(msg.get("agent_id", ""))
			if meta.has(id3):
				if msg.has("money"): meta[id3].money = int(msg.money)
				if msg.has("goal"): meta[id3].goal = String(msg.goal)
		"announce", "log":
			hud.log_line(String(msg.get("text", "")))
		"treasury":
			treasury = int(msg.get("amount", treasury))
			hud.set_treasury(treasury)
		"vision":
			vision_ids = msg.get("ids", [])
			if vision_ids.size() > 0:
				hud.log_line("[brain] %d citizen(s) can see their surroundings." % vision_ids.size())

func _on_player_request(text: String) -> void:
	hud.log_line("[You ask the town] " + text)
	Net.send({"type": "player_request", "text": text})
	for id in agents.keys():
		_push_event(id, "The town's founder asks: \"%s\"" % text)
		meta[id].next_think = min(meta[id].next_think, _life + 1.0 + randf() * 3.0)
	# in autopilot, have the mayor acknowledge
	if not Net.is_open() and agents.has("mayor"):
		agents["mayor"].speak("You heard the founder — let's make it happen!", 6.0)

# ---------------------------------------------------------------- input (pan/zoom)
func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP and e.pressed:
			camera.zoom = (camera.zoom * 1.1).clamp(Vector2(0.3, 0.3), Vector2(2.5, 2.5))
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN and e.pressed:
			camera.zoom = (camera.zoom * 0.9).clamp(Vector2(0.3, 0.3), Vector2(2.5, 2.5))
		elif e.button_index == MOUSE_BUTTON_LEFT:
			_drag = e.pressed
			if e.pressed:
				_try_select(e.position)
	elif e is InputEventMouseMotion and _drag:
		camera.position -= e.relative / camera.zoom

func _try_select(screen_pos: Vector2) -> void:
	var world_pos := camera.position + (screen_pos - get_viewport_rect().size * 0.5) / camera.zoom
	var best: Agent = null
	var bd := 40.0
	for id in agents.keys():
		var a: Agent = agents[id]
		var d := a.position.distance_to(world_pos)
		if d < bd:
			bd = d
			best = a
	if best:
		var m: Dictionary = meta[best.id]
		hud.show_agent({
			"name": best.agent_name, "title": best.title, "role": best.role,
			"mood": best.mood, "action": best.current_action, "energy": int(best.energy),
			"goal": m.get("goal", ""), "thought": m.get("thought", ""),
			"money": m.get("money", 0), "personality": best.personality,
		})
		return
	# no citizen hit: clicking a building enters its interior
	if focused_interior == "":
		var place := _building_at(world_pos)
		if place != "":
			focus_interior(place)

func _building_at(world_pos: Vector2) -> String:
	var hit := ""
	var best_by := -INF
	for b in town.get("buildings", []):
		var rect := Rect2(float(b.bx) - float(b.w) / 2.0, float(b.by) - float(b.h),
			float(b.w), float(b.h))
		if rect.has_point(world_pos) and interiors.has(String(b.get("place", ""))):
			if float(b.by) > best_by:        # prefer the front-most building
				best_by = float(b.by)
				hit = String(b.get("place", ""))
	return hit

# ---------------------------------------------------------------- screenshots
func _screenshot_logic(dt: float) -> void:
	if GameConfig.screenshot_path == "":
		return
	_shot_accum += dt
	var want: float = GameConfig.screenshot_delay
	if _shot_accum >= want:
		_shot_accum = 0.0
		_capture(_shot_path(_shots_taken))
		_shots_taken += 1
		if GameConfig.screenshot_series <= 0 or _shots_taken >= GameConfig.screenshot_series:
			if GameConfig.screenshot_series > 0:
				await get_tree().create_timer(0.2).timeout
				get_tree().quit()

func _shot_path(i: int) -> String:
	if GameConfig.screenshot_series <= 0:
		return GameConfig.screenshot_path
	var base := GameConfig.screenshot_path.get_basename()
	var ext := GameConfig.screenshot_path.get_extension()
	return "%s_%02d.%s" % [base, i, ext]

func _capture(path: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(path)
	print("[screenshot] ", path)
