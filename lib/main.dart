import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
  });

  final String id, name, gpu;
  final IconData icon;
  final DeviceState state;
  final bool paused;
  final double util, vramUsed, vramTotal, temp, power;
  final List<double> history;
  final int samples;

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
  }) =>
      Device(
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

class SwarmState {
  const SwarmState(this.devices, this.job);
  final List<Device> devices;
  final Job job;
}

// ---------- Mock data source (replace with WebSocket later) ----------
class SwarmNotifier extends Notifier<SwarmState> {
  final _rng = Random();
  Timer? _timer;
  int _tick = 0;

  @override
  SwarmState build() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _step());
    ref.onDispose(() => _timer?.cancel());
    return SwarmState(
      const [
        Device(
          id: 'pc',
          name: 'Linux PC',
          gpu: 'NVIDIA GPU · CUDA',
          icon: Icons.desktop_windows_rounded,
          vramTotal: 8,
          state: DeviceState.training,
        ),
        Device(
          id: 'mac',
          name: 'MacBook Air',
          gpu: 'Apple Silicon · MPS',
          icon: Icons.laptop_mac_rounded,
          vramTotal: 8,
        ),
      ],
      Job(round: 0, totalRounds: 50, acc: const [], loss: const [], log: const [], startedAt: DateTime.now()),
    );
  }

  void _step() {
    _tick++;
    final devices = state.devices.map((d) {
      var s = d.state;
      if (d.id == 'mac' && _tick == 8) s = DeviceState.training; // became idle-eligible
      final active = s == DeviceState.training && !d.paused;
      final target = active ? 88 + _rng.nextDouble() * 10 : 2 + _rng.nextDouble() * 4;
      final util = d.util + (target - d.util) * 0.5;
      final temp = d.temp + ((active ? 72 : 42) - d.temp) * 0.1 + _rng.nextDouble() - 0.5;
      final history = [...d.history, util];
      if (history.length > 40) history.removeAt(0);
      return d.copyWith(
        state: s,
        util: util,
        temp: temp,
        vramUsed: d.vramTotal * (active ? 0.62 : 0.08),
        power: active ? (d.id == 'pc' ? 160 : 18) * util / 100 + 5 : 5 + _rng.nextDouble() * 2,
        history: history,
        samples: d.samples + (active ? (d.id == 'pc' ? 1800 : 600) : 0),
      );
    }).toList();

    int sum(List<Device> l) => l.fold<int>(0, (a, d) => a + d.samples);
    final total = sum(devices);
    var job = state.job.copyWith(throughput: (total - sum(state.devices)).toDouble());
    if (devices.any((d) => d.active) && _tick % 4 == 0 && job.round < job.totalRounds) {
      final r = job.round + 1;
      final a = 0.86 * (1 - exp(-r / 10)) + (_rng.nextDouble() - 0.5) * 0.01;
      final l = 2.3 * exp(-r / 12) + 0.35 + (_rng.nextDouble() - 0.5) * 0.04;
      final n = devices.where((d) => d.active).length;
      job = job.copyWith(
        round: r,
        acc: [...job.acc, a],
        loss: [...job.loss, l],
        log: [RoundLog(r, a, l, n, total), ...job.log],
      );
    }
    state = SwarmState(devices, job);
  }

  void togglePause(String id) {
    state = SwarmState(
      [for (final d in state.devices) d.id == id ? d.copyWith(paused: !d.paused) : d],
      state.job,
    );
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
      body: IndexedStack(index: _i, children: const [HomeScreen(), TrainingScreen()]),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(border: Border(top: BorderSide(color: C.border))),
        child: NavigationBar(
          backgroundColor: C.bg,
          indicatorColor: C.accent.withValues(alpha: 0.18),
          height: 64,
          selectedIndex: _i,
          onDestinationSelected: (i) => setState(() => _i = i),
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          destinations: const [
            NavigationDestination(
                icon: Icon(Icons.grid_view_outlined), selectedIcon: Icon(Icons.grid_view_rounded), label: 'Overview'),
            NavigationDestination(
                icon: Icon(Icons.insights_outlined), selectedIcon: Icon(Icons.insights_rounded), label: 'Training'),
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
    final job = ref.watch(swarmProvider).job;
    final elapsed = DateTime.now().difference(job.startedAt);
    final done = job.round >= job.totalRounds;
    final eta = job.round == 0 ? null : elapsed * ((job.totalRounds - job.round) / job.round);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            const Text('Training',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5)),
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
                            Text('${(job.progress * 100).toStringAsFixed(0)}%',
                                style: const TextStyle(
                                    color: C.text, fontSize: 24, fontWeight: FontWeight.w700, fontFeatures: tabular)),
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
                        KV('ETA', done ? 'Complete' : eta == null ? '--' : fmtDur(eta)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Row(children: [
              MetricTile(label: 'Accuracy', value: pct(job.accuracy)),
              const SizedBox(width: 12),
              MetricTile(label: 'Best', value: pct(job.bestAccuracy)),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              MetricTile(label: 'Loss', value: job.currentLoss.toStringAsFixed(3)),
              const SizedBox(width: 12),
              MetricTile(label: 'Throughput', value: '${fmt(job.throughput.round())}/s'),
            ]),
            const SizedBox(height: 12),
            ChartCard(title: 'Accuracy', value: pct(job.accuracy), data: job.acc, max: 1, color: C.accent),
            const SizedBox(height: 12),
            ChartCard(
                title: 'Loss', value: job.currentLoss.toStringAsFixed(3), data: job.loss, max: 2.7, color: C.amber),
            const SizedBox(height: 28),
            const Text('RECENT ROUNDS',
                style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2)),
            const SizedBox(height: 12),
            Container(
              decoration: cardDeco,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: job.log.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Center(child: Text('Waiting for first round', style: TextStyle(color: C.muted))),
                    )
                  : Column(
                      children: [
                        const _RoundRow(cells: ['Round', 'Accuracy', 'Loss', 'Devices'], header: true),
                        for (final r in job.log.take(8))
                          _RoundRow(cells: [
                            '#${r.round}',
                            pct(r.acc),
                            r.loss.toStringAsFixed(3),
                            '${r.devices}',
                          ]),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
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
          Text(v,
              style: const TextStyle(
                  color: C.text, fontSize: 14, fontWeight: FontWeight.w600, fontFeatures: tabular)),
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
            Text(value,
                style: const TextStyle(
                    color: C.text, fontSize: 22, fontWeight: FontWeight.w700, fontFeatures: tabular)),
          ],
        ),
      ),
    );
  }
}

