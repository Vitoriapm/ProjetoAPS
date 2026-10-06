import 'dart:async';

import 'package:ecopulse/models/report.dart';
import 'package:ecopulse/services/location_service.dart';
import 'package:ecopulse/models/position_point.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import 'core_fakes.dart';

class DeniedGps implements LocationGateway {
  @override
  Future<PositionPoint> requestCurrentPosition() async =>
      throw const LocationUnavailable(
        'Localização não autorizada. Escolha um ponto no mapa.',
      );
  @override
  Stream<PositionPoint> watchPosition() => const Stream.empty();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'Offline report survives restart and a lost POST response reuses its UUID',
    () async {
      final store = MemoryStore();
      final firstApi = FakeApi()..offline = true;
      final first = ReportController(
        store: store,
        api: firstApi,
        enableDeviceServices: false,
      );
      await first.initialize();
      await first.submitReport(
        latitude: -21.1775,
        longitude: -47.8103,
        severity: Severity.high,
        type: ReportType.obstruction,
        description: 'Árvore caída',
      );
      await first.synchronize();
      expect(first.pendingCount, 1);
      final saved = first.reports.single;
      expect(store.reports[saved.id]?.isPending, isTrue);
      first.dispose();

      final restartedApi = FakeApi()..timeoutAfterAccepting = true;
      final restarted = ReportController(
        store: store,
        api: restartedApi,
        enableDeviceServices: false,
      );
      await restarted.initialize();
      // GET can see the accepted report, but only idempotent POST ACK clears the queue.
      expect(restarted.pendingCount, 1);
      await restarted.synchronize();
      expect(restarted.pendingCount, 0);
      expect(restartedApi.serverReports.length, 1);
      expect(restartedApi.postedPayloads.length, 2);
      expect(
        restartedApi.postedPayloads.first,
        restartedApi.postedPayloads.last,
      );
      expect(restarted.reports.single.id, saved.id);
      restarted.dispose();
    },
  );

  test('Concurrent reconnect/sync calls run one sender', () async {
    final store = MemoryStore();
    await store.upsertReports([fixtureReport(pending: true)]);
    final api = FakeApi()..offline = true;
    final controller = ReportController(
      store: store,
      api: api,
      enableDeviceServices: false,
    );
    await controller.initialize();
    api.offline = false;
    api.postedPayloads.clear();
    api.postGate = Completer<void>();
    final requests = [
      controller.synchronize(),
      controller.synchronize(),
      controller.synchronize(),
    ];
    await Future<void>.delayed(Duration.zero);
    expect(api.activePosts, 1);
    api.postGate!.complete();
    await Future.wait(requests);
    expect(api.maxActivePosts, 1);
    expect(api.postedPayloads.length, 1);
    expect(controller.pendingCount, 0);
    controller.dispose();
  });

  test('Failed GET retains reports and layers; a lagging empty GET keeps POST acknowledgement', () async {
    final store = MemoryStore();
    final api = FakeApi()
      ..serverReports['cached'] = fixtureReport(id: 'cached');
    api.incidentItems = [fixtureIncident()];
    final controller = ReportController(
      store: store,
      api: api,
      enableDeviceServices: false,
    );
    await controller.initialize();
    api.offline = true;
    await controller.synchronize();
    expect(controller.serverReachable, isFalse);
    expect(controller.reports.single.id, 'cached');
    expect(controller.incidents.length, 1);
    api.offline = false;
    api.staleGet = true;
    await controller.submitReport(
      latitude: -21.18,
      longitude: -47.82,
      severity: Severity.medium,
      type: ReportType.flood,
    );
    await controller.synchronize();
    expect(controller.reports.length, 2);
    expect(controller.pendingCount, 0);
    expect(store.reports.length, 2);
    controller.dispose();

    api.offline = true;
    final restored = ReportController(
      store: store,
      api: api,
      enableDeviceServices: false,
    );
    await restored.initialize();
    expect(restored.reports.length, 2);
    expect(restored.incidents.length, 1);
    restored.dispose();
  });

  test(
    'Merge preserves pending and cached reports when server is empty/lagging',
    () {
      final pending = fixtureReport(pending: true);
      final cached = fixtureReport(id: 'cached');
      final result = ReportController.mergeReports(
        [pending, cached],
        [pending.confirmed()],
      );
      expect(result.length, 2);
      expect(
        result.firstWhere((report) => report.id == pending.id).isPending,
        isTrue,
      );
      expect(ReportController.mergeReports(result, []).length, 2);
    },
  );

  test(
    'A new offline report is not lost while a cached GET commit is awaiting IO',
    () async {
      final store = MemoryStore();
      final api = FakeApi();
      final controller = ReportController(
        store: store,
        api: api,
        enableDeviceServices: false,
      );
      await controller.initialize();
      final gate = Completer<void>();
      store.nextWriteGate = gate;
      final refreshing = controller.synchronize();
      await Future<void>.delayed(Duration.zero);
      api.offline = true;
      final submitting = controller.submitReport(
        latitude: -21.17,
        longitude: -47.81,
        severity: Severity.low,
        type: ReportType.obstruction,
      );
      await Future<void>.delayed(Duration.zero);
      expect(controller.pendingCount, 1);
      gate.complete();
      await Future.wait([refreshing, submitting]);
      expect(controller.pendingCount, 1);
      expect(store.reports.length, 1);
      controller.dispose();
    },
  );

  test('Denied GPS supports explicit manual origin and proximity alerts deduplicate versions', () async {
    final store = MemoryStore();
    final api = FakeApi()..incidentItems = [fixtureIncident()];
    final controller = ReportController(
      store: store,
      api: api,
      location: DeniedGps(),
      enableDeviceServices: false,
    );
    await controller.initialize();
    await controller.requestLocation();
    expect(controller.position, isNull);
    expect(controller.message, contains('Localização não autorizada'));
    controller.setManualPosition(latitude: -21.1775, longitude: -47.8103);
    await Future<void>.delayed(Duration.zero);
    expect(controller.proximityMessage, contains('Demonstração:'));
    expect(controller.proximityMessage, contains('ponto selecionado'));
    controller.clearProximityMessage();
    await controller.synchronize();
    expect(controller.message, isNull);
    api.incidentItems = [fixtureIncident(version: 2)];
    await controller.synchronize();
    expect(controller.proximityMessage, contains('Alagamento'));
    controller.clearProximityMessage();
    controller.setManualPosition(latitude: -22, longitude: -48);
    await controller.synchronize();
    expect(controller.message, isNull);
    controller.dispose();
  });

  test('Routes need an explicit origin and provider failure never fabricates geometry', () async {
    final api = FakeApi();
    final controller = ReportController(
      store: MemoryStore(),
      api: api,
      enableDeviceServices: false,
    );
    await controller.initialize();
    await controller.calculateRoute(
      destinationLatitude: -21.2,
      destinationLongitude: -47.9,
    );
    expect(api.routeCalls, 0);
    expect(controller.message, contains('origem'));
    controller.setManualPosition(latitude: -21.17, longitude: -47.81);
    await controller.calculateRoute(
      destinationLatitude: -21.2,
      destinationLongitude: -47.9,
    );
    expect(api.routeCalls, 1);
    expect(controller.route, isNull);
    expect(controller.message, contains('não configurado'));
    expect(controller.pushStatus, contains('pendente'));
    controller.dispose();
  });

  test('Invalid report never creates a falsely saved queue item', () async {
    final store = MemoryStore();
    final controller = ReportController(
      store: store,
      api: FakeApi(),
      enableDeviceServices: false,
    );
    await controller.initialize();
    await controller.submitReport(
      latitude: double.nan,
      longitude: -47.81,
      severity: Severity.high,
      type: ReportType.flood,
    );
    expect(controller.reports, isEmpty);
    expect(store.reports, isEmpty);
    expect(controller.message, contains('ponto válido'));
    controller.dispose();
  });
}
