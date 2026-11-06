# Interfaces entre UI e lógica mobile

Revisão: **06/11/2026**. Aplicativo **1.0.0+5**, com Alagamentos e Vias.

Os modelos, a persistência, o estado e os serviços ficam em `lib/models`, `lib/data`, `lib/state` e `lib/services`. As telas e os componentes visuais ficam em `lib/screens` e `lib/widgets`; `main.dart` e `app.dart` inicializam o aplicativo.

`models/report.dart`: enum Severity {low,medium,high} com label (Baixa,Média,Alta) e wireValue (baixa,media,alta); enum ReportType {flood,obstruction} com label (Alagamento,Via obstruída) e wireValue (alagamento,obstrucao). Classe Report: id,latitude,longitude,severity,type,description,occurredAt,receivedAt(nullable),isDemo,isPending,positionSource,accuracyM(nullable). Construtor named args; parse/serialize JSON.

`models/incident.dart`: Incident com id,type,severity,centerLatitude,centerLongitude,radiusM,updatedAt,expiresAt,isDemo,reportCount,version,state; polygons como List<List<double>> em ordemlongitude,latitude.

`models/route_result.dart`: RouteResult com coordinates List<List<double>> (lon,lat),distanceM,durationS,avoidedIncidents,source,updatedAt.

`models/position_point.dart`: PositionPoint(latitude,longitude,accuracyM nullable,source='gps').

`state/report_controller.dart`: ReportController extends ChangeNotifier com construtor default utilizável. Getters reports(List<Report>),incidents(List<Incident>),route(RouteResult?),position(PositionPoint?),apiBaseUrl(String),isLoading(bool),isSyncing(bool),serverReachable(bool),demoMode(bool),pendingCount(int),lastUpdatedAt(DateTime?),message(String?),proximityMessage(String?),pushStatus(String),pushReceipt(String?).

Métodos Future<void> initialize(),synchronize(),configureServer(String),requestLocation(),submitReport({required double latitude,required double longitude,required Severity severity,required ReportType type,String description='',String positionSource='manual',double? accuracyM,bool isDemo=false}),calculateRoute({required double destinationLatitude,required double destinationLongitude,String profile='driving-car'}); setManualPosition({required double latitude,required double longitude}),clearMessage(),clearProximityMessage(),clearRoute(),dispose(). Erros operacionais viram message humano; nunca apagar fila em falha/GET vazio. Sincronização automática ao reabrir/reconectar. UI trata initialize no startup e chama listener de mensagens.

O aviso de proximidade usa incidentes ativos cujo centro está a até 1.000 m da posição de referência. O texto distingue a posição GPS do ponto selecionado manualmente. `proximityMessage` é independente de `message`, e `clearProximityMessage()` fecha o aviso. O app desenha o trajeto recebido do backend e apresenta distância, duração, quantidade de zonas evitadas e provedor da rota.

Persistência SQLite Android/iOS; browser preview usa SharedPreferences JSON. ApiURL via --dart-define=API_BASE_URL, configurável no painel e persistido. `FIREBASE_ENABLED` é bool com padrão false: arquivos/credenciais ausentes deixam push pendente com status explícito, sem quebrar startup. Dados demo visivelmente rotulados. Coordenadas aproximadas do centro de Ribeirão para demo: -21.1775,-47.8103; são referência de mapa, não ocorrência real.
