import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'agent_link.dart';
import 'world_mask.dart';

void main() => runApp(const ProviderScope(child: AirTrainApp()));

// ---------- Theme ----------
class C {
  static const bg = Color(0xFF0B0B0F);
  static const card = Color(0xFF15151B);
  static const border = Color(0xFF24242D);
  static const text = Color(0xFFEDEDF0);
  static const muted = Color(0xFF8A8A96);
  static const accent = Color(0xFF7C6CFF);
  static const green = Color(0xFF3DD68C);
  static const amber = Color(0xFFF5A524);
  static const red = Color(0xFFF2555A);
}

final cardDeco = BoxDecoration(
  color: C.card,
  borderRadius: BorderRadius.circular(16),
  border: Border.all(color: C.border),
);

const tabular = [FontFeature.tabularFigures()];

String fmt(int n) => n >= 1e6
    ? '${(n / 1e6).toStringAsFixed(1)}M'
    : n >= 1e3
    ? '${(n / 1e3).toStringAsFixed(1)}K'
    : '$n';

class AirTrainApp extends StatelessWidget {
  const AirTrainApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AirTrain',
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: C.bg,
        colorScheme: const ColorScheme.dark(primary: C.accent, surface: C.card),
      ),
      home: const MainShell(),
    );
  }
}

// ---------- Models ----------
enum DeviceState { training, idle, busy, offline }

/// The training cluster an agent has joined with `airtrain connect`.
class ClusterRef {
  const ClusterRef({required this.id, required this.name, this.region, this.lat, this.lon, this.latencyMs});
  final String id, name;
  final String? region;

  /// Where the cluster's coordinator runs (its region); null when unknown.
  final double? lat, lon;
  final double? latencyMs;
}

class Device {
  const Device({
    required this.id,
    required this.name,
    required this.gpu,
    required this.icon,
    required this.vramTotal,
    this.state = DeviceState.idle,
    this.paused = false,
    this.util = 0,
    this.vramUsed = 0,
    this.temp = 40,
    this.power = 5,
    this.history = const [],
    this.samples = 0,
    required this.tempLimit,
    required this.powerLimit,
    required this.ramTotal,
    this.hasFan = true,
    this.cpu = 0,
    this.ram = 0,
    this.fan = 0,
    this.clock = 0,
    this.throttled = false,
    this.tempHistory = const [],
    this.city,
    this.lat,
    this.lon,
    this.linkId,
    this.fanUnit = 'rpm',
    this.cpuOnly = false,
    this.jobName,
    this.cluster,
  });

  final String id, name, gpu;

  /// "City, CC" as reported by the agent; null when it does not know where it is.
  final String? city;

  /// Set for devices reported by a paired PC agent; null for demo devices.
  final String? linkId;
  final String fanUnit;

  /// No supported GPU: util/VRAM fields carry CPU load and system RAM instead.
  final bool cpuOnly;

  /// Job picked with `airtrain analysis` and the cluster joined with `airtrain connect`, if any.
  final String? jobName;
  final ClusterRef? cluster;

  /// Map position; both null when the location (or its coordinates) is unknown.
  final double? lat, lon;
  final IconData icon;
  final DeviceState state;
  final bool paused;
  final double util, vramUsed, vramTotal, temp, power;
  final List<double> history;
  final int samples;
  final double tempLimit, powerLimit, ramTotal;
  final bool hasFan;
  final double cpu, ram, clock;
  final int fan;
  final bool throttled;
  final List<double> tempHistory;

  String get unitLabel => cpuOnly ? 'CPU' : 'GPU';
  String get memLabel => cpuOnly ? 'RAM' : 'VRAM';

  /// Agents report 0 for sensors the machine does not expose.
  String get tempText => linkId != null && temp == 0 ? '—' : '${temp.toStringAsFixed(0)}°C';
  String get powerText => linkId != null && power == 0 ? '—' : '${power.toStringAsFixed(0)}W';

  /// 0-100 composite load score from GPU load, heat, power draw and memory pressure.
  double get stress {
    final t = ((temp - 35) / (tempLimit - 35)).clamp(0.0, 1.0) * 100;
    final p = (power / powerLimit).clamp(0.0, 1.0) * 100;
    final m = (vramUsed / vramTotal).clamp(0.0, 1.0) * 100;
    return (0.35 * util + 0.35 * t + 0.2 * p + 0.1 * m).clamp(0.0, 100.0);
  }

  double get headroom => tempLimit - temp;

  bool get active => state == DeviceState.training && !paused;

  Device copyWith({
    DeviceState? state,
    bool? paused,
    double? util,
    double? vramUsed,
    double? temp,
    double? power,
    List<double>? history,
    int? samples,
    double? cpu,
    double? ram,
    int? fan,
    double? clock,
    bool? throttled,
    List<double>? tempHistory,
  }) => Device(
    id: id,
    name: name,
    gpu: gpu,
    icon: icon,
    vramTotal: vramTotal,
    state: state ?? this.state,
    paused: paused ?? this.paused,
    util: util ?? this.util,
    vramUsed: vramUsed ?? this.vramUsed,
    temp: temp ?? this.temp,
    power: power ?? this.power,
    history: history ?? this.history,
    samples: samples ?? this.samples,
    tempLimit: tempLimit,
    powerLimit: powerLimit,
    ramTotal: ramTotal,
    hasFan: hasFan,
    cpu: cpu ?? this.cpu,
    ram: ram ?? this.ram,
    fan: fan ?? this.fan,
    clock: clock ?? this.clock,
    throttled: throttled ?? this.throttled,
    tempHistory: tempHistory ?? this.tempHistory,
    city: city,
    lat: lat,
    lon: lon,
    linkId: linkId,
    fanUnit: fanUnit,
    cpuOnly: cpuOnly,
    jobName: jobName,
    cluster: cluster,
  );
}

class RoundLog {
  const RoundLog(this.round, this.acc, this.loss, this.devices, this.samples);
  final int round, devices, samples;
  final double acc, loss;
}

class Job {
  const Job({
    required this.round,
    required this.totalRounds,
    required this.acc,
    required this.loss,
    required this.log,
    required this.startedAt,
    this.throughput = 0,
  });
  final int round, totalRounds;
  final List<double> acc, loss;
  final List<RoundLog> log; // newest first
  final DateTime startedAt;
  final double throughput; // samples per second
  double get accuracy => acc.isEmpty ? 0 : acc.last;
  double get bestAccuracy => acc.isEmpty ? 0 : acc.reduce((a, b) => a > b ? a : b);
  double get currentLoss => loss.isEmpty ? 0 : loss.last;
  double get progress => round / totalRounds;

  Job copyWith({int? round, List<double>? acc, List<double>? loss, List<RoundLog>? log, double? throughput}) => Job(
    round: round ?? this.round,
    totalRounds: totalRounds,
    acc: acc ?? this.acc,
    loss: loss ?? this.loss,
    log: log ?? this.log,
    startedAt: startedAt,
    throughput: throughput ?? this.throughput,
  );
}

