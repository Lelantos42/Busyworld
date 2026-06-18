class_name DoorNode
extends Node2D
# An animated door sliced from a LimeZu door spritesheet. Frame 0 is the closed
# door (which matches the building's own drawn door), so the overlay aligns
# seamlessly and plays open/shut when triggered.

var _spr: AnimatedSprite2D
var _is_open := false
var _auto := 0.0

func setup(sheet: Texture2D, fw := 32, fh := -1, n := -1, offset := Vector2.ZERO) -> void:
	if fh < 0:
		fh = sheet.get_height()
	if n < 1:
		n = int(sheet.get_width() / fw)
	var sf := SpriteFrames.new()
	sf.remove_animation("default")
	sf.add_animation("open"); sf.set_animation_loop("open", false); sf.set_animation_speed("open", 16.0)
	sf.add_animation("shut"); sf.set_animation_loop("shut", false); sf.set_animation_speed("shut", 16.0)
	for i in range(n):
		var at := AtlasTexture.new(); at.atlas = sheet
		at.region = Rect2(i * fw, 0, fw, fh); at.filter_clip = true
		sf.add_frame("open", at)
	for i in range(n - 1, -1, -1):
		var at2 := AtlasTexture.new(); at2.atlas = sheet
		at2.region = Rect2(i * fw, 0, fw, fh); at2.filter_clip = true
		sf.add_frame("shut", at2)
	_spr = AnimatedSprite2D.new()
	_spr.sprite_frames = sf
	_spr.centered = false
	_spr.offset = offset
	_spr.animation = "open"
	_spr.frame = 0
	add_child(_spr)

func _process(dt: float) -> void:
	if _auto > 0.0:
		_auto -= dt
		if _auto <= 0.0:
			close()

func open(auto_close := 0.0) -> void:
	if not _is_open:
		_is_open = true
		_spr.play("open")
	_auto = auto_close

func close() -> void:
	if _is_open:
		_is_open = false
		_spr.play("shut")
