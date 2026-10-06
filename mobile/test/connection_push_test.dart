import 'package:ecopulse/services/push_service.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:ecopulse/widgets/connection_sheet.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'core_fakes.dart';
import 'push_service_test.dart' show FakePushGateway;

class ReceiptController extends ReportController {
  ReceiptController(PushService push)
    : super(
        store: MemoryStore(),
        api: FakeApi(),
        push: push,
        enableDeviceServices: false,
      );

  void received() => notifyListeners();
}

void main() {
  testWidgets('An already open connection sheet shows a new foreground push', (
    tester,
  ) async {
    final gateway = FakePushGateway();
    final service = gateway.service();
    final controller = ReceiptController(service);
    await service.initialize(
      registrar: (_, _) async {},
      onNotification: controller.received,
      onStatus: (_) {},
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ConnectionSheet(controller: controller)),
      ),
    );
    expect(find.textContaining('Push recebido com o app aberto'), findsNothing);
    gateway.foreground.add(
      const RemoteMessage(data: {'event_id': 'foreground-receipt'}),
    );
    await tester.pump();
    expect(
      find.textContaining('Push recebido com o app aberto'),
      findsOneWidget,
    );
    expect(find.textContaining('(1 nesta sessão)'), findsOneWidget);
    gateway.foreground.add(
      const RemoteMessage(data: {'event_id': 'foreground-receipt'}),
    );
    await tester.pump();
    expect(find.textContaining('(1 nesta sessão)'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
    await gateway.close();
  });
}
