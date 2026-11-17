# AirTrain agent

The device-side CLI for AirTrain. It runs on the PC or laptop that contributes compute. It reads GPU, CPU, RAM, temperature and power, works out whether you are using the machine, and trains a small model only when the machine is idle. It streams everything live to the AirTrain phone app over WebSocket.

Supported: **Windows 10/11 and Linux**, Python 3.10+. GPU telemetry and CUDA training need an NVIDIA GPU. Machines without one still work, reporting CPU and RAM and training on the CPU. macOS is not supported yet.

## Install

The `[train]` extra pulls in PyTorch. Leave it out if you only want monitoring.

### Windows (PowerShell)

```powershell
git clone https://github.com/Script-GH/AirTrain.git
cd AirTrain
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install ".\agent[train]"
# NVIDIA GPU: replace the CPU-only torch wheel with the CUDA build
pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu128
airtrain status
```

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### Linux

```bash
git clone https://github.com/Script-GH/AirTrain.git
cd AirTrain
python3 -m venv .venv
source .venv/bin/activate
pip install "./agent[train]"     # the default Linux torch wheel already includes CUDA
airtrain status
```

Optional extras:
- `sudo apt install xprintidle` (X11) for accurate keyboard and mouse idle time. On GNOME, including Wayland, the agent asks Mutter over D-Bus instead.
- `pip install "./agent[qr]"` prints a QR code of the pairing URL in the terminal.

## Commands

| Command | What it does |
| --- | --- |
| `airtrain status` | One-shot snapshot: device, OS, GPU, utilization, VRAM, temperature and limits, power and power limit, fan, clocks, throttle reasons, CPU, RAM, battery, idle state. Add `--json` for the raw telemetry. |
| `airtrain serve` | Starts the WebSocket server for the phone app and prints the LAN IP, token and `ws://` URL. Options: `--host 0.0.0.0`, `--port 8765`, `--token TOKEN`, `--train`, `--quiet`. |
| `airtrain serve --train` | Same, and also trains whenever the machine is idle. Training progress is included in the stream. |
| `airtrain train` | Trains locally when idle and prints progress, without the server. Options: `--rounds 50`, `--steps 100` (batches per round), `--dataset cifar10\|synthetic`, `--no-idle-check`. |
| `airtrain token [--reset]` | Shows, or regenerates, the pairing token. |
| `airtrain config [--set KEY=VALUE ...]` | Shows or changes settings. |

The first run creates the config and a random pairing token in:
- Windows: `%APPDATA%\AirTrain\config.json`
- Linux: `~/.config/airtrain/config.json` (or `$XDG_CONFIG_HOME/airtrain`)

The CIFAR-10 dataset (about 170 MB) is downloaded to `data/` in the same folder on the first training run.

Settings:

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | hostname | Device name shown in the app |
| `port` | 8765 | Default port for `serve` |
| `gpu_index` | 0 | Which NVIDIA GPU to monitor |
| `idle_minutes` | 5 | No keyboard or mouse input for this long counts as idle |
| `max_temp_c` | 83 | Pause training at or above this temperature (GPU, or CPU when there is no GPU) |
| `resume_temp_margin_c` | 5 | Resume once the temperature is this far below `max_temp_c` |
| `min_battery_pct` | 50 | On battery below this, the device counts as busy |
| `gpu_busy_util` | 30 | Another process using the GPU above this % makes the device busy |

## When it trains

Training runs only while none of these blockers apply. The app shows them as "In use":

- **User active.** The last keyboard or mouse input was less than `idle_minutes` ago. On Windows this comes from `GetLastInputInfo`. On Linux it comes from `xprintidle`, then GNOME Mutter, then terminal activity (the same source `w` uses). If none of those are available, the agent relies on the GPU and battery checks alone.
- **Another process is using the GPU.** NVML reports another compute process while utilization is above `gpu_busy_util`, or the GPU is busy before training has started (a game, for example).
- **On battery** below `min_battery_pct`.
- **Too hot.** The temperature has reached `max_temp_c`.
- **Paused** from the phone app.

The trainer checks these between batches, so it stops within a fraction of a second when you come back, and resumes once the machine has been idle for `idle_minutes` again.

Training is currently a single-device stub: a small CNN on CIFAR-10, using CUDA if available and otherwise the CPU. Federated rounds through the coordinator and Flower come next (see `TODO(coordinator)` in `airtrain_agent/trainer.py`).

## Pairing the phone app

1. On the PC, run `airtrain serve --train`. It prints something like:
   ```
   LAN IP   192.168.1.20
   Token    q3Zk1bY0tXo-
   App URL  ws://192.168.1.20:8765/?token=q3Zk1bY0tXo-
   ```
2. In the app, open **Overview**, tap the link button at the top right, paste the App URL and tap **Connect**. You can also type `192.168.1.20:8765` with the token in the second field.
3. The phone and the PC must be on the same Wi-Fi or LAN. The app remembers paired agents and shows demo data until at least one is paired.

### Windows firewall

Windows asks to allow Python on first `serve`. Allow it on **Private networks**. To add the rule yourself, run this in an Administrator PowerShell:

```powershell
New-NetFirewallRule -DisplayName "AirTrain agent" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
```

Make sure your Wi-Fi network is set to Private, not Public. On Linux with `ufw`: `sudo ufw allow 8765/tcp`.

## WebSocket protocol

Connect to `ws://<host>:<port>/?token=<token>`. A missing or wrong token gets HTTP 401.

