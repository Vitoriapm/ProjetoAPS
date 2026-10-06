import 'dart:async';

import 'package:ecopulse/services/push_service.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('iOS without APNs token never requests FCM token', () async {
    var apnsCalls = 0;
    var fcmCalls = 0;
    final result = await readPushRegistrationToken(
      isIos: true,
      getApnsToken: () async {
        apnsCalls++;
        return null;
      },
      getFcmToken: () async {
        fcmCalls++;
        return 'must-not-be-requested';
      },
    );

    expect(apnsCalls, 1);
    expect(fcmCalls, 0);
    expect(result.token, isNull);
    expect(result.waitingForApns, isTrue);
  });

  test('iOS requests FCM only after APNs becomes available on retry', () async {
    String? apnsToken;
    final calls = <String>[];
    Future<({String? token, bool waitingForApns})> read() =>
        readPushRegistrationToken(
          isIos: true,
          getApnsToken: () async {
            calls.add('apns');
            return apnsToken;
          },
          getFcmToken: () async {
            calls.add('fcm');
            return 'ios-fcm-token';
          },
        );

    final firstAttempt = await read();
    expect(firstAttempt.waitingForApns, isTrue);
    expect(calls, ['apns']);

    apnsToken = 'apns-ready';
    final resumedAttempt = await read();
    expect(calls, ['apns', 'apns', 'fcm']);
    expect(resumedAttempt.token, 'ios-fcm-token');
    expect(resumedAttempt.waitingForApns, isFalse);
  });

  test('Android requests FCM without touching APNs', () async {
    var fcmCalls = 0;
    final result = await readPushRegistrationToken(
      isIos: false,
      getApnsToken: () async => throw StateError('APNs is iOS-only'),
      getFcmToken: () async {
        fcmCalls++;
        return 'android-fcm-token';
      },
    );

    expect(fcmCalls, 1);
    expect(result.token, 'android-fcm-token');
    expect(result.waitingForApns, isFalse);
  });

  test(
    'Unavailable FCM token after APNs is not reported as APNs pending',
    () async {
      final result = await readPushRegistrationToken(
        isIos: true,
        getApnsToken: () async => 'apns-ready',
        getFcmToken: () async => null,
      );

      expect(result.token, isNull);
      expect(result.waitingForApns, isFalse);
    },
  );

  test(
    'Default disabled Firebase leaves registration pending without SDK calls',
    () async {
      expect(PushService.enabled, isFalse);
      final service = PushService();
      final statuses = <String>[];
      var registrationCalls = 0;
      var notificationCalls = 0;
      await service.initialize(
        registrar: (token, platform) async {
          registrationCalls++;
        },
        onNotification: () => notificationCalls++,
        onStatus: statuses.add,
      );
      await service.retryRegistration();

      expect(registrationCalls, 0);
      expect(notificationCalls, 0);
      expect(statuses.single, contains('Push pendente'));
      service.dispose();
    },
  );

  test('Denied permission does not generate tokens; resume uses settings without a new prompt', () async {
    final gateway = FakePushGateway()
      ..authorization = AuthorizationStatus.denied;
    final service = gateway.service();
    final registered = <String>[];
    final statuses = <String>[];
    await service.initialize(
      registrar: (token, platform) async => registered.add(token),
      onNotification: () {},
      onStatus: statuses.add,
    );
    await service.retryRegistration();
    expect(gateway.permissionRequests, 1);
    expect(gateway.fcmCalls, 0);
    expect(gateway.enableCalls, 0);
    expect(registered, isEmpty);
    expect(statuses.last, contains('não autorizadas'));
    gateway.authorization = AuthorizationStatus.authorized;
    await service.retryRegistration();
    expect(registered, ['first-token']);
    expect(gateway.permissionRequests, 1);
    service.dispose();
    await gateway.close();
  });

  test(
    'iOS waits for APNs before enabling FCM and retries on resume',
    () async {
      final gateway = FakePushGateway()..apns = null;
      final service = gateway.service(ios: true);
      final platforms = <String>[];
      final statuses = <String>[];
      await service.initialize(
        registrar: (token, platform) async => platforms.add(platform),
        onNotification: () {},
        onStatus: statuses.add,
      );
      expect(gateway.fcmCalls, 0);
      expect(gateway.enableCalls, 0);
      expect(statuses.last, contains('APNs'));
      gateway.apns = 'apple-token';
      await service.retryRegistration();
      expect(platforms, ['ios']);
      service.dispose();
      await gateway.close();
    },
  );

  test('Offline registration retries the same token without losing the subscription', () async {
    final gateway = FakePushGateway();
    final service = gateway.service();
    var calls = 0;
    final statuses = <String>[];
    await service.initialize(
      registrar: (token, platform) async {
        calls++;
        if (calls == 1) throw StateError('network offline');
        expect(token, 'first-token');
      },
      onNotification: () {},
      onStatus: statuses.add,
    );
    expect(
      statuses.last,
      contains('aguardando conexão com o servidor EcoPulse'),
    );
    expect(statuses.last, isNot(contains('Firebase')));
    await service.retryRegistration();
    expect(calls, 2);
    expect(statuses.last, contains('registrado'));
    service.dispose();
    await gateway.close();
  });

  test(
    'Firebase token failure is distinct from a backend registration failure',
    () async {
      final gateway = FakePushGateway()..failTokenRead = true;
      final service = gateway.service();
      final statuses = <String>[];
      var registrations = 0;
      await service.initialize(
        registrar: (_, _) async => registrations++,
        onNotification: () {},
        onStatus: statuses.add,
      );
      expect(registrations, 0);
      expect(statuses.last, contains('aguardando conexão do Firebase'));
      expect(statuses.last, isNot(contains('servidor EcoPulse')));
      gateway.failTokenRead = false;
      await service.retryRegistration();
      expect(registrations, 1);
      expect(statuses.last, 'Push registrado no servidor.');
      service.dispose();
      await gateway.close();
    },
  );

  test(
    'Refresh during registration is serialized and sends the newest token',
    () async {
      final gateway = FakePushGateway();
      final service = gateway.service();
      final started = Completer<void>();
      final release = Completer<void>();
      final registered = <String>[];
      var inFlight = 0;
      var maximumInFlight = 0;
      final initialized = service.initialize(
        registrar: (token, platform) async {
          inFlight++;
          if (inFlight > maximumInFlight) maximumInFlight = inFlight;
          registered.add(token);
          if (registered.length == 1) {
            started.complete();
            await release.future;
          }
          inFlight--;
        },
        onNotification: () {},
        onStatus: (_) {},
      );
      await started.future;
      gateway.fcm = 'renewed-token';
      gateway.tokens.add('renewed-token');
      final retried = service.retryRegistration();
      release.complete();
      await Future.wait([initialized, retried]);
      expect(registered, ['first-token', 'renewed-token']);
      expect(maximumInFlight, 1);
      service.dispose();
      await gateway.close();
    },
  );

  test('Notification tap after termination refreshes once; foreground and tap paths deduplicate independently', () async {
    final gateway = FakePushGateway();
    const initial = RemoteMessage(data: {'event_id': 'initial-event'});
    gateway.initial = initial;
    final service = gateway.service();
    var received = 0;
    await service.initialize(
      registrar: (token, platform) async {},
      onNotification: () => received++,
      onStatus: (_) {},
    );
    gateway.opened.add(initial);
    expect(received, 1);
    const event = RemoteMessage(data: {'event_id': 'event-2'});
    gateway.foreground.add(event);
    gateway.foreground.add(event);
    expect(received, 2);
    expect(service.lastReceipt, contains('Push recebido com o app aberto'));
    expect(service.lastReceipt, contains('(1 nesta sessão)'));
    final receipt = service.lastReceipt;
    await service.retryRegistration();
    expect(service.lastReceipt, receipt);
    gateway.opened.add(event);
    gateway.opened.add(event);
    expect(received, 3);
    expect(service.lastReceipt, contains('aberto por toque'));
    service.dispose();
    gateway.foreground.add(
      const RemoteMessage(data: {'event_id': 'after-dispose'}),
    );
    expect(received, 3);
    await gateway.close();
  });

  test('Repeated initialization keeps one listener and browser never starts native Firebase', () async {
    final gateway = FakePushGateway();
    final service = gateway.service();
    var received = 0;
    Future<void> initialize() => service.initialize(
      registrar: (token, platform) async {},
      onNotification: () => received++,
      onStatus: (_) {},
    );
    await initialize();
    await initialize();
    gateway.foreground.add(const RemoteMessage(messageId: 'console-message'));
    expect(received, 1);
    expect(gateway.initializeCalls, 1);
    service.dispose();
    final web = PushService(
      gateway: gateway,
      enableFirebase: true,
      isWeb: true,
    );
    await web.initialize(
      registrar: (token, platform) async {},
      onNotification: () {},
      onStatus: (_) {},
    );
    expect(gateway.initializeCalls, 1);
    web.dispose();
    await gateway.close();
  });
}