/// A device owned by someone else that has joined the same training job.
class Peer {
  const Peer({
    required this.id,
    required this.name,
    required this.hw,
    required this.city,
    required this.lat,
    required this.lon,
    required this.baseLatency,
    this.joinAt = 0,
    this.leaveAt = -1,
    this.offline = false,
    this.state = DeviceState.idle,
    this.latency = 0,
  });
  final String id, name, hw, city;
  final double lat, lon;
  final int baseLatency, joinAt, leaveAt;
  final bool offline;
  final DeviceState state;
  final int latency;

  Peer step(int tick, Random rng) => Peer(
    id: id,
    name: name,
    hw: hw,
    city: city,
    lat: lat,
    lon: lon,
    baseLatency: baseLatency,
    joinAt: joinAt,
    leaveAt: leaveAt,
    offline: offline,
    state: offline
        ? DeviceState.offline
        : tick >= joinAt && (leaveAt < 0 || tick < leaveAt)
        ? DeviceState.training
        : DeviceState.idle,
    latency: offline ? 0 : baseLatency + rng.nextInt(max(4, baseLatency ~/ 6)),
  );
}

/// Where the FedAvg coordinator runs. Every device talks only to it (star topology).
const coordinator = (name: 'Coordinator', city: 'Mumbai, IN', lat: 19.07, lon: 72.88);

/// A paired PC agent as shown in the pairing sheet.
class AgentInfo {
  const AgentInfo({required this.id, required this.url, required this.status, this.error});
  final String id;
  final String url;
  final LinkStatus status;
  final String? error;
}

class SwarmState {
  const SwarmState(this.devices, this.job, [this.peers = const [], this.agents = const []]);
  final List<Device> devices;
  final Job job;
  final List<Peer> peers;
  final List<AgentInfo> agents;

  /// True once at least one PC agent is paired; the app then shows real devices.
  bool get live => agents.isNotEmpty;

  int get activeCount =>
      devices.where((d) => d.active).length + peers.where((p) => p.state == DeviceState.training).length;
  int get connectedCount =>
      devices.where((d) => d.state != DeviceState.offline).length + peers.where((p) => !p.offline).length;
  int get totalCount => devices.length + peers.length;
}

const _mockPeers = [
  Peer(id: 'lab4', name: 'Lab PC 04', hw: 'RTX 3060', city: 'Bengaluru, IN', lat: 13.03, lon: 77.50, baseLatency: 14),
  Peer(
    id: 'm2',
    name: 'MacBook Pro M2',
    hw: 'Apple M2 Pro',
    city: 'Hyderabad, IN',
    lat: 17.39,
    lon: 78.49,
    baseLatency: 31,
    joinAt: 5,
  ),
  Peer(
    id: 'pune',
    name: 'Gaming PC',
    hw: 'RTX 4060',
    city: 'Pune, IN',
    lat: 18.52,
    lon: 73.86,
    baseLatency: 22,
    joinAt: 12,
  ),
  Peer(
    id: 'del',
    name: 'Workstation',
    hw: 'RTX A4000',
    city: 'Delhi, IN',
    lat: 28.61,
    lon: 77.21,
    baseLatency: 38,
    joinAt: 20,
  ),
  Peer(
    id: 'ber',
    name: 'Desktop',
    hw: 'RTX 3080',
    city: 'Berlin, DE',
    lat: 52.52,
    lon: 13.40,
    baseLatency: 142,
    joinAt: 3,
  ),
  Peer(
    id: 'tyo',
    name: 'Mac Studio',
    hw: 'Apple M3 Max',
    city: 'Tokyo, JP',
    lat: 35.68,
    lon: 139.69,
    baseLatency: 96,
    joinAt: 2,
    leaveAt: 30,
  ),
  Peer(
    id: 'aus',
    name: 'Tower PC',
    hw: 'RTX 4070',
    city: 'Austin, US',
    lat: 30.27,
    lon: -97.74,
    baseLatency: 231,
    joinAt: 16,
  ),
  Peer(
    id: 'sp',
    name: 'Laptop',
    hw: 'GTX 1660 Ti',
    city: 'São Paulo, BR',
    lat: -23.55,
    lon: -46.63,
    baseLatency: 0,
    offline: true,
  ),
];

// ---------- Agent telemetry -> models ----------
double _n(Object? v, [double fallback = 0]) => v is num ? v.toDouble() : fallback;

List<double> _push(List<double> l, double v) {
  final out = [...l, v];
  if (out.length > 40) out.removeAt(0);
  return out;
}

/// Reads the agent's `location` block. Coordinates are only kept as a valid pair.
({String? city, double? lat, double? lon}) locationFromTelemetry(Map<String, dynamic> t) {
  final l = t['location'];
  if (l is! Map) return (city: null, lat: null, lon: null);
  String? str(Object? v) => v is String && v.trim().isNotEmpty ? v.trim() : null;
  double? coord(Object? v, double limit) => v is num && v.isFinite && v.abs() <= limit ? v.toDouble() : null;
  final parts = [str(l['city']), str(l['country'])].whereType<String>();
  final lat = coord(l['lat'], 90), lon = coord(l['lon'], 180);
  final hasPos = lat != null && lon != null;
  return (city: parts.isEmpty ? null : parts.join(', '), lat: hasPos ? lat : null, lon: hasPos ? lon : null);
}

/// Reads the agent's `cluster` block; null until the device has joined one.
ClusterRef? clusterFromTelemetry(Map<String, dynamic> t) {
  final c = t['cluster'];
  if (c is! Map || c['id'] == null) return null;
  double? num_(Object? v) => v is num && v.isFinite ? v.toDouble() : null;
  final lat = num_(c['lat']), lon = num_(c['lon']);
  final hasPos = lat != null && lon != null && lat.abs() <= 90 && lon.abs() <= 180;
  return ClusterRef(
    id: '${c['id']}',
    name: '${c['name'] ?? c['id']}',
    region: c['region'] is String ? c['region'] as String : null,
    lat: hasPos ? lat : null,
    lon: hasPos ? lon : null,
    latencyMs: num_(c['latency_ms']),
  );
}

