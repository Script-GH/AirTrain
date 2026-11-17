# AirTrain web UI

A React + TypeScript preview of the AirTrain dashboard. It mirrors the Flutter app's look and layout (Overview, Training, Health, Network) using the same colors, typography, land masks and component structure. There is no WebSocket or agent connection here; the screens run on mock data with a one-second live update loop.

## Run

```bash
cd web
npm install
npm run dev
```

Then open the URL Vite prints (http://127.0.0.1:5173). Append `?tab=overview`, `?tab=training`, `?tab=health` or `?tab=network` to land on a tab.

```bash
npm run build    # type-check and production build
npm run preview  # serve the build
```

The page is laid out for a phone-width column (max 430px), centered on larger screens.

## What's on each tab

- **Overview** and **Health** use the same demo devices as the Flutter app (Linux PC and MacBook Air) and show a Demo data pill until a real agent is wired up.
- **Training** shows the CIFAR-10 CNN · FedAvg job: progress ring, accuracy, loss, throughput and recent rounds.
- **Network** lists only mock CLI-paired agents (not the demo devices), with a World / India dotted map, coordinator pins and cluster arcs. The empty state — shown when that list is empty — prints the three CLI steps (`airtrain analysis`, `airtrain connect`, `airtrain start training`) and a Pair device button.

The pairing sheet is UI only. It validates a `ws://` URL and token the same way the Flutter app does, and lists "paired" agents in the sheet, but it does not open a socket.

## Components

| Component | Role |
| --- | --- |
| `AppShell` / `TabBar` | Phone column layout and the four-tab bar |
| `Stat` / `StatCard` | Inline stats and the large metric tiles |
| `Sparkline` | SVG utilization, temperature, accuracy and loss charts |
| `StressGauge` | SVG 270-degree health gauge |
| `LoadBar` | GPU / CPU / VRAM / RAM / power bars |
| `DeviceTile` / `DeviceList` | Overview device cards |
| `HealthPanel` | Per-device stress, bars and temperature history |
| `DottedMap` | Canvas map from the equirectangular land masks |
| `MapToggle` | World / India switch |
| `EmptyState` | CLI install steps and Pair device |
| `PairingSheet` | Bottom sheet to paste an agent URL and token |
| `JobCard`, `ChartCard`, `ProgressRing`, `RoundTable` | Training job chrome |

Types for `Device`, `Job` and the v1 agent `telemetry` message live in `src/types/`. Mock fixtures and the land masks (`worldMap`, `indiaMap`, copied from `lib/world_mask.dart`) are in `src/data/`.
