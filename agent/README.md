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