/// Maps one `telemetry` message from `airtrain serve` (schema in agent/README.md) to a [Device].
Device deviceFromTelemetry(Map<String, dynamic> t, String linkId, Device? prev) {
  final dev = (t['device'] as Map?) ?? const {};
  final g = (t['gpu'] as Map?) ?? const {};
  final c = (t['cpu'] as Map?) ?? const {};
  final r = (t['ram'] as Map?) ?? const {};
  final train = t['train'] as Map?;
  final limits = (t['limits'] as Map?) ?? const {};
  final hasGpu = g['available'] == true;
  final loc = locationFromTelemetry(t);

  final util = hasGpu ? _n(g['util']) : _n(c['util']);
  final temp = hasGpu ? _n(g['temp_c']) : _n(c['temp_c']);
  final ramTotal = max(_n(r['total_gb'], 1), 0.1);
  final ram = _n(r['used_gb']);
  final fan = g['fan_pct'];
  final paused = t['paused'] == true;
  final state = switch (t['state']) {
    'training' => DeviceState.training,
    'busy' => DeviceState.busy,
    'offline' => DeviceState.offline,
    _ => DeviceState.idle,
  };

  return Device(
    id: 'agent:${dev['id'] ?? linkId}',
    linkId: linkId,
    name: '${dev['name'] ?? linkId}',
    gpu: hasGpu ? '${g['name']} · CUDA' : '${c['name'] ?? 'CPU'} · CPU only',
    icon: dev['kind'] == 'laptop' ? Icons.laptop_rounded : Icons.desktop_windows_rounded,
    vramTotal: hasGpu ? max(_n(g['vram_total_gb'], 1), 0.1) : ramTotal,
    vramUsed: hasGpu ? _n(g['vram_used_gb']) : ram,
    state: state,
    paused: paused,
    util: util,
    temp: temp,
    tempLimit: _n(g['temp_limit_c'], _n(limits['max_temp_c'], 90)),
    power: _n(g['power_w']),
    powerLimit: max(_n(g['power_limit_w'], 1), 1),
    ramTotal: ramTotal,
    ram: ram,
    cpu: _n(c['util']),
    hasFan: fan is num,
    fan: fan is num ? fan.round() : 0,
    fanUnit: '%',
    cpuOnly: !hasGpu,
    clock: _n(g['clock_mhz'], _n(c['freq_mhz'])),
    throttled: g['throttled'] == true,
    samples: train == null ? 0 : _n(train['samples']).round(),
    history: _push(prev?.history ?? const [], util),
    tempHistory: _push(prev?.tempHistory ?? const [], temp),
    city: loc.city,
    lat: loc.lat,
    lon: loc.lon,
    jobName: (t['job'] as Map?)?['name'] as String?,
    cluster: clusterFromTelemetry(t),
  );
}

/// Builds the training job view from the agent that has made the most progress.
Job? jobFromTelemetry(Iterable<Map<String, dynamic>> snaps, DateTime startedAt) {
  Map? best;
  for (final s in snaps) {
    final t = s['train'];
    if (t is Map && (best == null || _n(t['round']) > _n(best['round']))) best = t;
  }
  if (best == null) return null;
  final hist = [for (final h in (best['history'] as List? ?? const [])) h as Map];
  return Job(
    round: _n(best['round']).round(),
    totalRounds: max(_n(best['total_rounds'], 1).round(), 1),
    acc: [for (final h in hist) _n(h['accuracy'])],
    loss: [for (final h in hist) _n(h['loss'])],
    log: [
      for (final h in hist.reversed)
        RoundLog(_n(h['round']).round(), _n(h['accuracy']), _n(h['loss']), 1, _n(h['samples']).round()),
    ],
    startedAt: startedAt,
    throughput: snaps.fold(0.0, (a, s) => a + _n((s['train'] as Map?)?['samples_per_s'])),
  );
}

// ---------- Data source: demo simulation, replaced by real agents once paired ----------
class SwarmNotifier extends Notifier<SwarmState> {
  static const _prefsKey = 'agents';
  final _rng = Random();
  Timer? _timer;
  int _tick = 0;

  // Real agents.
  final _links = <String, AgentLink>{};
  final _agentInfo = <String, AgentInfo>{};
  final _snaps = <String, Map<String, dynamic>>{};
  final _liveDevices = <String, Device>{};
  DateTime? _liveStart;
  SwarmState? _demo; // demo state, kept so unpairing everything falls back to it

