# Backend do EcoPulse

Três processos Python compartilham o contrato em contracts/API.md: API FastAPI, worker de risco e worker de alertas. A API grava relato e outbox em uma transação PostgreSQL. O worker publica a outbox somente após confirmação do RabbitMQ, processa por GeoHash e registra idempotência antes do ack. O serviço de alertas atualiza o Redis Cluster, distribui avisos WebSocket entre APIs e seleciona instalações por posição válida para FCM/APNs.

## Execução local para desenvolver a interface

Na raiz do projeto, em PowerShell:

```powershell
python -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install --no-cache-dir -r backend/requirements.txt
$env:ECOPULSE_MODE = 'demo'
./backend/.venv/Scripts/python.exe -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

O modo demo usa backend/data/ecopulse-demo.db, processa o risco sincronamente e distribui WebSocket na mesma API. `/health` identifica permanentemente esse modo. Ele permite testar a interface, persistência e regras; não comprova PostGIS, broker, Redis, cluster ou FCM. DATABASE_URL pode apontar para outro arquivo SQLite somente em demo. Não inicie os workers separados nesse modo.

Em outro terminal:

```powershell
./backend/.venv/Scripts/python.exe scripts/seed_demo.py --url http://localhost:8000
./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

O seed insere quatro relatos identificados por is_demo=true, usando três instalações distintas perto do mesmo ponto e uma obstrução. IDs e horário são estáveis para a mesma rodada `--batch AAAAMMDDHHMM` UTC. Uma nova rodada cria relatos novos, sem esconder nem alterar os antigos.

## Execução dos serviços reais

O Compose em infra/ fornece os componentes. Os entrypoints são:

- API: `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
- Risco/outbox: `python -m backend.worker.main`.
- Alertas: `python -m backend.alerts.main`.

O Dockerfile em backend/ usa contexto da raiz. `ECOPULSE_MODE=full` é o padrão e exige DATABASE_URL PostgreSQL com driver psycopg e JWT_SECRET com ao menos 32 caracteres. Não há troca silenciosa para SQLite se a infraestrutura falhar. PostGIS/tabelas/índices são criados durante a inicialização, protegidos por advisory lock para duas APIs; backend/migrations/001_schema.sql também permite preparar o schema manualmente. O usuário de banco da demonstração precisa poder criar a extensão PostGIS.

Variáveis: DATABASE_URL (`postgresql+psycopg://...`), AMQP_URLS e REDIS_CLUSTER_URLS em CSV, JWT_SECRET, SHARD_COUNT (2–32), RABBIT_QUORUM_SIZE (1 em desenvolvimento/3 no cluster), FCM_CREDENTIALS_FILE, ORS_API_KEY, ENVIRONMENT_SOURCE, HEAT_DATASET_FILE e DATA_DIR. Não guardar credenciais no repositório. HEAT_DATASET_FILE é opcional: o padrão é `backend/datasets/heat-ribeirao-preto.geojson`, incluído na imagem. Ao substituir no Docker, informar um caminho acessível dentro do contêiner e preparar o arquivo com sua proveniência.

O processo de risco opera filas `ecopulse.risk.0` até SHARD_COUNT-1; todos os workers competem em todas as filas. GeoHash decide a partição estável do evento; a falha de um consumidor devolve mensagens não confirmadas aos demais. A consulta espacial usa o raio completo, incluindo vizinhos; o processamento usa trava global curta para evitar criação concorrente de incidentes cruzando partições. É particionamento de eventos, não fragmentação física do PostgreSQL.

Filas de processamento, retry e DLQ são quorum e duráveis. Mensagens são persistentes e a republicação para retry/DLQ é confirmada antes de reconhecer a original. Retry usa espera 1, 5 e 15 segundos; depois vai à DLQ. As filas `.retry` precisam da política RabbitMQ `dead-letter-strategy=at-least-once` e `overflow=reject-publish`, configurada na infraestrutura, para a transferência após TTL. A outbox pode publicar novamente após falha entre confirmação do broker e commit: consumidores deduplicam por event_id e vínculos de relato. Não há promessa de exatamente uma entrega de push: um crash após FCM aceitar e antes da gravação pode reenviar; event_id/version permitem supressão no cliente.

