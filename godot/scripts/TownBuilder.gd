class_name TownBuilder
extends RefCounted
# Reconstructs the town from data/town_layout.json:
#   * ground texture (single baked sprite, drawn behind everything)
#   * Y-sorted buildings + props
#   * returns the list of solid tile-cells for the A* navigation grid

const ASSET_PREFIX := "res://assets/"

static func build(world: Node2D, entities: Node2D, town: Dictionary) -> Array:
	var solids: Array = []      # Array[Vector2i]
	var tile: int = int(town.get("tile", 32))

	# --- ground ---
	var gtex := _load(town.get("ground_texture", ""))
	if gtex:
		var ground := Sprite2D.new()
		ground.texture = gtex
		ground.centered = false
		ground.z_index = -100
		ground.name = "Ground"
		world.add_child(ground)
		world.move_child(ground, 0)

	# --- buildings ---
	for b in town.get("buildings", []):
		_add_sprite(entities, b.get("file", ""), float(b.bx), float(b.by),
			int(b.w), int(b.h))

	# --- props ---
	for p in town.get("props", []):
		_add_sprite(entities, p.get("file", ""), float(p.bx), float(p.by),
			int(p.w), int(p.h))
		if p.get("collide", false):
			_mark_circle(solids, float(p.bx), float(p.by) - 6.0,
				float(p.get("crad", 10)), tile)

	# --- building collision slabs -> solid cells ---
	for c in town.get("collisions", []):
		_mark_rect(solids, float(c.x), float(c.y), float(c.w), float(c.h), tile)

	return solids

static func _add_sprite(entities: Node2D, rel: String, bx: float, by: float, w: int, h: int) -> void:
	var tex := _load(rel)
	if tex == null:
		return
	var n := Node2D.new()
	n.position = Vector2(bx, by)          # baseline (bottom-center) -> drives Y-sort
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	s.offset = Vector2(-w / 2.0, -h)      # draw up-left from the baseline
	n.add_child(s)
	entities.add_child(n)

static func _load(rel: String) -> Texture2D:
	if rel == "":
		return null
	var path := ASSET_PREFIX + rel
	if not ResourceLoader.exists(path):
		push_warning("[TownBuilder] missing texture: " + path)
		return null
	return load(path) as Texture2D

static func _mark_rect(solids: Array, x: float, y: float, w: float, h: float, tile: int) -> void:
	var cx0 := int(floor(x / tile))
	var cy0 := int(floor(y / tile))
	var cx1 := int(floor((x + w) / tile))
	var cy1 := int(floor((y + h) / tile))
	for cy in range(cy0, cy1 + 1):
		for cx in range(cx0, cx1 + 1):
			solids.append(Vector2i(cx, cy))

static func _mark_circle(solids: Array, cx: float, cy: float, r: float, tile: int) -> void:
	var c0 := Vector2i(int(floor((cx - r) / tile)), int(floor((cy - r) / tile)))
	var c1 := Vector2i(int(floor((cx + r) / tile)), int(floor((cy + r) / tile)))
	for y in range(c0.y, c1.y + 1):
		for x in range(c0.x, c1.x + 1):
			solids.append(Vector2i(x, y))