  @override
  SwarmState build() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _step());
    ref.onDispose(() {
      _timer?.cancel();
      for (final l in _links.values) {
        l.close();
      }
    });
    _restore();
    return SwarmState(
      const [
        Device(
          id: 'pc',
          name: 'Linux PC',
          gpu: 'NVIDIA GPU · CUDA',
          icon: Icons.desktop_windows_rounded,
          vramTotal: 8,
          state: DeviceState.training,
          tempLimit: 83,
          powerLimit: 170,
          ramTotal: 16,
          city: 'Bengaluru, IN',
          lat: 12.97,
          lon: 77.59,
        ),
        Device(
          id: 'mac',
          name: 'MacBook Air',
          gpu: 'Apple Silicon · MPS',
          icon: Icons.laptop_mac_rounded,
          vramTotal: 8,
          tempLimit: 95,
          powerLimit: 25,
          ramTotal: 8,
          hasFan: false,
          city: 'Bengaluru, IN',
          lat: 12.90,
          lon: 77.66,
        ),
      ],
      Job(round: 0, totalRounds: 50, acc: const [], loss: const [], log: const [], startedAt: DateTime.now()),
      [for (final p in _mockPeers) p.step(0, _rng)],
    );
  }

  void _step() {
    _tick++;
    if (state.live) {
      _demo = _advanceDemo(_demo!);
      state = SwarmState(state.devices, state.job, _demo!.peers, state.agents);
      return;
    }
    state = _advanceDemo(state);
  }

  SwarmState _advanceDemo(SwarmState state) {
    final devices = state.devices.map((d) {
      var s = d.state;
      if (d.id == 'mac' && _tick == 8) s = DeviceState.training; // became idle-eligible
      final active = s == DeviceState.training && !d.paused;
      final target = active ? 88 + _rng.nextDouble() * 10 : 2 + _rng.nextDouble() * 4;
      final util = d.util + (target - d.util) * 0.5;
      final hotTarget = d.hasFan ? 72.0 : 84.0; // fanless laptops run hotter
      final temp = d.temp + ((active ? hotTarget : 42) - d.temp) * 0.1 + _rng.nextDouble() - 0.5;
      final history = [...d.history, util];
      if (history.length > 40) history.removeAt(0);
      final tempHistory = [...d.tempHistory, temp];
      if (tempHistory.length > 40) tempHistory.removeAt(0);
      final throttled = temp > d.tempLimit - 3;
      final baseClock = d.hasFan ? 1950.0 : 1400.0;
      return d.copyWith(
        cpu: active ? 35 + _rng.nextDouble() * 20 : 4 + _rng.nextDouble() * 6,
        ram: d.ramTotal * (active ? 0.68 : 0.42) + _rng.nextDouble() * 0.2,
        fan: d.hasFan ? (active ? 1700 + ((temp - 40) * 25).round() + _rng.nextInt(80) : 900 + _rng.nextInt(60)) : 0,
        clock: active ? baseClock * (throttled ? 0.82 : 1.0) - _rng.nextDouble() * 30 : 300 + _rng.nextDouble() * 40,
        throttled: active && throttled,
        tempHistory: tempHistory,
        state: s,
        util: util,
        temp: temp,
        vramUsed: d.vramTotal * (active ? 0.62 : 0.08),
        power: active ? (d.id == 'pc' ? 160 : 18) * util / 100 + 5 : 5 + _rng.nextDouble() * 2,
        history: history,
        samples: d.samples + (active ? (d.id == 'pc' ? 1800 : 600) : 0),
      );
    }).toList();

    final peers = [for (final p in state.peers) p.step(_tick, _rng)];
    int sum(List<Device> l) => l.fold<int>(0, (a, d) => a + d.samples);
    final total = sum(devices);
    var job = state.job.copyWith(throughput: (total - sum(state.devices)).toDouble());
    if (devices.any((d) => d.active) && _tick % 4 == 0 && job.round < job.totalRounds) {
      final r = job.round + 1;
      final a = 0.86 * (1 - exp(-r / 10)) + (_rng.nextDouble() - 0.5) * 0.01;
      final l = 2.3 * exp(-r / 12) + 0.35 + (_rng.nextDouble() - 0.5) * 0.04;
      final n = devices.where((d) => d.active).length + peers.where((p) => p.state == DeviceState.training).length;
      job = job.copyWith(
        round: r,
        acc: [...job.acc, a],
        loss: [...job.loss, l],
        log: [RoundLog(r, a, l, n, total), ...job.log],
      );
    }
    return SwarmState(devices, job, peers);
  }

  void togglePause(String id) {
    final dev = state.devices.firstWhere((d) => d.id == id);
    final link = dev.linkId == null ? null : _links[dev.linkId];
    link?.send(dev.paused ? 'resume' : 'pause');
    state = SwarmState(
      [for (final d in state.devices) d.id == id ? d.copyWith(paused: !d.paused) : d],
      state.job,
      state.peers,
      state.agents,
    );
  }

  // ---- pairing ----
  Future<void> _restore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final u in prefs.getStringList(_prefsKey) ?? const <String>[]) {
        addAgent(u, save: false);
      }
    } catch (_) {
      // No storage available (tests, unsupported platform): stay in demo mode.
    }
  }

  Future<void> _save() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_prefsKey, [for (final l in _links.values) l.uri.toString()]);
    } catch (_) {}
  }

  /// Pairs a PC agent. Throws [FormatException] if the address or token is invalid.
  void addAgent(String address, {String token = '', bool save = true}) {
    final uri = parseAgentUri(address, token);
    final id = '${uri.host}:${uri.port}';
    _links.remove(id)?.close();
    final real = AgentLink(
      uri,
      onMessage: (m) => _onMessage(id, m),
      onStatus: (st, err) => _onStatus(id, uri, st, err),
    );
    _links[id] = real;
    _agentInfo[id] = AgentInfo(id: id, url: '${uri.host}:${uri.port}', status: LinkStatus.connecting);
    _demo ??= state;
    _publish();
    real.connect();
    if (save) _save();
  }

  void removeAgent(String id) {
    _links.remove(id)?.close();
    _agentInfo.remove(id);
    _snaps.remove(id);
    _liveDevices.remove(id);
    if (_links.isEmpty) {
      _liveStart = null;
      state = _demo ?? state;
      _demo = null;
    } else {
      _publish();
    }
    _save();
  }

  void _onStatus(String id, Uri uri, LinkStatus st, String? err) {
    if (!_links.containsKey(id)) return;
    _agentInfo[id] = AgentInfo(id: id, url: '${uri.host}:${uri.port}', status: st, error: err);
    if (st != LinkStatus.connected) {
      final d = _liveDevices[id];
      if (d != null) _liveDevices[id] = d.copyWith(state: DeviceState.offline);
    }
    _publish();
  }

  void _onMessage(String id, Map<String, dynamic> m) {
    if (m['type'] != 'telemetry' || !_links.containsKey(id)) return;
    _snaps[id] = m;
    _liveDevices[id] = deviceFromTelemetry(m, id, _liveDevices[id]);
    if (m['train'] != null) _liveStart ??= DateTime.now();
    _publish();
  }

  void _publish() {
    final job =
        jobFromTelemetry(_snaps.values, _liveStart ?? DateTime.now()) ??
        Job(round: 0, totalRounds: 1, acc: const [], loss: const [], log: const [], startedAt: DateTime.now());
    state = SwarmState(_liveDevices.values.toList(), job, (_demo ?? state).peers, _agentInfo.values.toList());
  }
}

final swarmProvider = NotifierProvider<SwarmNotifier, SwarmState>(SwarmNotifier.new);

// ---------- UI ----------
class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _i = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _i, children: const [HomeScreen(), TrainingScreen(), HealthScreen(), NetworkScreen()]),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: C.border)),
        ),
        child: NavigationBar(
          backgroundColor: C.bg,
          indicatorColor: C.accent.withValues(alpha: 0.18),
          height: 64,
          selectedIndex: _i,
          onDestinationSelected: (i) => setState(() => _i = i),
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.grid_view_outlined),
              selectedIcon: Icon(Icons.grid_view_rounded),
              label: 'Overview',
            ),
            NavigationDestination(
              icon: Icon(Icons.insights_outlined),
              selectedIcon: Icon(Icons.insights_rounded),
              label: 'Training',
            ),
            NavigationDestination(
              icon: Icon(Icons.monitor_heart_outlined),
              selectedIcon: Icon(Icons.monitor_heart_rounded),
              label: 'Health',
            ),
            NavigationDestination(
              icon: Icon(Icons.public_outlined),
              selectedIcon: Icon(Icons.public_rounded),
              label: 'Network',
            ),
          ],
        ),
      ),
    );
  }
}

String pct(double v) => '${(v * 100).toStringAsFixed(1)}%';

String fmtDur(Duration d) {
  final h = d.inHours, m = d.inMinutes % 60, s = d.inSeconds % 60;
  return h > 0 ? '${h}h ${m}m' : '${m}m ${s.toString().padLeft(2, '0')}s';
}