As chaves Redis de incidentes incluem GeoHash, ID e versão no valor. Lua faz a comparação atômica de versões para impedir regressão. Dados ativos expiram conforme expires_at; tombstones de expiração são metadados de controle por uma hora. A API seleciona os incidentes espaciais no PostgreSQL, usa o cache quando a versão coincide e mantém o estado do banco diante de cache atrasado/indisponível. Reconstrói o cache ao conectar ao Redis. Pub/Sub distribui avisos entre instâncias; reconectar WebSocket exige consultar REST novamente. `/health` mostra degradação por componente e o acumulado da outbox, sem segredos. O broker indisponível não impede a gravação PostgreSQL de novos relatos.

As camadas de AQI e calor também têm cache Redis. A observação e o evento `camada.atualizada` são gravados na mesma transação; o serviço de alertas consome o evento pela mensageria, atualiza o cache e publica no canal WebSocket. As chaves `ecopulse:environment:{região}:tipo:id` mantêm a versão, a feature e o TTL restante de `expires_at`. A comparação Lua rejeita eventos antigos. PostgreSQL continua sendo a referência: a API usa Redis apenas quando ID, versão e validade coincidem; ausência, atraso, corrupção ou indisponibilidade preservam a resposta durável. A reconstrução relê observações válidas do banco, sem chamar os provedores externos. Consultas repetidas da mesma observação válida preservam a versão e não renovam o prazo indefinidamente.

## Fontes, rotas e alertas

AQI real consulta Open-Meteo Air Quality com domínio CAMS Global e escala US AQI. É previsão modelada (~45 km), não estação local; cada feature carrega origem, horário, validade, atribuição e rótulo. Resultados são guardados por região por até 15 minutos. Falha do provedor retorna 503 e não vira dado fictício. Com a configuração padrão, `full` combina AQI modelado real e calor histórico Landsat; `demo` combina AQI simulado identificado e o mesmo calor histórico real. `ENVIRONMENT_SOURCE=fixtures` permite ensaio explícito com ambas as camadas simuladas.

A camada de calor lê 32 polígonos reais derivados da cena Landsat 9 de **17/09/2025**, com máscara de qualidade, contraste em relação à vegetação, checksum e origem verificáveis. O rótulo **Histórico — 17/09/2025** e `observation_type=historic` permanecem nos dados; `updated_at` é a aquisição e a validade de 24 horas indica somente quando reler o arquivo para o cache. Trata-se de temperatura da superfície e contraste espacial, sem medição atual do ar, climatologia ou alerta de risco iminente. Arquivo ausente/inválido gera erro explícito. Fonte, método e limites estão em [CALOR.md](CALOR.md).

O roteamento une os polígonos de incidentes ativos e envia o resultado em `options.avoid_polygons` no POST GeoJSON do OpenRouteService. Rejeita origem/destino dentro de bloqueio, geometria inválida, resposta que intersecta bloqueios, extremos incompatíveis, resumo inválido ou ausência de alternativa. Limita o encaixe em ruas a 200 m, verifica os segmentos de acesso e consulta novamente os incidentes antes de responder. Não remove exclusões para obter rota. Sem ORS_API_KEY retorna 503 claro; não inventa uma rota de demonstração. Limite didático de 50 km, com carro ou caminhada. As zonas circulares são influência definida por engenharia; não são extensão medida de inundação nem certificação de segurança. Configuração e prova real em [ROTAS.md](ROTAS.md).

