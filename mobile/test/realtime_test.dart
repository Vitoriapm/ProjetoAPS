import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ecopulse/models/position_point.dart';
import 'package:ecopulse/services/realtime_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Socket subscribes by radius, receives invalidation and reconciles on reconnect', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final peers = <WebSocket>[];
    final subscriptions = StreamController<Map<String, dynamic>>.broadcast();
    final connected = StreamController<void>.broadcast();
    final events = StreamController<Map<String, dynamic>>.broadcast();
    final service = RealtimeService();
    final serverListener = server.listen((request) async {
      expect(request.uri.path, '/v1/ws');
      expect(request.uri.queryParameters['token'], 'test-session');
      final peer = await WebSocketTransformer.upgrade(request);
      peers.add(peer);
      peer.listen((raw) {
        final message = Map<String, dynamic>.from(
          jsonDecode(raw as String) as Map,
        );
        if (message['type'] == 'subscribe') {
          subscriptions.add(message);
          peer.add(
            jsonEncode({
              'type': 'subscribed',
              'region_ids': ['6gyd'],
            }),
          );
        }
      });
    });
    addTearDown(() async {
      service.dispose();
      for (final peer in peers) {
        await peer.close();
      }
      await serverListener.cancel();
      await server.close(force: true);
      await subscriptions.close();
      await connected.close();
      await events.close();
    });

    final firstSubscription = subscriptions.stream.first;
    final firstConnection = connected.stream.first;
    service.connect(
      baseUrl: 'http://127.0.0.1:${server.port}',
      tokenProvider: () async => 'test-session',
      position: const PositionPoint(latitude: -21.1775, longitude: -47.8103),
      onReconnected: () => connected.add(null),
      onEvent: events.add,
    );
    await firstConnection.timeout(const Duration(seconds: 5));
    expect(await firstSubscription.timeout(const Duration(seconds: 5)), {
      'type': 'subscribe',
      'latitude': -21.1775,
      'longitude': -47.8103,
      'radius_m': 1000,
    });
    final invalidation = events.stream.first;
    peers.first.add(
      jsonEncode({
        'type': 'incidente.atualizado',
        'id': 'incident-id',
        'version': 2,
      }),
    );
    expect(
      (await invalidation.timeout(const Duration(seconds: 5)))['version'],
      2,
    );

    final restored = connected.stream.first;
    final nextSubscription = subscriptions.stream.first;
    await peers.first.close();
    await restored.timeout(const Duration(seconds: 5));
    expect(
      (await nextSubscription.timeout(const Duration(seconds: 5)))['radius_m'],
      1000,
    );
    // Client ready can precede the server's async upgrade continuation.
    // Receiving subscribe proves that the new server peer has been registered.
    expect(peers.length, 2);
  });
}