class TrainingScreen extends ConsumerWidget {
  const TrainingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final swarm = ref.watch(swarmProvider);
    final job = swarm.job;
    final elapsed = DateTime.now().difference(job.startedAt);
    final done = job.round >= job.totalRounds;
    final eta = job.round == 0 ? null : elapsed * ((job.totalRounds - job.round) / job.round);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            const Text(
              'Training',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5),
            ),
            const SizedBox(height: 2),
            const Text('CIFAR-10 CNN · FedAvg', style: TextStyle(color: C.muted, fontSize: 13)),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: cardDeco,
              child: Row(
                children: [
                  SizedBox(
                    width: 112,
                    height: 112,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        SizedBox.expand(
                          child: TweenAnimationBuilder<double>(
                            tween: Tween(end: job.progress),
                            duration: const Duration(milliseconds: 500),
                            builder: (_, v, _) => CircularProgressIndicator(
                              value: v,
                              strokeWidth: 8,
                              strokeCap: StrokeCap.round,
                              backgroundColor: C.border,
                              color: done ? C.green : C.accent,
                            ),
                          ),
                        ),
                        Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '${(job.progress * 100).toStringAsFixed(0)}%',
                              style: const TextStyle(
                                color: C.text,
                                fontSize: 24,
                                fontWeight: FontWeight.w700,
                                fontFeatures: tabular,
                              ),
                            ),
                            Text(done ? 'done' : 'trained', style: const TextStyle(color: C.muted, fontSize: 11)),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 20),
                  Expanded(
                    child: Column(
                      children: [
                        KV('Round', '${job.round} / ${job.totalRounds}'),
                        KV('Elapsed', fmtDur(elapsed)),
                        KV(
                          'ETA',
                          done
                              ? 'Complete'
                              : eta == null
                              ? '--'
                              : fmtDur(eta),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                MetricTile(label: 'Accuracy', value: pct(job.accuracy)),
                const SizedBox(width: 12),
                MetricTile(label: 'Best', value: pct(job.bestAccuracy)),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                MetricTile(label: 'Loss', value: job.currentLoss.toStringAsFixed(3)),
                const SizedBox(width: 12),
                MetricTile(label: 'Throughput', value: '${fmt(job.throughput.round())}/s'),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                MetricTile(label: 'Devices training', value: '${swarm.activeCount}'),
                const SizedBox(width: 12),
                MetricTile(label: 'Connected', value: '${swarm.connectedCount} / ${swarm.totalCount}'),
              ],
            ),
            const SizedBox(height: 12),
            ChartCard(title: 'Accuracy', value: pct(job.accuracy), data: job.acc, max: 1, color: C.accent),
            const SizedBox(height: 12),
            ChartCard(
              title: 'Loss',
              value: job.currentLoss.toStringAsFixed(3),
              data: job.loss,
              max: 2.7,
              color: C.amber,
            ),
            const SizedBox(height: 28),
            const Text(
              'RECENT ROUNDS',
              style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2),
            ),
            const SizedBox(height: 12),
            Container(
              decoration: cardDeco,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: job.log.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Center(
                        child: Text('Waiting for first round', style: TextStyle(color: C.muted)),
                      ),
                    )
                  : Column(
                      children: [
                        const _RoundRow(cells: ['Round', 'Accuracy', 'Loss', 'Devices'], header: true),
                        for (final r in job.log.take(8))
                          _RoundRow(cells: ['#${r.round}', pct(r.acc), r.loss.toStringAsFixed(3), '${r.devices}']),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

(String, Color) stressLevel(double s) => s < 40
    ? ('Low', C.green)
    : s < 65
    ? ('Moderate', C.accent)
    : s < 85
    ? ('High', C.amber)
    : ('Critical', C.red);

class HealthScreen extends ConsumerWidget {
  const HealthScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devices = ref.watch(swarmProvider).devices;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            const Text(
              'Device health',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5),
            ),
            const SizedBox(height: 2),
            const Text('How hard each device is working', style: TextStyle(color: C.muted, fontSize: 13)),
            const SizedBox(height: 20),
            for (final d in devices)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: HealthCard(device: d),
              ),
          ],
        ),
      ),
    );
  }
}

class HealthCard extends ConsumerWidget {
  const HealthCard({super.key, required this.device});
  final Device device;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final d = device;
    final (label, color) = stressLevel(d.stress);
    final tempColor = d.headroom < 5
        ? C.red
        : d.headroom < 15
        ? C.amber
        : C.green;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardDeco,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(d.icon, color: C.text, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  d.name,
                  style: const TextStyle(color: C.text, fontWeight: FontWeight.w600),
                ),
              ),
              if (d.throttled) ...[const StatusPill(label: 'Throttling', color: C.red), const SizedBox(width: 6)],
              StatusPill(label: label, color: color),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              SizedBox(
                width: 120,
                height: 100,
                child: TweenAnimationBuilder<double>(
                  tween: Tween(end: d.stress),
                  duration: const Duration(milliseconds: 600),
                  builder: (_, v, _) => CustomPaint(
                    painter: _GaugePainter(v / 100, color),
                    child: Padding(
                      padding: const EdgeInsets.only(top: 34),
                      child: Column(
                        children: [
                          Text(
                            d.stress.toStringAsFixed(0),
                            style: const TextStyle(
                              color: C.text,
                              fontSize: 28,
                              fontWeight: FontWeight.w700,
                              fontFeatures: tabular,
                            ),
                          ),
                          const Text('stress', style: TextStyle(color: C.muted, fontSize: 11)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  children: [
                    if (!d.cpuOnly) LoadBar(label: 'GPU', value: d.util / 100, text: '${d.util.toStringAsFixed(0)}%'),
                    LoadBar(label: 'CPU', value: d.cpu / 100, text: '${d.cpu.toStringAsFixed(0)}%'),
                    if (!d.cpuOnly)
                      LoadBar(
                        label: 'VRAM',
                        value: d.vramUsed / d.vramTotal,
                        text: '${d.vramUsed.toStringAsFixed(1)}/${d.vramTotal.toStringAsFixed(0)}G',
                      ),
                    LoadBar(
                      label: 'RAM',
                      value: d.ram / d.ramTotal,
                      text: '${d.ram.toStringAsFixed(1)}/${d.ramTotal.toStringAsFixed(0)}G',
                    ),
                    if (d.powerText != '—')
                      LoadBar(
                        label: 'Power',
                        value: d.power / d.powerLimit,
                        text: '${d.power.toStringAsFixed(0)}/${d.powerLimit.toStringAsFixed(0)}W',
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Text('Temperature', style: TextStyle(color: C.muted, fontSize: 12)),
              const Spacer(),
              Text(
                d.tempText,
                style: TextStyle(color: tempColor, fontWeight: FontWeight.w600, fontFeatures: tabular),
              ),
              Text(
                '  /  limit ${d.tempLimit.toStringAsFixed(0)}°C',
                style: const TextStyle(color: C.muted, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Sparkline(data: d.tempHistory, max: d.tempLimit + 5, color: tempColor, height: 56),
          const SizedBox(height: 16),
          Row(
            children: [
              Stat(label: 'Headroom', value: d.tempText == '—' ? '—' : '${d.headroom.toStringAsFixed(0)}°C'),
              Stat(label: 'Clock', value: '${d.clock.toStringAsFixed(0)} MHz'),
              Stat(
                label: 'Fan',
                value: d.hasFan
                    ? '${d.fan} ${d.fanUnit}'
                    : d.linkId != null
                    ? 'n/a'
                    : 'Fanless',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class LoadBar extends StatelessWidget {
  const LoadBar({super.key, required this.label, required this.value, required this.text});
  final String label, text;
  final double value;

  @override
  Widget build(BuildContext context) {
    final v = value.clamp(0.0, 1.0);
    final color = v > 0.9
        ? C.red
        : v > 0.75
        ? C.amber
        : C.accent;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 44,
            child: Text(label, style: const TextStyle(color: C.muted, fontSize: 12)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: TweenAnimationBuilder<double>(
                tween: Tween(end: v),
                duration: const Duration(milliseconds: 500),
                builder: (_, x, _) =>
                    LinearProgressIndicator(value: x, minHeight: 5, backgroundColor: C.border, color: color),
              ),
            ),
          ),
          SizedBox(
            width: 64,
            child: Text(
              text,
              textAlign: TextAlign.right,
              style: const TextStyle(color: C.text, fontSize: 12, fontFeatures: tabular),
            ),
          ),
        ],
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  _GaugePainter(this.value, this.color);
  final double value;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const start = pi * 0.75, sweep = pi * 1.5;
    final r = min(size.width, size.height * 1.2) / 2 - 6;
    final rect = Rect.fromCircle(center: Offset(size.width / 2, r + 6), radius: r);
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, start, sweep, false, base..color = C.border);
    canvas.drawArc(rect, start, sweep * value.clamp(0.0, 1.0), false, base..color = color);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter old) => old.value != value || old.color != color;
}

class KV extends StatelessWidget {
  const KV(this.k, this.v, {super.key});
  final String k, v;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Text(k, style: const TextStyle(color: C.muted, fontSize: 13)),
          const Spacer(),
          Text(
            v,
            style: const TextStyle(color: C.text, fontSize: 14, fontWeight: FontWeight.w600, fontFeatures: tabular),
          ),
        ],
      ),
    );
  }
}

class MetricTile extends StatelessWidget {
  const MetricTile({super.key, required this.label, required this.value});
  final String label, value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: cardDeco,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: C.muted, fontSize: 12)),
            const SizedBox(height: 6),
            Text(
              value,
              style: const TextStyle(color: C.text, fontSize: 22, fontWeight: FontWeight.w700, fontFeatures: tabular),
            ),
          ],
        ),
      ),
    );
  }
}

