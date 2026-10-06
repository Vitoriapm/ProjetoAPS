import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';
import 'package:uuid/uuid.dart';

import '../data/api_client.dart';
import '../data/device_store.dart';
import '../data/local_store.dart';
import '../models/environmental_point.dart';
import '../models/incident.dart';
import '../models/position_point.dart';
import '../models/report.dart';
import '../models/route_result.dart';
import '../services/location_service.dart';
import '../services/push_service.dart';
import '../services/realtime_service.dart';

class ReportController extends ChangeNotifier with WidgetsBindingObserver {
  ReportController({
    LocalStore? store,
    EcoPulseApi? api,
    LocationGateway? location,
    RealtimeService? realtime,
    PushService? push,
    this.enableDeviceServices = true,
  }) : _store = store ?? createDeviceStore(),
       _api = api ?? ApiClient(),
       _location = location ?? LocationService(),
       _realtime = realtime ?? RealtimeService(),
       _push = push ?? PushService();

  static const defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  static const _uuid = Uuid();
  final LocalStore _store;
  final EcoPulseApi _api;
  final LocationGateway _location;
  final RealtimeService _realtime;
  final PushService _push;
  final bool enableDeviceServices;
  final Map<String, Report> _reports = {};
  final Set<String> _alertedVersions = {};
  final Map<String, String> _proximityAlerts = {};
  List<Incident> _incidents = [];
  List<EnvironmentalPoint> _environment = [];
  RouteResult? _route;
  PositionPoint? _position;
  String _apiBaseUrl = defaultBaseUrl;
  String _installationId = '';
  bool _isLoading = false;
  bool _isSyncing = false;
  bool _serverReachable = false;
  bool _demoMode = true;
  bool _initialized = false;
  bool _disposed = false;
  bool _foreground = true;
  bool _refreshRequested = false;
  DateTime? _lastUpdatedAt;
  DateTime? _positionSentAt;
  PositionPoint? _lastSentPosition;
  String? _message;
  String _pushStatus = 'Push pendente: configure Firebase para Android/iOS.';
  Future<void>? _initialization;
  Future<void>? _synchronization;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  StreamSubscription<PositionPoint>? _positionSubscription;
  Timer? _eventDebounce;
  Timer? _proximityExpiry;

  List<Report> get reports {
    final items = _reports.values.toList();
    items.sort((a, b) => b.occurredAt.compareTo(a.occurredAt));
    return List.unmodifiable(items);
  }

  List<Incident> get incidents => List.unmodifiable(_incidents);
  List<EnvironmentalPoint> get environment => List.unmodifiable(_environment);
  RouteResult? get route => _route;
  PositionPoint? get position => _position;
  String get apiBaseUrl => _apiBaseUrl;
  bool get isLoading => _isLoading;
  bool get isSyncing => _isSyncing;
  bool get serverReachable => _serverReachable;
  bool get demoMode => _demoMode;
  int get pendingCount =>
      _reports.values.where((report) => report.isPending).length;
  DateTime? get lastUpdatedAt => _lastUpdatedAt;
  String? get message => _message;
  String? get proximityMessage =>
      _proximityAlerts.isEmpty ? null : _proximityAlerts.values.join('\n');
  String get pushStatus => _pushStatus;
  String? get pushReceipt => _push.lastReceipt;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> initialize() => _initialization ??= _initialize();

