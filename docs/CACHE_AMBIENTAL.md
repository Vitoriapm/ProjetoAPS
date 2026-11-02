> **Arquivo histórico:** Ar (AQI) e Calor foram retirados do projeto em **02/11/2026**, por solicitação do usuário. Este documento preserva a implementação e os resultados da versão de outubro; não descreve o escopo atual de Alagamento e Vias nem comprova a suíte atual. Evidências e entregas antigas foram mantidas.

# Cache ambiental do EcoPulse

AQI e calor agora usam o Redis Cluster real, além do cache de incidentes. A consulta mantém o PostgreSQL como fonte de referência e usa o payload do Redis quando a versão coincide e a validade da observação ainda está vigente.

## Fluxo implementado

1. A API consulta o AQI Open-Meteo/CAMS ou lê o conjunto Landsat já importado.
2. A observação e o evento `camada.atualizada` são gravados na mesma transação do PostgreSQL. Uma versão crescente identifica cada alteração; consultas repetidas da mesma observação válida preservam a versão e o prazo original.
3. O relay publica o outbox com confirmação no RabbitMQ; o serviço de alertas processa a mensagem.
4. Uma operação Lua compara versões e grava o payload com TTL. Uma mensagem antiga não sobrescreve o conteúdo mais recente. Conteúdo corrompido pode ser reconstruído.
5. O evento é publicado no canal Redis usado pelos WebSockets. Os clientes consultam as camadas para obter o GeoJSON atualizado.

As chaves seguem `ecopulse:environment:{GeoHash}:tipo:UUID`. O trecho entre chaves mantém a comparação e a gravação atômicas em um slot do Redis Cluster.

O AQI tem validade de cache de 15 minutos. O conjunto Landsat tem prazo de reconstrução de 24 horas. Esse prazo não transforma uma cena histórica em informação atual: o horário de aquisição permanece **17/09/2025** e `observation_type` continua `historic`.

## Validação real em 04/10/2026

O teste foi executado no projeto isolado `ecopulse-validation`, com gateway em `8001`, seis Redis, três RabbitMQ, duas APIs e o PostgreSQL previamente promovido. O primário antigo permaneceu isolado; nenhum volume foi removido.

| Verificação | Resultado |
|---|---|
| Camadas ambientais reais | 33: um AQI modelado atual e 32 polígonos Landsat históricos |
| PostgreSQL, outbox e consumidor | 33 eventos publicados e processados pelo serviço de alertas; outbox pendente zero |
| Conteúdo do Redis | 33 IDs, versões e payloads iguais às observações persistidas |
| TTL na captura | AQI 392 segundos; calor 85.892 segundos; diferença para a validade restante de até três segundos |
| Redis Cluster | 16.384 slots cobertos |
| Duas APIs | Mesmos IDs, versões e valores |
| Dois WebSockets | Cada cliente recebeu as 33 camadas durante a reconstrução; 1,578 segundo no ensaio |
| Evento antigo | Lua rejeitou a regressão de versão |
| Cache legado ou inválido | Leitura manteve a observação do PostgreSQL; reconstrução reparou o JSON corrompido |
| Expiração real de chave | Uma chave de calor expirou no Redis; leitura manteve a observação e reconstrução restaurou a chave |
| Reconstrução | Não chamou o provedor HTTP nem o importador de calor/GDAL |
| Todos os Redis parados | As duas APIs retornaram HTTP 200 com as mesmas 33 camadas, usando PostgreSQL |
| Retomada dos Redis | Payloads, versões e TTLs convergiram novamente |

A verificação inicial de convergência levou 2,031 segundos com observações já aquecidas. Esses números descrevem este ensaio pequeno; não medem capacidade de produção nem garantem latência de uma primeira consulta ao provedor.

Evidência automatizada: [environment-cache.json](evidence/environment-cache.json). O script não grava JWTs, senhas, tokens FCM ou URLs de conexão na evidência.

## Correção encontrada na retomada da infraestrutura

Após reiniciar o Docker, endereços de peers persistidos no Redis ficaram antigos. Um nó anunciava `redis5:0` e `noaddr`, apesar de `cluster_state:ok`. A leitura de determinadas chaves falhou e duas mensagens ambientais chegaram à DLQ.

O inicializador [infra/redis/init.sh](../infra/redis/init.sh) agora reintroduz peers existentes com `CLUSTER MEET` usando os IPs resolvidos no momento. Ele só aceita o cluster quando todos os membros estão conectados, sem `noaddr`, `fail`, `handshake` ou porta zero, e os 16.384 slots estão íntegros. O caminho de criação de um cluster vazio permanece separado. A reconciliação não executa reset, flush, exclusão de volumes ou redistribuição de slots.

O job corrigido passou no cluster real. As duas mensagens ambientais foram reenviadas seletivamente, com confirmação de publicação antes do ACK da DLQ. Seis mensagens preexistentes de outros testes permaneceram na DLQ. Portanto, este ensaio não afirma que todas as DLQs do projeto estão vazias. Registro da recuperação: [environment-cache-recovery.json](evidence/environment-cache-recovery.json).

## Reprodução da versão anterior

O validador ambiental foi retirado junto com Ar e Calor. As provas registradas em `docs/evidence/` permanecem como histórico, sem uma rotina ambiental ativa na versão atual.

## Limites

O cache preserva consistência eventual dos payloads e a API continua consultando as observações duráveis; este teste não demonstra redução da carga de consultas ao PostgreSQL. A fonte do AQI é uma previsão modelada de grade ampla, e o calor é um contraste histórico de temperatura de superfície. A infraestrutura inteira está em um único computador. Push físico, rotas autenticadas, capacidade para grandes volumes e disponibilidade diante de falha do computador exigem suas próprias evidências.
