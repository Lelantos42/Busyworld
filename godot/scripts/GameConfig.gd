extends Node
# Autoload. Loads world/town/citizen config and parses command-line overrides.

var world: Dictionary = {}
var town: Dictionary = {}
var citizens: Array = []

# runtime / CLI
var agent_count: int = 6
var screenshot_path: String = ""
var screenshot_delay: float = 8.0
var screenshot_series: int = 0          # >0: take N shots spaced screenshot_delay apart
var autopilot: bool = false             # force local heuristic movement (ignore brain)
var quit_after: float = 0.0             # seconds; 0 = never
var overview: bool = false              # zoom camera to fit the whole town
var demo_interior: String = ""          # auto-focus this interior on start (debug)

func _ready() -> void:
	world = _load_json("res://data/world_config.json")
	town = _load_json("res://data/town_layout.json")
	var c := _load_json("res://data/citizens.json")
	citizens = c.get("citizens", [])
	agent_count = int(world.get("default_agent_count", 6))
	_parse_cli()
	agent_count = clampi(agent_count, 1, citizens.size())
	print("[GameConfig] town=", world.get("town_name", "?"),
		" citizens_available=", citizens.size(), " starting=", agent_count,
		" brain=", world.get("brain_url", ""))

func _parse_cli() -> void:
	var args := OS.get_cmdline_user_args()
	var i := 0
	while i < args.size():
		var a: String = args[i]
		match a:
			"--agents", "--count":
				if i + 1 < args.size(): agent_count = int(args[i + 1]); i += 1
			"--screenshot":
				if i + 1 < args.size(): screenshot_path = args[i + 1]; i += 1
			"--shotdelay":
				if i + 1 < args.size(): screenshot_delay = float(args[i + 1]); i += 1
			"--shotseries":
				if i + 1 < args.size(): screenshot_series = int(args[i + 1]); i += 1
			"--autopilot":
				autopilot = true
			"--overview":
				overview = true
			"--interior":
				if i + 1 < args.size(): demo_interior = args[i + 1]; i += 1
			"--quit-after":
				if i + 1 < args.size(): quit_after = float(args[i + 1]); i += 1
		i += 1

func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("Missing config: " + path)
		return {}
	var txt := FileAccess.get_file_as_string(path)
	var data: Variant = JSON.parse_string(txt)
	if typeof(data) != TYPE_DICTIONARY:
		push_error("Bad JSON: " + path)
		return {}
	return data

# ---- helpers -------------------------------------------------------------
func get_w(key: String, def: Variant) -> Variant:
	return world.get(key, def)

func starting_citizens() -> Array:
	return citizens.slice(0, agent_count)

func place_by_name(pname: String) -> Dictionary:
	for p in town.get("places", []):
		if p.get("name", "") == pname:
			return p
	return {}
