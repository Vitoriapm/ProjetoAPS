# Validação real da infraestrutura EcoPulse

O cluster foi executado em 03/10/2026, das 22h43 às 22h59 de Brasília aproximadamente (os arquivos registram 04/10 em UTC). Os resultados comprovam o protótipo distribuído em um único notebook. Não comprovam disponibilidade de produção, SLA, falha do host ou recebimento de push físico.

## Ambiente e isolamento

- Windows, 8 GB RAM, 8 processadores lógicos; Docker Desktop com containers Linux, Engine 29.8.1 e Compose 5.5.1.
- Projeto `ecopulse-validation`, rede e volumes próprios; API/Nginx em `127.0.0.1:8001`, painel RabbitMQ em `127.0.0.1:15673`.
- Demo em 8000 e preview Flutter em 5173 preservados. Nenhum outro projeto Docker foi parado ou removido; nenhuma instalação ou reinicialização do sistema foi feita.
- PostGIS 17/3.5, RabbitMQ 4.3.6 com três nós, Redis 8.2.10 com três primários e três réplicas, duas APIs, dois workers de risco/outbox e um worker de alertas.
- Consumo observado dos containers próximo de 1,1 GiB; memória livre do host próxima de 896 MiB no ponto medido. As medições são locais, não requisitos garantidos de hardware.
- Todos os relatos usados nos ensaios foram explicitamente fictícios (`is_demo=true`). As evidências não incluem senhas, JWT, tokens de dispositivo ou conteúdo do `.env`.

## Resultados

| Cenário | Resultado observado | Evidência |
| --- | --- | --- |
| Saúde full | PostgreSQL, broker e cache `ok`; outbox sem pendências | [full-pipeline.json](../infra/evidence/full-pipeline.json) |
| Fluxo completo | POST 201 → PostGIS/outbox → RabbitMQ → worker → Redis → duas conexões WS receberam mesmo ID/versão em 0,641 s | [full-pipeline.json](../infra/evidence/full-pipeline.json) |
| Resposta perdida/reenvio | Ignorada a primeira confirmação do cliente; o mesmo UUID/conteúdo retornou 200 sem duplicação | [full-pipeline.json](../infra/evidence/full-pipeline.json) |
| Colaboração | Três instalações distintas produziram incidente colaborativo, versão 3, três relatos | [full-pipeline.json](../infra/evidence/full-pipeline.json) |
| PostGIS/cache/replicação | Índices espaciais presentes; versões do Redis coincidem com banco; réplica `streaming`, `async`, lag 0 no ponto medido | [full-backing.json](../infra/evidence/full-backing.json), [full-topology-promoted.json](../infra/evidence/full-topology-promoted.json) |
| Quorum RabbitMQ | As 15 filas de processamento/retry/DLQ têm três membros quorum; políticas duráveis aplicadas | [full-topology-promoted.json](../infra/evidence/full-topology-promoted.json) |
| Redis Cluster | 16.384 slots; três primários e três réplicas; após falha, redis5 primário e redis1 réplica | [full-topology-promoted.json](../infra/evidence/full-topology-promoted.json) |
| Ambos workers parados | POST 201 continuou durável; outbox acumulou; ao reiniciar, backlog processado | [full-faults.json](../infra/evidence/full-faults.json) |
| Uma API parada | Nginx manteve GET 200 pela outra API | [full-faults.json](../infra/evidence/full-faults.json) |
| Um worker parado | Outro consumidor processou e entregou WS | [full-faults.json](../infra/evidence/full-faults.json) |
| Um Rabbit parado | Quorum restante e fallback AMQP entregaram novo evento WS | [full-faults.json](../infra/evidence/full-faults.json) |
| Um primário Redis parado | Réplica assumiu; consulta REST e novo evento WS funcionaram | [full-faults.json](../infra/evidence/full-faults.json) |
| Reinício PostgreSQL | 68 IDs de relatos persistiram no reinício com escritores pausados | [full-faults.json](../infra/evidence/full-faults.json) |
| Mensagem inválida | JSON inválido foi para DLQ com corpo persistente e erro identificado | [full-dlq.json](../infra/evidence/full-dlq.json) |
| Falha transitória | FCM explicitamente ausente: três retries e DLQ em 22,657 s; entrega ficou `pending` | [full-dlq.json](../infra/evidence/full-dlq.json) |
| Replay controlado DLQ | Republicação confirmada antes de ack da DLQ; replay e duplicata deixaram um registro processado | [full-dlq-replay.json](../infra/evidence/full-dlq-replay.json) |
| AQI simultâneo | GeoHash inicialmente vazio; primeira consulta em api e api2 retornou 200/200, AQI real 59 e uma linha persistida | [full-aqi-concurrent.json](../infra/evidence/full-aqi-concurrent.json) |
| Promoção planejada PostgreSQL | Escritores pausados, réplica alcançou LSN, antigo primário isolado/parado, promoção em 14,852 s | [failover registrado](../infra/evidence/failover-ecopulse-validation-20261004-015502.json) |
| Após promoção | Novos relatos e dois WS funcionaram em 0,391 s; reenvio 200 e colaboração versão 3; 60 IDs da carga preservados | [full-pipeline-promoted.json](../infra/evidence/full-pipeline-promoted.json), [full-persistence-promoted.json](../infra/evidence/full-persistence-promoted.json) |

