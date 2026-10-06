import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

typedef PushRegistrar = Future<void> Function(String token, String platform);

/// The gateway keeps retries and notification handling testable without FCM.
abstract class PushGateway {
  Future<void> initialize();
  Future<AuthorizationStatus> permission({required bool request});
  Future<void> enableTokenGeneration();
  Future<void> configureForeground();
  Future<String?> getApnsToken();
  Future<String?> getFcmToken();
  Stream<String> get tokenRefresh;
  Stream<RemoteMessage> get messages;
  Stream<RemoteMessage> get openedMessages;
  Future<RemoteMessage?> initialMessage();
}

class FirebasePushGateway implements PushGateway {
  @override
  Future<void> initialize() async {
    await Firebase.initializeApp();
  }

  @override
  Future<AuthorizationStatus> permission({required bool request}) async {
    final settings = request
        ? await FirebaseMessaging.instance.requestPermission()
        : await FirebaseMessaging.instance.getNotificationSettings();
    return settings.authorizationStatus;
  }

  @override
  Future<void> enableTokenGeneration() =>
      FirebaseMessaging.instance.setAutoInitEnabled(true);

  @override
  Future<void> configureForeground() =>
      FirebaseMessaging.instance.setForegroundNotificationPresentationOptions(
        alert: false,
        badge: true,
        sound: false,
      );

