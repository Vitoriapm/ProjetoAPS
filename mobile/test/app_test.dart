import 'package:ecopulse/app.dart';
import 'package:ecopulse/models/report.dart';
import 'package:ecopulse/screens/home_screen.dart';
import 'package:ecopulse/screens/report_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'ui_test.dart' show UiController;

class OfflineFlowController extends UiController {
  int locationRequests = 0;

  @override
  Future<void> requestLocation() async {
    // This UI scenario exercises the explicit example fallback, not a GPS plugin.
    locationRequests++;
  }
}

void main() {
  testWidgets('Full offline example flow scrolls and returns to pending report', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final errors = <String>[];
    final originalErrorHandler = FlutterError.onError;
    FlutterError.onError = (details) {
      errors.add(details.toString());
      originalErrorHandler?.call(details);
    };
    addTearDown(() => FlutterError.onError = originalErrorHandler);

    final controller = OfflineFlowController();
    await tester.pumpWidget(
      EcoPulseApp(controller: controller, initializeController: false),
    );
    await tester.pumpAndSettle();

    expect(controller.serverReachable, isFalse);
    expect(controller.savedReports, isEmpty);
    await tester.tap(find.text('Relatar'));
    await tester.pumpAndSettle();
    expect(find.byType(ReportScreen), findsOneWidget);
    expect(controller.locationRequests, 1);
    expect(find.text('Nenhum local selecionado'), findsOneWidget);

    await tester.tap(find.text('Via obstruída'));
    await tester.tap(find.text('Média'));
    await tester.ensureVisible(find.text('Usar ponto de exemplo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Usar ponto de exemplo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Exemplo • Centro'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Simulação acadêmica. O relato'), findsOneWidget);
    final saveButton = find.text('Salvar relato');
    expect(saveButton, findsOneWidget);
    await tester.ensureVisible(saveButton);
    await tester.pumpAndSettle();
    expect(saveButton.hitTestable(), findsOneWidget);
    await tester.tap(saveButton);
    await tester.pumpAndSettle();

    expect(find.byType(ReportScreen), findsNothing);
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(controller.savedReports, hasLength(1));
    final report = controller.savedReports.single;
    expect(report.type, ReportType.obstruction);
    expect(report.severity, Severity.medium);
    expect(report.latitude, -21.1775);
    expect(report.longitude, -47.8103);
    expect(report.positionSource, 'demo');
    expect(report.isDemo, isTrue);
    expect(report.isPending, isTrue);
    expect(find.textContaining('relato salvo no aparelho'), findsOneWidget);

    await tester.tap(find.text('Lista'));
    await tester.pumpAndSettle();
    expect(find.text('Via obstruída'), findsOneWidget);
    expect(find.textContaining('Salvo • aguardando envio'), findsOneWidget);
    expect(find.textContaining('Simulação acadêmica'), findsOneWidget);
    expect(tester.takeException(), isNull, reason: errors.join('\n'));

    await tester.pumpWidget(const SizedBox.shrink());
    controller.dispose();
  });
}
