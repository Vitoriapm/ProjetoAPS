import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/environmental_point.dart';
import '../models/incident.dart';
import '../models/position_point.dart';
import '../models/report.dart';
import '../models/route_result.dart';

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

abstract interface class EcoPulseApi {
  void configure({required String baseUrl, required String installationId});
  Future<String> sessionToken();
  Future<bool> isDemoMode();
  Future<List<Report>> getReports();
  Future<Report> postReport(Report report);
  Future<List<Incident>> getIncidents(PositionPoint? position);
  Future<List<EnvironmentalPoint>> getEnvironment(PositionPoint? position);
  Future<RouteResult> getRoute({
    required PositionPoint origin,
    required PositionPoint destination,
    required String profile,
  });
  Future<void> registerPush({
    required String token,
    required String platform,
    PositionPoint? position,
  });
  Future<void> updatePosition(PositionPoint position);
  void dispose();
}

class ApiClient implements EcoPulseApi {
  ApiClient({http.Client? client, this.timeout = const Duration(seconds: 12)})
    : _client = client ?? http.Client();

  final http.Client _client;
  final Duration timeout;
  String _baseUrl = '';
  String _installationId = '';
  String? _token;
  Future<String>? _session;

  @override
  void configure({required String baseUrl, required String installationId}) {
    _baseUrl = baseUrl.replaceFirst(RegExp(r'/+$'), '');
    _installationId = installationId;
    _token = null;
    _session = null;
  }

  Uri _uri(String endpoint, [Map<String, String>? query]) =>
      Uri.parse('$_baseUrl$endpoint').replace(queryParameters: query);

  @override
  Future<String> sessionToken() {
    if (_token != null) return Future.value(_token);
    return _session ??= _createSession().whenComplete(() => _session = null);
  }

  Future<String> _createSession() async {
    final result = await _request(
      'POST',
      '/v1/sessoes',
      body: {'installation_id': _installationId},
    );
    _token = (result as Map)['access_token'] as String;
    return _token!;
  }

  Future<dynamic> _request(
    String method,
    String endpoint, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
    bool authenticated = false,
    bool renewSession = true,
  }) async {
    final headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (authenticated) {
      headers['Authorization'] = 'Bearer ${await sessionToken()}';
    }
    http.Response response;
    try {
      final request = http.Request(method, _uri(endpoint, query));
      request.headers.addAll(headers);
      if (body != null) request.body = jsonEncode(body);
      response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(timeout);
    } on TimeoutException {
      throw const ApiException(
        'O servidor demorou para responder. Os relatos pendentes continuam salvos.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Sem conexão com o servidor. Confira a rede e o endereço configurado.',
      );
    }
    if (response.statusCode == 401 && authenticated && renewSession) {
      _token = null;
      return _request(
        method,
        endpoint,
        query: query,
        body: body,
        authenticated: true,
        renewSession: false,
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String? detail;
      try {
        final parsed = jsonDecode(response.body);
        if (parsed is Map && parsed['detail'] is String) {
          detail = parsed['detail'] as String;
        }
      } on FormatException {
        // A reverse proxy can return HTML; keep the operational error readable.
      }
      throw ApiException(
        detail ??
            switch (response.statusCode) {
              409 => 'Este relato tem um identificador em conflito. Ele foi preservado para revisão.',
              422 => 'O servidor não aceitou os dados enviados. Revise o ponto e a descrição.',
              503 => 'Serviço temporariamente indisponível. Tente novamente em instantes.',
              _ =>
                'O servidor não conseguiu concluir a solicitação (${response.statusCode}).',
            },
        statusCode: response.statusCode,
      );
    }
    if (response.body.isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const ApiException(
        'O endereço respondeu em um formato inesperado. Confira o servidor EcoPulse.',
      );
    }
  }

  @override
  Future<bool> isDemoMode() async =>
      (await _request('GET', '/health') as Map)['mode'] == 'demo';

  @override
  Future<List<Report>> getReports() async {
    final reports = <Report>[];
    const limit = 200;
    for (var offset = 0; ; offset += limit) {
      final page = await _request(
        'GET',
        '/v1/relatos',
        query: {'limit': '$limit', 'offset': '$offset'},
      ) as List;
      reports.addAll(
        page.map(
          (item) => Report.fromJson(Map<String, dynamic>.from(item as Map)),
        ),
      );
      if (page.length < limit) return reports;
    }
  }

  @override
  Future<Report> postReport(Report report) async => Report.fromJson(
    Map<String, dynamic>.from(
      await _request(
        'POST',
        '/v1/relatos',
        body: report.toJson(),
        authenticated: true,
      ) as Map,
    ),
  );

  Map<String, String>? _positionQuery(PositionPoint? point) => point == null
      ? null
      : {'latitude': '${point.latitude}', 'longitude': '${point.longitude}'};

  @override
  Future<List<Incident>> getIncidents(PositionPoint? position) async {
    // Fetch the city's map, not only the 1 km alert radius. Notifications filter locally.
    final features = await _request(
      'GET',
      '/v1/incidentes/ativos',
      query: position == null
          ? null
          : {..._positionQuery(position)!, 'radius_m': '30000'},
    ) as Map;
    return (features['features'] as List)
        .map(
          (item) =>
              Incident.fromFeature(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  @override
  Future<List<EnvironmentalPoint>> getEnvironment(
    PositionPoint? position,
  ) async {
    final collection = await _request(
      'GET',
      '/v1/camadas/ambientais',
      query: _positionQuery(position),
    ) as Map;
    return (collection['features'] as List)
        .map(
          (item) => EnvironmentalPoint.fromFeature(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  @override
  Future<RouteResult> getRoute({
    required PositionPoint origin,
    required PositionPoint destination,
    required String profile,
  }) async => RouteResult.fromJson(
    Map<String, dynamic>.from(
      await _request(
        'POST',
        '/v1/rotas',
        body: {
          'origem': {
            'latitude': origin.latitude,
            'longitude': origin.longitude,
          },
          'destino': {
            'latitude': destination.latitude,
            'longitude': destination.longitude,
          },
          'perfil': profile,
        },
        authenticated: true,
      ) as Map,
    ),
  );

  @override
  Future<void> registerPush({
    required String token,
    required String platform,
    PositionPoint? position,
  }) async {
    await _request(
      'PUT',
      '/v1/dispositivos/push',
      authenticated: true,
      body: {
        'token': token,
        'platform': platform,
        'latitude': position?.latitude,
        'longitude': position?.longitude,
        'position_at': position == null
            ? null
            : DateTime.now().toUtc().toIso8601String(),
        'radius_m': 1000,
      },
    );
  }

  @override
  Future<void> updatePosition(PositionPoint position) async {
    await _request(
      'POST',
      '/v1/dispositivos/posicao',
      authenticated: true,
      body: {
        'latitude': position.latitude,
        'longitude': position.longitude,
        'accuracy_m': position.accuracyM,
        'position_at': DateTime.now().toUtc().toIso8601String(),
        'radius_m': 1000,
      },
    );
  }

  @override
  void dispose() => _client.close();
}
