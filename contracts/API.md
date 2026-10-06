# Contrato compartilhado EcoPulse

Backend `/v1` e Flutter compartilham estes formatos. Datas ISO 8601 com fuso UTC. Coordenadas nomeadas na API; GeoJSON usa longitude,latitude.

POST `/v1/sessoes`: `{ "installation_id": "uuid" }` -> `{ "access_token": "...", "installation_id": "uuid" }`. Escritas, push e posição usam Authorization Bearer. DEMO também registra sessão, sem exigir login humano. GET de camadas/incidentes/relatos públicos.

POST `/v1/relatos`: `{id:uuid,tipo:"alagamento"|"obstrucao",gravidade:"baixa"|"media"|"alta",latitude:number,longitude:number,descricao:string,occurred_at:ISO,position_source:"gps"|"manual"|"demo",accuracy_m:number|null,is_demo:bool}`. Novo201; reenvio idêntico200; conteúdo conflitante409; inválido422. Response inclui mesmos campos, received_at e region_id. GET `/v1/relatos` retorna array, paginação limit/offset.

GET `/v1/incidentes/ativos?latitude=...&longitude=...&radius_m=...`: GeoJSON FeatureCollection. Feature id=UUID; geometry=Polygon (zona de influência didática); properties={id,tipo,gravidade,estado:"relatado"|"colaborativo",version:int,report_count:int,center_latitude:number,center_longitude:number,radius_m:number,updated_at:ISO,expires_at:ISO,is_demo:bool}. Incidente deriva de eventos, geometria não comprova extensão real de inundação.

GET `/v1/camadas/ambientais?latitude=...&longitude=...`: GeoJSON FeatureCollection de Point/Polygon com properties={id,kind:"aqi"|"calor",value:number,unit:string,scale:string,source:string,updated_at:ISO,expires_at:ISO,version:int,region_id:string,is_demo:bool,label:string}. Versões são inteiros em microssegundos; leitura repetida preserva a versão/validade do mesmo dado. Eventos `camada.atualizada` usam a mesma versão. Redis mantém uma chave por região/tipo/ID e só substitui dados por versão mais recente; banco é a fonte principal.

No demo, AQI permanece fixture identificada e calor usa a imagem real histórica incluída. No full, AQI consulta Open-Meteo/CAMS e calor usa o mesmo conjunto Landsat. `ENVIRONMENT_SOURCE=fixtures` seleciona explicitamente fixtures para ambos. Calor real tem `observation_type:"historic"`, `scene_id`, `surface_temperature_c`, `reference_temperature_c`, centro e raio. `value` é contraste térmico da **superfície**, não temperatura do ar; `updated_at` mantém a aquisição de **17/09/2025**. `expires_at` é prazo de atualização do cache, não atualidade ambiental. Histórico não gera alerta de risco iminente. Dado ausente/inválido retorna 503 e não vira simulação silenciosa.

POST `/v1/rotas`: `{origem:{latitude,longitude},destino:{latitude,longitude},perfil:"driving-car"|"foot-walking"}` -> `{geometry:LineString,distance_m:number,duration_s:number,avoided_incidents:int,source:string,updated_at:ISO}`. Sem chave/provedor/rota responde erro503/422 compreensível, sem ignorar bloqueios nem inventar trajeto seguro.

PUT `/v1/dispositivos/push`: `{token:string,platform:"android"|"ios"|"web",latitude:number|null,longitude:number|null,position_at:ISO|null,radius_m:number}` -> status. POST `/v1/dispositivos/posicao`: `{latitude,longitude,accuracy_m,position_at,radius_m}`. Dispositivo ligado à sessão.

WebSocket `/v1/ws?token=...`: cliente envia `{type:"subscribe",latitude,longitude,radius_m:1000}`; servidor confirma `{type:"subscribed",region_ids:[...]}`. Cliente ping recebe pong. Eventos `{type:"incidente.criado"|"incidente.atualizado"|"incidente.expirado"|"camada.atualizada",id,version}` são avisos para consultar estado atual. Reconectar sempre faz GET. `/health` informa status,mode e configuração (sem segredos).

Full mode depende PostGIS/RabbitMQ/Redis e três processos API/worker/alerts. Demo mode ECOPULSE_MODE=demo permite SQLite/síncrono exclusivamente para validar UI e domínio; não valida cluster/infra distribuída. Use DATABASE_URL, AMQP_URLS (CSV), REDIS_CLUSTER_URLS (CSV), JWT_SECRET, FCM_CREDENTIALS_FILE, ORS_API_KEY, SHARD_COUNT, DATA_DIR e opcional HEAT_DATASET_FILE como contrato de ambiente da infraestrutura. Sem HEAT_DATASET_FILE, o backend carrega o conjunto histórico de backend/datasets/ incluído na imagem.
