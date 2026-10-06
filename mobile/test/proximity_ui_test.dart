import 'package:ecopulse/app.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'core_fakes.dart';

void main() {
  testWidgets(
    'Proximity stays visible through refresh and closes independently of errors',
    (tester) async {
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = FakeApi()..incidentItems = [fixtureIncident()];
      final controller = ReportController(
        store: MemoryStore(),
        api: api,
        enableDeviceServices: false,
      );
      await controller.initialize();
      await tester.pumpWidget(
        EcoPulseApp(controller: controller, initializeController: false),
      );
      await tester.tap(find.text('Lista'));
      await tester.pumpAndSettle();

      controller.setManualPosition(latitude: -21.1775, longitude: -47.8103);
      await tester.pumpAndSettle();
      final warning = find.textContaining('a até 1 km do ponto selecionado');
      expect(warning, findsOneWidget);
      await controller.synchronize();
      await controller.synchronize();
      await tester.pumpAndSettle();
      expect(warning, findsOneWidget);

      api.offline = true;
      await controller.synchronize();
      await tester.pumpAndSettle();
      expect(warning, findsOneWidget);
      expect(find.text('Sem conexão com o servidor.'), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.tap(find.byTooltip('Fechar aviso de proximidade'));
      await tester.pumpAndSettle();
      expect(warning, findsNothing);
      expect(find.text('Sem conexão com o servidor.'), findsOneWidget);
      controller.setManualPosition(latitude: -21.1775, longitude: -47.8103);
      await tester.pumpAndSettle();
      expect(warning, findsNothing);
      expect(tester.takeException(), isNull);

      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
    },
  );
}