  @override
  Future<String?> getApnsToken() => FirebaseMessaging.instance.getAPNSToken();
  @override
  Future<String?> getFcmToken() => FirebaseMessaging.instance.getToken();
  @override
  Stream<String> get tokenRefresh => FirebaseMessaging.instance.onTokenRefresh;
  @override
  Stream<RemoteMessage> get messages => FirebaseMessaging.onMessage;
  @override
  Stream<RemoteMessage> get openedMessages =>
      FirebaseMessaging.onMessageOpenedApp;
  @override
  Future<RemoteMessage?> initialMessage() =>
      FirebaseMessaging.instance.getInitialMessage();
}

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
  PushService({
    PushGateway? gateway,
    bool? enableFirebase,
    bool? isIos,
    bool? isWeb,
  }) : _gateway = gateway ?? FirebasePushGateway(),
       _enabled = enableFirebase ?? enabled,
       _isIos = isIos ?? defaultTargetPlatform == TargetPlatform.iOS,
       _isWeb = isWeb ?? kIsWeb;

  static const enabled = bool.fromEnvironment(
    'FIREBASE_ENABLED',
    defaultValue: false,
  );
  final PushGateway _gateway;
  final bool _enabled;
  final bool _isIos;
  final bool _isWeb;
  final _foregroundEvents = <String>{};
  final _openedEvents = <String>{};
  StreamSubscription<String>? _tokenSubscription;
  StreamSubscription<RemoteMessage>? _messageSubscription;
  StreamSubscription<RemoteMessage>? _openedSubscription;
  Future<void>? _initialization;
  Future<void>? _registration;
  String? _token;
  bool _disposed = false;
  bool _ready = false;
  bool _registrationAgain = false;
  PushRegistrar? _registrar;
  void Function(String)? _onStatus;
  void Function()? _onNotification;
  String? _lastReceipt;
  int _foregroundReceiptCount = 0;

  /// Local callback observation for this process, without tokens or coordinates.
  String? get lastReceipt => _lastReceipt;

  Future<void> initialize({
    required PushRegistrar registrar,
    required void Function() onNotification,
    required void Function(String) onStatus,
  }) {
    _registrar = registrar;
    _onStatus = onStatus;
    _onNotification = onNotification;
    return _initialization ??= _initialize();
  }

  void _status(String value) {
    if (!_disposed) _onStatus?.call(value);
  }

  Future<void> _initialize() async {
    if (_disposed) return;
    if (!_enabled) {
      _status('Push pendente: configure Firebase para Android/iOS.');
      return;
    }
    if (_isWeb) {
      _status(
        'Push nativo disponível nas versões Android/iOS; preview usa avisos no app.',
      );
      return;
    }
    try {
      await _gateway.initialize();
      if (_disposed) return;
      await _gateway.configureForeground();
      if (_disposed) return;
      _tokenSubscription = _gateway.tokenRefresh.listen(
        (token) {
          _token = token;
          unawaited(retryRegistration());
        },
        onError: (Object error) =>
            _status('Push aguardando token do Firebase.'),
      );
      _messageSubscription = _gateway.messages.listen(
        (message) => _receive(message, opened: false),
        onError: (Object error) =>
            _status('Push aguardando conexão do Firebase.'),
      );
      _openedSubscription = _gateway.openedMessages.listen(
        (message) => _receive(message, opened: true),
        onError: (Object error) =>
            _status('Push aguardando conexão do Firebase.'),
      );
      _ready = true;
      // Ask once; subsequent resume/network retries only read the permission.
      await _gateway.permission(request: true);
      await retryRegistration();
      final initial = await _gateway.initialMessage();
      if (initial != null) _receive(initial, opened: true);
    } catch (_) {
      _status(
        'Push pendente: confira os arquivos Firebase e a permissão do aparelho.',
      );
    }
  }

  void _receive(RemoteMessage message, {required bool opened}) {
    if (_disposed) return;
    final eventId = message.data['event_id']?.toString();
    final incidentId = message.data['incident_id']?.toString();
    final version = message.data['version']?.toString();
    final key =
        eventId ??
        message.messageId ??
        (incidentId != null && version != null ? '$incidentId:$version' : null);
    // A tap may refresh a previously received foreground message. Duplicate
    // callbacks within the same path are bounded and ignored in this process.
    final seen = opened ? _openedEvents : _foregroundEvents;
    if (key != null) {
      if (!seen.add(key)) return;
      if (seen.length > 128) seen.remove(seen.first);
    }
    final now = DateTime.now();
    final time = [
      now.hour,
      now.minute,
      now.second,
    ].map((value) => value.toString().padLeft(2, '0')).join(':');
    if (opened) {
      _lastReceipt = 'Último push: aberto por toque às $time.';
    } else {
      _foregroundReceiptCount++;
      _lastReceipt =
          'Push recebido com o app aberto às $time '
          '($_foregroundReceiptCount nesta sessão).';
    }
    _onNotification?.call();
  }

  Future<void> retryRegistration() {
    if (_disposed || !_ready || !_enabled || _isWeb) return Future.value();
    if (_registration != null) {
      _registrationAgain = true;
      return _registration!;
    }
    final task = _register();
    _registration = task;
    return task.whenComplete(() => _registration = null);
  }

  Future<void> _register() async {
    do {
      _registrationAgain = false;
      var registeringWithServer = false;
      try {
        final permission = await _gateway.permission(request: false);
        if (_disposed) return;
        if (permission != AuthorizationStatus.authorized &&
            permission != AuthorizationStatus.provisional) {
          _status(
            'Notificações não autorizadas. Ative nas configurações do aparelho; os avisos no app continuam disponíveis.',
          );
          return;
        }
        // A refreshed token delivered during this await takes precedence.
        final beforeRead = _token;
        final result = await readPushRegistrationToken(
          isIos: _isIos,
          getApnsToken: _gateway.getApnsToken,
          getFcmToken: () async {
            if (_disposed) return null;
            await _gateway.enableTokenGeneration();
            if (_disposed) return null;
            return _gateway.getFcmToken();
          },
        );
        if (_disposed) return;
        if (result.waitingForApns) {
          _status(
            'Push aguardando registro APNs do iPhone. O app tentará novamente ao retomar.',
          );
          return;
        }
        if (_token == beforeRead) _token = result.token ?? _token;
        final token = _token;
        if (token == null) {
          _status('Push aguardando registro do aparelho no Firebase.');
          return;
        }
        registeringWithServer = true;
        await _registrar?.call(token, _isIos ? 'ios' : 'android');
        _status('Push registrado no servidor.');
      } catch (_) {
        _status(
          registeringWithServer
              ? 'Push aguardando conexão com o servidor EcoPulse. O app tentará novamente.'
              : 'Push aguardando conexão do Firebase. O app tentará novamente.',
        );
      }
    } while (_registrationAgain && !_disposed);
  }

  void dispose() {
    _disposed = true;
    unawaited(_tokenSubscription?.cancel());
    unawaited(_messageSubscription?.cancel());
    unawaited(_openedSubscription?.cancel());
    _foregroundEvents.clear();
    _openedEvents.clear();
  }
}