  Future<void> _initialize() async {
    _isLoading = true;
    _notify();
    try {
      await _store.initialize();
      if (_disposed) return;
      for (final report in await _store.loadReports()) {
        _reports[report.id] = report;
      }
      _installationId =
          await _store.readSetting('installation_id') ?? _uuid.v4();
      await _store.writeSetting('installation_id', _installationId);
      _apiBaseUrl = await _store.readSetting('api_base_url') ?? defaultBaseUrl;
      _api.configure(baseUrl: _apiBaseUrl, installationId: _installationId);
      final mode = await _store.readSetting('demo_mode');
      _demoMode = mode == null || mode == 'true';
      final updated = await _store.readSetting('last_updated_at');
      _lastUpdatedAt = updated == null ? null : DateTime.tryParse(updated);
      await _restoreCachedLayers();
      final alertLog = await _store.readSetting('alerted_versions');
      if (alertLog != null) {
        _alertedVersions.addAll((jsonDecode(alertLog) as List).cast<String>());
      }
      _initialized = true;
      if (enableDeviceServices && !_disposed) {
        WidgetsBinding.instance.addObserver(this);
        _connectivitySubscription = Connectivity().onConnectivityChanged.listen(
          (results) {
            if (_foreground &&
                results.any((result) => result != ConnectivityResult.none)) {
              _scheduleSync();
            }
          },
          onError: (Object error) {
            // Reachability is determined by HTTP, not by the network-interface label.
          },
        );
        unawaited(
          _push.initialize(
            registrar: (token, platform) => _api.registerPush(
              token: token,
              platform: platform,
              position: _position,
            ),
            onNotification: _scheduleSync,
            onStatus: (status) {
              _pushStatus = status;
              _notify();
            },
          ),
        );
        _connectRealtime();
      }
      await synchronize();
    } catch (_) {
      _message = 'Não foi possível abrir os dados locais. Reinicie o app para tentar novamente.';
      // Never claim a report is saved when local initialization failed.
    } finally {
      _isLoading = false;
      _notify();
    }
  }

