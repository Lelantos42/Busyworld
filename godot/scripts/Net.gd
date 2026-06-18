extends Node
# Autoload. WebSocket client to the Python "brain" server.
# Emits decoded JSON messages; World/HUD react to them.

signal connected()
signal disconnected()
signal message(msg: Dictionary)

var _ws := WebSocketPeer.new()
var _url := ""
var _state := WebSocketPeer.STATE_CLOSED
var _was_open := false
var enabled := true

func _ready() -> void:
	_url = String(GameConfig.get_w("brain_url", "ws://127.0.0.1:8765"))
	if GameConfig.autopilot:
		enabled = false
		return
	var err := _ws.connect_to_url(_url)
	if err != OK:
		push_warning("[Net] connect_to_url failed: %s" % err)

func _process(_dt: float) -> void:
	if not enabled:
		return
	_ws.poll()
	_state = _ws.get_ready_state()
	if _state == WebSocketPeer.STATE_OPEN:
		if not _was_open:
			_was_open = true
			emit_signal("connected")
		while _ws.get_available_packet_count() > 0:
			var pkt := _ws.get_packet()
			var data: Variant = JSON.parse_string(pkt.get_string_from_utf8())
			if typeof(data) == TYPE_DICTIONARY:
				emit_signal("message", data)
	elif _state == WebSocketPeer.STATE_CLOSED:
		if _was_open:
			_was_open = false
			emit_signal("disconnected")

func is_open() -> bool:
	return enabled and _state == WebSocketPeer.STATE_OPEN

func send(msg: Dictionary) -> void:
	if is_open():
		_ws.send_text(JSON.stringify(msg))