class FakePushGateway implements PushGateway {
  final tokens = StreamController<String>.broadcast(sync: true);
  final foreground = StreamController<RemoteMessage>.broadcast(sync: true);
  final opened = StreamController<RemoteMessage>.broadcast(sync: true);
  AuthorizationStatus authorization = AuthorizationStatus.authorized;
  String? apns = 'apple-token';
  String? fcm = 'first-token';
  RemoteMessage? initial;
  var initializeCalls = 0;
  var permissionRequests = 0;
  var enableCalls = 0;
  var fcmCalls = 0;
  var failTokenRead = false;
  PushService service({bool ios = false}) => PushService(
    gateway: this,
    enableFirebase: true,
    isIos: ios,
    isWeb: false,
  );
  @override
  Future<void> initialize() async {
    initializeCalls++;
  }

  @override
  Future<AuthorizationStatus> permission({required bool request}) async {
    if (request) permissionRequests++;
    return authorization;
  }

  @override
  Future<void> enableTokenGeneration() async {
    enableCalls++;
  }

  @override
  Future<void> configureForeground() async {}
  @override
  Future<String?> getApnsToken() async => apns;
  @override
  Future<String?> getFcmToken() async {
    fcmCalls++;
    if (failTokenRead) throw StateError('token temporarily unavailable');
    return fcm;
  }

  @override
  Stream<String> get tokenRefresh => tokens.stream;
  @override
  Stream<RemoteMessage> get messages => foreground.stream;
  @override
  Stream<RemoteMessage> get openedMessages => opened.stream;
  @override
  Future<RemoteMessage?> initialMessage() async => initial;
  Future<void> close() async {
    await Future.wait([tokens.close(), foreground.close(), opened.close()]);
  }
}
