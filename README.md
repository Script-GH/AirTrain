# AirTrain

Pool idle GPU and SoC compute across laptops and desktops to collaboratively train small models. This repo holds the mobile dashboard (Flutter) used to monitor devices and training jobs.

## Status
v1: phone dashboard running on mock live data. The PC agent and coordinator come next.

## Features
- Live job card with an accuracy curve, round progress and total samples
- Per-device cards with GPU utilization sparkline, VRAM, temperature, power and share of work
- Pause or resume training per device

## Run
```bash
flutter pub get
flutter run            # connected phone
flutter run -d linux   # desktop preview
```

## Planned architecture
- PC agent (Python): GPU stats via pynvml, idle/AC/network checks, Flower client training
- Coordinator (FastAPI): device registry, jobs, live stats over WebSocket
- Aggregation (Flower SuperLink): FedAvg with partial rounds
- Dashboard (this app): Flutter + Riverpod
