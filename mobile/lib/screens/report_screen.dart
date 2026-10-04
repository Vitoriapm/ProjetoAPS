import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/report.dart';
import '../state/report_controller.dart';
import '../widgets/report_style.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, required this.controller, this.initialPoint});
  final ReportController controller;
  final LatLng? initialPoint;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final TextEditingController _description = TextEditingController();
  final MapController _mapController = MapController();
  ReportType _type = ReportType.flood;
  Severity _severity = Severity.medium;
  LatLng? _point;
  String _pointSource = 'manual';
  double? _accuracy;
  bool _locating = false;
  bool _submitting = false;
  bool _mapReady = false;
  bool _isDemoPoint = false;
  int _pointRevision = 0;
  String? _locationNote;

  @override
  void initState() {
    super.initState();
    _point = widget.initialPoint;
    if (_point == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _locate());
    }
  }

  @override
  void dispose() {
    _description.dispose();
    _mapController.dispose();
    super.dispose();
  }

  Future<void> _locate() async {
    if (_locating) return;
    setState(() => _locating = true);
    final requestedRevision = _pointRevision;
    await widget.controller.requestLocation();
    if (!mounted) return;
    if (requestedRevision != _pointRevision) {
      setState(() => _locating = false);
      return;
    }
    final position = widget.controller.position;
    setState(() {
      _locating = false;
      if (position != null) {
        _point = LatLng(position.latitude, position.longitude);
        _pointSource = position.source;
        _accuracy = position.accuracyM;
        _isDemoPoint = position.source == 'demo';
        _locationNote = switch (position.source) {
          'gps' => 'Localização obtida pelo GPS. Confira o ponto abaixo.',
          'demo' =>
            'GPS indisponível. Confira o ponto de exemplo mantido abaixo.',
          _ => 'GPS indisponível. Confira o ponto escolhido anteriormente no mapa.',
        };
      } else {
        _locationNote = 'Não foi possível obter o GPS. Toque no mapa ou escolha um ponto de exemplo.';
      }
    });
    if (_mapReady && _point != null) _mapController.move(_point!, 15);
  }

  void _selectPoint(LatLng point, {bool demo = false}) {
    setState(() {
      _pointRevision++;
      _point = point;
      _pointSource = demo ? 'demo' : 'manual';
      _accuracy = null;
      _isDemoPoint = demo;
      _locationNote = demo
          ? 'Ponto de exemplo escolhido para a apresentação.'
          : 'Ponto escolhido manualmente no mapa.';
    });
    if (demo && _mapReady) _mapController.move(point, 15);
  }

  Future<void> _submit() async {
    if (_point == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Escolha o local da ocorrência antes de salvar.'),
        ),
      );
      return;
    }
    setState(() => _submitting = true);
    final before = widget.controller.reports.map((report) => report.id).toSet();
    await widget.controller.submitReport(
      latitude: _point!.latitude,
      longitude: _point!.longitude,
      type: _type,
      severity: _severity,
      description: _description.text.trim(),
      positionSource: _pointSource,
      accuracyM: _accuracy,
      isDemo: _isDemoPoint || widget.controller.demoMode,
    );
    if (!mounted) return;
    setState(() => _submitting = false);
    final saved = widget.controller.reports.any(
      (report) => !before.contains(report.id),
    );
    if (saved) {
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.controller.message ??
                'Não foi possível salvar. Tente novamente.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Novo relato', style: TextStyle(fontSize: 20)),
    ),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 26),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'O que você viu?',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            const Text(
              'Um relato rápido ajuda a turma a acompanhar as ocorrências da cidade.',
              style: TextStyle(
                fontSize: 13,
                height: 1.5,
                color: Color(0xFF637269),
              ),
            ),
            const SizedBox(height: 22),
            _heading('Tipo de ocorrência'),
            const SizedBox(height: 9),
            Row(
              children: [
                for (final type in ReportType.values)
                  Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(
                        right: type == ReportType.flood ? 8 : 0,
                      ),
                      child: _typeChoice(type),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 21),
            _heading('Qual a gravidade?'),
            const SizedBox(height: 8),
            SegmentedButton<Severity>(
              expandedInsets: EdgeInsets.zero,
              showSelectedIcon: false,
              style: const ButtonStyle(
                padding: WidgetStatePropertyAll(
                  EdgeInsets.symmetric(horizontal: 10),
                ),
                minimumSize: WidgetStatePropertyAll(Size(0, 46)),
              ),
              segments: [
                for (final severity in Severity.values)
                  ButtonSegment(
                    value: severity,
                    label: Text(severity.label),
                    icon: Icon(
                      Icons.circle,
                      size: 9,
                      color: severityColor(severity),
                    ),
                  ),
              ],
              selected: {_severity},
              onSelectionChanged: (selection) =>
                  setState(() => _severity = selection.first),
            ),
            const SizedBox(height: 7),
            Text(switch (_severity) {
              Severity.low => 'Pequeno transtorno, com passagem possível.',
              Severity.medium =>
                'Passagem difícil ou situação que pede atenção.',
              Severity.high =>
                'Passagem bloqueada ou risco importante observado.',
            }, style: const TextStyle(fontSize: 12, color: Color(0xFF637269))),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(child: _heading('Onde aconteceu?')),
                TextButton.icon(
                  onPressed: _locating ? null : _locate,
                  icon: _locating
                      ? const SizedBox(
                          width: 13,
                          height: 13,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.my_location, size: 17),
                  label: Text(_locating ? 'Buscando…' : 'Usar GPS'),
                ),
              ],
            ),
            const Text(
              'Toque no mapa para ajustar o local.',
              style: TextStyle(fontSize: 12, color: Color(0xFF637269)),
            ),
            const SizedBox(height: 9),
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox(
                height: 155,
                child: FlutterMap(
                  mapController: _mapController,
                  options: MapOptions(
                    initialCenter: _point ?? const LatLng(-21.1775, -47.8103),
                    initialZoom: _point == null ? 13 : 15,
                    backgroundColor: const Color(0xFFEAF0E9),
                    onMapReady: () => _mapReady = true,
                    onTap: (_, point) => _selectPoint(point),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate:
                          'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'br.edu.ecopulse',
                    ),
                    MarkerLayer(
                      markers: [
                        if (_point != null)
                          Marker(
                            point: _point!,
                            width: 38,
                            height: 38,
                            child: const Icon(
                              Icons.location_on,
                              color: Color(0xFF237C70),
                              size: 37,
                            ),
                          ),
                      ],
                    ),
                    const Align(
                      alignment: Alignment.bottomLeft,
                      child: ColoredBox(
                        color: Color(0xEEF9FCF9),
                        child: Padding(
                          padding: EdgeInsets.symmetric(
                            horizontal: 5,
                            vertical: 3,
                          ),
                          child: Text(
                            '© OpenStreetMap contributors',
                            style: TextStyle(fontSize: 9),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _point == null
                  ? 'Nenhum local selecionado'
                  : '${_point!.latitude.toStringAsFixed(5)}, ${_point!.longitude.toStringAsFixed(5)}${_accuracy == null ? '' : ' • precisão ~${_accuracy!.round()} m'}',
              style: TextStyle(
                fontSize: 12,
                color: _point == null
                    ? const Color(0xFF9B604A)
                    : const Color(0xFF637269),
              ),
            ),
            if (_locationNote != null)
              Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Text(
                  _locationNote!,
                  style: const TextStyle(
                    fontSize: 12,
                    height: 1.4,
                    color: Color(0xFF637269),
                  ),
                ),
              ),
            const SizedBox(height: 8),
            PopupMenuButton<LatLng>(
              tooltip: 'Escolher local simulado',
              onSelected: (point) => _selectPoint(point, demo: true),
              itemBuilder: (_) => const [
                PopupMenuItem(
                  value: LatLng(-21.1775, -47.8103),
                  child: Text('Exemplo • Centro'),
                ),
                PopupMenuItem(
                  value: LatLng(-21.1882, -47.8065),
                  child: Text('Exemplo • região sul do centro'),
                ),
                PopupMenuItem(
                  value: LatLng(-21.1681, -47.8210),
                  child: Text('Exemplo • região oeste do centro'),
                ),
              ],
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 7),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.science_outlined,
                      size: 17,
                      color: Color(0xFF8B651D),
                    ),
                    SizedBox(width: 7),
                    Flexible(
                      child: Text(
                        'Usar ponto de exemplo',
                        style: TextStyle(
                          fontSize: 13,
                          color: Color(0xFF8B651D),
                        ),
                      ),
                    ),
                    Icon(Icons.expand_more, size: 18, color: Color(0xFF8B651D)),
                  ],
                ),
              ),
            ),
            if (_isDemoPoint || widget.controller.demoMode)
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: InfoStrip(
                  icon: Icons.science_outlined,
                  text: 'Simulação acadêmica. O relato será identificado como exemplo.',
                  color: Color(0xFF8B651D),
                ),
              ),
            const SizedBox(height: 20),
            TextField(
              controller: _description,
              maxLines: 3,
              maxLength: 500,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Quer contar mais? (opcional)',
                hintText: 'Ex.: água na esquina, passagem difícil…',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'Envie apenas o que observou. Os relatos são colaborativos e a área no mapa é aproximada.',
              style: TextStyle(
                fontSize: 12,
                height: 1.5,
                color: Color(0xFF637269),
              ),
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _submitting || _locating ? null : _submit,
                icon: _submitting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check, size: 19),
                label: Text(_submitting ? 'Salvando…' : 'Salvar relato'),
              ),
            ),
            const SizedBox(height: 9),
            const Text(
              'Sem conexão? O relato fica salvo e o app tenta enviar depois.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: Color(0xFF637269)),
            ),
          ],
        ),
      ),
    ),
  );

  Widget _heading(String text) => Text(
    text,
    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
  );

  Widget _typeChoice(ReportType type) {
    final selected = _type == type;
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: selected
          ? colors.primaryContainer.withValues(alpha: .55)
          : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: selected ? colors.primary : const Color(0xFFDAE3DA),
        ),
      ),
      child: InkWell(
        onTap: () => setState(() => _type = type),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 14),
          child: Column(
            children: [
              Icon(
                reportIcon(type),
                color: selected ? colors.primary : const Color(0xFF637269),
              ),
              const SizedBox(height: 6),
              Text(
                type.label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
