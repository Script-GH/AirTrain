import 'dart:convert';

import 'package:airtrain/agent_link.dart';
import 'package:airtrain/main.dart';
import 'package:flutter_test/flutter_test.dart';

// Trimmed telemetry message as sent by `airtrain serve` (see agent/README.md).
const gpuSnapshot = '''
{"type":"telemetry","v":1,"ts":1763370000.0,
 "device":{"id":"a1b2c3","name":"Gaming PC","hostname":"gaming-pc","os":"Windows 11","platform":"win32","kind":"desktop"},
 "gpu":{"available":true,"vendor":"nvidia","name":"NVIDIA GeForce RTX 3060","util":97,"vram_used_gb":3.1,
        "vram_total_gb":12.0,"temp_c":71,"temp_limit_c":93,"power_w":151.5,"power_limit_w":170.0,"fan_pct":55,
        "clock_mhz":1890,"clock_max_mhz":2100,"throttle_reasons":["sw_power_cap"],"throttled":true,"processes":[]},
 "cpu":{"name":"AMD Ryzen 5 5600X","util":35.0,"cores":12,"freq_mhz":4200,"temp_c":null},
 "ram":{"used_gb":11.2,"total_gb":32.0},
 "battery":{"present":false,"percent":null,"plugged":null},
 "idle":{"user_idle_s":900.0,"method":"GetLastInputInfo","idle":true,"eligible":true,"reasons":[]},
 "blockers":[],"state":"training","paused":false,"uptime_s":120,
 "limits":{"max_temp_c":83.0,"idle_minutes":5.0,"min_battery_pct":50.0},
 "train":{"status":"running","round":2,"total_rounds":50,"step":40,"steps_per_round":100,"loss":1.71,
          "accuracy":0.38,"samples":19200,"samples_per_s":2400.0,"device":"cuda:NVIDIA GeForce RTX 3060",
          "dataset":"cifar10","history":[{"round":1,"loss":2.01,"accuracy":0.27,"samples":6400},
                                         {"round":2,"loss":1.71,"accuracy":0.38,"samples":12800}],"error":null}}
''';

const cpuSnapshot = '''
{"type":"telemetry","v":1,"device":{"id":"x","name":"thinkpad","kind":"laptop"},
 "gpu":{"available":false,"vendor":null,"name":null,"reason":"NVML Shared Library Not Found"},
 "cpu":{"name":"Intel Core i7","util":12.5,"cores":8,"freq_mhz":2800,"temp_c":54},
 "ram":{"used_gb":6.0,"total_gb":16.0},"battery":{"present":true,"percent":80,"plugged":true},
 "state":"busy","paused":true,"train":null}
''';

void main() {
  group('parseAgentUri', () {
    test('accepts the URL printed by airtrain serve', () {
      final u = parseAgentUri('ws://192.168.1.20:8765/?token=abc123');
      expect(u.toString(), 'ws://192.168.1.20:8765/?token=abc123');
    });
    test('host only plus token field', () {
      expect(parseAgentUri('192.168.1.20', 'tok').toString(), 'ws://192.168.1.20:8765/?token=tok');
    });
    test('token field overrides URL token', () {
      expect(parseAgentUri('ws://10.0.0.5:9000/?token=old', 'new').queryParameters['token'], 'new');
    });
    test('missing token is rejected', () {
      expect(() => parseAgentUri('10.0.0.5:8765'), throwsFormatException);
    });
  });

  group('deviceFromTelemetry', () {
    test('maps an NVIDIA snapshot', () {
      final d = deviceFromTelemetry(jsonDecode(gpuSnapshot) as Map<String, dynamic>, '10.0.0.5:8765', null);
      expect(d.id, 'agent:a1b2c3');
      expect(d.linkId, '10.0.0.5:8765');
      expect(d.name, 'Gaming PC');
      expect(d.gpu, 'NVIDIA GeForce RTX 3060 · CUDA');
      expect(d.state, DeviceState.training);
      expect(d.util, 97);
      expect(d.vramTotal, 12);
      expect(d.tempLimit, 93);
      expect(d.powerLimit, 170);
      expect(d.fan, 55);
      expect(d.fanUnit, '%');
      expect(d.throttled, isTrue);
      expect(d.samples, 19200);
      expect(d.history, [97]);
    });

    test('CPU-only machine falls back to CPU and RAM', () {
      final d = deviceFromTelemetry(jsonDecode(cpuSnapshot) as Map<String, dynamic>, 'h:1', null);
      expect(d.gpu, 'Intel Core i7 · CPU only');
      expect(d.util, 12.5);
      expect(d.vramTotal, 16);
      expect(d.temp, 54);
      expect(d.tempLimit, 90);
      expect(d.hasFan, isFalse);
      expect(d.paused, isTrue);
      expect(d.state, DeviceState.busy);
      expect(d.stress.isFinite, isTrue);
    });

    test('history accumulates across snapshots', () {
      final m = jsonDecode(gpuSnapshot) as Map<String, dynamic>;
      final a = deviceFromTelemetry(m, 'h:1', null);
      final b = deviceFromTelemetry(m, 'h:1', a);
      expect(b.history.length, 2);
    });
  });

  test('jobFromTelemetry builds curves from the training history', () {
    final job = jobFromTelemetry([jsonDecode(gpuSnapshot) as Map<String, dynamic>], DateTime(2026))!;
    expect(job.round, 2);
    expect(job.totalRounds, 50);
    expect(job.acc, [0.27, 0.38]);
    expect(job.log.first.round, 2);
    expect(job.throughput, 2400);
    expect(jobFromTelemetry([jsonDecode(cpuSnapshot) as Map<String, dynamic>], DateTime(2026)), isNull);
  });
}
