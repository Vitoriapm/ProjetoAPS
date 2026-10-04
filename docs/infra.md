# Infraestrutura da demonstração EcoPulse

O cluster real foi executado neste Windows em 03/10/2026, no projeto isolado `ecopulse-validation`, com API em 8001 e RabbitMQ em 15673. Docker Desktop foi localizado fora do PATH inicial; os scripts agora procuram também os diretórios de instalação do Windows. O fluxo distribuído, quorum, réplica, recuperação de falhas e promoção planejada foram testados. Resultados e limites estão em [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md); arquivos Compose sozinhos continuam sem comprovar execução em outro equipamento.

## Dois ambientes separados

| Ambiente | Componentes | Projeto Compose |
| --- | --- | --- |
| Desenvolvimento | PostGIS, RabbitMQ único/quorum 1, Redis Cluster 3 primários sem réplicas, API, risco/outbox, alertas e Nginx | ecopulse-dev |
| Demonstração distribuída | PostgreSQL/PostGIS principal+réplica física, RabbitMQ 3 nós/quorum 3, Redis 3 primários+3 réplicas, 2 APIs/WebSocket, 2 workers de risco, alertas e Nginx | ecopulse-cluster |

Usar projetos separados evita reaproveitar filas criadas com um único membro e volumes Redis de outra topologia. O overlay de cluster é aplicado junto com o arquivo base; não se usa isoladamente. Não executar os dois projetos na mesma porta 8000 ao mesmo tempo.

As imagens são postgis/postgis:17-3.5 (amd64), rabbitmq:4.3.6-management, redis:8.2.10-alpine e nginx:1.28-alpine. A equipe precisa de Docker Engine/Desktop com contêineres Linux e Compose **2.24.4 ou superior**, além de memória/disco suficientes. Medir o consumo no equipamento que será apresentado; não atribuir capacidade ou SLA sem executar os testes.

## Configuração e inicialização

Na raiz, em PowerShell:

```powershell
# Só cria .env quando ausente; nunca imprime ou sobrescreve os segredos.
./scripts/start_cluster.ps1 -PrepareOnly

# Desenvolvimento (projeto separado).
./scripts/start_cluster.ps1 -Development

# Demonstração completa, depois de parar o desenvolvimento.
./scripts/start_cluster.ps1
```

O script gera senhas aleatórias URL-safe para PostgreSQL, replicação, RabbitMQ, Redis e JWT. Preserva `.env` existente e usa `docker compose config --quiet`, pois a saída normal de `config` contém segredos expandidos. `.env`, secrets/, bancos locais e ambiente virtual não entram no Docker build nem no Git. Não copiar `.env` para o relatório ou artefatos públicos.

