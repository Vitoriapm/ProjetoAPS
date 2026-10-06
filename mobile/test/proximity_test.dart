import 'package:ecopulse/models/incident.dart';
import 'package:ecopulse/models/position_point.dart';
import 'package:ecopulse/services/push_service.dart';
import 'package:ecopulse/services/realtime_service.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'core_fakes.dart';

const _centerLatitude = -21.1775;
const _centerLongitude = -47.8103;
const _manualWarning =
    'Demonstração: Alagamento a até 1 km do ponto selecionado. Evite a área indicada.';

Future<void> _settlePosition() async {
  // Let the controller finish local persistence without using any device service.
  await Future<void>.delayed(Duration.zero);
}

Incident _incident({int version = 1, DateTime? expiresAt}) {
  final source = fixtureIncident(version: version);
  return Incident(
    id: source.id,
    type: source.type,
    severity: source.severity,
    centerLatitude: source.centerLatitude,
    centerLongitude: source.centerLongitude,
    radiusM: source.radiusM,
    updatedAt: source.updatedAt,
    expiresAt: expiresAt ?? source.expiresAt,
    isDemo: source.isDemo,
    reportCount: source.reportCount,
    version: source.version,
    state: source.state,
    polygons: source.polygons,
  );
}

class _CountingApi extends FakeApi {
  int incidentReads = 0;

  @override
  Future<List<Incident>> getIncidents(PositionPoint? position) async {
    incidentReads++;
    return super.getIncidents(position);
  }
}

class _FakeRealtime extends RealtimeService {
  void Function(Map<String, dynamic>)? onEvent;

  @override
  void connect({
    required String baseUrl,
    required Future<String> Function() tokenProvider,
    required void Function() onReconnected,
    required void Function(Map<String, dynamic>) onEvent,
    PositionPoint? position,
  }) {
    this.onEvent = onEvent;
  }

  @override
  void updatePosition(PositionPoint? position) {}

  @override
  void disconnect() => onEvent = null;

  @override
  void dispose() => disconnect();
}

