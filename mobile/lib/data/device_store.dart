import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as path;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

import '../models/report.dart';
import 'local_store.dart';

LocalStore createDeviceStore() =>
    kIsWeb ? BrowserPreviewStore() : SqliteLocalStore();

/// SQLite is the mobile persistence used on Android and iOS.
class SqliteLocalStore implements LocalStore {
  Database? _database;

  @override
  Future<void> initialize() async {
    if (_database != null) return;
    final directory = await getDatabasesPath();
    _database = await openDatabase(
      path.join(directory, 'ecopulse.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute(
          'CREATE TABLE reports (id TEXT PRIMARY KEY, payload TEXT NOT NULL)',
        );
        await db.execute(
          'CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
        );
      },
    );
  }

  Database get _db =>
      _database ?? (throw StateError('Banco local não iniciado.'));

  @override
  Future<List<Report>> loadReports() async => (await _db.query('reports'))
      .map(
        (row) => Report.fromJson(
          Map<String, dynamic>.from(
            jsonDecode(row['payload'] as String) as Map,
          ),
        ),
      )
      .toList();

  @override
  Future<void> upsertReports(Iterable<Report> reports) async {
    final items = reports.toList();
    if (items.isEmpty) return;
    await _db.transaction((transaction) async {
      final batch = transaction.batch();
      for (final report in items) {
        batch.insert('reports', {
          'id': report.id,
          'payload': jsonEncode(report.toLocalJson()),
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      }
      await batch.commit(noResult: true);
    });
  }

  @override
  Future<String?> readSetting(String key) async {
    final rows = await _db.query(
      'settings',
      where: 'key = ?',
      whereArgs: [key],
    );
    return rows.isEmpty ? null : rows.first['value'] as String;
  }

  @override
  Future<void> writeSetting(String key, String value) async {
    await _db.insert('settings', {
      'key': key,
      'value': value,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  @override
  Future<void> close() async {
    await _database?.close();
    _database = null;
  }
}

/// Browser preview only. Flutter's sqflite mobile database is not available
/// in a browser, so preview stores the same queue JSON in local preferences.
class BrowserPreviewStore implements LocalStore {
  static const _reportsKey = 'ecopulse.preview.reports.v1';
  SharedPreferences? _preferences;
  final Map<String, Report> _reports = {};

  @override
  Future<void> initialize() async {
    if (_preferences != null) return;
    _preferences = await SharedPreferences.getInstance();
    final raw = _preferences!.getString(_reportsKey);
    if (raw != null) {
      for (final item in jsonDecode(raw) as List) {
        final report = Report.fromJson(Map<String, dynamic>.from(item as Map));
        _reports[report.id] = report;
      }
    }
  }

  @override
  Future<List<Report>> loadReports() async => _reports.values.toList();

  @override
  Future<void> upsertReports(Iterable<Report> reports) async {
    for (final report in reports) {
      _reports[report.id] = report;
    }
    final accepted = await _preferences!.setString(
      _reportsKey,
      jsonEncode(
        _reports.values.map((report) => report.toLocalJson()).toList(),
      ),
    );
    if (!accepted) throw StateError('Não foi possível salvar a fila local.');
  }

  @override
  Future<String?> readSetting(String key) async =>
      _preferences!.getString('ecopulse.preview.$key');

  @override
  Future<void> writeSetting(String key, String value) async {
    if (!await _preferences!.setString('ecopulse.preview.$key', value)) {
      throw StateError('Não foi possível salvar as preferências locais.');
    }
  }

  @override
  Future<void> close() async {}
}