class ChartCard extends StatelessWidget {
  const ChartCard({
    super.key,
    required this.title,
    required this.value,
    required this.data,
    required this.max,
    required this.color,
  });
  final String title, value;
  final List<double> data;
  final double max;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardDeco,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                title,
                style: const TextStyle(color: C.text, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              Text(
                value,
                style: TextStyle(color: color, fontWeight: FontWeight.w600, fontFeatures: tabular),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Sparkline(data: data, max: max, color: color, height: 110),
        ],
      ),
    );
  }
}

class _RoundRow extends StatelessWidget {
  const _RoundRow({required this.cells, this.header = false});
  final List<String> cells;
  final bool header;

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(
      color: header ? C.muted : C.text,
      fontSize: header ? 12 : 14,
      fontWeight: header ? FontWeight.w500 : FontWeight.w500,
      fontFeatures: tabular,
    );
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: header
          ? null
          : const BoxDecoration(
              border: Border(top: BorderSide(color: C.border)),
            ),
      child: Row(
        children: [
          SizedBox(width: 56, child: Text(cells[0], style: style)),
          Expanded(child: Text(cells[1], style: style)),
          Expanded(child: Text(cells[2], style: style)),
          SizedBox(
            width: 56,
            child: Text(cells[3], style: style, textAlign: TextAlign.right),
          ),
        ],
      ),
    );
  }
}

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(swarmProvider);
    final online = s.devices.where((d) => d.state != DeviceState.offline).length;
    final active = s.devices.where((d) => d.active).length;
    final total = s.devices.fold<int>(0, (a, d) => a + d.samples);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            Row(
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AirTrain',
                        style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5),
                      ),
                      SizedBox(height: 2),
                      Text('Idle compute, put to work', style: TextStyle(color: C.muted, fontSize: 13)),
                    ],
                  ),
                ),
                StatusPill(label: s.live ? '$online online' : 'Demo data', color: s.live ? C.green : C.amber),
                const SizedBox(width: 8),
                IconButton.filledTonal(
                  tooltip: 'Pair a PC agent',
                  onPressed: () => showPairSheet(context),
                  style: IconButton.styleFrom(backgroundColor: C.border, foregroundColor: C.text),
                  icon: const Icon(Icons.add_link_rounded, size: 20),
                ),
              ],
            ),
            const SizedBox(height: 20),
            JobCard(job: s.job, totalSamples: total, activeDevices: active),
            const SizedBox(height: 28),
            const Text(
              'DEVICES',
              style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2),
            ),
            const SizedBox(height: 12),
            for (final d in s.devices)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: DeviceCard(device: d, share: total == 0 ? 0 : d.samples / total),
              ),
          ],
        ),
      ),
    );
  }
}

class JobCard extends StatelessWidget {
  const JobCard({super.key, required this.job, required this.totalSamples, required this.activeDevices});
  final Job job;
  final int totalSamples, activeDevices;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: cardDeco,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text(
                'CIFAR-10 CNN',
                style: TextStyle(color: C.text, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              Text(
                'Round ${job.round}/${job.totalRounds}',
                style: const TextStyle(color: C.muted, fontSize: 13, fontFeatures: tabular),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${(job.accuracy * 100).toStringAsFixed(1)}%',
                style: const TextStyle(
                  fontSize: 40,
                  fontWeight: FontWeight.w700,
                  color: C.text,
                  letterSpacing: -1,
                  fontFeatures: tabular,
                ),
              ),
              const SizedBox(width: 8),
              const Padding(
                padding: EdgeInsets.only(bottom: 9),
                child: Text('accuracy', style: TextStyle(color: C.muted)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Sparkline(data: job.acc, max: 1, color: C.accent, height: 56),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: TweenAnimationBuilder<double>(
              tween: Tween(end: job.round / job.totalRounds),
              duration: const Duration(milliseconds: 400),
              builder: (_, v, _) =>
                  LinearProgressIndicator(value: v, minHeight: 6, backgroundColor: C.border, color: C.accent),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Stat(label: 'Samples', value: fmt(totalSamples)),
              Stat(label: 'Training on', value: '$activeDevices devices'),
            ],
          ),
        ],
      ),
    );
  }
}

class DeviceCard extends ConsumerWidget {
  const DeviceCard({super.key, required this.device, required this.share});
  final Device device;
  final double share;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final d = device;
    final color = d.paused
        ? C.amber
        : switch (d.state) {
            DeviceState.training => C.green,
            DeviceState.idle => C.muted,
            DeviceState.busy => C.amber,
            DeviceState.offline => C.red,
          };
    final label = d.paused
        ? 'Paused'
        : switch (d.state) {
            DeviceState.training => 'Training',
            DeviceState.idle => 'Idle',
            DeviceState.busy => 'In use',
            DeviceState.offline => 'Offline',
          };

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardDeco,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(color: C.border, borderRadius: BorderRadius.circular(10)),
                child: Icon(d.icon, color: C.text, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      d.name,
                      style: const TextStyle(color: C.text, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 2),
                    Text(d.gpu, style: const TextStyle(color: C.muted, fontSize: 12)),
                  ],
                ),
              ),
              StatusPill(label: label, color: color),
            ],
          ),
          const SizedBox(height: 16),
          Sparkline(data: d.history, max: 100, color: color, height: 44),
          const SizedBox(height: 16),
          Row(
            children: [
              Stat(label: d.unitLabel, value: '${d.util.toStringAsFixed(0)}%'),
              Stat(label: d.memLabel, value: '${d.vramUsed.toStringAsFixed(1)}/${d.vramTotal.toStringAsFixed(0)}G'),
              Stat(label: 'Temp', value: d.tempText),
              Stat(label: 'Power', value: d.powerText),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Text(
                '${(share * 100).toStringAsFixed(0)}% of work',
                style: const TextStyle(color: C.muted, fontSize: 12, fontFeatures: tabular),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: () => ref.read(swarmProvider.notifier).togglePause(d.id),
                icon: Icon(d.paused ? Icons.play_arrow_rounded : Icons.pause_rounded, size: 18),
                label: Text(d.paused ? 'Resume' : 'Pause'),
                style: TextButton.styleFrom(
                  foregroundColor: C.text,
                  backgroundColor: C.border,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class Stat extends StatelessWidget {
  const Stat({super.key, required this.label, required this.value});
  final String label, value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: C.muted, fontSize: 12)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(color: C.text, fontSize: 15, fontWeight: FontWeight.w600, fontFeatures: tabular),
          ),
        ],
      ),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class Sparkline extends StatelessWidget {
  const Sparkline({super.key, required this.data, required this.max, required this.color, this.height = 48});
  final List<double> data;
  final double max, height;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      width: double.infinity,
      child: CustomPaint(painter: _SparkPainter(data, max, color)),
    );
  }
}

