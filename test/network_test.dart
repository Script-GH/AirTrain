import 'dart:convert';

import 'package:airtrain/agent_link.dart';
import 'package:airtrain/main.dart';
// ignore: deprecated_member_use
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> snapshot({Object? location, Object? cluster, String state = 'training'}) => jsonDecode(
  jsonEncode({
    'type': 'telemetry',
    'device': {'id': 'p1', 'name': 'Lab PC', 'kind': 'desktop'},
    'gpu': {'available': false},
    'cpu': {'name': 'Ryzen 7', 'util': 80},
    'ram': {'used_gb': 4, 'total_gb': 16},
    'state': state,
    'location': location,
    'job': {'id': 'cifar10-cnn', 'name': 'CIFAR-10 CNN', 'batch_size': 64},
    'cluster': cluster,
  }),
) as Map<String, dynamic>;

const bengaluru = {'city': 'Bengaluru', 'country': 'IN', 'lat': 12.97, 'lon': 77.59, 'source': 'config'};
const hyderabadCluster = {
  'id': 'hyd-gamers-cifar10-cnn',
  'name': 'Hyderabad Gamers',
  'region': 'ap-south-2',
  'latency_ms': 37.1,
  'lat': 17.39,
  'lon': 78.49,
};

const demoDevice = Device(
  id: 'pc',
  name: 'Demo Linux PC',
  gpu: 'NVIDIA GPU · CUDA',
  icon: Icons.desktop_windows_rounded,
  vramTotal: 8,
  state: DeviceState.training,
  tempLimit: 83,
  powerLimit: 170,
  ramTotal: 16,
);

final emptyJob = Job(round: 0, totalRounds: 1, acc: const [], loss: const [], log: const [], startedAt: DateTime(2026));

class _FixedSwarm extends SwarmNotifier {
  _FixedSwarm(this.fixed);
  final SwarmState fixed;
  @override
  SwarmState build() => fixed;
}

Future<void> pumpNetwork(WidgetTester tester, SwarmState state) async {
  tester.view.physicalSize = const Size(412 * 2, 2400 * 2);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [swarmProvider.overrideWith(() => _FixedSwarm(state))],
      child: const MaterialApp(home: NetworkScreen()),
    ),
  );
  await tester.pump();
}

void main() {
  group('location from telemetry', () {
    test('maps city, country and coordinates', () {
      final d = deviceFromTelemetry(snapshot(location: bengaluru), 'h:1', null);
      expect(d.city, 'Bengaluru, IN');
      expect(d.lat, 12.97);
      expect(d.lon, 77.59);
    });

    test('no location means listed but not placed', () {
      final d = deviceFromTelemetry(snapshot(), 'h:1', null);
      expect(d.city, isNull);
      expect(d.lat, isNull);
      expect(d.lon, isNull);
    });

    test('a city without coordinates keeps its name only', () {
      final d = deviceFromTelemetry(
        snapshot(location: {'city': 'Smalltown', 'country': 'IN', 'lat': null, 'lon': null}),
        'h:1',
        null,
      );
      expect(d.city, 'Smalltown, IN');
      expect(d.lat, isNull);
    });

    test('out-of-range or half coordinates are dropped', () {
      expect(
        locationFromTelemetry({
          'location': {'lat': 120, 'lon': 10},
        }).lat,
        isNull,
      );
      expect(
        locationFromTelemetry({
          'location': {'lat': 12.0},
        }).lat,
        isNull,
      );
    });

    test('no Bengaluru default for unknown devices', () {
      expect(demoDevice.city, isNull);
      expect(demoDevice.lat, isNull);
    });
  });

  group('cluster and job from telemetry', () {
    test('maps the connected cluster at its region', () {
      final d = deviceFromTelemetry(snapshot(location: bengaluru, cluster: hyderabadCluster), 'h:1', null);
      expect(d.jobName, 'CIFAR-10 CNN');
      expect(d.cluster!.name, 'Hyderabad Gamers');
      expect(d.cluster!.region, 'ap-south-2');
      expect(d.cluster!.lat, 17.39);
      expect(d.cluster!.lon, 78.49);
      expect(d.cluster!.latencyMs, 37.1);
    });

    test('not connected means no cluster', () {
      expect(deviceFromTelemetry(snapshot(), 'h:1', null).cluster, isNull);
    });
  });

  group('network devices', () {
    test('excludes demo devices and counts agents only', () {
      final agent = deviceFromTelemetry(snapshot(location: bengaluru), 'h:1', null);
      final s = SwarmState(
        [demoDevice, agent],
        emptyJob,
        const [AgentInfo(id: 'h:1', url: 'h:1', status: LinkStatus.connected)],
      );
      expect(networkDevices(s).map((d) => d.name), ['Lab PC']);
      expect(s.activeCount, 1);
      expect(s.connectedCount, 1);
      expect(s.totalCount, 1);
    });

    test('demo mode has no network devices', () {
      final s = SwarmState(const [demoDevice], emptyJob);
      expect(networkDevices(s), isEmpty);
      expect(s.totalCount, 0);
    });
  });

  group('NetworkScreen', () {
    testWidgets('lists agent devices with job and cluster, never demo devices', (tester) async {
      final agent = deviceFromTelemetry(snapshot(location: bengaluru, cluster: hyderabadCluster), 'h:1', null);
      await pumpNetwork(
        tester,
        SwarmState(
          [demoDevice, agent],
          emptyJob,
          const [AgentInfo(id: 'h:1', url: 'h:1', status: LinkStatus.connected)],
        ),
      );
      expect(find.text('Lab PC'), findsOneWidget);
      expect(find.textContaining('Demo Linux PC'), findsNothing);
      expect(find.text('CIFAR-10 CNN · Hyderabad Gamers'), findsOneWidget);
      expect(find.text('Hyderabad Gamers · ap-south-2'), findsOneWidget);
      expect(find.text('No devices yet'), findsNothing);
    });

    testWidgets('shows the CLI steps and a pair button when nothing is paired', (tester) async {
      await pumpNetwork(tester, SwarmState(const [demoDevice], emptyJob));
      expect(find.text('No devices yet'), findsOneWidget);
      expect(find.text('airtrain start training'), findsOneWidget);
      expect(find.text('Pair device'), findsOneWidget);
      expect(find.textContaining('Demo Linux PC'), findsNothing);
      expect(find.text('NODES'), findsNothing);
    });
  });
}
