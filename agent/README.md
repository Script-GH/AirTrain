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
