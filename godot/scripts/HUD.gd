extends Control
# In-game overlay: status bar, event log, the founder's request box, and a
# click-to-inspect citizen panel.

signal request_submitted(text: String)

var _town := "Busyworld"
var _clock_lbl: Label
var _treasury_lbl: Label
var _pop_lbl: Label
var _log: RichTextLabel
var _input: LineEdit
var _inspector: Panel
var _insp_text: RichTextLabel

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_top_bar()
	_build_log()
	_build_input()
	_build_inspector()

func _panel(bg := Color(0.10, 0.11, 0.15, 0.86)) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(8)
	sb.set_content_margin_all(8)
	sb.border_color = Color(1, 1, 1, 0.10)
	sb.set_border_width_all(1)
	return sb

func _build_top_bar() -> void:
	var bar := PanelContainer.new()
	bar.add_theme_stylebox_override("panel", _panel(Color(0.08, 0.09, 0.13, 0.92)))
	bar.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	bar.offset_left = 10; bar.offset_right = -10; bar.offset_top = 8; bar.offset_bottom = 44
	add_child(bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	bar.add_child(row)
	var title := Label.new()
	title.text = "  " + _town
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.5))
	row.add_child(title)
	_clock_lbl = _stat(row, "Day 1  08:00")
	_pop_lbl = _stat(row, "Pop 0")
	_treasury_lbl = _stat(row, "Treasury 0")
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(spacer)
	var hint := Label.new()
	hint.text = "drag to pan · scroll to zoom · click a citizen  "
	hint.add_theme_font_size_override("font_size", 11)
	hint.add_theme_color_override("font_color", Color(1, 1, 1, 0.45))
	row.add_child(hint)

func _stat(row: HBoxContainer, t: String) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", Color(0.9, 0.93, 1.0))
	row.add_child(l)
	return l

func _build_log() -> void:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", _panel())
	p.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	p.offset_left = 10; p.offset_top = -210; p.offset_right = 560; p.offset_bottom = -52
	add_child(p)
	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_active = true
	_log.scroll_following = true
	_log.add_theme_font_size_override("normal_font_size", 12)
	p.add_child(_log)

func _build_input() -> void:
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	row.offset_left = 10; row.offset_top = -44; row.offset_right = 560; row.offset_bottom = -12
	row.add_theme_constant_override("separation", 6)
	add_child(row)
	_input = LineEdit.new()
	_input.placeholder_text = "Ask your town to do something…  (e.g. \"open a bakery stall in the plaza\")"
	_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_input.text_submitted.connect(_on_submit)
	row.add_child(_input)
	var btn := Button.new()
	btn.text = "Ask"
	btn.pressed.connect(func(): _on_submit(_input.text))
	row.add_child(btn)

func _on_submit(text: String) -> void:
	text = text.strip_edges()
	if text == "":
		return
	emit_signal("request_submitted", text)
	_input.clear()

func _build_inspector() -> void:
	_inspector = Panel.new()
	_inspector.add_theme_stylebox_override("panel", _panel(Color(0.10, 0.11, 0.16, 0.92)))
	_inspector.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	_inspector.offset_left = -320; _inspector.offset_right = -10
	_inspector.offset_top = 52; _inspector.offset_bottom = 330
	_inspector.visible = false
	add_child(_inspector)
	_insp_text = RichTextLabel.new()
	_insp_text.bbcode_enabled = true
	_insp_text.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_insp_text.offset_left = 12; _insp_text.offset_top = 10
	_insp_text.offset_right = -12; _insp_text.offset_bottom = -10
	_inspector.add_child(_insp_text)
	var close := Button.new()
	close.text = "x"
	close.flat = true
	close.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	close.offset_left = -28; close.offset_right = -6; close.offset_top = 4; close.offset_bottom = 26
	close.pressed.connect(func(): _inspector.visible = false)
	_inspector.add_child(close)

# ---- public API ----------------------------------------------------------
func set_town_name(n: String) -> void:
	_town = n

func set_clock(t: String, day: int) -> void:
	if _clock_lbl: _clock_lbl.text = "Day %d  %s" % [day, t]

func set_treasury(v: int) -> void:
	if _treasury_lbl: _treasury_lbl.text = "Treasury %d¢" % v

func set_population(v: int) -> void:
	if _pop_lbl: _pop_lbl.text = "Pop %d" % v

func log_line(text: String) -> void:
	if _log:
		_log.append_text(text + "\n")

func show_agent(d: Dictionary) -> void:
	if _insp_text == null: return
	var s := "[b][color=#ffd98a]%s[/color][/b]  [color=#9fb0c8](%s)[/color]\n" % [d.get("name", ""), d.get("title", "")]
	s += "[color=#9fb0c8]mood[/color] %s   [color=#9fb0c8]doing[/color] %s\n" % [d.get("mood", "?"), d.get("action", "?")]
	s += "[color=#9fb0c8]energy[/color] %d   [color=#9fb0c8]coins[/color] %d¢\n" % [d.get("energy", 0), d.get("money", 0)]
	s += "\n[color=#9fb0c8]goal[/color]\n%s\n" % d.get("goal", "")
	if String(d.get("thought", "")) != "":
		s += "\n[color=#9fb0c8]last thought[/color]\n[i]%s[/i]\n" % d.get("thought", "")
	s += "\n[color=#9fb0c8]about[/color]\n%s" % d.get("personality", "")
	_insp_text.text = s
	_inspector.visible = true