Server to app:
- `{"type": "hello", "v": 1, "device_id": "..."}` once on connect
- one `telemetry` message per second (below)
- `{"type": "ack", "cmd": "pause", "ok": true, "paused": true}` after each command

App to server:
- `{"cmd": "pause"}` stops training and keeps it stopped until resumed
- `{"cmd": "resume"}`
- `{"cmd": "snapshot"}` returns a telemetry message right away
- `{"cmd": "ping"}`

### Telemetry schema (v1)

Any sensor the machine does not expose is `null`. Units are in the field names.

```json
{
  "type": "telemetry",
  "v": 1,
  "ts": 1763370000.12,
  "device": {
    "id": "a1b2c3d4e5f6",
    "name": "Gaming PC",
    "hostname": "gaming-pc",
    "os": "Windows 11",
    "platform": "win32",
    "kind": "desktop"
  },
  "gpu": {
    "available": true,
    "vendor": "nvidia",
    "name": "NVIDIA GeForce RTX 3060",
    "driver": "555.42",
    "util": 97,
    "vram_used_gb": 3.1,
    "vram_total_gb": 12.0,
    "temp_c": 71,
    "temp_limit_c": 93,
    "temp_shutdown_c": 98,
    "power_w": 151.5,
    "power_limit_w": 170.0,
    "fan_pct": 55,
    "clock_mhz": 1890,
    "clock_max_mhz": 2100,
    "throttle_reasons": ["sw_power_cap"],
    "throttled": true,
    "processes": [{"pid": 4242, "kind": "compute", "mem_gb": 2.0}]
  },
  "cpu": {"name": "AMD Ryzen 5 5600X", "util": 35.0, "cores": 12, "freq_mhz": 4200, "temp_c": null},
  "ram": {"used_gb": 11.2, "total_gb": 32.0},
  "battery": {"present": false, "percent": null, "plugged": null},
  "idle": {
    "user_idle_s": 900.0,
    "method": "GetLastInputInfo",
    "idle": true,
    "eligible": true,
    "reasons": []
  },
  "blockers": [],
  "state": "training",
  "paused": false,
  "uptime_s": 120,
  "limits": {"max_temp_c": 83.0, "idle_minutes": 5.0, "min_battery_pct": 50.0},
  "train": {
    "status": "running",
    "round": 2,
    "total_rounds": 50,
    "step": 40,
    "steps_per_round": 100,
    "loss": 1.71,
    "accuracy": 0.38,
    "samples": 19200,
    "samples_per_s": 2400.0,
    "device": "cuda:NVIDIA GeForce RTX 3060",
    "dataset": "cifar10",
    "history": [{"round": 1, "loss": 2.01, "accuracy": 0.27, "samples": 6400}],
    "error": null
  }
}
```

Field notes:
- `gpu.available` is `false` when no NVIDIA GPU or driver is found. `gpu.reason` then says why, and every other GPU field is absent.
- `state` is one of `training`, `idle` or `busy`. `blockers` lists why the device is busy.
- `throttle_reasons` values: `gpu_idle`, `app_clock_setting`, `sw_power_cap`, `hw_slowdown`, `sync_boost`, `sw_thermal`, `hw_thermal`, `hw_power_brake`, `display_clock`. `throttled` is true when any power or thermal reason is active.
- `train` is `null` unless the agent runs with `--train`. `train.status` is one of `starting`, `loading`, `waiting`, `running`, `done`, `error` or `stopped`. `history` holds the last 50 rounds.

How the app maps it to a device card: GPU `util`, `vram_*`, `temp_c`, `power_w`, `fan_pct` and `clock_mhz` fill the card directly. Without a GPU, the card shows CPU load and system RAM instead. `train.samples` becomes the device's share of work, and the training tab reads `train.history`.

## Run on login

### Linux (systemd user service)

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/airtrain.service <<'UNIT'
[Unit]
Description=AirTrain agent
After=network-online.target

[Service]
ExecStart=%h/AirTrain/.venv/bin/airtrain serve --train --quiet
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
UNIT
systemctl --user import-environment DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS
systemctl --user daemon-reload
systemctl --user enable --now airtrain
journalctl --user -u airtrain -f      # logs
```

Adjust `ExecStart` if you cloned somewhere other than `~/AirTrain`. The `import-environment` line gives the service access to your desktop session, which idle detection needs.

### Windows (Task Scheduler)

Run this in PowerShell. It starts the agent hidden at logon, inside your session, which idle detection needs:

```powershell
$exe = "$env:USERPROFILE\AirTrain\.venv\Scripts\airtrain.exe"
$action = New-ScheduledTaskAction -Execute $exe -Argument "serve --train --quiet"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "AirTrain agent" -Action $action -Trigger $trigger -Settings $settings
```

To remove it: `Unregister-ScheduledTask -TaskName "AirTrain agent"`.

## Development checks

```bash
pip install -e ./agent
python -m unittest discover -s agent/tests -v                    # no GPU needed; NVML is faked
python agent/tests/smoke_ws.py                                   # serve + client + pause/resume
python agent/tests/smoke_ws.py --train --dataset synthetic       # with the trainer (needs [train])
```

## Limitations

- GPU telemetry and CUDA training cover NVIDIA only. AMD and Intel GPUs fall back to CPU and RAM reporting and CPU training.
- macOS is not supported yet.
- Training runs locally on each machine. Federated averaging through the coordinator is the next step.
- Traffic is plain `ws://` on the LAN, protected by the pairing token. Do not expose the port to the internet.
