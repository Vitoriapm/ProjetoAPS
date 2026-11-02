import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/incident.dart';
import '../models/report.dart';
import '../state/report_controller.dart';
import '../widgets/connection_sheet.dart';
import '../widgets/report_style.dart';
import 'report_screen.dart';

const ribeiraoCenter = LatLng(-21.1775, -47.8103);

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.controller});
  final ReportController controller;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final MapController _mapController = MapController();
  final Set<String> _layers = {'alagamento', 'obstrucao'};
  bool _showList = false;
  bool _mapUnavailable = false;
  bool _mapErrorScheduled = false;

  ReportController get controller => widget.controller;

  bool get _hasDemo =>
      controller.demoMode ||
      controller.reports.any((report) => report.isDemo) ||
      controller.incidents.any((incident) => incident.isDemo);

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  void _record([LatLng? point]) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            ReportScreen(controller: controller, initialPoint: point),
      ),
    );
  }

  void _tileFailed() {
    if (_mapUnavailable || _mapErrorScheduled) return;
    _mapErrorScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _mapErrorScheduled = false;
      if (mounted) setState(() => _mapUnavailable = true);
    });
  }

  Future<void> _locate() async {
    await controller.requestLocation();
    if (!mounted || _showList || controller.position == null) return;
    final point = controller.position!;
    _mapController.move(LatLng(point.latitude, point.longitude), 15);
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) {
      final count = controller.incidents.length;
      return Scaffold(
        appBar: AppBar(
          titleSpacing: 18,
          title: Row(
            children: [
              const Icon(
                Icons.eco_outlined,
                color: Color(0xFF237C70),
                size: 29,
              ),
              const SizedBox(width: 9),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'EcoPulse',
                    style: TextStyle(fontSize: 21, fontWeight: FontWeight.w600),
                  ),
                  Text(
                    'Ribeirão Preto',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
          actions: [
            IconButton(
              onPressed: _settings,
              icon: const Icon(Icons.tune),
              tooltip: 'Conexão e informações',
            ),
            const SizedBox(width: 6),
          ],
        ),
        body: SafeArea(
          top: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: _connectionStatus(),
              ),
              if (_hasDemo)
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: InfoStrip(
                    icon: Icons.science_outlined,
                    text: 'Simulação acadêmica • exemplos para a apresentação',
                    color: Color(0xFF8B651D),
                  ),
                ),
              if (controller.proximityMessage != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: InfoStrip(
                    icon: Icons.warning_amber_rounded,
                    color: const Color(0xFFAC6B15),
                    text: controller.proximityMessage!,
                    trailing: IconButton(
                      onPressed: controller.clearProximityMessage,
                      constraints: const BoxConstraints(
                        minWidth: 28,
                        minHeight: 28,
                      ),
                      padding: EdgeInsets.zero,
                      icon: const Icon(Icons.close, size: 16),
                      tooltip: 'Fechar aviso de proximidade',
                    ),
                  ),
                ),
              if (controller.message != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: InfoStrip(
                    icon: Icons.info_outline,
                    text: controller.message!,
                    trailing: IconButton(
                      onPressed: controller.clearMessage,
                      constraints: const BoxConstraints(
                        minWidth: 28,
                        minHeight: 28,
                      ),
                      padding: EdgeInsets.zero,
                      icon: const Icon(Icons.close, size: 16),
                      tooltip: 'Fechar aviso',
                    ),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 13, 16, 5),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'O que acontece na cidade',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    SegmentedButton<bool>(
                      showSelectedIcon: false,
                      style: const ButtonStyle(
                        visualDensity: VisualDensity.compact,
                      ),
                      segments: const [
                        ButtonSegment(
                          value: false,
                          label: Text('Mapa'),
                          icon: Icon(Icons.map_outlined, size: 16),
                        ),
                        ButtonSegment(
                          value: true,
                          label: Text('Lista'),
                          icon: Icon(Icons.format_list_bulleted, size: 16),
                        ),
                      ],
                      selected: {_showList},
                      onSelectionChanged: (value) =>
                          setState(() => _showList = value.first),
                    ),
                  ],
                ),
              ),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    _layerChip(
                      'alagamento',
                      'Alagamento',
                      Icons.water_drop_outlined,
                    ),
                    _layerChip('obstrucao', 'Vias', Icons.block_outlined),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Expanded(child: _showList ? _list() : _map()),
              if (controller.route != null) _routeSummary(),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 9),
                child: Row(
                  children: [
                    Icon(
                      Icons.groups_outlined,
                      size: 17,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        count == 0
                            ? 'Nenhuma ocorrência processada por aqui.'
                            : '$count ${count == 1 ? 'ocorrência compartilhada' : 'ocorrências compartilhadas'}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    TextButton(
                      onPressed: _legend,
                      child: const Text('Legenda'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        floatingActionButton: Padding(
          padding: EdgeInsets.only(bottom: controller.route == null ? 51 : 114),
          child: FloatingActionButton.extended(
            onPressed: _record,
            icon: const Icon(Icons.add_location_alt_outlined),
            label: const Text('Relatar'),
          ),
        ),
      );
    },
  );

  Widget _connectionStatus() {
    final pending = controller.pendingCount;
    final busy = controller.isSyncing || controller.isLoading;
    final reachable = controller.serverReachable;
    final status = busy
        ? 'Atualizando os relatos…'
        : reachable
        ? pending > 0
              ? '$pending ${pending == 1 ? 'relato aguardando envio' : 'relatos aguardando envio'}'
              : 'Relatos atualizados'
        : pending > 0
        ? 'Sem conexão • $pending ${pending == 1 ? 'relato salvo no aparelho' : 'relatos salvos no aparelho'}'
        : 'Sem conexão • você ainda pode relatar';
    return Row(
      children: [
        if (busy)
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        else
          Icon(
            reachable ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
            size: 17,
            color: reachable
                ? const Color(0xFF237C70)
                : const Color(0xFF826B47),
          ),
        const SizedBox(width: 7),
        Expanded(child: Text(status, style: const TextStyle(fontSize: 12))),
        IconButton(
          tooltip: 'Atualizar e enviar pendências',
          onPressed: busy ? null : controller.synchronize,
          visualDensity: VisualDensity.compact,
          icon: const Icon(Icons.refresh, size: 21),
        ),
      ],
    );
  }

  Widget _layerChip(String id, String label, IconData icon) => Padding(
    padding: const EdgeInsets.only(right: 7),
    child: FilterChip(
      avatar: Icon(icon, size: 16),
      label: Text(label),
      selected: _layers.contains(id),
      showCheckmark: false,
      visualDensity: VisualDensity.compact,
      onSelected: (enabled) =>
          setState(() => enabled ? _layers.add(id) : _layers.remove(id)),
    ),
  );

  Widget _map() {
    final incidents = controller.incidents
        .where((i) => _layers.contains(i.type.wireValue))
        .toList();
    final reports = controller.reports
        .where((r) => _layers.contains(r.type.wireValue))
        .toList();
    return Stack(
      children: [
        FlutterMap(
          mapController: _mapController,
          options: MapOptions(
            initialCenter: ribeiraoCenter,
            initialZoom: 13,
            minZoom: 3,
            maxZoom: 18,
            backgroundColor: const Color(0xFFEAF0E9),
            onTap: (_, point) => _pointActions(point),
            onLongPress: (_, point) => _pointActions(point),
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'br.edu.ecopulse',
              errorTileCallback: (_, _, _) => _tileFailed(),
            ),
            PolygonLayer(
              polygons: [
                for (final incident in incidents)
                  if (incident.polygons.length >= 3)
                    Polygon(
                      points: incident.polygons
                          .map((p) => LatLng(p[1], p[0]))
                          .toList(),
                      color: severityColor(incident.severity)
                          .withValues(alpha: .20),
                      borderColor: severityColor(incident.severity),
                      borderStrokeWidth: 1.5,
                    ),
              ],
            ),
            CircleLayer(
              circles: [
                for (final incident in incidents)
                  if (incident.polygons.isEmpty)
                    CircleMarker(
                      point: LatLng(
                        incident.centerLatitude,
                        incident.centerLongitude,
                      ),
                      radius: incident.radiusM,
                      useRadiusInMeter: true,
                      color: severityColor(incident.severity)
                          .withValues(alpha: .2),
                      borderColor: severityColor(incident.severity),
                      borderStrokeWidth: 1,
                    ),
              ],
            ),
            if (controller.route != null)
              PolylineLayer(
                polylines: [
                  Polyline(
                    points: controller.route!.coordinates
                        .map((p) => LatLng(p[1], p[0]))
                        .toList(),
                    color: const Color(0xFF3068A9),
                    strokeWidth: 5,
                  ),
                ],
              ),
            MarkerLayer(
              markers: [
                for (final incident in incidents)
                  Marker(
                    point: LatLng(
                      incident.centerLatitude,
                      incident.centerLongitude,
                    ),
                    width: 44,
                    height: 44,
                    child: _marker(
                      reportIcon(incident.type),
                      severityColor(incident.severity),
                      '${incident.type.label}, gravidade ${incident.severity.label}',
                      () => _incidentDetails(incident),
                    ),
                  ),
                for (final report in reports)
                  Marker(
                    point: LatLng(report.latitude, report.longitude),
                    width: 34,
                    height: 34,
                    child: _marker(
                      report.isPending
                          ? Icons.schedule
                          : reportIcon(report.type),
                      report.isPending
                          ? const Color(0xFF7C7566)
                          : severityColor(report.severity),
                      '${report.type.label}${report.isPending ? ', aguardando envio' : ''}',
                      () => _reportDetails(report),
                      small: true,
                    ),
                  ),
                if (controller.position != null)
                  Marker(
                    point: LatLng(
                      controller.position!.latitude,
                      controller.position!.longitude,
                    ),
                    width: 26,
                    height: 26,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF346EC1),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 3),
                      ),
                      child: Tooltip(
                        message: controller.position!.source == 'gps'
                            ? 'Sua localização pelo GPS'
                            : 'Ponto de partida escolhido',
                        child: const SizedBox.expand(),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
        Positioned(
          top: 12,
          right: 12,
          child: Column(
            children: [
              _mapButton(
                Icons.my_location,
                'Buscar minha localização',
                _locate,
              ),
              const SizedBox(height: 8),
              _mapButton(
                Icons.home_outlined,
                'Voltar para Ribeirão Preto',
                () => _mapController.move(ribeiraoCenter, 13),
              ),
            ],
          ),
        ),
        if (_mapUnavailable)
          const Positioned(
            top: 12,
            left: 12,
            right: 70,
            child: InfoStrip(
              icon: Icons.wifi_off,
              text: 'Mapa de ruas indisponível. Use a lista ou os pontos de exemplo no formulário.',
              color: Color(0xFF826B47),
            ),
          ),
        if (!_mapUnavailable)
          Positioned(
            left: 12,
            bottom: 68,
            child: Container(
              constraints: const BoxConstraints(maxWidth: 205),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: .94),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Toque no mapa para relatar\nou escolher um destino.',
                style: TextStyle(fontSize: 11),
              ),
            ),
          ),
        const Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          child: ColoredBox(
            color: Color(0xEEF9FCF9),
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              child: Text(
                '© OpenStreetMap contributors',
                textAlign: TextAlign.left,
                style: TextStyle(fontSize: 10, color: Color(0xFF3F5049)),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _mapButton(IconData icon, String tooltip, VoidCallback action) =>
      Material(
        color: Colors.white,
        elevation: 1,
        borderRadius: BorderRadius.circular(12),
        child: IconButton(
          onPressed: action,
          icon: Icon(icon, size: 22),
          tooltip: tooltip,
        ),
      );

  Widget _marker(
    IconData icon,
    Color color,
    String label,
    VoidCallback action, {
    bool small = false,
  }) => Semantics(
    label: label,
    button: true,
    child: GestureDetector(
      onTap: action,
      child: Container(
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
          boxShadow: const [
            BoxShadow(
              color: Color(0x22000000),
              blurRadius: 3,
              offset: Offset(0, 1),
            ),
          ],
        ),
        child: Icon(icon, color: Colors.white, size: small ? 16 : 22),
      ),
    ),
  );

  Widget _list() {
    final incidents = controller.incidents.where(
      (i) => _layers.contains(i.type.wireValue),
    );
    final reports = controller.reports.where(
      (r) => _layers.contains(r.type.wireValue),
    );
    return RefreshIndicator(
      onRefresh: controller.synchronize,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
        children: [
          if (incidents.isEmpty && reports.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 46, horizontal: 20),
              child: Column(
                children: [
                  Icon(
                    Icons.park_outlined,
                    size: 42,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Ainda não há relatos por aqui.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Viu uma ocorrência? Toque em Relatar.\nSe estiver sem conexão, ela fica salva no aparelho.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 13),
                  ),
                ],
              ),
            ),
          if (incidents.isNotEmpty) _listHeading('Ocorrências compartilhadas'),
          for (final incident in incidents)
            _listTile(
              icon: reportIcon(incident.type),
              color: severityColor(incident.severity),
              title: incident.type.label,
              subtitle:
                  '${incident.severity.label} • ${incident.reportCount} ${incident.reportCount == 1 ? 'relato' : 'relatos'}\n${shortDate(incident.updatedAt)}${incident.isDemo ? ' • exemplo' : ''}',
              onTap: () => _incidentDetails(incident),
            ),
          if (reports.isNotEmpty) _listHeading('Relatos recebidos e pendentes'),
          for (final report in reports)
            _listTile(
              icon: report.isPending ? Icons.schedule : reportIcon(report.type),
              color: severityColor(report.severity),
              title: report.type.label,
              subtitle:
                  '${report.isPending ? 'Salvo • aguardando envio' : report.severity.label}\n${shortDate(report.occurredAt)}${report.isDemo ? ' • exemplo' : ''}',
              onTap: () => _reportDetails(report),
            ),
        ],
      ),
    );
  }

  Widget _listHeading(String value) => Padding(
    padding: const EdgeInsets.fromLTRB(2, 12, 0, 7),
    child: Text(
      value,
      style: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: Color(0xFF5A6960),
      ),
    ),
  );

  Widget _listTile({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) => Card(
    elevation: 0,
    color: Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: const BorderSide(color: Color(0xFFE3EAE3)),
    ),
    margin: const EdgeInsets.only(bottom: 8),
    child: ListTile(
      leading: CircleAvatar(
        backgroundColor: color.withValues(alpha: .1),
        foregroundColor: color,
        child: Icon(icon, size: 21),
      ),
      title: Text(
        title,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(fontSize: 12, height: 1.5),
      ),
      trailing: const Icon(Icons.chevron_right, size: 20),
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
    ),
  );

  Widget _routeSummary() {
    final route = controller.route!;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFEAF0F8),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.route, color: Color(0xFF3068A9)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${(route.distanceM / 1000).toStringAsFixed(1)} km • ${(route.durationS / 60).ceil()} min\n${route.avoidedIncidents} zonas evitadas • ${route.source}',
              style: const TextStyle(fontSize: 12),
            ),
          ),
          IconButton(
            onPressed: controller.clearRoute,
            icon: const Icon(Icons.close, size: 19),
            tooltip: 'Limpar rota',
          ),
        ],
      ),
    );
  }

  Future<void> _pointActions(LatLng point) async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Este ponto no mapa',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 5),
              Text(
                '${point.latitude.toStringAsFixed(5)}, ${point.longitude.toStringAsFixed(5)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 12),
              ListTile(
                leading: const Icon(Icons.add_location_alt_outlined),
                title: const Text('Relatar uma ocorrência aqui'),
                onTap: () => Navigator.pop(context, 'report'),
              ),
              ListTile(
                leading: const Icon(Icons.trip_origin),
                title: const Text('Usar como ponto de partida'),
                subtitle: const Text('Localização escolhida manualmente'),
                onTap: () => Navigator.pop(context, 'origin'),
              ),
              ListTile(
                leading: const Icon(Icons.directions_walk),
                title: const Text('Calcular rota a pé até aqui'),
                onTap: () => Navigator.pop(context, 'foot-walking'),
              ),
              ListTile(
                leading: const Icon(Icons.directions_car_outlined),
                title: const Text('Calcular rota de carro até aqui'),
                onTap: () => Navigator.pop(context, 'driving-car'),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Text(
                  'As rotas consideram as zonas informadas. Isso não garante a segurança do trajeto.',
                  style: TextStyle(fontSize: 12, color: Color(0xFF647269)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (!mounted || choice == null) return;
    if (choice == 'report') {
      _record(point);
      return;
    }
    if (choice == 'origin') {
      controller.setManualPosition(
        latitude: point.latitude,
        longitude: point.longitude,
      );
      return;
    }
    if (controller.position == null) await controller.requestLocation();
    if (!mounted) return;
    await controller.calculateRoute(
      destinationLatitude: point.latitude,
      destinationLongitude: point.longitude,
      profile: choice,
    );
  }

  void _reportDetails(Report report) => _detailSheet(report.type.label, [
    _detailRow('Gravidade', report.severity.label),
    _detailRow('Registrado em', shortDate(report.occurredAt)),
    _detailRow(
      'Localização',
      '${report.latitude.toStringAsFixed(5)}, ${report.longitude.toStringAsFixed(5)}',
    ),
    _detailRow(
      'Origem do ponto',
      report.positionSource == 'gps'
          ? 'GPS${report.accuracyM == null ? '' : ' • precisão aproximada ${report.accuracyM!.round()} m'}'
          : report.positionSource == 'demo'
          ? 'Ponto de exemplo'
          : 'Selecionado no mapa',
    ),
    _detailRow(
      'Envio',
      report.isPending
          ? 'Salvo no aparelho, aguardando conexão'
          : 'Recebido pelo servidor',
    ),
    if (report.description.isNotEmpty)
      _detailRow('Descrição', report.description),
    if (report.isDemo)
      const InfoStrip(
        icon: Icons.science_outlined,
        text: 'Este relato é um exemplo para a apresentação.',
        color: Color(0xFF8B651D),
      ),
  ]);

  void _incidentDetails(Incident incident) =>
      _detailSheet(incident.type.label, [
        _detailRow('Gravidade', incident.severity.label),
        _detailRow('Relatos agrupados', '${incident.reportCount}'),
        _detailRow('Atualização', shortDate(incident.updatedAt)),
        _detailRow('Validade do aviso', shortDate(incident.expiresAt)),
        _detailRow(
          'Origem',
          'Relatos colaborativos • versão ${incident.version}',
        ),
        const InfoStrip(
          icon: Icons.info_outline,
          text: 'A área desenhada é uma zona de influência do relato; não representa a extensão medida de um alagamento.',
        ),
        if (incident.isDemo)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: InfoStrip(
              icon: Icons.science_outlined,
              text: 'Ocorrência simulada para a apresentação.',
              color: Color(0xFF8B651D),
            ),
          ),
      ]);

  Widget _detailRow(String label, String value) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: Color(0xFF657167)),
        ),
        const SizedBox(height: 3),
        SelectableText(value, style: const TextStyle(fontSize: 14)),
      ],
    ),
  );

  void _detailSheet(String title, List<Widget> content) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (context) => SafeArea(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(context).height * .78,
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 22),
                  ...content,
                ],
              ),
            ),
          ),
        ),
      );

  void _legend() => _detailSheet('Como ler o mapa', [
    const Text(
      'Cores das ocorrências',
      style: TextStyle(fontWeight: FontWeight.w600),
    ),
    const SizedBox(height: 8),
    Wrap(
      spacing: 12,
      runSpacing: 8,
      children: [
        for (final severity in Severity.values)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.circle, size: 12, color: severityColor(severity)),
              const SizedBox(width: 5),
              Text(severity.label),
            ],
          ),
      ],
    ),
    const SizedBox(height: 18),
    const Text(
      'Gota: alagamento • círculo cortado: via obstruída.\nRelógio: relato salvo, ainda sem envio.\nPonto azul: localização GPS ou origem escolhida.',
      style: TextStyle(fontSize: 13, height: 1.7),
    ),
    const SizedBox(height: 16),
    const InfoStrip(
      icon: Icons.info_outline,
      text: 'As zonas de influência são aproximadas. Relatos são colaborativos e não substituem avisos oficiais.',
    ),
    const SizedBox(height: 18),
    const Text(
      'Mapa de ruas: © OpenStreetMap contributors',
      style: TextStyle(fontSize: 12),
    ),
    const SelectableText(
      'https://www.openstreetmap.org/copyright',
      style: TextStyle(fontSize: 12),
    ),
  ]);

  Future<void> _settings() async {
    final chosen = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => ConnectionSheet(controller: controller),
    );
    if (chosen != null && chosen.isNotEmpty && mounted) {
      await controller.configureServer(chosen);
    }
  }
}
