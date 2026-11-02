import 'package:ecopulse/app.dart';
import 'package:ecopulse/data/api_client.dart';
import 'package:ecopulse/data/device_store.dart';
import 'package:ecopulse/models/report.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('SQLite nativo mantém relato offline e sincroniza com API real',
      (tester) async {
    final store = SqliteLocalStore();
    await store.initialize();
    await store.writeSetting('api_base_url', 'http://127.0.0.1:9');
    final controller = ReportController(
      store: store,
      api: ApiClient(timeout: const Duration(seconds: 2)),
      enableDeviceServices: false,
    );
    await controller.initialize();
    await controller.submitReport(
      latitude: -21.1775,
      longitude: -47.8103,
      severity: Severity.medium,
      type: ReportType.flood,
      description: 'Teste Android: fila SQLite e API real (simulação).',
      positionSource: 'demo',
      isDemo: true,
    );
    await controller.synchronize();
    final saved = controller.reports.first;
    expect(saved.isPending, isTrue);
    final id = saved.id;
    controller.dispose();
    await store.close();

    final reopened = SqliteLocalStore();
    await reopened.initialize();
    expect(
      (await reopened.loadReports()).singleWhere((report) => report.id == id)
          .isPending,
      isTrue,
    );
    final restored = ReportController(
      store: reopened,
      api: ApiClient(timeout: const Duration(seconds: 5)),
      enableDeviceServices: false,
    );
    await restored.initialize();
    await restored.configureServer('http://10.0.2.2:8000');
    expect(restored.serverReachable, isTrue);
    expect(restored.reports.singleWhere((report) => report.id == id).isPending,
        isFalse);
    expect(restored.incidents, isNotEmpty);
    await tester.pumpWidget(EcoPulseApp(
      controller: restored,
      initializeController: false,
    ));
    await tester.pumpAndSettle(const Duration(milliseconds: 100));
    expect(find.text('EcoPulse'), findsOneWidget);
    expect(find.text('Ribeirão Preto'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    restored.dispose();
    await reopened.close();
  });
}
