class_name CharacterFrames
extends RefCounted

# Builds a SpriteFrames resource from a LimeZu "Premade_Character" sheet.
#
# Sheet geometry (verified against the asset pack):
#   * Each frame is 48 px wide and ~64 px tall; a character spans TWO 48px grid
#     rows (head in the upper cell, body in the lower), so each animation row of
#     frames occupies a vertical "pair" of grid rows.
#   * Pair 0 (grid rows 0-1)  = 4 single-frame facing poses (unused here)
#   * Pair 1 (grid rows 2-3)  = idle, 6 frames x 4 directions
#   * Pair 2 (grid rows 4-5)  = walk, 6 frames x 4 directions
#   * Within a 24-wide row the direction order is: Right, Up, Left, Down
#     (columns 0-5 = Right, 6-11 = Up, 12-17 = Left, 18-23 = Down)

const CELL := 48
const FRAME_W := 48
const FRAME_H := 68
const PAIR_PX := 96          # two grid rows
const Y_OFFSET := 28         # head-top inside the pair
const FRAMES := 6

# direction name -> starting column of its 6-frame group
const DIRS := {
	"right": 0,
	"up": 6,
	"left": 12,
	"down": 18,
}

static func build(sheet: Texture2D) -> SpriteFrames:
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")
	_add_anim(sf, sheet, "idle", 1, 5.0)
	_add_anim(sf, sheet, "walk", 2, 9.0)
	return sf

static func _add_anim(sf: SpriteFrames, sheet: Texture2D, base: String, pair_index: int, fps: float) -> void:
	var y0 := pair_index * PAIR_PX + Y_OFFSET
	for dir in DIRS.keys():
		var anim: String = base + "_" + str(dir)
		sf.add_animation(anim)
		sf.set_animation_loop(anim, true)
		sf.set_animation_speed(anim, fps)
		var col0: int = DIRS[dir]
		for f in range(FRAMES):
			var at := AtlasTexture.new()
			at.atlas = sheet
			at.region = Rect2((col0 + f) * CELL, y0, FRAME_W, FRAME_H)
			at.filter_clip = true
			sf.add_frame(anim, at)
