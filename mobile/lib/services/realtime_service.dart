import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/position_point.dart';

/// Events are invalidations; the controller always reconciles from REST.
class RealtimeService {
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _retry;
  Timer? _heartbeat;
  int _attempt = 0;
  int _generation = 0;
  bool _enabled = false;
  String _baseUrl = '';
  Future<String> Function()? _tokenProvider;
  PositionPoint? _position;
  void Function()? _onReconnected;
  void Function(Map<String, dynamic>)? _onEvent;

  void connect({
    required String baseUrl,
    required Future<String> Function() tokenProvider,
    required void Function() onReconnected,
    required void Function(Map<String, dynamic>) onEvent,
    PositionPoint? position,
  }) {
    if (_enabled && baseUrl == _baseUrl) {
      _position = position;
      _subscribe();
      return;
    }
    disconnect();
    _enabled = true;
    _baseUrl = baseUrl;
    _tokenProvider = tokenProvider;
    _onReconnected = onReconnected;
    _onEvent = onEvent;
    _position = position;
    unawaited(_dial(_generation));
  }

  void updatePosition(PositionPoint? position) {
    _position = position;
    _subscribe();
  }

  Future<void> _dial(int generation) async {
    if (!_enabled || generation != _generation) return;
    WebSocketChannel? channel;
    try {
      final token = await _tokenProvider!();
      if (!_enabled || generation != _generation) return;
      final base = Uri.parse(_baseUrl);
      final uri = base.replace(
        scheme: base.scheme == 'https' ? 'wss' : 'ws',
        path: '${base.path}/v1/ws',
        queryParameters: {'token': token},
      );
      channel = WebSocketChannel.connect(uri);
      await channel.ready.timeout(const Duration(seconds: 12));
      if (!_enabled || generation != _generation) {
        unawaited(channel.sink.close());
        return;
      }
      _channel = channel;
      _attempt = 0;
      _subscription = channel.stream.listen(
        (raw) {
          try {
            final event = Map<String, dynamic>.from(
              jsonDecode(raw as String) as Map,
            );
            if (event['type'] != 'pong' && event['type'] != 'subscribed') {
              _onEvent?.call(event);
            }
          } on FormatException {
            // An invalid event cannot clear the cached data.
          } on TypeError {
            // Ignore malformed events and let the next REST reconciliation recover.
          }
        },
        onError: (Object error) => _lost(generation),
        onDone: () => _lost(generation),
      );
      _subscribe();
      _heartbeat = Timer.periodic(const Duration(seconds: 25), (_) {
        _channel?.sink.add(jsonEncode({'type': 'ping'}));
      });
      _onReconnected?.call();
    } catch (_) {
      unawaited(channel?.sink.close());
      _lost(generation);
    }
  }

  void _subscribe() {
    final position = _position;
    if (_channel == null || position == null) return;
    _channel!.sink.add(
      jsonEncode({
        'type': 'subscribe',
        'latitude': position.latitude,
        'longitude': position.longitude,
        'radius_m': 1000,
      }),
    );
  }

  void _lost(int generation) {
    if (!_enabled || generation != _generation || _retry != null) return;
    _heartbeat?.cancel();
    _heartbeat = null;
    unawaited(_subscription?.cancel());
    _subscription = null;
    unawaited(_channel?.sink.close());
    _channel = null;
    final seconds = math.min(30, math.pow(2, _attempt++).toInt());
    _retry = Timer(Duration(seconds: seconds), () {
      _retry = null;
      unawaited(_dial(generation));
    });
  }

  void disconnect() {
    _enabled = false;
    _generation++;
    _retry?.cancel();
    _retry = null;
    _heartbeat?.cancel();
    _heartbeat = null;
    unawaited(_subscription?.cancel());
    _subscription = null;
    unawaited(_channel?.sink.close());
    _channel = null;
  }

  void dispose() => disconnect();
}
