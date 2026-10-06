import 'dart:convert';
import 'dart:io';

import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() async {
  final output = Directory('../docs/evidence');
  await output.create(recursive: true);
  await integrationDriver(
    onScreenshot: (name, bytes, [args]) async {
      if (name != 'android-proximity' || bytes.length < 8 || bytes[0] != 137) {
        return false;
      }
      await File('${output.path}/$name.png').writeAsBytes(bytes, flush: true);
      return true;
    },
    responseDataCallback: (data) async {
      final sanitized = Map<String, dynamic>.from(data ?? {})
        ..remove('screenshots');
      sanitized['checked_at_utc'] = DateTime.now().toUtc().toIso8601String();
      await File('${output.path}/android-proximity.json').writeAsString(
        '${const JsonEncoder.withIndent('  ').convert(sanitized)}\n',
        flush: true,
      );
    },
  );
}
