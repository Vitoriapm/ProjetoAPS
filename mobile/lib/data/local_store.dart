import '../models/report.dart';

/// Persistent queue plus last known public data. Writes precede network calls.
abstract interface class LocalStore {
  Future<void> initialize();
  Future<List<Report>> loadReports();
  Future<void> upsertReports(Iterable<Report> reports);
  Future<String?> readSetting(String key);
  Future<void> writeSetting(String key, String value);
  Future<void> close();
}
