import 'package:ecopulse/data/device_store.dart';
import 'package:ecopulse/models/report.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core_fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('Browser preview storage reloads pending payload and metadata after restart', () async {
    SharedPreferences.setMockInitialValues({});
    final first = BrowserPreviewStore();
    await first.initialize();
    final pending = fixtureReport(pending: true);
    await first.upsertReports([pending]);
    await first.writeSetting('installation_id', 'installation-test');
    await first.close();
    final reopened = BrowserPreviewStore();
    await reopened.initialize();
    final restored = (await reopened.loadReports()).single;
    expect(restored.toLocalJson(), pending.toLocalJson());
    expect(restored.isPending, isTrue);
    expect(await reopened.readSetting('installation_id'), 'installation-test');
    await reopened.upsertReports([
      restored.confirmed(receivedAt: DateTime.utc(2026, 10, 4)),
    ]);
    final again = BrowserPreviewStore();
    await again.initialize();
    expect((await again.loadReports()).single.isPending, isFalse);
    expect((await again.loadReports()).length, 1);
  });

  test(
    'API payload excludes local queue metadata and retains GPS/demo metadata',
    () {
      final report = Report(
        id: 'id-test',
        latitude: -21.1775,
        longitude: -47.8103,
        severity: Severity.medium,
        type: ReportType.obstruction,
        occurredAt: DateTime.utc(2026, 10, 3),
        positionSource: 'gps',
        accuracyM: 8,
        isDemo: false,
        isPending: true,
      );
      expect(
        report.toJson().keys,
        unorderedEquals([
          'id',
          'tipo',
          'gravidade',
          'latitude',
          'longitude',
          'descricao',
          'occurred_at',
          'position_source',
          'accuracy_m',
          'is_demo',
        ]),
      );
      expect(report.toJson()['tipo'], 'obstrucao');
      expect(report.toJson()['gravidade'], 'media');
      expect(report.toJson()['accuracy_m'], 8);
      expect(report.toJson()['position_source'], 'gps');
      expect(report.toLocalJson()['is_pending'], true);
      expect(Report.fromJson(report.toLocalJson()).toJson(), report.toJson());
    },
  );
}