Future<ReportController> _controller({
  required MemoryStore store,
  required FakeApi api,
  RealtimeService? realtime,
  bool enableDeviceServices = false,
}) async {
  final controller = ReportController(
    store: store,
    api: api,
    realtime: realtime,
    push: PushService(enableFirebase: false),
    enableDeviceServices: enableDeviceServices,
  );
  addTearDown(controller.dispose);
  await controller.initialize();
  return controller;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'A nearby active incident shows a manual-location proximity warning',
    () async {
      final controller = await _controller(
        store: MemoryStore(),
        api: FakeApi()..incidentItems = [fixtureIncident()],
      );
      controller.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(controller.proximityMessage, _manualWarning);
    },
  );

  test(
    'A location beyond one kilometre does not trigger a proximity warning',
    () async {
      final store = MemoryStore();
      final controller = await _controller(
        store: store,
        api: FakeApi()..incidentItems = [fixtureIncident()],
      );
      controller.setManualPosition(
        latitude: _centerLatitude + .02, // About 2.2 km north of the incident.
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(controller.proximityMessage, isNull);
      expect(store.settings['alerted_versions'], isNull);
    },
  );

  test('A point outside the incident geometry but within one kilometre still warns', () async {
    final controller = await _controller(
      store: MemoryStore(),
      api: FakeApi()..incidentItems = [fixtureIncident()],
    );
    controller.setManualPosition(
      latitude: _centerLatitude + .004, // About 445 m; fixture radius is 150 m.
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);
  });

  test('REST reconciliation keeps a new proximity warning until explicitly dismissed', () async {
    final controller = await _controller(
      store: MemoryStore(),
      api: FakeApi()..incidentItems = [fixtureIncident()],
    );
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);

    await controller.synchronize();
    expect(controller.proximityMessage, _manualWarning);
    controller.clearProximityMessage();
    await controller.synchronize();
    expect(controller.proximityMessage, isNull);
  });

  test('A transient REST failure keeps the proximity warning separate from the error', () async {
    final api = FakeApi()..incidentItems = [fixtureIncident()];
    final controller = await _controller(store: MemoryStore(), api: api);
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    api.offline = true;
    await controller.synchronize();
    expect(controller.message, contains('Sem conexão'));
    expect(controller.proximityMessage, _manualWarning);
    controller.clearProximityMessage();
    expect(controller.proximityMessage, isNull);
    expect(controller.message, contains('Sem conexão'));
  });

  test('A realtime invalidation refreshes incidents without dismissing a new warning', () async {
    const connectivityChannel = MethodChannel(
      'dev.fluttercommunity.plus/connectivity_status',
    );
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(connectivityChannel, (_) async => null);
    addTearDown(() {
      messenger.setMockMethodCallHandler(connectivityChannel, null);
    });
    final api = _CountingApi()..incidentItems = [fixtureIncident()];
    final realtime = _FakeRealtime();
    final controller = await _controller(
      store: MemoryStore(),
      api: api,
      realtime: realtime,
      enableDeviceServices: true,
    );
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);
    final previousReads = api.incidentReads;
    expect(realtime.onEvent, isNotNull);
    realtime.onEvent!({'type': 'incidente.atualizado'});
    await Future<void>.delayed(const Duration(milliseconds: 350));
    expect(api.incidentReads, greaterThan(previousReads));
    expect(controller.proximityMessage, _manualWarning);
    expect(api.postedPayloads, isEmpty);
  });

  test('Dismissing an incident version prevents repeats after leaving and returning', () async {
    final controller = await _controller(
      store: MemoryStore(),
      api: FakeApi()..incidentItems = [fixtureIncident()],
    );
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);
    controller.clearProximityMessage();
    controller.setManualPosition(
      latitude: _centerLatitude + .02,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    await controller.synchronize();
    expect(controller.proximityMessage, isNull);
  });

  test(
    'Seen incident versions remain suppressed after controller restart offline',
    () async {
      final store = MemoryStore();
      final first = await _controller(
        store: store,
        api: FakeApi()..incidentItems = [fixtureIncident()],
      );
      first.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(first.proximityMessage, _manualWarning);
      expect(store.settings['alerted_versions'], isNotNull);
      first.clearProximityMessage();
      first.dispose();

      final restarted = await _controller(
        store: store,
        api: FakeApi()..offline = true,
      );
      expect(restarted.incidents, hasLength(1));
      restarted.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(restarted.proximityMessage, isNull);
      expect(restarted.message, contains('Sem conexão'));
    },
  );

  test(
    'A new version can alert once after the previous version was dismissed',
    () async {
      final api = FakeApi()..incidentItems = [fixtureIncident()];
      final controller = await _controller(store: MemoryStore(), api: api);
      controller.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(controller.proximityMessage, _manualWarning);
      controller.clearProximityMessage();
      api.incidentItems = [fixtureIncident(version: 2)];
      await controller.synchronize();
      expect(controller.proximityMessage, _manualWarning);
      controller.clearProximityMessage();
      await controller.synchronize();
      expect(controller.proximityMessage, isNull);
    },
  );

  test('An expired incident does not warn or consume its version', () async {
    final store = MemoryStore();
    final api = FakeApi()
      ..incidentItems = [
        _incident(
          expiresAt: DateTime.now().toUtc().subtract(
            const Duration(minutes: 1),
          ),
        ),
      ];
    final controller = await _controller(store: store, api: api);
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, isNull);
    expect(store.settings['alerted_versions'], isNull);
    api.incidentItems = [fixtureIncident()];
    await controller.synchronize();
    expect(controller.proximityMessage, _manualWarning);
  });

  test('Leaving the radius removes the active warning without rearming its version', () async {
    final controller = await _controller(
      store: MemoryStore(),
      api: FakeApi()..incidentItems = [fixtureIncident()],
    );
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);
    controller.setManualPosition(
      latitude: _centerLatitude + .02,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, isNull);
    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, isNull);
  });

  test(
    'An active warning is removed when the server expires that incident',
    () async {
      final api = FakeApi()..incidentItems = [fixtureIncident()];
      final controller = await _controller(store: MemoryStore(), api: api);
      controller.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(controller.proximityMessage, _manualWarning);
      api.incidentItems = [
        _incident(
          expiresAt: DateTime.now().toUtc().subtract(
            const Duration(minutes: 1),
          ),
        ),
      ];
      await controller.synchronize();
      expect(controller.proximityMessage, isNull);
    },
  );

  test(
    'An active warning is removed when reconciliation removes that incident',
    () async {
      final api = FakeApi()..incidentItems = [fixtureIncident()];
      final controller = await _controller(store: MemoryStore(), api: api);
      controller.setManualPosition(
        latitude: _centerLatitude,
        longitude: _centerLongitude,
      );
      await _settlePosition();
      expect(controller.proximityMessage, _manualWarning);
      api.incidentItems = [];
      await controller.synchronize();
      expect(controller.proximityMessage, isNull);
    },
  );

  test('An offline warning expires without synchronization or another position fix', () async {
    final api = _CountingApi()..incidentItems = [fixtureIncident()];
    final controller = await _controller(store: MemoryStore(), api: api);
    final expiresAt = DateTime.now().toUtc().add(
      const Duration(milliseconds: 500),
    );
    api.incidentItems = [_incident(version: 2, expiresAt: expiresAt)];
    await controller.synchronize();
    api.offline = true;
    final readsBeforeExpiry = api.incidentReads;

    controller.setManualPosition(
      latitude: _centerLatitude,
      longitude: _centerLongitude,
    );
    await _settlePosition();
    expect(controller.proximityMessage, _manualWarning);

    // Real wall-clock time: the controller must expire its cached warning
    // without any REST call, realtime event or further location update.
    await Future<void>.delayed(
      expiresAt.difference(DateTime.now().toUtc()) +
          const Duration(milliseconds: 150),
    );
    expect(controller.proximityMessage, isNull);
    expect(api.incidentReads, readsBeforeExpiry);
    expect(api.postedPayloads, isEmpty);
  });
}
