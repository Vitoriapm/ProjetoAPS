class RouteResult {
  const RouteResult({
    required this.coordinates,
    required this.distanceM,
    required this.durationS,
    required this.avoidedIncidents,
    required this.source,
    required this.updatedAt,
  });

  final List<List<double>> coordinates;
  final double distanceM;
  final double durationS;
  final int avoidedIncidents;
  final String source;
  final DateTime updatedAt;

  factory RouteResult.fromJson(Map<String, dynamic> json) {
    final geometry = Map<String, dynamic>.from(json['geometry'] as Map);
    return RouteResult(
      coordinates: (geometry['coordinates'] as List)
          .map(
            (coordinate) => (coordinate as List)
                .map((number) => (number as num).toDouble())
                .toList(),
          )
          .toList(),
      distanceM: (json['distance_m'] as num).toDouble(),
      durationS: (json['duration_s'] as num).toDouble(),
      avoidedIncidents: (json['avoided_incidents'] as num).toInt(),
      source: json['source'] as String,
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}
