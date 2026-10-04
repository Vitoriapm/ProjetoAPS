import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

typedef PushRegistrar = Future<void> Function(String token, String platform);

/// Keeps the iOS ordering testable without starting the Firebase SDK.
Future<({String? token, bool waitingForApns})> readPushRegistrationToken({
  required bool isIos,
  required Future<String?> Function() getApnsToken,
  required Future<String?> Function() getFcmToken,
}) async {
  if (isIos && await getApnsToken() == null) {
    return (token: null, waitingForApns: true);
  }
  return (token: await getFcmToken(), waitingForApns: false);
}

class PushService {
  static const enabled = bool.fromEnvironment(
    'FIREBASE_ENABLED',
    defaultValue: false,
  );
  StreamSubscription<String>? _tokenSubscription;
  StreamSubscription<RemoteMessage>? _messageSubscription;
  StreamSubscription<RemoteMessage>? _openedSubscription;
  String? _token;
  bool _disposed = false;
  PushRegistrar? _registrar;
  void Function(String)? _onStatus;

  Future<void> initialize({
    required PushRegistrar registrar,
    required void Function() onNotification,
    required void Function(String) onStatus,
  }) async {
    _registrar = registrar;
    _onStatus = onStatus;
    if (!enabled) {
      onStatus('Push pendente: configure Firebase para Android/iOS.');
      return;
    }
    if (kIsWeb) {
      onStatus(
        'Push nativo disponível nas versões Android/iOS; preview usa avisos no app.',
      );
      return;
    }
    try {
      await Firebase.initializeApp();
      if (_disposed) return;
      final permission = await FirebaseMessaging.instance.requestPermission();
      if (permission.authorizationStatus == AuthorizationStatus.denied) {
        onStatus(
          'Notificações não autorizadas. Os avisos no app continuam disponíveis.',
        );
        return;
      }
      await FirebaseMessaging.instance
          .setForegroundNotificationPresentationOptions(
            alert: false,
            badge: true,
            sound: false,
          );
      _tokenSubscription = FirebaseMessaging.instance.onTokenRefresh.listen(
        (token) {
          _token = token;
          unawaited(retryRegistration());
        },
        onError: (Object error) =>
            onStatus('Push aguardando token do Firebase.'),
      );
      _messageSubscription = FirebaseMessaging.onMessage.listen(
        (message) => onNotification(),
      );
      _openedSubscription = FirebaseMessaging.onMessageOpenedApp.listen(
        (message) => onNotification(),
      );
      // A missing APNs token leaves listeners active for refresh/resume retry.
      await retryRegistration();
      if (await FirebaseMessaging.instance.getInitialMessage() != null &&
          !_disposed) {
        onNotification();
      }
    } catch (_) {
      if (!_disposed) {
        onStatus(
          'Push pendente: confira os arquivos Firebase e a permissão do aparelho.',
        );
      }
    }
  }

  Future<void> retryRegistration() async {
    if (_disposed || !enabled || kIsWeb) return;
    try {
      if (_token == null) {
        final messaging = FirebaseMessaging.instance;
        final result = await readPushRegistrationToken(
          isIos: defaultTargetPlatform == TargetPlatform.iOS,
          getApnsToken: messaging.getAPNSToken,
          getFcmToken: messaging.getToken,
        );
        if (_disposed) return;
        if (result.waitingForApns) {
          _onStatus?.call(
            'Push aguardando registro APNs do iPhone. O app tentará novamente ao retomar.',
          );
          return;
        }
        _token = result.token;
      }
      if (_token == null) {
        _onStatus?.call('Push aguardando registro do aparelho no Firebase.');
        return;
      }
      await _registrar?.call(
        _token!,
        defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android',
      );
      if (!_disposed) {
        _onStatus?.call(
          'Push registrado; teste de recebimento em aparelho ainda necessário.',
        );
      }
    } catch (_) {
      if (!_disposed) {
        _onStatus?.call('Push aguardando conexão ou configuração do Firebase.');
      }
    }
  }

  void dispose() {
    _disposed = true;
    unawaited(_tokenSubscription?.cancel());
    unawaited(_messageSubscription?.cancel());
    unawaited(_openedSubscription?.cancel());
  }
}