class _SparkPainter extends CustomPainter {
  _SparkPainter(this.data, this.max, this.color);
  final List<double> data;
  final double max;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (data.length < 2) return;
    final dx = size.width / (data.length - 1);
    final path = Path();
    for (var i = 0; i < data.length; i++) {
      final x = i * dx;
      final y = size.height - (data[i] / max).clamp(0.0, 1.0) * size.height;
      i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
    }
    final fill = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.25), color.withValues(alpha: 0)],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _SparkPainter old) => true;
}

// ---------- Network ----------
/// One point on the map: either one of your devices or a peer.
class NetNode {
  const NetNode(this.name, this.detail, this.city, this.lat, this.lon, this.state, this.latency, this.mine);
  final String name, detail;
  final String? city;
  final double? lat, lon;
  final DeviceState state;
  final int latency;
  final bool mine;
}

Color stateColor(DeviceState s) => switch (s) {
  DeviceState.training => C.green,
  DeviceState.idle => C.muted,
  DeviceState.busy => C.amber,
  DeviceState.offline => C.red,
};

class NetworkScreen extends ConsumerStatefulWidget {
  const NetworkScreen({super.key});
  @override
  ConsumerState<NetworkScreen> createState() => _NetworkScreenState();
}

class _NetworkScreenState extends ConsumerState<NetworkScreen> with SingleTickerProviderStateMixin {
  late final _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800))..repeat();
  bool _india = false;

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(swarmProvider);
    final nodes = [
      for (final d in s.devices)
        NetNode(d.name, d.gpu, d.city, d.lat, d.lon, d.paused ? DeviceState.idle : d.state, 8 + d.id.length, true),
      for (final p in s.peers) NetNode(p.name, p.hw, p.city, p.lat, p.lon, p.state, p.latency, false),
    ];
    final live = nodes.where((n) => n.state != DeviceState.offline && n.latency > 0).toList();
    final avgLatency = live.isEmpty ? 0 : live.fold<int>(0, (a, n) => a + n.latency) ~/ live.length;
    final countries = nodes
        .where((n) => n.state != DeviceState.offline)
        .map((n) => n.city?.split(', ').last)
        .nonNulls
        .toSet();
    final sorted = [...nodes]..sort((a, b) => a.state.index.compareTo(b.state.index));

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            const Text(
              'Network',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5),
            ),
            const SizedBox(height: 2),
            const Text('Every device syncs with one coordinator', style: TextStyle(color: C.muted, fontSize: 13)),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: cardDeco,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${s.activeCount}',
                        style: const TextStyle(
                          color: C.text,
                          fontSize: 44,
                          height: 1,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -1,
                          fontFeatures: tabular,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text('devices training now', style: TextStyle(color: C.muted, fontSize: 12)),
                    ],
                  ),
                  const Spacer(),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      _NetStat('Connected', '${s.connectedCount} / ${s.totalCount}'),
                      _NetStat('Yours', '${s.devices.where((d) => d.active).length} / ${s.devices.length}'),
                      _NetStat('Countries', '${countries.length}'),
                      _NetStat('Avg latency', '$avgLatency ms'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: cardDeco,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text(
                        'Device map',
                        style: TextStyle(color: C.text, fontWeight: FontWeight.w600),
                      ),
                      const Spacer(),
                      _Seg(
                        labels: const ['World', 'India'],
                        index: _india ? 1 : 0,
                        onTap: (i) => setState(() => _india = i == 1),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  LayoutBuilder(
                    builder: (_, c) {
                      final region = _india ? indiaMap : worldMap;
                      return SizedBox(
                        width: c.maxWidth,
                        height: c.maxWidth * region.aspect,
                        child: AnimatedBuilder(
                          animation: _pulse,
                          builder: (_, _) => CustomPaint(painter: _MapPainter(region, nodes, _pulse.value)),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 12),
                  const Wrap(
                    spacing: 14,
                    runSpacing: 6,
                    children: [
                      _Legend(C.accent, 'Coordinator'),
                      _Legend(C.green, 'Training'),
                      _Legend(C.muted, 'Idle'),
                      _Legend(C.red, 'Offline'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 28),
            const Text(
              'NODES',
              style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2),
            ),
            const SizedBox(height: 12),
            Container(
              decoration: cardDeco,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              child: Column(children: [for (final n in sorted) _NodeRow(n)]),
            ),
          ],
        ),
      ),
    );
  }
}

class _NetStat extends StatelessWidget {
  const _NetStat(this.label, this.value);
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: const TextStyle(color: C.muted, fontSize: 12)),
        const SizedBox(width: 10),
        SizedBox(
          width: 64,
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(color: C.text, fontSize: 12, fontWeight: FontWeight.w600, fontFeatures: tabular),
          ),
        ),
      ],
    ),
  );
}

class _Seg extends StatelessWidget {
  const _Seg({required this.labels, required this.index, required this.onTap});
  final List<String> labels;
  final int index;
  final ValueChanged<int> onTap;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(3),
    decoration: BoxDecoration(
      color: C.bg,
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: C.border),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < labels.length; i++)
          GestureDetector(
            onTap: () => onTap(i),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: i == index ? C.border : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                labels[i],
                style: TextStyle(color: i == index ? C.text : C.muted, fontSize: 12, fontWeight: FontWeight.w500),
              ),
            ),
          ),
      ],
    ),
  );
}

class _Legend extends StatelessWidget {
  const _Legend(this.color, this.label);
  final Color color;
  final String label;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(color: C.muted, fontSize: 11)),
    ],
  );
}

