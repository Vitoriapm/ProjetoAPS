import 'dart:math' as math;

import 'package:geolocator/geolocator.dart';

import '../models/position_point.dart';

class LocationUnavailable implements Exception {
  const LocationUnavailable(this.message);
  final String message;
  @override
  String toString() => message;
}

abstract interface class LocationGateway {
  Future<PositionPoint> requestCurrentPosition();
  Stream<PositionPoint> watchPosition();
}

class LocationService implements LocationGateway {
  @override
  Future<PositionPoint> requestCurrentPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const LocationUnavailable(
        'Ative a localização do aparelho ou escolha um ponto no mapa.',
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw const LocationUnavailable(
        'Localização não autorizada. Você pode escolher um ponto no mapa.',
      );
    }
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
    return _point(position);
  }

  @override
  Stream<PositionPoint> watchPosition() => Geolocator.getPositionStream(
    locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 30,
    ),
  ).map(_point);

  PositionPoint _point(Position value) => PositionPoint(
    latitude: value.latitude,
    longitude: value.longitude,
    accuracyM: value.accuracy,
    source: 'gps',
  );
}

double distanceInMeters(
  double latitudeA,
  double longitudeA,
  double latitudeB,
  double longitudeB,
) {
  const earthRadius = 6371000.0;
  double radians(double value) => value * math.pi / 180;
  final deltaLatitude = radians(latitudeB - latitudeA);
  final deltaLongitude = radians(longitudeB - longitudeA);
  final a =
      math.pow(math.sin(deltaLatitude / 2), 2) +
      math.cos(radians(latitudeA)) *
          math.cos(radians(latitudeB)) *
          math.pow(math.sin(deltaLongitude / 2), 2);
  return 2 * earthRadius * math.asin(math.sqrt(a.toDouble().clamp(0, 1)));
}
