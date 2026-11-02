import 'package:ecopulse/app.dart';
import 'package:ecopulse/models/report.dart';
import 'package:ecopulse/screens/report_screen.dart';
import 'package:ecopulse/state/report_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

class UiController extends ReportController {
  UiController() : super(enableDeviceServices: false);
  final List<Report> savedReports = [];

  @override
  List<Report> get reports => savedReports;
  @override
  bool get serverReachable => false;
  @override
  int get pendingCount => savedReports.length;
  @override
  bool get demoMode => false;

  @override
  Future<void> submitReport({
    required double latitude,
    required double longitude,
    required Severity severity,
    required ReportType type,
    String description = '',
    String positionSource = 'manual',
    double? accuracyM,
    bool isDemo = false,
  }) async {
    savedReports.add(
      Report(
        id: 'ui-report',
        latitude: latitude,
        longitude: longitude,
        severity: severity,
        type: type,
        description: description,
        occurredAt: DateTime.utc(2026, 10, 3),
        isPending: true,
        isDemo: isDemo,
        positionSource: positionSource,
        accuracyM: accuracyM,
      ),
    );
    notifyListeners();
  }
}

void main() {
  testWidgets('Offline reports use only flood and road filters at mobile size', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = UiController();
    await controller.submitReport(
      latitude: -21.1775,
      longitude: -47.8103,
      severity: Severity.high,
      type: ReportType.obstruction,
      isDemo: true,
    );
    await controller.submitReport(
      latitude: -21.178,
      longitude: -47.811,
      severity: Severity.medium,
      type: ReportType.flood,
    );
    await tester.pumpWidget(
      EcoPulseApp(controller: controller, initializeController: false),
    );
    expect(find.textContaining('relatos salvos no aparelho'), findsOneWidget);
    expect(find.textContaining('Simulação acadêmica'), findsOneWidget);
    expect(find.byType(FilterChip), findsNWidgets(2));
    expect(find.widgetWithText(FilterChip, 'Alagamento'), findsOneWidget);
    expect(find.widgetWithText(FilterChip, 'Vias'), findsOneWidget);
    expect(find.text('Ar'), findsNothing);
    expect(find.text('Calor'), findsNothing);
    await tester.tap(find.text('Lista'));
    await tester.pumpAndSettle();
    expect(find.text('Via obstruída'), findsOneWidget);
    expect(find.widgetWithText(ListTile, 'Alagamento'), findsOneWidget);
    expect(find.textContaining('Salvo • aguardando envio'), findsNWidgets(2));

    await tester.tap(find.widgetWithText(FilterChip, 'Vias'));
    await tester.pumpAndSettle();
    expect(find.text('Via obstruída'), findsNothing);
    expect(find.widgetWithText(ListTile, 'Alagamento'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilterChip, 'Alagamento'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(ListTile, 'Alagamento'), findsNothing);
    expect(find.text('Ainda não há relatos por aqui.'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilterChip, 'Vias'));
    await tester.pumpAndSettle();
    expect(find.text('Via obstruída'), findsOneWidget);
    expect(find.widgetWithText(ListTile, 'Alagamento'), findsNothing);

    await tester.tap(find.widgetWithText(FilterChip, 'Alagamento'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(ListTile, 'Alagamento'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    controller.dispose();
  });

  testWidgets(
    'Form preserves severity, manual position and optional description',
    (tester) async {
      final errors = <String>[];
      final originalErrorHandler = FlutterError.onError;
      FlutterError.onError = (details) {
        errors.add(details.toString());
        originalErrorHandler?.call(details);
      };
      addTearDown(() => FlutterError.onError = originalErrorHandler);
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final controller = UiController();
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => ReportScreen(
                      controller: controller,
                      initialPoint: const LatLng(-21.1775, -47.8103),
                    ),
                  ),
                ),
                child: const Text('Abrir formulário'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Abrir formulário'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Via obstruída'));
      await tester.tap(find.text('Alta'));
      await tester.enterText(
        find.byType(TextField),
        'Galho bloqueando parte da via.',
      );
      await tester.ensureVisible(find.text('Salvar relato'));
      await tester.tap(find.text('Salvar relato'));
      await tester.pumpAndSettle();
      expect(controller.savedReports, hasLength(1));
      final report = controller.savedReports.single;
      expect(report.type, ReportType.obstruction);
      expect(report.severity, Severity.high);
      expect(report.positionSource, 'manual');
      expect(report.latitude, -21.1775);
      expect(report.description, 'Galho bloqueando parte da via.');
      expect(report.isPending, isTrue);
      expect(report.isDemo, isFalse);
      expect(tester.takeException(), isNull, reason: errors.join('\n'));
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
    },
  );
}
