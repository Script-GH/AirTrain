# AirTrain

Pool idle GPU and SoC compute across laptops and desktops to collaboratively train small models. This repo holds the mobile dashboard (Flutter) used to monitor devices and training jobs, and the device agent (`agent/`) that runs on each PC.

## Status
- Phone dashboard: Overview, Training, Health and Network tabs. Shows demo data until a PC agent is paired, then live data.
- PC agent (`agent/`, Windows and Linux): live GPU/CPU/RAM telemetry, idle detection, local CIFAR-10 training, pause/resume from the phone. See [agent/README.md](agent/README.md).
- Coordinator and federated rounds: next.

## Quick start: agent
```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install "./agent[train]"
airtrain status
airtrain serve --train      # prints the ws:// URL and token to paste into the app
```
In the app, tap the link button on Overview and paste the URL.

## Features
- Live job card with an accuracy curve, round progress and total samples
- Per-device cards with GPU utilization sparkline, VRAM, temperature, power and share of work
- Pause or resume training per device (sent to the PC agent when paired)
- Pair PC agents by URL and token; paired agents are remembered

## Run
```bash
flutter pub get
flutter run            # connected phone
flutter run -d linux   # desktop preview
```

## Planned architecture
- PC agent (Python, `agent/`): GPU stats via pynvml, idle/battery/thermal checks, local training now, Flower client next
- Coordinator (FastAPI): device registry, jobs, live stats over WebSocket
- Aggregation (Flower SuperLink): FedAvg with partial rounds
- Dashboard (this app): Flutter + Riverpod
