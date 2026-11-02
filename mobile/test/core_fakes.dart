import 'dart:async';

import 'package:ecopulse/data/api_client.dart';
import 'package:ecopulse/data/local_store.dart';
import 'package:ecopulse/models/incident.dart';
import 'package:ecopulse/models/position_point.dart';
import 'package:ecopulse/models/report.dart';
import 'package:ecopulse/models/route_result.dart';

class MemoryStore implements LocalStore {
  final Map<String, Report> reports = {};
  final Map<String, String> settings = {};
  Completer<void>? nextWriteGate;
  @override
  Future<void> initialize() async {}
  @override
  Future<List<Report>> loadReports() async => reports.values.toList();
  @override
  Future<void> upsertReports(Iterable<Report> items) async {
    final gate = nextWriteGate;
    nextWriteGate = null;
    if (gate != null) await gate.future;
    for (final item in items) {
      reports[item.id] = item;
    }
  }

  @override
  Future<String?> readSetting(String key) async => settings[key];
  @override
  Future<void> writeSetting(String key, String value) async =>
      settings[key] = value;
  @override
  Future<void> close() async {}
}

class FakeApi implements EcoPulseApi {
  bool offline = false;
  bool staleGet = false;
  bool timeoutAfterAccepting = false;
  bool demo = true;
  int routeCalls = 0;
  int activePosts = 0;
  int maxActivePosts = 0;
  Completer<void>? postGate;
  final Map<String, Report> serverReports = {};
  final List<Map<String, dynamic>> postedPayloads = [];
  List<Incident> incidentItems = [];
  @override
  void configure({required String baseUrl, required String installationId}) {}
  @override
  Future<String> sessionToken() async => 'test-session';
  void _check() {
    if (offline) throw const ApiException('Sem conexão com o servidor.');
  }

  @override
  Future<bool> isDemoMode() async {
    _check();
    return demo;
  }

  @override
  Future<List<Report>> getReports() async {
    _check();
    return staleGet ? [] : serverReports.values.toList();
  }

  @override
  Future<Report> postReport(Report report) async {
    postedPayloads.add(report.toJson());
    _check();
    activePosts++;
    if (activePosts > maxActivePosts) maxActivePosts = activePosts;
    try {
      await postGate?.future;
      final accepted = serverReports.putIfAbsent(
        report.id,
        () => report.confirmed(receivedAt: DateTime.now().toUtc()),
      );
      if (timeoutAfterAccepting) {
        timeoutAfterAccepting = false;
        throw const ApiException('Resposta perdida após aceitar o relato.');
      }
      return accepted;
    } finally {
      activePosts--;
    }
  }

  @override
  Future<List<Incident>> getIncidents(PositionPoint? position) async {
    _check();
    return incidentItems;
  }

  @override
  Future<RouteResult> getRoute({
    required PositionPoint origin,
    required PositionPoint destination,
    required String profile,
  }) async {
    routeCalls++;
    throw const ApiException(
      'Provedor de rotas não configurado.',
      statusCode: 503,
    );
  }

  @override
  Future<void> registerPush({
    required String token,
    required String platform,
    PositionPoint? position,
  }) async {
    _check();
  }

  @override
  Future<void> updatePosition(PositionPoint position) async {
    _check();
  }

  @override
  void dispose() {}
}

Report fixtureReport({
  String id = '22222222-2222-4222-8222-222222222222',
  bool pending = false,
}) => Report(
  id: id,
  latitude: -21.1775,
  longitude: -47.8103,
  severity: Severity.high,
  type: ReportType.flood,
  occurredAt: DateTime.utc(2026, 10, 3),
  description: 'Relato de teste',
  isDemo: true,
  isPending: pending,
  positionSource: 'manual',
);

Incident fixtureIncident({int version = 1}) => Incident(
  id: '33333333-3333-4333-8333-333333333333',
  type: ReportType.flood,
  severity: Severity.high,
  centerLatitude: -21.1775,
  centerLongitude: -47.8103,
  radiusM: 150,
  updatedAt: DateTime.now().toUtc(),
  expiresAt: DateTime.now().toUtc().add(const Duration(hours: 2)),
  isDemo: true,
  reportCount: 2,
  version: version,
  state: 'colaborativo',
  polygons: const [
    [-47.811, -21.178],
    [-47.809, -21.178],
    [-47.809, -21.176],
    [-47.811, -21.178],
  ],
);