class _NodeRow extends StatelessWidget {
  const _NodeRow(this.n);
  final NetNode n;
  @override
  Widget build(BuildContext context) {
    final color = stateColor(n.state);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        n.name,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: C.text, fontSize: 14, fontWeight: FontWeight.w500),
                      ),
                    ),
                    if (n.mine) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: C.accent.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'You',
                          style: TextStyle(color: C.accent, fontSize: 10, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${n.detail} · ${n.city ?? 'Location unknown'}',
                  style: const TextStyle(color: C.muted, fontSize: 12),
                ),
              ],
            ),
          ),
          Text(
            n.state == DeviceState.offline ? 'offline' : '${n.latency} ms',
            style: TextStyle(
              color: n.state == DeviceState.offline ? C.red : C.muted,
              fontSize: 12,
              fontFeatures: tabular,
            ),
          ),
        ],
      ),
    );
  }
}

class _MapPainter extends CustomPainter {
  _MapPainter(this.region, this.nodes, this.t);
  final MapRegion region;
  final List<NetNode> nodes;
  final double t;

  Offset _project(double lat, double lon, Size size) {
    var x = lon;
    if (x < region.lonMin) x += 360;
    return Offset(
      (x - region.lonMin) / (region.lonMax - region.lonMin) * size.width,
      (region.latMax - lat) / (region.latMax - region.latMin) * size.height,
    );
  }

  Offset _bezier(Offset a, Offset c, Offset b, double t) =>
      a * ((1 - t) * (1 - t)) + c * (2 * (1 - t) * t) + b * (t * t);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.clipRect(Offset.zero & size);
    final cw = size.width / region.cols, ch = size.height / region.rows.length;
    final r = min(cw, ch) * 0.3;
    final land = Paint()..color = Colors.white.withValues(alpha: 0.13);
    for (var j = 0; j < region.rows.length; j++) {
      final row = region.rows[j];
      for (var i = 0; i < row.length; i++) {
        if (row.codeUnitAt(i) == 49) canvas.drawCircle(Offset((i + 0.5) * cw, (j + 0.5) * ch), r, land);
      }
    }

    final hub = _project(coordinator.lat, coordinator.lon, size);
    final dotR = max(2.6, size.width / 120);

    for (var k = 0; k < nodes.length; k++) {
      final n = nodes[k];
      final lat = n.lat, lon = n.lon;
      if (lat == null || lon == null) continue; // listed below the map, not drawn
      final p = _project(lat, lon, size);
      final color = stateColor(n.state);
      final mid = (p + hub) / 2;
      final d = hub - p;
      final ctrl = mid + Offset(d.dy, -d.dx) * 0.25 - Offset(0, d.distance * 0.12);

      if (n.state != DeviceState.offline) {
        final path = Path()
          ..moveTo(p.dx, p.dy)
          ..quadraticBezierTo(ctrl.dx, ctrl.dy, hub.dx, hub.dy);
        canvas.drawPath(
          path,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.2
            ..color = color.withValues(alpha: n.state == DeviceState.training ? 0.45 : 0.18),
        );
        if (n.state == DeviceState.training) {
          // update packets: device -> coordinator, then averaged weights back
          final ph = (t + k * 0.137) % 1.0;
          final up = ph < 0.5;
          final q = _bezier(p, ctrl, hub, up ? ph * 2 : 2 - ph * 2);
          canvas.drawCircle(q, 2.2, Paint()..color = up ? C.green : C.accent);
        }
      }
      canvas.drawCircle(p, dotR * 2.2, Paint()..color = color.withValues(alpha: 0.15));
      canvas.drawCircle(p, dotR, Paint()..color = color);
    }

    final glow = 0.5 + 0.5 * sin(t * 2 * pi);
    canvas.drawCircle(hub, dotR * (2.6 + glow), Paint()..color = C.accent.withValues(alpha: 0.18));
    canvas.drawCircle(hub, dotR * 1.4, Paint()..color = C.accent);
    canvas.drawCircle(hub, dotR * 0.6, Paint()..color = C.bg);
  }

  @override
  bool shouldRepaint(_MapPainter old) => true;
}

// ---------- Pairing ----------
void showPairSheet(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: C.card,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => const PairSheet(),
  );
}

class PairSheet extends ConsumerStatefulWidget {
  const PairSheet({super.key});
  @override
  ConsumerState<PairSheet> createState() => _PairSheetState();
}

class _PairSheetState extends ConsumerState<PairSheet> {
  final _url = TextEditingController();
  final _token = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _url.dispose();
    _token.dispose();
    super.dispose();
  }

  void _connect() {
    try {
      ref.read(swarmProvider.notifier).addAgent(_url.text, token: _token.text);
      _url.clear();
      _token.clear();
      setState(() => _error = null);
    } on FormatException catch (e) {
      setState(() => _error = e.message);
    }
  }

  InputDecoration _deco(String label, String hint) => InputDecoration(
    labelText: label,
    hintText: hint,
    labelStyle: const TextStyle(color: C.muted),
    hintStyle: const TextStyle(color: C.muted, fontSize: 13),
    filled: true,
    fillColor: C.bg,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: C.border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: C.border),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final agents = ref.watch(swarmProvider.select((s) => s.agents));
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Pair a PC agent',
            style: TextStyle(color: C.text, fontSize: 20, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          const Text(
            'Run `airtrain serve` on the PC and paste the App URL it prints. Phone and PC must be on the same network.',
            style: TextStyle(color: C.muted, fontSize: 13),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _url,
            style: const TextStyle(color: C.text),
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: _deco('Agent URL', 'ws://192.168.1.20:8765/?token=...'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _token,
            style: const TextStyle(color: C.text),
            autocorrect: false,
            decoration: _deco('Token (if not in the URL)', 'printed by airtrain serve'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: C.red, fontSize: 13)),
          ],
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _connect,
              style: FilledButton.styleFrom(
                backgroundColor: C.accent,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Connect', style: TextStyle(fontWeight: FontWeight.w600)),
            ),
          ),
          if (agents.isNotEmpty) ...[
            const SizedBox(height: 20),
            const Text(
              'PAIRED AGENTS',
              style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2),
            ),
            const SizedBox(height: 6),
            for (final a in agents) _AgentRow(agent: a),
          ] else ...[
            const SizedBox(height: 12),
            const Text(
              'No agents paired. The app shows demo data until you add one.',
              style: TextStyle(color: C.muted, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }
}

class _AgentRow extends ConsumerWidget {
  const _AgentRow({required this.agent});
  final AgentInfo agent;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final (label, color) = switch (agent.status) {
      LinkStatus.connected => ('Connected', C.green),
      LinkStatus.connecting => ('Connecting', C.amber),
      LinkStatus.unauthorized => ('Wrong token', C.red),
      LinkStatus.error => ('Unreachable', C.red),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.computer_rounded, color: C.muted, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              agent.url,
              style: const TextStyle(color: C.text, fontFeatures: tabular),
            ),
          ),
          StatusPill(label: label, color: color),
          IconButton(
            tooltip: 'Remove',
            onPressed: () => ref.read(swarmProvider.notifier).removeAgent(agent.id),
            icon: const Icon(Icons.close_rounded, color: C.muted, size: 18),
          ),
        ],
      ),
    );
  }
}