A invalidação da resposta perdida foi simulada no cliente ignorando a primeira resposta recebida. Não houve corte físico do pacote TCP. O teste de retry usou registro de dispositivo fictício com FCM ausente; seu token foi removido antes do replay, portanto nenhum envio foi apresentado como recebido. A mensagem inválida permanece na DLQ para inspeção e não foi replayada sem corrigir seu formato.

As pausas foram controladas (`docker compose stop/start`); não equivalem a desligar o notebook, corromper disco ou particionar a rede de forma arbitrária. O aviso WS não é uma fila durável por cliente: após reconectar, o app deve recuperar o estado por REST.

## Carga pequena

A rodada final enviou 60 relatos fictícios com no máximo quatro requisições simultâneas. Todos retornaram 201. Entrada concluída em 1,328 s (45,18 relatos/s); p50 32 ms e p95 297 ms. Processamento/agregação e outbox convergiram em 2,469 s desde o início; versões do cache foram verificadas em 3,860 s. Evidência: [full-load.json](../infra/evidence/full-load.json).

Houve uma rodada preliminar de 60 relatos antes das falhas; a rodada acima inclui confirmação cronometrada do cache e é a referência final. O ensaio é curto, local, com dados pequenos e influenciado pelo notebook e seus outros processos. Não mede carga sustentada, capacidade máxima ou comportamento com grandes volumes.

## Correções comprovadas durante o ensaio

1. A topologia RabbitMQ falhava porque pamqp não serializa `x-delivery-limit=-1` como argumento. O limite da DLQ passou para política do servidor; o teste agora serializa os argumentos pela biblioteca real.
2. Uvicorn logava JWT do WebSocket mesmo com access log desativado. Filtro no logger remove o token; logs pós-correção exibem `[redacted]`.
3. Duas APIs podiam disputar INSERT da mesma observação AQI. Upsert PostgreSQL/SQLite resolveu a chave atomicamente na transação da outbox; teste forçado de concorrência e ensaio real passaram.
4. Scripts PowerShell passaram a localizar Docker fora do PATH e selecionar um único executável quando `Get-Command` retorna múltiplos candidatos.

Validação estática Compose e AST PowerShell passaram. A suíte final do backend passou com **60 testes**; houve um aviso de depreciação de biblioteca sem falha. Os testes unitários com mock de ORS/FCM validam regras, não serviços reais.

## Limites e próximo passo

O PostgreSQL usa replicação assíncrona. A promoção realizada aguardou a LSN com os escritores pausados; não comprova perda zero em falha inesperada. O antigo primário terminou parado e sem rede. Depois da promoção, o novo primário ainda não tem uma nova réplica: é necessário reconstruir o nó antigo de forma controlada, com backup e análise, antes de outra demonstração de redundância PostgreSQL.

Ainda faltam credenciais e execução real do ORS; configuração FCM/APNs e recebimento em aparelhos Android/iOS; fonte espacial real de calor; cache Redis das camadas ambientais (hoje AQI usa PostgreSQL/validade de 15 minutos e calor é fixture); teste em múltiplos hosts e perda abrupta do host. O cenário mínimo da faculdade pode ser apresentado identificando essas limitações e os dados simulados.

Ao encerrar os ensaios, a raiz parou somente `ecopulse-validation`, preservando volumes para liberar memória e atualizar o APK. Demo 8000 e prévia 5173 continuaram abertos. Para voltar ao estado promovido, usar base + cluster + overlay local de portas + `compose.failover.yaml` por último. Não iniciar o antigo primário nem executar a configuração anterior sobre esse projeto. O projeto normal `ecopulse-cluster` é separado e não reutiliza os volumes da validação.

Fontes do comportamento das filas e replicação: [quorum/limite e dead lettering RabbitMQ](https://www.rabbitmq.com/docs/quorum-queues), [standby PostgreSQL 17](https://www.postgresql.org/docs/17/warm-standby.html).
