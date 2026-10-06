import 'dart:convert';
import 'dart:io';

import 'package:ecopulse/models/environmental_point.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'Landsat historical metadata and polygon center survive offline storage',
    () {
      final dataset = jsonDecode(
        File('../backend/datasets/heat-ribeirao-preto.geojson')
            .readAsStringSync(),
      ) as Map<String, dynamic>;
      final feature = Map<String, dynamic>.from(
        (dataset['features'] as List).first as Map,
      );
      final properties = Map<String, dynamic>.from(
        feature['properties'] as Map,
      );
      final point = EnvironmentalPoint.fromFeature(feature);
      final restored = EnvironmentalPoint.fromFeature(
        jsonDecode(jsonEncode(point.toFeature())) as Map<String, dynamic>,
      );
      expect(restored.isDemo, isFalse);
      expect(restored.observationType, 'historic');
      expect(restored.updatedAt.year, 2025);
      expect(restored.sceneId, 'LC09_L2SP_220075_20250917_02_T1');
      expect(restored.label, contains('não representa o calor atual'));
      expect(restored.latitude, properties['center_latitude']);
      expect(restored.longitude, properties['center_longitude']);
      expect(restored.surfaceTemperatureC, point.surfaceTemperatureC);
      expect(restored.referenceTemperatureC, point.referenceTemperatureC);
      expect(restored.polygon, point.polygon);
    },
  );

  test('AQI without optional historic fields remains compatible', () {
    final point = EnvironmentalPoint.fromFeature({
      'type': 'Feature',
      'id': 'air',
      'geometry': {
        'type': 'Point',
        'coordinates': [-47.8, -21.2],
      },
      'properties': {
        'id': 'air',
        'kind': 'aqi',
        'value': 77,
        'unit': 'AQI',
        'scale': 'US AQI',
        'source': 'Open-Meteo / CAMS',
        'updated_at': '2026-10-04T17:00:00Z',
        'is_demo': false,
        'label': 'AQI modelado; não é medição de estação local',
      },
    });
    expect(point.observationType, isNull);
    expect(point.expiresAt, isNull);
    expect(point.latitude, -21.2);
    expect(point.toFeature()['properties'], isNot(contains('scene_id')));
  });
}