class ChartCard extends StatelessWidget {
  const ChartCard(
      {super.key, required this.title, required this.value, required this.data, required this.max, required this.color});
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
              Text(title, style: const TextStyle(color: C.text, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontFeatures: tabular)),
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
      decoration: header ? null : const BoxDecoration(border: Border(top: BorderSide(color: C.border))),
      child: Row(
        children: [
          SizedBox(width: 56, child: Text(cells[0], style: style)),
          Expanded(child: Text(cells[1], style: style)),
          Expanded(child: Text(cells[2], style: style)),
          SizedBox(width: 56, child: Text(cells[3], style: style, textAlign: TextAlign.right)),
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
                      Text('AirTrain',
                          style: TextStyle(
                              fontSize: 28, fontWeight: FontWeight.w700, color: C.text, letterSpacing: -0.5)),
                      SizedBox(height: 2),
                      Text('Idle compute, put to work', style: TextStyle(color: C.muted, fontSize: 13)),
                    ],
                  ),
                ),
                StatusPill(label: '$online online', color: C.green),
              ],
            ),
            const SizedBox(height: 20),
            JobCard(job: s.job, totalSamples: total, activeDevices: active),
            const SizedBox(height: 28),
            const Text('DEVICES',
                style: TextStyle(color: C.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2)),
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
              const Text('CIFAR-10 CNN', style: TextStyle(color: C.text, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text('Round ${job.round}/${job.totalRounds}',
                  style: const TextStyle(color: C.muted, fontSize: 13, fontFeatures: tabular)),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${(job.accuracy * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(
                      fontSize: 40,
                      fontWeight: FontWeight.w700,
                      color: C.text,
                      letterSpacing: -1,
                      fontFeatures: tabular)),
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
              builder: (_, v, _) => LinearProgressIndicator(
                value: v,
                minHeight: 6,
                backgroundColor: C.border,
                color: C.accent,
              ),
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
                    Text(d.name, style: const TextStyle(color: C.text, fontWeight: FontWeight.w600)),
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
              Stat(label: 'GPU', value: '${d.util.toStringAsFixed(0)}%'),
              Stat(label: 'VRAM', value: '${d.vramUsed.toStringAsFixed(1)}/${d.vramTotal.toStringAsFixed(0)}G'),
              Stat(label: 'Temp', value: '${d.temp.toStringAsFixed(0)}°C'),
              Stat(label: 'Power', value: '${d.power.toStringAsFixed(0)}W'),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Text('${(share * 100).toStringAsFixed(0)}% of work',
                  style: const TextStyle(color: C.muted, fontSize: 12, fontFeatures: tabular)),
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
          Text(value,
              style: const TextStyle(
                  color: C.text, fontSize: 15, fontWeight: FontWeight.w600, fontFeatures: tabular)),
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
          Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
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
