class EnvironmentalPoint {
  const EnvironmentalPoint({
    required this.id,
    required this.kind,
    required this.value,
    required this.unit,
    required this.scale,
    required this.source,
    required this.updatedAt,
    required this.isDemo,
    required this.label,
    required this.latitude,
    required this.longitude,
    this.polygon,
  });

  final String id;
  final String kind;
  final double value;
  final String unit;
  final String scale;
  final String source;
  final DateTime updatedAt;
  final bool isDemo;
  final String label;
  final double latitude;
  final double longitude;
  final List<List<double>>? polygon;

  factory EnvironmentalPoint.fromFeature(Map<String, dynamic> feature) {
    final properties = Map<String, dynamic>.from(feature['properties'] as Map);
    final geometry = Map<String, dynamic>.from(feature['geometry'] as Map);
    final coords = geometry['coordinates'] as List;
    final isPolygon = geometry['type'] == 'Polygon';
    final polygon = isPolygon
        ? (coords.first as List)
              .map(
                (coordinate) => (coordinate as List)
                    .map((number) => (number as num).toDouble())
                    .toList(),
              )
              .toList()
        : null;
    final anchor = isPolygon ? polygon!.first : coords;
    return EnvironmentalPoint(
      id: properties['id'] as String? ?? feature['id'] as String,
      kind: properties['kind'] as String,
      value: (properties['value'] as num).toDouble(),
      unit: properties['unit'] as String,
      scale: properties['scale'] as String,
      source: properties['source'] as String,
      updatedAt: DateTime.parse(properties['updated_at'] as String),
      isDemo: properties['is_demo'] as bool? ?? false,
      label: properties['label'] as String,
      longitude: (anchor[0] as num).toDouble(),
      latitude: (anchor[1] as num).toDouble(),
      polygon: polygon,
    );
  }

  Map<String, dynamic> toFeature() => {
    'type': 'Feature',
    'id': id,
    'geometry': polygon == null
        ? {
            'type': 'Point',
            'coordinates': [longitude, latitude],
          }
        : {
            'type': 'Polygon',
            'coordinates': [polygon],
          },
    'properties': {
      'id': id,
      'kind': kind,
      'value': value,
      'unit': unit,
      'scale': scale,
      'source': source,
      'updated_at': updatedAt.toUtc().toIso8601String(),
      'is_demo': isDemo,
      'label': label,
    },
  };
}