Push registra token e plataforma associados à sessão JWT de instalação. O despacho seleciona posição com no máximo uma hora, raio configurado mais a influência do incidente. Tokens FCM não aparecem em eventos públicos. Firebase Admin usa credenciais em arquivo externo e define TTL limitado à validade e a 30 minutos; tag Android e agrupamento APNs usam o ID do incidente. Token não registrado é removido sem apagar uma renovação concorrente. Aceitação pelo FCM é registrada como accepted, sem afirmar recebimento no aparelho. Firebase/APNs, Android/iOS físicos e permissões ainda exigem validação real. Não configurar FCM faz as entregas elegíveis falharem e seguirem retry/DLQ, em vez de simular sucesso. O cliente verifica permissão, espera APNs no iOS, serializa registro/renovação e atualiza o app ao receber ou abrir avisos. [PUSH.md](PUSH.md) reúne preparo, diagnóstico e teste de envio.

JWT identifica uma instalação anônima com UUID informado pelo app, sem senha. Não representa autenticação de uma pessoa nem evita fraude por criação de instalações. O protótipo deve ser usado em rede controlada/HTTPS conforme o cenário acadêmico. Logs de acesso ficam desativados para evitar expor JWT presente no query string WebSocket. Endpoints de escrita e WebSocket exigem token; leitura pública contém somente dados de relatos/incidentes.

## Evidências e limites

Testes em backend/tests verificam commit/reenvio após resposta perdida, reinício, conflito, replay de evento, fronteira GeoHash, três instalações, expiração, relatos offline antigos, JWT, WebSocket bidirecional, retry/DLQ antes de ack, seleção de posição para push e adaptadores de rotas/AQI com transporte HTTP mock. Testes de mock validam contrato e regras, sem comprovar os provedores reais.

Docker Desktop foi localizado e o cluster real executou em 03/10/2026 os testes documentados em [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md): fluxo por PostGIS/RabbitMQ/Redis, duas APIs e workers, replicação, falhas controladas e promoção planejada do PostgreSQL. A atualização de 04/10/2026 acrescentou calor histórico real, cache ambiental e as verificações de push/rotas descritas em [VALIDACAO_INTEGRACOES.md](VALIDACAO_INTEGRACOES.md). A prova real do cache em [environment-cache.json](evidence/environment-cache.json) passou com 33 camadas persistidas/publicadas/consumidas, versões e TTL Redis corretos, duas APIs/WebSockets, rejeição de evento antigo, reparação/reconstrução e interrupção dos seis nós Redis com leitura durável HTTP 200. Resultados e contagem final da suíte ficam em [VALIDACAO.md](VALIDACAO.md). A execução está limitada a um único host e a uma carga pequena. O cliente Android já tem configuração Firebase válida e APK com Firebase ativado compilado em 04/10 às 15:58. A conta de serviço foi autenticada no Google e carregada na API demo, mantendo os 18 IDs de relatos existentes. A chave ORS foi configurada; consultas reais pelo adaptador com um bloqueio fictício e pela API com zero bloqueios ativos passaram (3.035,2 m / 432,8 s). A API foi reiniciada com acesso externo ao provedor, preservando os 18 IDs. O usuário confirmou a rota aparecendo no celular, conforme [routes-phone-confirmation.json](evidence/routes-phone-confirmation.json). Depois, o usuário confirmou GPS, offline, reabertura e reenvio no Android. O banco passou de 18 para 19 relatos, com um único novo UUID de obstrução simulada ligado a uma ocorrência de um relato, sem duplicação. Essa checagem está em [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json); não houve observação independente da tela nem exposição de coordenadas. Permanecem pendentes ensaio geográfico de push e iOS/APNs. Um Android está registrado, e uma validação FCM real em dry-run foi aceita sem entrega. Depois, um único envio fictício ao mesmo celular preparado em segundo plano foi aceito; o usuário confirmou a chegada em segundo plano e a abertura do app ao tocar. A evidência humana do teste direto está em [fcm-phone-receipt.json](evidence/fcm-phone-receipt.json), sem provar a seleção geográfica. O serviço geográfico do modo full não foi iniciado nesta etapa. Apple Developer, Mac e iPhone também permanecem pendentes; compilação Android não comprova entrega.

Fontes técnicas: [quorum/dead lettering RabbitMQ](https://www.rabbitmq.com/docs/quorum-queues), [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), [opções OpenRouteService](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options).
