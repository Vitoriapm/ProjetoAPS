import 'package:flutter/material.dart';

import '../models/report.dart';

Color severityColor(Severity severity) => switch (severity) {
  Severity.low => const Color(0xFF297D68),
  Severity.medium => const Color(0xFFAC6B15),
  Severity.high => const Color(0xFFB2493D),
};

IconData reportIcon(ReportType type) => switch (type) {
  ReportType.flood => Icons.water_drop_outlined,
  ReportType.obstruction => Icons.block_outlined,
};

String shortDate(DateTime value) {
  final date = value.toLocal();
  final day = date.day.toString().padLeft(2, '0');
  final month = date.month.toString().padLeft(2, '0');
  final hour = date.hour.toString().padLeft(2, '0');
  final minute = date.minute.toString().padLeft(2, '0');
  return '$day/$month às $hour:$minute';
}

class InfoStrip extends StatelessWidget {
  const InfoStrip({
    super.key,
    required this.icon,
    required this.text,
    this.color,
    this.trailing,
  });

  final IconData icon;
  final String text;
  final Color? color;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final tone = color ?? Theme.of(context).colorScheme.primary;
    return Container(
      decoration: BoxDecoration(
        color: tone.withValues(alpha: .08),
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Icon(icon, size: 18, color: tone),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: TextStyle(fontSize: 12, color: tone)),
          ),
          ?trailing,
        ],
      ),
    );
  }
}
