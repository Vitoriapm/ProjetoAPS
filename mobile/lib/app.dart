import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'state/report_controller.dart';

class EcoPulseApp extends StatefulWidget {
  const EcoPulseApp({
    super.key,
    this.controller,
    this.initializeController = true,
  });

  final ReportController? controller;
  final bool initializeController;

  @override
  State<EcoPulseApp> createState() => _EcoPulseAppState();
}

class _EcoPulseAppState extends State<EcoPulseApp> {
  late final ReportController _controller;

  @override
  void initState() {
    super.initState();
    _controller = widget.controller ?? ReportController();
    if (widget.initializeController) _controller.initialize();
  }

  @override
  void dispose() {
    if (widget.controller == null) _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF237C70),
      brightness: Brightness.light,
      surface: const Color(0xFFFAFCFA),
    );
    return MaterialApp(
      title: 'EcoPulse',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: colorScheme,
        scaffoldBackgroundColor: colorScheme.surface,
        appBarTheme: AppBarTheme(
          backgroundColor: colorScheme.surface,
          foregroundColor: const Color(0xFF203C35),
          elevation: 0,
          scrolledUnderElevation: 0,
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(minimumSize: const Size(0, 48)),
        ),
      ),
      builder: (context, child) => ColoredBox(
        color: const Color(0xFFE6ECE7),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: child!,
          ),
        ),
      ),
      home: HomeScreen(controller: _controller),
    );
  }
}
