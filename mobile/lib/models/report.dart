enum Severity {
  low('Baixa', 'baixa'),
  medium('Média', 'media'),
  high('Alta', 'alta');

  const Severity(this.label, this.wireValue);
  final String label;
  final String wireValue;

  static Severity parse(String value) =>
      values.firstWhere((item) => item.wireValue == value);
}

enum ReportType {
  flood('Alagamento', 'alagamento'),
  obstruction('Via obstruída', 'obstrucao');

  const ReportType(this.label, this.wireValue);
  final String label;
  final String wireValue;

  static ReportType parse(String value) =>
      values.firstWhere((item) => item.wireValue == value);
}

class Report {
  const Report({
    required this.id,
    required this.latitude,
    required this.longitude,
    required this.severity,
    required this.type,
    required this.occurredAt,
    this.description = '',
    this.receivedAt,
    this.isDemo = false,
    this.isPending = false,
    this.positionSource = 'manual',
    this.accuracyM,
  });

  final String id;
  final double latitude;
  final double longitude;
  final Severity severity;
  final ReportType type;
  final String description;
  final DateTime occurredAt;
  final DateTime? receivedAt;
  final bool isDemo;
  final bool isPending;
  final String positionSource;
  final double? accuracyM;

  /// Exactly the POST contract: local queue flags never leave the device.
  Map<String, dynamic> toJson() => {
    'id': id,
    'tipo': type.wireValue,
    'gravidade': severity.wireValue,
    'latitude': latitude,
    'longitude': longitude,
    'descricao': description,
    'occurred_at': occurredAt.toUtc().toIso8601String(),
    'position_source': positionSource,
    'accuracy_m': accuracyM,
    'is_demo': isDemo,
  };

  Map<String, dynamic> toLocalJson() => {
    ...toJson(),
    'received_at': receivedAt?.toUtc().toIso8601String(),
    'is_pending': isPending,
  };

  factory Report.fromJson(Map<String, dynamic> json) => Report(
    id: json['id'] as String,
    latitude: (json['latitude'] as num).toDouble(),
    longitude: (json['longitude'] as num).toDouble(),
    severity: Severity.parse(json['gravidade'] as String),
    type: ReportType.parse(json['tipo'] as String),
    occurredAt: DateTime.parse(json['occurred_at'] as String),
    description: json['descricao'] as String? ?? '',
    receivedAt: json['received_at'] == null
        ? null
        : DateTime.parse(json['received_at'] as String),
    isDemo: json['is_demo'] as bool? ?? false,
    isPending: json['is_pending'] as bool? ?? false,
    positionSource: json['position_source'] as String? ?? 'manual',
    accuracyM: (json['accuracy_m'] as num?)?.toDouble(),
  );

  Report confirmed({DateTime? receivedAt}) => Report(
    id: id,
    latitude: latitude,
    longitude: longitude,
    severity: severity,
    type: type,
    occurredAt: occurredAt,
    description: description,
    receivedAt: receivedAt ?? this.receivedAt,
    isDemo: isDemo,
    isPending: false,
    positionSource: positionSource,
    accuracyM: accuracyM,
  );
}
