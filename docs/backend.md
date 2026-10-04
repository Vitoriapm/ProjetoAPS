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

Variáveis: DATABASE_URL (`postgresql+psycopg://...`), AMQP_URLS e REDIS_CLUSTER_URLS em CSV, JWT_SECRET, SHARD_COUNT (2–32), RABBIT_QUORUM_SIZE (1 em desenvolvimento/3 no cluster), FCM_CREDENTIALS_FILE, ORS_API_KEY e DATA_DIR. Não guardar credenciais no repositório.

O processo de risco opera filas `ecopulse.risk.0` até SHARD_COUNT-1; todos os workers competem em todas as filas. GeoHash decide a partição estável do evento; a falha de um consumidor devolve mensagens não confirmadas aos demais. A consulta espacial usa o raio completo, incluindo vizinhos; o processamento usa trava global curta para evitar criação concorrente de incidentes cruzando partições. É particionamento de eventos, não fragmentação física do PostgreSQL.

Filas de processamento, retry e DLQ são quorum e duráveis. Mensagens são persistentes e a republicação para retry/DLQ é confirmada antes de reconhecer a original. Retry usa espera 1, 5 e 15 segundos; depois vai à DLQ. As filas `.retry` precisam da política RabbitMQ `dead-letter-strategy=at-least-once` e `overflow=reject-publish`, configurada na infraestrutura, para a transferência após TTL. A outbox pode publicar novamente após falha entre confirmação do broker e commit: consumidores deduplicam por event_id e vínculos de relato. Não há promessa de exatamente uma entrega de push: um crash após FCM aceitar e antes da gravação pode reenviar; event_id/version permitem supressão no cliente.

As chaves Redis de incidentes incluem GeoHash, ID e versão no valor. Lua faz a comparação atômica de versões para impedir regressão. Dados ativos expiram conforme expires_at; tombstones de expiração são metadados de controle por uma hora. A API seleciona os incidentes espaciais no PostgreSQL, usa o cache quando a versão coincide e mantém o estado do banco diante de cache atrasado/indisponível. Reconstrói o cache ao conectar ao Redis. Pub/Sub distribui avisos entre instâncias; reconectar WebSocket exige consultar REST novamente. `/health` mostra degradação por componente e o acumulado da outbox, sem segredos. O broker indisponível não impede a gravação PostgreSQL de novos relatos.

## Fontes, rotas e alertas

AQI real consulta Open-Meteo Air Quality com domínio CAMS Global e escala US AQI. É previsão modelada (~45 km), não estação local; cada feature carrega origem, horário, validade, atribuição e rótulo. Resultados são guardados por região por até 15 minutos. Falha do provedor retorna 503 e não vira dado fictício. `ENVIRONMENT_SOURCE=fixtures` permite ensaio explícito. No modo demo todas as camadas ambientais são simuladas.

A camada de calor permanece fixture geográfica rotulada permanentemente “Dados simulados para demonstração”. Não foi encontrada/verificada fonte geoespacial real de ilhas de calor de Ribeirão Preto nesta implementação; esse requisito real segue pendente. Uma temperatura pontual não é apresentada como ilha de calor medida.

O roteamento envia todos os polígonos de incidentes ativos ao `options.avoid_polygons` do OpenRouteService. Rejeita origem/destino dentro de bloqueio, geometria inválida, resposta que intersecta bloqueios ou ausência de alternativa. Não remove exclusões para obter rota. Sem ORS_API_KEY retorna 503 claro; não inventa uma rota de demonstração. Limite didático de 50 km. As zonas circulares são influência definida por engenharia; não são extensão medida de inundação nem certificação de segurança.

Push registra token e plataforma associados à sessão JWT de instalação. O despacho seleciona posição com no máximo uma hora, raio configurado mais a influência do incidente. Tokens FCM não aparecem em eventos públicos. Firebase Admin usa credenciais em arquivo externo e define TTL limitado à validade. Aceitação pelo FCM é registrada como accepted, sem afirmar recebimento no aparelho. Firebase/APNs, Android/iOS físicos e permissões ainda exigem validação real. Não configurar FCM faz as entregas elegíveis falharem e seguirem retry/DLQ, em vez de simular sucesso.

JWT identifica uma instalação anônima com UUID informado pelo app, sem senha. Não representa autenticação de uma pessoa nem evita fraude por criação de instalações. O protótipo deve ser usado em rede controlada/HTTPS conforme o cenário acadêmico. Logs de acesso ficam desativados para evitar expor JWT presente no query string WebSocket. Endpoints de escrita e WebSocket exigem token; leitura pública contém somente dados de relatos/incidentes.

## Evidências e limites

Testes em backend/tests verificam commit/reenvio após resposta perdida, reinício, conflito, replay de evento, fronteira GeoHash, três instalações, expiração, relatos offline antigos, JWT, WebSocket bidirecional, retry/DLQ antes de ack, seleção de posição para push e adaptadores de rotas/AQI com transporte HTTP mock. Testes de mock validam contrato e regras, sem comprovar os provedores reais.

Docker Desktop foi localizado e o cluster real executou os testes documentados em [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md): fluxo por PostGIS/RabbitMQ/Redis, duas APIs e workers, replicação, falhas controladas e promoção planejada do PostgreSQL. A suíte final passou com 60 testes. A execução está limitada a um único host e a uma carga pequena. Continuam pendentes ORS/FCM reais, fonte espacial de calor, cache Redis das camadas ambientais e recebimento físico de push nas duas plataformas.

Fontes técnicas: [quorum/dead lettering RabbitMQ](https://www.rabbitmq.com/docs/quorum-queues), [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), [opções OpenRouteService](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options).
