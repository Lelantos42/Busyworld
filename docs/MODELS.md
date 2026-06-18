# Choosing models for your citizens

Each citizen thinks on an [Ollama](https://ollama.com) model you choose in
`brain/agents.yaml`. You don't need anything fancy — every citizen only has to
read a small JSON perception and reply with a small JSON action. Small models do
this well. Here's how to choose.

## Quick start (one machine)
Pull one small model and point everyone at it (this is already the default):
```bash
ollama pull llama3.2:3b
```
```yaml
# brain/agents.yaml
defaults:
  host: "127.0.0.1"
  port: 11434
  model: "llama3.2:3b"
```
That's enough to bring the whole town to life. Tune from there.

## Recommended models by role tier

| Tier | Use for | Good choices | Rough RAM |
|------|---------|--------------|-----------|
| **Hero** | mayor, and any citizen you interact with a lot | `llama3.1:8b`, `qwen2.5:7b`, `mistral:7b` | 6–10 GB |
| **Citizen** | most townsfolk | `llama3.2:3b`, `qwen2.5:3b`, `phi3.5:3.8b` | 3–5 GB |
| **Extra / Pi** | background citizens, low-RAM boxes | `qwen2.5:1.5b`, `llama3.2:1b`, `gemma2:2b` | 1–3 GB |
| **Eyes (vision)** | citizens with `vision: true` | `llama3.2-vision:11b`, `llava:7b`, `moondream` (tiny) | 5–10 GB |

Notes:
- **`qwen2.5` models follow the "reply in JSON" instruction very reliably** at
  small sizes — a great default for citizens. `llama3.2:3b` is also solid.
- The brain requests **JSON mode** from Ollama, so even small models stay on-format.
- **Raspberry Pi**: a Pi 5 (8 GB) can run a 1–3B model, but slowly (seconds per
  thought). That's fine here — citizens think on an interval, not every frame.
  Use `qwen2.5:1.5b` or `llama3.2:1b`, and raise that citizen's `timeout`.
- **Vision is heavier.** Start with one or two seers; `moondream` is tiny if RAM is
  tight, `llama3.2-vision:11b` is much sharper.

## Distributing across machines / Raspberry Pis
Give each citizen its own `host`/`port`/`model`. Anyone omitted uses `defaults`.
```yaml
agents:
  mayor:
    host: "192.168.1.50"   # a desktop with a GPU
    model: "llama3.1:8b"
    vision: true
    model_vision: "llama3.2-vision:11b"
  baker:
    host: "192.168.1.51"   # a Raspberry Pi
    model: "qwen2.5:1.5b"
    timeout: 60
  shopkeeper:
    host: "192.168.1.52"
    model: "qwen2.5:3b"
```
On each machine: install Ollama, `ollama pull <model>`, and make sure it listens on
the network (`OLLAMA_HOST=0.0.0.0 ollama serve`). The brain reaches each one over
plain HTTP; unreachable ones fall back to instinct automatically.

## A sensible starting layout
- **One good machine?** `defaults: qwen2.5:3b`, give the mayor `llama3.1:8b`.
- **A few machines?** Heroes (mayor, an innkeeper) on 7–8B; everyone else 3B.
- **A pile of Pis?** 1.5–3B each, longer timeouts, vision off (or one `moondream`).

You can change models any time — just edit `agents.yaml` and restart the brain.
