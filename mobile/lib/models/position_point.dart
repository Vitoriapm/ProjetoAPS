class PositionPoint {
  const PositionPoint({
    required this.latitude,
    required this.longitude,
    this.accuracyM,
    this.source = 'gps',
  });

  final double latitude;
  final double longitude;
  final double? accuracyM;
  final String source;
}
