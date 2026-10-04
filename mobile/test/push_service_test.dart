import 'package:ecopulse/services/push_service.dart';
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

  test('Unavailable FCM token after APNs is not reported as APNs pending', () async {
    final result = await readPushRegistrationToken(
      isIos: true,
      getApnsToken: () async => 'apns-ready',
      getFcmToken: () async => null,
    );

    expect(result.token, isNull);
    expect(result.waitingForApns, isFalse);
  });

  test('Default disabled Firebase leaves registration pending without SDK calls', () async {
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
  });
}
