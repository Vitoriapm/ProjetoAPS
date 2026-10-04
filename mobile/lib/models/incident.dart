import 'report.dart';

class Incident {
  const Incident({
    required this.id,
    required this.type,
    required this.severity,
    required this.centerLatitude,
    required this.centerLongitude,
    required this.radiusM,
    required this.updatedAt,
    required this.expiresAt,
    required this.isDemo,
    required this.reportCount,
    required this.version,
    required this.state,
    required this.polygons,
  });

  final String id;
  final ReportType type;
  final Severity severity;
  final double centerLatitude;
  final double centerLongitude;
  final double radiusM;
  final DateTime updatedAt;
  final DateTime expiresAt;
  final bool isDemo;
  final int reportCount;
  final int version;
  final String state;
  final List<List<double>> polygons;

  factory Incident.fromFeature(Map<String, dynamic> feature) {
    final properties = Map<String, dynamic>.from(feature['properties'] as Map);
    final geometry = Map<String, dynamic>.from(feature['geometry'] as Map);
    final rings = geometry['coordinates'] as List;
    return Incident(
      id: properties['id'] as String? ?? feature['id'] as String,
      type: ReportType.parse(properties['tipo'] as String),
      severity: Severity.parse(properties['gravidade'] as String),
      centerLatitude: (properties['center_latitude'] as num).toDouble(),
      centerLongitude: (properties['center_longitude'] as num).toDouble(),
      radiusM: (properties['radius_m'] as num).toDouble(),
      updatedAt: DateTime.parse(properties['updated_at'] as String),
      expiresAt: DateTime.parse(properties['expires_at'] as String),
      isDemo: properties['is_demo'] as bool? ?? false,
      reportCount: (properties['report_count'] as num).toInt(),
      version: (properties['version'] as num).toInt(),
      state: properties['estado'] as String,
      polygons: (rings.first as List)
          .map(
            (coordinate) => (coordinate as List)
                .map((number) => (number as num).toDouble())
                .toList(),
          )
          .toList(),
    );
  }

  Map<String, dynamic> toFeature() => {
    'type': 'Feature',
    'id': id,
    'geometry': {
      'type': 'Polygon',
      'coordinates': [polygons],
    },
    'properties': {
      'id': id,
      'tipo': type.wireValue,
      'gravidade': severity.wireValue,
      'center_latitude': centerLatitude,
      'center_longitude': centerLongitude,
      'radius_m': radiusM,
      'updated_at': updatedAt.toUtc().toIso8601String(),
      'expires_at': expiresAt.toUtc().toIso8601String(),
      'is_demo': isDemo,
      'report_count': reportCount,
      'version': version,
      'estado': state,
    },
  };
}