  Future<void> _restoreCachedLayers() async {
    try {
      final incidents = await _store.readSetting('incidents');
      final environment = await _store.readSetting('environment');
      if (incidents != null) {
        _incidents = (jsonDecode(incidents) as List)
            .map(
              (item) =>
                  Incident.fromFeature(Map<String, dynamic>.from(item as Map)),
            )
            .toList();
      }
      if (environment != null) {
        _environment = (jsonDecode(environment) as List)
            .map(
              (item) => EnvironmentalPoint.fromFeature(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList();
      }
    } catch (_) {
      _message = 'As camadas salvas precisam ser atualizadas. A fila de relatos foi mantida.';
    }
  }

  Future<void> synchronize() async {
    if (_disposed) return;
    if (!_initialized) {
      await initialize();
      return;
    }
    final running = _synchronization;
    if (running != null) return running;
    final run = _syncLoop();
    _synchronization = run;
    try {
      await run;
    } finally {
      if (identical(_synchronization, run)) _synchronization = null;
    }
  }

  Future<void> _syncLoop() async {
    _isSyncing = true;
    _notify();
    try {
      do {
        _refreshRequested = false;
        await _syncOnce();
      } while (_refreshRequested && !_disposed && _foreground);
    } catch (failure) {
      _message = _humanError(failure);
    } finally {
      _isSyncing = false;
      _notify();
    }
  }

  Future<void> _syncOnce() async {
    String? error;
    var reportSyncSucceeded = false;
    // Snapshot the queue; a concurrently added report requests the next pass.
    final pending = _reports.values
        .where((report) => report.isPending)
        .toList();
    for (final report in pending) {
      if (_disposed) return;
      try {
        final accepted = await _api.postReport(report);
        if (accepted.id != report.id) {
          throw const ApiException(
            'O servidor retornou outro identificador. O relato continua pendente.',
          );
        }
        if (_disposed) return;
        final confirmed = accepted.confirmed();
        // Commit acknowledgement before removing the visible pending marker.
        await _store.upsertReports([confirmed]);
        _reports[report.id] = confirmed;
      } catch (failure) {
        error = _humanError(failure);
        if (failure is! ApiException ||
            (failure.statusCode != 409 && failure.statusCode != 422)) {
          break;
        }
      }
    }
    if (_disposed) return;
    try {
      final remote = await _api.getReports();
      if (_disposed) return;
      final merged = mergeReports(_reports.values, remote);
      await _store.upsertReports(merged);
      // Preserve a report submitted while the local commit was awaiting IO.
      _reports.addEntries(merged.map((report) => MapEntry(report.id, report)));
      reportSyncSucceeded = true;
      _serverReachable = true;
    } catch (failure) {
      error ??= _humanError(failure);
      _serverReachable = false;
    }
    if (_disposed) return;
    // Independent requests retain each cached layer if another request fails.
    if (reportSyncSucceeded) {
      try {
        _demoMode = await _api.isDemoMode();
        await _store.writeSetting('demo_mode', '$_demoMode');
      } catch (failure) {
        error ??= _humanError(failure);
      }
      try {
        final fetched = await _api.getIncidents(_position);
        if (_disposed) return;
        await _store.writeSetting(
          'incidents',
          jsonEncode(fetched.map((item) => item.toFeature()).toList()),
        );
        _incidents = fetched;
      } catch (failure) {
        error ??= _humanError(failure);
      }
      try {
        final fetched = await _api.getEnvironment(_position);
        if (_disposed) return;
        await _store.writeSetting(
          'environment',
          jsonEncode(fetched.map((item) => item.toFeature()).toList()),
        );
        _environment = fetched;
      } catch (failure) {
        error ??= _humanError(failure);
      }
      if (_disposed) return;
      _lastUpdatedAt = DateTime.now().toUtc();
      await _store.writeSetting(
        'last_updated_at',
        _lastUpdatedAt!.toIso8601String(),
      );
      if (enableDeviceServices) {
        _connectRealtime();
        unawaited(_push.retryRegistration());
        unawaited(_sendPosition());
      }
    }
    if (_disposed) return;
    _message = error;
    await _checkProximity();
    _notify();
  }

  /// An empty/lagging GET never discards local pending reports or an ACK.
  /// The UUID is immutable, so replays after a POST timeout remain idempotent.
  static List<Report> mergeReports(
    Iterable<Report> local,
    Iterable<Report> remote,
  ) {
    final merged = {for (final report in local) report.id: report};
    for (final report in remote) {
      if (merged[report.id]?.isPending == true) continue;
      merged[report.id] = report.confirmed();
    }
    return merged.values.toList();
  }

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
    if (!_initialized) await initialize();
    if (!_initialized || _disposed) {
      _message = 'O armazenamento local não está disponível. O relato ainda não foi salvo.';
      _notify();
      return;
    }
    if (!_validCoordinates(latitude, longitude) ||
        description.trim().length > 500 ||
        !{'gps', 'manual', 'demo'}.contains(positionSource) ||
        (accuracyM != null && (!accuracyM.isFinite || accuracyM < 0))) {
      _message =
          'Escolha um ponto válido e use até 500 caracteres na descrição.';
      _notify();
      return;
    }
    final report = Report(
      id: _uuid.v4(),
      latitude: latitude,
      longitude: longitude,
      severity: severity,
      type: type,
      occurredAt: DateTime.now().toUtc(),
      description: description.trim(),
      positionSource: positionSource,
      accuracyM: accuracyM,
      isDemo: isDemo || _demoMode,
      isPending: true,
    );
    try {
      await _store.upsertReports([report]);
      _reports[report.id] = report;
      _message =
          'Relato salvo no aparelho. O envio será feito quando houver conexão.';
      _notify();
      if (_position == null) {
        _position = PositionPoint(
          latitude: latitude,
          longitude: longitude,
          accuracyM: accuracyM,
          source: positionSource,
        );
        _realtime.updatePosition(_position);
      }
      if (_synchronization != null) _refreshRequested = true;
      unawaited(synchronize());
    } catch (_) {
      _message =
          'Não foi possível salvar o relato no aparelho. Tente novamente.';
      _notify();
    }
  }

  Future<void> configureServer(String value) async {
    final normalized = value.trim().replaceFirst(RegExp(r'/+$'), '');
    final uri = Uri.tryParse(normalized);
    if (uri == null ||
        !uri.hasAuthority ||
        !{'http', 'https'}.contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      _message = 'Use um endereço válido, como http://192.168.1.10:8000.';
      _notify();
      return;
    }
    if (!_initialized) await initialize();
    if (!_initialized || _disposed) return;
    // A report being sent must finish on its original server/session first.
    final active = _synchronization;
    if (active != null) {
      await active;
      if (identical(_synchronization, active)) _synchronization = null;
    }
    try {
      await _store.writeSetting('api_base_url', normalized);
      _realtime.disconnect();
      _apiBaseUrl = normalized;
      _api.configure(baseUrl: normalized, installationId: _installationId);
      _serverReachable = false;
      _route = null;
      _lastSentPosition = null;
      _positionSentAt = null;
      await synchronize();
    } catch (_) {
      _message = 'Não foi possível salvar o endereço do servidor.';
      _notify();
    }
  }

  Future<void> requestLocation() async {
    try {
      final point = await _location.requestCurrentPosition();
      if (_disposed) return;
      _position = point;
      _message =
          'Localização encontrada. Você também pode ajustar o ponto no mapa.';
      _realtime.updatePosition(point);
      if (enableDeviceServices && _foreground) _startLocationStream();
      await _checkProximity();
      unawaited(_sendPosition());
      _notify();
      _scheduleSync();
    } catch (failure) {
      _message = failure is LocationUnavailable
          ? failure.message
          : 'Não foi possível obter o GPS. Escolha um ponto no mapa.';
      _notify();
    }
  }

  /// Explicit map reference for proximity/routing when GPS is unavailable.
  void setManualPosition({
    required double latitude,
    required double longitude,
  }) {
    if (!_validCoordinates(latitude, longitude)) return;
    unawaited(_positionSubscription?.cancel());
    _positionSubscription = null;
    _position = PositionPoint(
      latitude: latitude,
      longitude: longitude,
      source: 'manual',
    );
    _realtime.updatePosition(_position);
    _lastSentPosition = null;
    unawaited(_sendPosition());
    unawaited(_checkProximity());
    _notify();
  }

  void _startLocationStream() {
    if (_positionSubscription != null || _position?.source != 'gps') return;
    _positionSubscription = _location.watchPosition().listen(
      (point) {
        if (_disposed || !_foreground) return;
        _position = point;
        _realtime.updatePosition(point);
        unawaited(_sendPosition());
        unawaited(_checkProximity());
        _notify();
      },
      onError: (Object error) {
        _message = 'GPS temporariamente indisponível. A última posição continua no mapa.';
        _notify();
      },
    );
  }

  Future<void> _sendPosition() async {
    final point = _position;
    if (!enableDeviceServices ||
        _disposed ||
        !_foreground ||
        point == null ||
        !_serverReachable) {
      return;
    }
    // Avoid uploading every GPS sample. A move of 100 m or 60 s renews the radius.
    final previous = _lastSentPosition;
    if (previous != null &&
        _positionSentAt != null &&
        DateTime.now().difference(_positionSentAt!) <
            const Duration(seconds: 60) &&
        distanceInMeters(
              previous.latitude,
              previous.longitude,
              point.latitude,
              point.longitude,
            ) <
            100) {
      return;
    }
    try {
      await _api.updatePosition(point);
      _lastSentPosition = point;
      _positionSentAt = DateTime.now();
    } catch (_) {
      // The next reconnect/resume retries the position without discarding reports.
    }
  }

  Future<void> _checkProximity() async {
    final point = _position;
    if (point == null || _disposed) return;
    final now = DateTime.now().toUtc();
    final nearby = _incidents
        .where(
          (incident) =>
              incident.expiresAt.isAfter(now) &&
              distanceInMeters(
                    point.latitude,
                    point.longitude,
                    incident.centerLatitude,
                    incident.centerLongitude,
                  ) <=
                  1000,
        )
        .toList();
    final nearbyKeys = {
      for (final incident in nearby) '${incident.id}:${incident.version}',
    };
    final previousCount = _proximityAlerts.length;
    _proximityAlerts.removeWhere((key, _) => !nearbyKeys.contains(key));
    var displayChanged = previousCount != _proximityAlerts.length;
    var logChanged = false;
    for (final incident in nearby) {
      final key = '${incident.id}:${incident.version}';
      if (_alertedVersions.contains(key) &&
          !_proximityAlerts.containsKey(key)) {
        continue;
      }
      logChanged = _alertedVersions.add(key) || logChanged;
      final prefix = incident.isDemo ? 'Demonstração: ' : '';
      final reference = point.source == 'gps'
          ? 'a até 1 km de você'
          : 'a até 1 km do ponto selecionado';
      final text =
          '$prefix${incident.type.label} $reference. Evite a área indicada.';
      if (_proximityAlerts[key] != text) displayChanged = true;
      _proximityAlerts[key] = text;
    }
    // Refresh messages and route feedback cannot dismiss a proximity warning.
    // A warning ends when closed, outside the range, expired or removed.
    if (displayChanged) _notify();
    _proximityExpiry?.cancel();
    final visibleExpirations = nearby
        .where(
          (incident) => _proximityAlerts.containsKey(
            '${incident.id}:${incident.version}',
          ),
        )
        .map((incident) => incident.expiresAt);
    if (visibleExpirations.isNotEmpty) {
      final firstExpiry = visibleExpirations.reduce(
        (a, b) => a.isBefore(b) ? a : b,
      );
      final remaining = firstExpiry.difference(DateTime.now().toUtc());
      _proximityExpiry = Timer(
        remaining.isNegative ? Duration.zero : remaining,
        () => unawaited(_checkProximity()),
      );
    }
    if (logChanged) {
      // Keep the last 500 version keys, persisted across app restarts.
      if (_alertedVersions.length > 500) {
        final excess = _alertedVersions
            .take(_alertedVersions.length - 500)
            .toList();
        _alertedVersions.removeAll(excess);
      }
      try {
        await _store.writeSetting(
          'alerted_versions',
          jsonEncode(_alertedVersions.toList()),
        );
      } catch (_) {
        // Still deduplicate during this session if preferences cannot be written.
      }
    }
  }

  Future<void> calculateRoute({
    required double destinationLatitude,
    required double destinationLongitude,
    String profile = 'driving-car',
  }) async {
    final origin = _position;
    _route = null;
    if (origin == null) {
      _message =
          'Use o GPS ou escolha sua origem no mapa antes de calcular a rota.';
      _notify();
      return;
    }
    if (!_validCoordinates(destinationLatitude, destinationLongitude) ||
        !{'driving-car', 'foot-walking'}.contains(profile)) {
      _message = 'Escolha um destino válido no mapa.';
      _notify();
      return;
    }
    _isLoading = true;
    _notify();
    try {
      final result = await _api.getRoute(
        origin: origin,
        destination: PositionPoint(
          latitude: destinationLatitude,
          longitude: destinationLongitude,
          source: 'manual',
        ),
        profile: profile,
      );
      if (!_disposed) {
        _route = result;
        _message = 'Rota calculada considerando as áreas relatadas. Confira as condições da via.';
      }
    } catch (failure) {
      _message = _humanError(failure);
    } finally {
      _isLoading = false;
      _notify();
    }
  }

  bool _validCoordinates(double latitude, double longitude) =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude >= -85 &&
      latitude <= 85 &&
      longitude >= -180 &&
      longitude <= 180;

  String _humanError(Object error) => error is ApiException
      ? error.message
      : 'Não foi possível atualizar agora. Seus dados salvos continuam no aparelho.';

  void _connectRealtime() {
    if (!enableDeviceServices || !_foreground || _disposed) return;
    _realtime.connect(
      baseUrl: _apiBaseUrl,
      tokenProvider: _api.sessionToken,
      // The city centre is a map subscription only, never an invented GPS fix.
      position:
          _position ??
          const PositionPoint(
            latitude: -21.1775,
            longitude: -47.8103,
            source: 'demo',
          ),
      onReconnected: _scheduleSync,
      onEvent: (event) {
        if ({
          'incidente.criado',
          'incidente.atualizado',
          'incidente.expirado',
          'camada.atualizada',
        }.contains(event['type'])) {
          _eventDebounce?.cancel();
          _eventDebounce = Timer(
            const Duration(milliseconds: 250),
            _scheduleSync,
          );
        }
      },
    );
  }

  void _scheduleSync() {
    if (_disposed || !_initialized || !_foreground) return;
    if (_synchronization != null) _refreshRequested = true;
    unawaited(synchronize());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_disposed || !enableDeviceServices) return;
    if (state == AppLifecycleState.resumed) {
      _foreground = true;
      _connectRealtime();
      _startLocationStream();
      _scheduleSync();
      unawaited(_push.retryRegistration());
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _foreground = false;
      _realtime.disconnect();
      unawaited(_positionSubscription?.cancel());
      _positionSubscription = null;
    }
  }

  void clearMessage() {
    _message = null;
    _notify();
  }

  void clearProximityMessage() {
    _proximityAlerts.clear();
    _proximityExpiry?.cancel();
    _notify();
  }

  void clearRoute() {
    _route = null;
    _notify();
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    if (enableDeviceServices) WidgetsBinding.instance.removeObserver(this);
    _eventDebounce?.cancel();
    _proximityExpiry?.cancel();
    unawaited(_connectivitySubscription?.cancel());
    unawaited(_positionSubscription?.cancel());
    _realtime.dispose();
    _push.dispose();
    _api.dispose();
    unawaited(_closeStore());
    super.dispose();
  }

  Future<void> _closeStore() async {
    try {
      await _synchronization;
      await _initialization;
      await _store.close();
    } catch (_) {
      // A shutdown must not emit a late notification to a disposed screen.
    }
  }
}