Por padrão, a API fica em [http://localhost:8000](http://localhost:8000) e o painel RabbitMQ em [http://localhost:15672](http://localhost:15672). Somente o painel Rabbit é publicado em 127.0.0.1; bancos/Redis/AMQP ficam na rede interna Docker. Para aparelhos na mesma rede, configurar `ECOPULSE_BIND_ADDRESS=0.0.0.0` no `.env` e usar o IP local do notebook no app. Permitir a porta somente na rede da demonstração. Para serviço remoto, configurar HTTPS/WSS e regras da rede.

Para FCM, colocar a credencial Firebase Admin em `secrets/firebase-admin.json` e definir `FCM_CREDENTIALS_FILE=/run/secrets/firebase-admin.json`. Configurar ORS_API_KEY para o provedor de rotas. Esses valores não estão fornecidos no projeto; o backend apresenta erros explícitos quando uma integração não pode executar. AQI real usa Open-Meteo; calor continua fixture rotulada e requisito real pendente.

O Nginx encaminha HTTP e WebSocket com Upgrade, HTTP/1.1, timeout longo e duas instâncias no cluster. O DNS interno Docker é consultado dinamicamente a cada cinco segundos para acompanhar APIs recriadas com outro IP. Logs de acesso são desativados; erros de requisição também são suprimidos para não registrar JWT presente no query string WebSocket. O backend ainda aplica filtro ao logger do Uvicorn, que registra conexões WebSocket mesmo com `--no-access-log`; o token aparece como `[redacted]`. Inspecionar `/health` e logs dos serviços para diagnóstico. O script de failover recria APIs e gateway após alterar o endpoint do banco.

## Broker, Redis e persistência

RabbitMQ usa nomes rabbit@rabbit1–3, cookie compartilhado e descoberta `classic_config`. O job rabbit-init aguarda os nós esperados e importa políticas após o primeiro boot: importar somente políticas durante boot de banco vazio impediria criação do usuário/vhost padrão. Aplicações aguardam conclusão do job. Filas quorum são declaradas pelo backend e a reconciliação automática busca 3 membros no cluster. Conferir os membros de cada fila depois da inicialização.

Políticas `.retry` e filas principais usam `dead-letter-strategy=at-least-once` com `overflow=reject-publish`. Filas principais têm DLX para sua DLQ, protegendo contra esgotamento de tentativas de entrega após crashes; a política `.dlq` define `delivery-limit=-1` no servidor. Esse valor não é enviado como argumento AMQP porque a versão da biblioteca pamqp utilizada falha ao serializar inteiros negativos pequenos. Backend confirma republicação para retry/DLQ antes do ack e publica outbox após confirmação. Se um nó cair, o loop de conexão tenta os outros AMQP_URLS, incluindo quando somente o canal fecha.

Redis usa volumes por nó, AOF, senha e masterauth, 16384 slots e hostname anunciado para os clientes na rede Docker. `redis-init` cria somente nós sem estado; em cluster existente aguarda convergência e nunca reseta/remove dados. O cluster completo cria uma réplica por primário. Verificar promoções e cobertura de slots com `CLUSTER NODES/INFO`; quantidade de contêineres não demonstra replicação saudável.

PostgreSQL utiliza volume próprio e índice PostGIS. A réplica física é criada com pg_basebackup, WAL streaming e slot ecopulse_replica. O bootstrap nunca sobrescreve diretório com estado parcial. Reiniciar uma réplica promovida preserva PG_VERSION e não recria standby.signal. A replicação é **assíncrona**: falha inesperada pode perder commits ainda não reproduzidos. O limite de WAL retido pelo slot é 1 GB; réplica indisponível além desse limite pode exigir reconstrução, sem remoção automática de volume pelo projeto.

## Failover PostgreSQL planejado

Executar sobre ecopulse-cluster saudável, com réplica acompanhando o principal:

```powershell
./scripts/failover_postgres.ps1
```

No ensaio isolado, o mesmo script foi executado com `-ProjectName ecopulse-validation -AdditionalComposeFile .runtime/compose.validation.yaml`. O overlay local preserva as portas 8000/5173 do desenvolvimento e limita memória por serviço. Esse projeto de teste foi promovido; toda operação posterior nele deve adicionar `-f infra/compose.failover.yaml` por último, além do overlay de portas.

O procedimento valida a réplica, para todos os escritores, captura a LSN do principal e espera a réplica alcançar essa posição. Desconecta o principal ainda em execução da rede Docker, grava o marco de isolamento e o para. Somente então chama pg_promote e confirma saída de recovery. Recria API/worker/alerts/Nginx apontando DATABASE_URL para db-replica. Não reinicia o principal diante de erro; as mensagens indicam o ponto para inspeção.

Depois da promoção, utilizar sempre os três arquivos:

```powershell
docker compose -p ecopulse-cluster --env-file .env -f infra/compose.yaml -f infra/compose.cluster.yaml -f infra/compose.failover.yaml ps
docker compose -p ecopulse-cluster --env-file .env -f infra/compose.yaml -f infra/compose.cluster.yaml -f infra/compose.failover.yaml up -d
```

O overlay substitui as dependências do banco com `!override` e coloca o principal antigo em perfil primary-fenced. O script de inicialização recusa o projeto que possui marco de isolamento. Não executar o principal antigo explicitamente nem voltar à configuração sem failover: isso poderia produzir dois bancos graváveis. A reconstrução/failback do nó antigo exige análise e backup; não há rotina que apague ou reconfigure seus dados automaticamente.

Evidências em infra/evidence/ registram LSN, horários UTC, duração, isolamento e endpoint promovido, sem senhas. A demonstração planejada com espera de LSN cobre esse cenário controlado; não demonstra failover automático, perda zero em falha inesperada ou sobrevivência à falha do notebook. Todos os nós no mesmo host compartilham energia, disco e rede.

## Verificação e registro

Validação que pode rodar sem Docker:

```powershell
./backend/.venv/Scripts/python.exe infra/validate_static.py
./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

Para repetir em outro equipamento, executar cada cenário e registrar hardware/rede, hora, IDs/versões, antes/depois, falhas observadas e tempo de recuperação:

1. Consultar /health, inserir dados fictícios e comprovar PostgreSQL → outbox → Rabbit → risco → Redis → segundo cliente WebSocket.
2. Parar um worker; observar outro processando as partições e recuperar mensagens não confirmadas.
3. Interromper um nó Rabbit; verificar membros quorum e persistência/reprocessamento.
4. Verificar retry/DLQ com mensagem inválida e republicação controlada; não atribuir sucesso a um log sem conferir efeito.
5. Parar um primário Redis; observar réplica promovida, slots cobertos e reconstrução/cache com mesma versão do banco.
6. Interromper uma API; manter consultas pelo Nginx, reconectar WebSocket e atualizar REST para recuperar avisos perdidos.
7. Executar promoção planejada PostgreSQL; conferir relatos/eventos confirmados após mudança de endpoint.
8. Reiniciar serviços preservando volumes; repetir consulta com IDs estáveis. Não usar `down -v` durante demonstração de persistência.

O ensaio já realizado comprovou esses cenários na escala acadêmica descrita em [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md). Foram 60 relatos por rodada com concorrência máxima 4; isso não mede capacidade de produção ou SLA. A réplica PostgreSQL era assíncrona e sua promoção aguardou a LSN com escritores parados. Depois da promoção não há nova réplica PostgreSQL até reconstruir o nó antigo de forma controlada.

Continuam pendentes: credenciais e chamada real ORS, configuração FCM/APNs e recebimento físico, fonte espacial real de calor, cache Redis das camadas ambientais, ensaio em múltiplos hosts e teste de perda abrupta do host. AQI real e duas primeiras consultas simultâneas em APIs distintas foram testados, com uma única observação persistida por GeoHash. Atualmente o cache AQI usa PostgreSQL e validade de 15 minutos; Redis armazena incidentes e transmite avisos das camadas.

Fontes: [PostgreSQL17 standby](https://www.postgresql.org/docs/17/warm-standby.html), [Rabbit cluster formation](https://www.rabbitmq.com/docs/cluster-formation), [definitions e primeiro boot](https://www.rabbitmq.com/docs/definitions), [quorum/retries Rabbit](https://www.rabbitmq.com/docs/quorum-queues), [Redis Cluster](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/), [Nginx WebSocket](https://nginx.org/en/docs/http/websocket.html), [ordem de startup Compose](https://docs.docker.com/compose/how-tos/startup-order/), [Docker network disconnect](https://docs.docker.com/reference/cli/docker/network/disconnect/).
