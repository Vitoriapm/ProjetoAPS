# Interfaces entre UI e lógica mobile

Agente core é dono de lib/models, lib/data, lib/state, lib/services e testes correspondentes. UI é dona de main.dart, app.dart, lib/screens e lib/widgets. Root é dono de pubspec/plataformas/infra/documentação. Não editar pastas de outro agente sem coordenação.

`models/report.dart`: enum Severity {low,medium,high} com label (Baixa,Média,Alta) e wireValue (baixa,media,alta); enum ReportType {flood,obstruction} com label (Alagamento,Via obstruída) e wireValue (alagamento,obstrucao). Classe Report: id,latitude,longitude,severity,type,description,occurredAt,receivedAt(nullable),isDemo,isPending,positionSource,accuracyM(nullable). Construtor named args; parse/serialize JSON.

`models/incident.dart`: Incident com id,type,severity,centerLatitude,centerLongitude,radiusM,updatedAt,expiresAt,isDemo,reportCount,version,state; polygons como List<List<double>> em ordemlongitude,latitude.

`models/environmental_point.dart`: EnvironmentalPoint com id,kind,value,unit,scale,source,updatedAt,isDemo,label,latitude,longitude,polygon(List<List<double>> nullable).

`models/route_result.dart`: RouteResult com coordinates List<List<double>> (lon,lat),distanceM,durationS,avoidedIncidents,source,updatedAt.

`models/position_point.dart`: PositionPoint(latitude,longitude,accuracyM nullable,source='gps').

`state/report_controller.dart`: ReportController extends ChangeNotifier com construtor default utilizável. Getters reports(List<Report>),incidents(List<Incident>),environment(List<EnvironmentalPoint>),route(RouteResult?),position(PositionPoint?),apiBaseUrl(String),isLoading(bool),isSyncing(bool),serverReachable(bool),demoMode(bool),pendingCount(int),lastUpdatedAt(DateTime?),message(String?),pushStatus(String).

Métodos Future<void> initialize(),synchronize(),configureServer(String),requestLocation(),submitReport({required double latitude,required double longitude,required Severity severity,required ReportType type,String description='',String positionSource='manual',double? accuracyM,bool isDemo=false}),calculateRoute({required double destinationLatitude,required double destinationLongitude,String profile='driving-car'}); clearMessage(),clearRoute(),dispose(). Erros operacionais viram message humano; nunca apagar fila em falha/GET vazio. Sincronização automática ao reabrir/reconectar. UI trata initialize no startup e chama listener de mensagens.

Persistência SQLite Android/iOS; browser preview usa SharedPreferences JSON (documentar diferença). ApiURL via --dart-define=API_BASE_URL, configurável no painel e persistido. Firebase_ENABLED bool padrão false: arquivos/credenciais ausentes deixam push pendente com status explícito, sem quebrar startup. Dados demo visivelmente rotulados. Coordenadas aproximadas do centro de Ribeirão para demo: -21.1775,-47.8103; são referência de mapa, não ocorrência real.
