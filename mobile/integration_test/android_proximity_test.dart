import 'package:ecopulse/app.dart';
import 'package:ecopulse/data/device_store.dart';
import 'package:ecopulse/models/incident.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:latlong2/latlong.dart';

import '../test/core_fakes.dart';

Incident _obstruction(int version, {bool expired = false}) {
  final feature = fixtureIncident(version: version).toFeature();
  final properties = feature['properties']! as Map<String, dynamic>;
  properties['tipo'] = 'obstrucao';
  properties['gravidade'] = 'baixa';
  properties['radius_m'] = 200;
  if (expired) {
    properties['expires_at'] = DateTime.now()
        .toUtc()
        .subtract(const Duration(minutes: 1))
        .toIso8601String();
  }
  return Incident.fromFeature(feature);
}

Future<void> _chooseMapOrigin(WidgetTester tester, LatLng point) async {
  final finder = find.byType(FlutterMap);
  final map = tester.widget<FlutterMap>(finder);
  map.mapController!.move(point, 15);
  await tester.pumpAndSettle();
  // Tap a street point beside the centre marker through the real map menu.
  final target = tester.getCenter(finder) + const Offset(-55, 65);
  expect(tester.getRect(finder).contains(target), isTrue);
  await tester.tapAt(target);
  // The map waits for the double-tap interval before opening this menu.
  // That timer may be pending while no frame is scheduled.
  for (
    var attempt = 0;
    attempt < 20 && find.text('Usar como ponto de partida').evaluate().isEmpty;
    attempt++
  ) {
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
  expect(find.text('Usar como ponto de partida'), findsOneWidget);
  await tester.tap(find.text('Usar como ponto de partida'));
  await tester.pump(const Duration(milliseconds: 500));
  await tester.pumpAndSettle();
  expect(find.text('Usar como ponto de partida'), findsNothing);
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Android: aviso no mapa resiste ao sync e SQLite evita repetição',
    (tester) async {
      final checks = <String, bool>{};
      final api = FakeApi()..incidentItems = [_obstruction(1)];
      final store = SqliteLocalStore();
      await store.initialize();
      // Run only on the dedicated test emulator; never against a user's phone.
      await store.writeSetting('alerted_versions', '[]');
      final controller = ReportController(
        store: store,
        api: api,
        enableDeviceServices: false,
      );
      await controller.initialize();
      await tester.pumpWidget(
        EcoPulseApp(controller: controller, initializeController: false),
      );
      await tester.pumpAndSettle();

      await _chooseMapOrigin(tester, const LatLng(-21.2075, -47.8103));
      expect(controller.proximityMessage, isNull);
      checks['outside_1km_no_warning'] = true;
      await _chooseMapOrigin(tester, const LatLng(-21.1775, -47.8103));
      final warning = find.textContaining('Via obstruída a até 1 km');
      expect(warning, findsOneWidget);
      checks['map_menu_entry_shows_warning'] = true;
      await controller.synchronize();
      await controller.synchronize();
      await tester.pumpAndSettle();
      expect(warning, findsOneWidget);
      checks['warning_survives_successful_refresh'] = true;
      expect(tester.takeException(), isNull);

      api.offline = true;
      await controller.synchronize();
      await tester.pumpAndSettle();
      expect(warning, findsOneWidget);
      expect(find.text('Sem conexão com o servidor.'), findsOneWidget);
      checks['warning_survives_offline_refresh'] = true;
      await tester.tap(find.byTooltip('Fechar aviso de proximidade'));
      await tester.pumpAndSettle();
      expect(warning, findsNothing);
      expect(find.text('Sem conexão com o servidor.'), findsOneWidget);
      checks['dismissal_independent_of_error'] = true;
      await _chooseMapOrigin(tester, const LatLng(-21.2075, -47.8103));
      await _chooseMapOrigin(tester, const LatLng(-21.1775, -47.8103));
      expect(warning, findsNothing);
      checks['same_version_no_repeat_after_exit_and_return'] = true;

      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
      await store.close();
      final reopenedStore = SqliteLocalStore();
      final restored = ReportController(
        store: reopenedStore,
        api: api,
        enableDeviceServices: false,
      );
      await restored.initialize();
      restored.setManualPosition(latitude: -21.1775, longitude: -47.8073);
      await restored.synchronize();
      expect(restored.proximityMessage, isNull);
      checks['sqlite_dedup_after_reopening_offline'] = true;
      api.offline = false;
      api.incidentItems = [_obstruction(2)];
      await restored.synchronize();
      expect(restored.proximityMessage, contains('Via obstruída'));
      checks['new_version_warns'] = true;
      await tester.pumpWidget(
        EcoPulseApp(controller: restored, initializeController: false),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Via obstruída a até 1 km'), findsOneWidget);
      await binding.convertFlutterSurfaceToImage();
      await tester.pumpAndSettle();
      await binding.takeScreenshot('android-proximity');
      await tester.pumpWidget(const SizedBox.shrink());
      api.incidentItems = [_obstruction(2, expired: true)];
      await restored.synchronize();
      expect(restored.proximityMessage, isNull);
      checks['expired_warning_removed'] = true;
      expect(tester.takeException(), isNull);
      restored.dispose();
      await reopenedStore.close();
      binding.reportData = {
        ...?binding.reportData,
        'scope': 'Android emulator, real map menu/UI and native SQLite; isolated fake backend',
        'physical_phone_observed': false,
        'real_server_mutated': false,
        'fcm_tested': false,
        'checks': checks,
      };
    },
  );
}
