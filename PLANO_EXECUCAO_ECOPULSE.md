# Plano de execução do EcoPulse com interface simples

Entregar até **30/10/2026** um protótipo acadêmico do EcoPulse para **Android e iOS**, com demonstração em **Ribeirão Preto** e trabalho dividido entre três desenvolvedores.

Escopo revisado em **02/11/2026**: o usuário solicitou retirar Ar e Calor. O aplicativo mantém os relatos de Alagamento e Vias, rotas e alertas. O cronograma e os resultados de outubro abaixo permanecem como histórico; esta revisão alinha as funcionalidades atuais. A referência é [Proposta_APS_DSD_EcoPulse.docx](<C:/Users/usuario/Desktop/APS APP/Proposta_APS_DSD_EcoPulse.docx>), especialmente as seções III, IV e V. Substitui a versão que previa somente uma API com SQLite no servidor.

**Diretriz:** manter duas telas principais, linguagem clara e visual discreto, com a arquitetura necessária para demonstrar os requisitos da disciplina. A simplicidade será aplicada à interface, às regras e ao tamanho da demonstração. Todos os itens da matriz abaixo fazem parte da entrega; GPS, WebSocket e push deixam de ser opcionais.

A inclusão neste documento significa **Planejado**, não Implementado ou Validado. O estado atual por requisito está em [docs/REQUISITOS.md](docs/REQUISITOS.md), com resultados em [docs/VALIDACAO.md](docs/VALIDACAO.md). Simulação deve ser identificada separadamente e não comprova uma integração real.

**Estado de execução em 05/10:** Firebase Android, conta de serviço e chave ORS foram fornecidos e configurados. O teste direto de push de 04/10 permanece como evidência do APK anterior. No ensaio de 05/10, um relato fictício percorreu o backend full e gerou uma entrega FCM aceita para o Android dentro do raio; o usuário confirmou chegada em segundo plano e abertura por toque no APK atual 1.0.0 (2), sem observação independente do aparelho. A exclusão fora foi verificada somente com cadastro web sintético. O adaptador ORS e a API retornaram rotas válidas, e o usuário confirmou a rota no Android sem informar pontos/valores. Aquisição GPS pontual, offline/reabertura/reenvio e aviso local com pontos manuais também possuem confirmação humana e provas próprias. Essas evidências não alteram os requisitos nem os critérios de aceite abaixo: movimento GPS físico, FCM em primeiro plano, telefone físico fora do raio e iOS/APNs continuam pendentes. O relatório e o roteiro formal Word foram produzidos em 05/10; o registro de atividades e assinaturas da APS deve ser preenchido pela equipe. Detalhes em [docs/VALIDACAO.md](docs/VALIDACAO.md).

## 1 Matriz de requisitos incorporados

| Requisito | Implementação planejada | Evidência de conclusão |
| --- | --- | --- |
| EDA e microsserviços | API, processamento de risco e entrega de alertas em serviços separados | Parar o worker não impede a API de persistir novos relatos |
| Broker distribuído | RabbitMQ com eventos duráveis; perfil de demonstração com três nós e filas de quorum | Replicação, confirmação e recuperação após falha de um nó |
| Particionamento geográfico | GeoHash, partições de eventos e pelo menos dois workers | Distribuição de trabalho e recuperação após falha de worker |
| Resiliência | Transações, outbox, confirmações, idempotência, retries e DLQ | Reenvio sem duplicação, recuperação e mensagem inválida na DLQ |
| WebSocket bidirecional | Assinatura por área, confirmação do servidor e atualizações de incidentes | Segundo cliente atualiza sem tocar em Atualizar |
| Push geográfico | FCM/APNs com seleção de dispositivos por área ou posição válida | Recebimento em Android e iOS físicos, inclusive em segundo plano |
| Cache e consistência eventual | Redis Cluster; PostgreSQL/PostGIS como estado principal | Banco, cache e clientes convergem para o mesmo ID e versão |
| Alagamentos | Relatos e zonas de influência no mapa | Geometria, legenda e horário apresentados |
| Vias obstruídas | Categoria de relato e camada própria | Via/trecho sinalizado e considerado no cálculo de rota |
| Relato colaborativo | Validação, GPS pontual e metadados | Captura automática e fallback quando a permissão é negada |
| Proximidade e roteamento | Entrada no raio do risco e rota evitando incidentes conhecidos | Alerta de proximidade e trajeto sem interseção com bloqueio |
| Offline-first | SQLite local, fila persistente e envio ao recuperar conexão | Reinício não perde pendências; reconexão inicia sincronização |
| Backend em Docker | FastAPI e workers conteinerizados com Compose | Ambiente sobe por comando documentado e preserva volumes |
| Disponibilidade e recuperação | Serviços redundantes, réplica PostgreSQL e failover controlado | Falha de instância e recuperação testadas, com tempo e estado dos dados registrados |
| Duas plataformas | Projeto Flutter com configurações e testes separados | Instalação e cenários comprovados em Android e iOS |

## 2 Interface simples e humanizada

Usar cores discretas, componentes nativos do Flutter, fonte padrão legível, ícones comuns e textos em português. Evitar dashboards, estatísticas decorativas, animações elaboradas e excesso de telas.

**Tela principal:** mapa de Ribeirão Preto; seleção das camadas Alagamento e Vias; legenda; lista acessível de ocorrências; indicador de pendências e botão Reportar. Detalhes, preferências de alerta, configuração de servidor e seleção de destino ficam em painéis pequenos sobre essa tela.

**Tela de relato:** tipo Alagamento ou Via obstruída, gravidade baixa/média/alta, descrição opcional e posição preenchida por GPS. Permitir corrigir o ponto manualmente. Mostrar origem e horário da posição quando necessário.

Mensagens propostas: “Seu relato foi salvo”, “Salvo no aparelho. Enviaremos quando a conexão voltar” e “Há uma ocorrência registrada perto de você”. Mostrar a idade dos dados e não apresentar uma rota como certificação de segurança.

Podem permanecer fora: login com senha, fotos, vídeos, painel administrativo completo, reputação de usuários, navegação curva a curva, mapas completos para download e publicação em lojas. Não são dependências dos requisitos confirmados.

## 3 Stack escolhida

| Camada | Tecnologia |
| --- | --- |
| Aplicativo | Flutter e Dart |
| Mapa e localização | flutter_map, geolocator e tiles baseados em OpenStreetMap |
| Banco do aparelho | SQLite com sqflite |
| Sincronização e comunicação | HTTP, WebSocket e detecção de conectividade |
| Push | Firebase Cloud Messaging e APNs no iOS |
| Backend | Python e FastAPI |
| Dados geográficos | PostgreSQL com PostGIS |
| Mensageria | RabbitMQ |
| Cache distribuído | Redis Cluster |
| Indexação espacial | GeoHash |
| Roteamento | Adaptador OpenRouteService |
| Execução | Docker Compose e configurações versionadas |

Flutter/React Native, FastAPI/Go/Node, RabbitMQ/Kafka/MQTT e GeoHash/H3 são alternativas. A escolha acima evita implementar várias opções equivalentes. SQLite continua no dispositivo; o servidor principal passa a PostgreSQL/PostGIS.

Estrutura do repositório: mobile/ para Flutter; backend/api/, backend/worker/ e backend/alerts/ para os serviços; infra/ para Docker e políticas; scripts/ para dados e testes; docs/ para arquitetura, instalação e evidências. Manter contratos compartilhados e versões fixadas.

## 4 Arquitetura orientada a eventos

Três serviços principais:

1. **API de ingestão e consulta:** valida relatos, consulta PostGIS, registra dispositivos/áreas de interesse e atua como proxy de rotas/fontes ambientais.
2. **Worker de risco:** processa eventos por partição, cria/atualiza incidentes, aplica expiração e gera novos eventos.
3. **Serviço de alertas:** recebe eventos de incidentes, atualiza o cache e entrega avisos via WebSocket e FCM.

Fluxo: **Flutter/SQLite → API → PostgreSQL e outbox → RabbitMQ → worker → incidente e outbox → RabbitMQ → serviço de alertas → Redis/WebSocket/FCM → Flutter**.

A gravação do relato e da outbox ocorre na mesma transação. O publicador marca o evento como publicado após a confirmação do RabbitMQ. O consumidor confirma somente após persistir o efeito e o controle de idempotência. Atualizações do incidente também usam outbox. Comunicação ao vivo não substitui o estado durável no banco.

Usar UUID do relato e ID do evento para deduplicação. Se o servidor salvar e a resposta se perder, o reenvio recupera o mesmo registro. O mesmo UUID com conteúdo diferente gera conflito. Cada incidente tem versão; mensagens antigas não podem regredir seu estado.

## 5 Mensageria, partições e cluster

Configurar filas duráveis, mensagens persistentes, publisher confirms, acknowledgements manuais e volumes persistentes. Aplicar retries limitados com espera crescente; após esgotamento, encaminhar à DLQ com motivo e identificadores. Demonstrar reprocessamento controlado. Usar dead-lettering ao menos uma vez devidamente configurado ou republicação confirmada antes de reconhecer a mensagem original. [Quorum queues do RabbitMQ](https://www.rabbitmq.com/docs/quorum-queues).

Derivar partições estáveis a partir do GeoHash e encaminhar eventos para filas por partição. Pelo menos dois workers processam essas filas. Documentar a atribuição e a redistribuição/continuidade de trabalho quando um worker falha. Uma coluna GeoHash ou uma sala WebSocket, sozinhas, não comprovam sharding e balanceamento.

Consultar o raio completo no PostGIS e cobrir todas as células que o intersectam. Testar fronteiras e células vizinhas. Proteger a criação concorrente de incidentes para não gerar duas ocorrências para a mesma agregação. A divisão horizontal demonstrada é dos eventos/processamento; não afirmar que o banco central está fragmentado em bancos independentes.

**Perfil de desenvolvimento:** contêineres com recursos reduzidos para construir o primeiro fluxo.

**Perfil obrigatório de demonstração distribuída:** três nós RabbitMQ com quorum queues; Redis Cluster com três primários e três réplicas; dois workers; duas instâncias da API e da entrega WebSocket atrás de um balanceador. Validar redistribuição de slots e promoção de réplica Redis. O cliente Redis precisa tratar redirecionamentos do cluster. [Redis Cluster](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/).

O perfil leve não aprova o requisito de cluster. Testar cedo o consumo de memória do perfil completo e obter máquina/servidor adequado se o notebook não suportar. A execução pode ser local durante desenvolvimento e em servidor Linux com Docker para acesso remoto, com HTTPS/WSS e segredos fora do repositório.

A disponibilidade deve ser descrita por componente. Incluir no perfil de demonstração PostgreSQL principal e réplica, procedimento de failover controlado e redundância do acesso aos serviços. Testar a interrupção de uma instância e a retomada do fluxo; registrar tempo de recuperação, estado dos eventos confirmados e nível de replicação adotado. Nós no mesmo notebook demonstram falha de processo/nó lógico, sem comprovar sobrevivência à perda do notebook. Não atribuir alta disponibilidade irrestrita ao sistema inteiro apenas porque os componentes são replicados; falhas do host e dos provedores externos precisam ter seu alcance explicitado.

## 6 Banco, cache e regras simples

No PostGIS, persistir pontos/polígonos e índice espacial. Transportar GeoJSON em EPSG:4326, na ordem longitude/latitude; calcular distâncias em metros com geography ou projeção adequada.

Tabelas essenciais: relatos, incidentes, vínculos relato/incidente, observações ambientais, outbox, eventos processados, dispositivos/áreas de interesse e entregas de alerta. No SQLite mobile: relatos locais, fila de sincronização, incidentes consultados e preferências.

O PostgreSQL é a fonte principal. Chaves Redis incluem região e versão; TTL não ultrapassa a validade dos dados. Atualizar/invalidate após eventos e reconstruir o cache pelo banco quando necessário. Medir a convergência de banco, cache e clientes. Redis Pub/Sub é usado para fan-out entre instâncias, sem substituir o broker persistente.

Regra inicial de engenharia, configurável: três instalações diferentes em dez minutos e raio de 200 metros elevam a confiança colaborativa; expiração inicial de 30 minutos sem atualização e raio de aviso de 1 km. Calibrar nos testes. Esses valores não têm validação científica, e instalações distintas não garantem pessoas distintas.

Um relato isolado pode aparecer com estado Relatado. A zona exibida é a influência definida pela regra; um círculo didático não é a extensão medida de uma inundação. Gravidade é informada pelo usuário. Relatos antigos sincronizados depois da janela não geram risco atual indevido. Expiração não comprova que a via voltou ao normal.

## 7 Ocorrências e roteamento

O mapa oferece os filtros Alagamento e Vias. Exibir tipo, gravidade, horário, legenda e relatos agrupados; as zonas de influência seguem a regra documentada. Os relatos de demonstração permanecem identificados como simulação acadêmica.

**Rotas:** escolher destino no mapa, enviar origem/destino à API e calcular rota que evita polígonos de incidentes ativos. Guardar a chave do provedor no servidor, validar geometrias/limites e testar indisponibilidade, origem dentro de bloqueio e ausência de alternativa. Verificar que o trajeto não intersecta os bloqueios. Não remover exclusões silenciosamente para obter uma resposta. Usar “Rota alternativa evitando ocorrências registradas”. [Opções do OpenRouteService](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options).

## 8 GPS, tempo real, push e offline

Capturar GPS pontualmente ao criar o relato, com permissão, horário e precisão quando disponível. O ponto manual é fallback. Para proximidade com app ativo, acompanhar mudanças de posição e testar entrada/saída do raio, validade e supressão de alertas repetidos.

WebSocket permite enviar a assinatura/área de interesse e receber confirmação; o servidor envia alterações de incidentes. Reconexão inclui consulta REST para recuperar eventos perdidos. Atualizar continua como apoio, sem substituir a atualização automática.

Push é implementado por FCM/APNs, com registro/renovação de token, seleção geográfica e expiração. Em segundo plano, usar área escolhida ou última localização válida, com horário; não presumir GPS continuamente atualizado. Android e iOS físicos devem receber uma notificação de teste. FCM aceito pelo servidor não comprova recebimento no aparelho. [Configuração FCM para Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

Na implementação atual, o full aceita a última posição GPS ou manual com idade de até uma hora. O app registra raio de dispositivo de 1.000 m, somado à influência de 200 m do incidente; o aviso local de 1.000 m é um fluxo distinto. Incidentes ativos de gravidade baixa também podem gerar push. O ensaio de 05/10 comprovou o envio para um Android dentro dessa seleção e sua recepção em segundo plano por confirmação humana; cadastro web sintético fora foi excluído. Isso não substitui testes de movimento GPS, telefone físico fora, primeiro plano e iOS.

Salvar o relato no SQLite antes de enviar. Ao recuperar conectividade com app ativo, sincronizar automaticamente; também retomar ao abrir/voltar ao app. A conectividade é um sinal para tentar: confirmar alcance da API. Tarefas oportunistas de fundo podem ajudar, mas a execução é controlada pelo sistema operacional e não tem prazo imediato garantido.

Não apagar pendências ao atualizar: mesclar por UUID. Timeout, GET vazio, reinício e falha de envio preservam dados locais. Usar um único processo de sincronização por aparelho. Marcar Enviado somente após confirmação. O offline cobre relatos e dados consultados; novas áreas do mapa e novas rotas dependem de rede.

## 9 Contratos de API e eventos

Definir no primeiro marco: POST /v1/relatos; GET /v1/incidentes/ativos; POST /v1/rotas; PUT /v1/dispositivos/push; atualização de posição/área de interesse; GET /health; WebSocket /v1/ws.

Relato: UUID, tipo, gravidade, latitude, longitude, origem da posição, precisão quando disponível, descrição opcional, occurred_at e indicador de demonstração. O servidor acrescenta received_at e GeoHash. Usar UTC/ISO 8601 no transporte, horário local na interface e nomes explícitos das coordenadas.

Evento: event_id, schema_version, tipo, aggregate_id, aggregate_version, occurred_at, region_id, trace_id e payload. Tipos iniciais: relato.criado, incidente.criado, incidente.atualizado, incidente.expirado e notificacao.solicitada.

Validar limites de campos, área consultada e submissão. Identificação simples da instalação não exige login com senha. Proteger endpoints de escrita e canais com token de sessão da instalação; excluir tokens e identificadores dos eventos públicos/logs de apresentação.

## 10 Divisão entre agentes e cronograma

| Responsável | Parte principal | Apoio |
| --- | --- | --- |
| Agente/Dev 1 | UI Flutter, formulário, seletores de camada, detalhes e rota | Textos, apresentação e evidências |
| Agente/Dev 2 | Mapa/GPS, SQLite, sincronização, REST/WebSocket e configuração mobile de push | Fixtures espaciais e testes Android/iOS |
| Agente/Dev 3 | FastAPI, PostGIS, RabbitMQ, workers, Redis e despacho de push | Docker, contratos, proxy de rotas e fontes |
| Coordenação | Contratos, integração, revisão e verificação ponta a ponta | Documentação e controle das dependências |

Dividir arquivos por responsabilidade e integrar continuamente. Dev 3 recebe apoio dos outros integrantes na infraestrutura e nos testes, evitando concentrar todas as validações.

| Período | Entrega e marco |
| --- | --- |
| **03–05/10** | Contratos, estrutura, dados de relatos, prova de rotas, Docker disponível e acesso macOS/iPhone/credenciais encaminhado |
| **06–11/10** | Fluxo GPS/SQLite → API/PostGIS/outbox → RabbitMQ → worker → mapa; duas partições/workers e perfil cluster iniciados |
| **12–18/10** | Regras, retries/DLQ, Redis, WS, push Android/iOS, proximidade e reconexão automática |
| **19–23/10** | Alagamento, Vias e rotas integrados; cluster, balanceamento, réplica PostgreSQL e failover controlado demonstrados |
| **24–27/10** | Matriz de testes nas plataformas, carga controlada, correções, evidências e relatório; escopo congelado |
| **28–29/10** | Builds instalados, ensaio, vídeo de apoio e pacote final |
| **30/10** | Entrega e apresentação; reserva para falhas críticas |

O escopo aumentou; a estimativa anterior de 90–130 horas deixa de valer. Reestimar após as provas do primeiro marco, por tarefa e disponibilidade real dos três integrantes. O cronograma é uma meta de execução com risco elevado, especialmente para iOS, push, rotas e cluster. Dependências sem acesso devem aparecer como pendentes, sem transformar requisito obrigatório em opcional.

## 11 Dependências que precisam ser resolvidas

A equipe informou que não dispõe de Mac nem iPhone. Obter acesso a macOS/Xcode, assinatura, aparelho físico e conta/capabilities necessárias para APNs. Fazer uma primeira execução e prova de push cedo. Flutter compartilhado não valida iOS. [Configuração iOS](https://docs.flutter.dev/platform-integration/ios/setup).

Na auditoria de 03/10, Docker Desktop foi localizado fora do PATH e o cluster completo executou testes reais de processamento, replicação e falha de nós. Os scripts passaram a localizar essa instalação. Resultados e limites ficam em [docs/VALIDACAO_INFRA.md](docs/VALIDACAO_INFRA.md); a execução no mesmo notebook não comprova sobrevivência à perda do host.

Firebase/APNs e chave do provedor de rotas foram dependências identificadas na fase inicial. Não inserir segredos no código. Eventuais contas, contratações ou equipamentos dependem de acesso providenciado pela equipe. Mocks identificados continuam úteis para ensaios controlados; cada integração real exige evidência própria.

Na fase anterior de preparação, a equipe ainda não possuía Firebase ou chave OpenRouteService; os fluxos foram implementados com scripts e testes controlados, sem comprovar recebimento FCM/APNs ou resposta real ORS naquele momento. A preparação está em [docs/PUSH.md](docs/PUSH.md) e [docs/ROTAS.md](docs/ROTAS.md).

**Evidência histórica de 04/10:** o usuário forneceu a configuração Android e a conta de serviço do mesmo projeto Firebase. OAuth, dry-run FCM e um único envio fictício foram aceitos. No APK anterior, com o app em segundo plano, o usuário confirmou que a notificação chegou e tocar abriu o EcoPulse; [docs/evidence/fcm-phone-receipt.json](docs/evidence/fcm-phone-receipt.json) registra essa fonte humana, sem observação independente. O script de envio mantém `device_receipt_verified=false`, pois não observa o aparelho. Esse ensaio direto não exercitou primeiro plano, GPS, seleção geográfica ou dispatcher full; o ensaio geográfico posterior está documentado ao final deste plano. iOS/APNs permanecem pendentes.

A chave ORS também está configurada. O adaptador real passou evitando um bloqueio fictício em Ribeirão Preto: 3.035,2 m e 432,8 s, conforme [docs/evidence/routes-live.json](docs/evidence/routes-live.json). Após o ajuste de acesso à rede do processo, a API retornou HTTP 200 com os mesmos valores, zero bloqueios ativos e nenhum novo relato; os 18 IDs anteriores foram preservados, conforme [docs/evidence/routes-api-live.json](docs/evidence/routes-api-live.json). O usuário confirmou que a rota apareceu no Android após os passos de origem/destino, conforme [docs/evidence/routes-phone-confirmation.json](docs/evidence/routes-phone-confirmation.json). Essa confirmação é humana, sem observação independente; os pontos e valores do percurso no celular não foram informados. Esses resultados não aprovam integralmente os critérios de push geográfico, proximidade ou duas plataformas.

No ensaio físico posterior, o usuário respondeu “tudo funcionou” ao roteiro de aquisição GPS, salvar um relato fictício offline, reabrir ainda offline e reconectar/reenviar. O banco demo passou de 18 para 19 relatos: um único UUID novo de via obstruída simulada ligado a um incidente com `report_count=1`, sem novo relato duplicado; um Android tinha posição e `accuracy_m` registradas, sem divulgar seus valores. A identificação usou o único novo registro em relação à baseline, pois a descrição não coincidiu exatamente com o marcador sugerido. [docs/evidence/android-physical-gps-offline.json](docs/evidence/android-physical-gps-offline.json) separa a confirmação humana da conferência do banco; não houve observação independente da tela, coordenadas ou precisão. Esse teste não incluiu movimento GPS ou FCM. As provas posteriores de aviso local manual e push geográfico full estão ao final do plano; movimento GPS físico, FCM em primeiro plano, telefone físico fora do raio, iOS/APNs permanecem pendentes. O relatório Word foi produzido; faltam o preenchimento efetivo da ficha e o ensaio.

## 12 Testes, documentação e apresentação

| Teste | Aceite |
| --- | --- |
| Offline e reinício | Relato permanece no SQLite e é enviado automaticamente após reconexão com app ativo |
| Resposta perdida após commit | Reenvio recupera o registro e não duplica relato/incidente |
| Worker/broker indisponível | API aceita relato durável; recuperação processa o acumulado |
| Retry/DLQ | Falha transitória repete com limite; mensagem inválida fica rastreável na DLQ e pode ser reprocessada |
| GeoHash e fronteira | Risco dentro do raio é recebido mesmo em célula vizinha; duas partições distribuem trabalho |
| Redis Cluster | Slots distribuídos, réplica promovida e cache reconstruído pelo banco |
| Consistência eventual | Banco/cache/clientes convergem para mesma versão; intervalo observado registrado |
| WebSocket bidirecional | Assinatura e confirmação; atualização no segundo cliente sem ação manual; recuperação após queda |
| Push | Recebimento geográfico comprovado separadamente em Android e iOS físicos |
| GPS/proximidade | Captura automática, fallback e entrada no raio; alertas não repetem indevidamente |
| Alagamento e Vias | Tipo/gravidade/horário/legenda presentes; relatos simulados identificados |
| Roteamento | Trajeto evita bloqueio; falta de alternativa/serviço é tratada |
| Docker/persistência | Ambiente sobe com healthchecks e mantém dados após reiniciar |
| Disponibilidade/recuperação | Interromper instância de serviço e banco principal; executar failover, verificar eventos confirmados e registrar tempo de recuperação |
| Duas plataformas | Compilar, instalar e executar os cenários em Android e iOS |

Executar carga crescente de teste e registrar volume, latência, fila acumulada, hardware e rede. Não inventar SLA ou alegar grandes volumes sem medição. Monitorar pendências da outbox, retries, DLQ e entregas de alerta. Persistência e reprocessamento reduzem perdas nos cenários testados; a entrega de push ao aparelho depende também de sistemas externos e permissões.

Relatório conforme a seção VI da proposta e manual UNIP: capa; índice; objetivo e motivação (1–2 páginas); introdução (2–4); fundamentos tecnológicos (4–8); plano de desenvolvimento (5–15); projeto e arquitetura (3–8); relatório de código (máximo 10); apresentação em funcionamento; bibliografia e ficha APS. Explicar a arquitetura realmente executada, parâmetros, fontes, simulações e limites.

Demonstração: GPS e relato; persistência offline/reinício; sincronização; processamento pelo broker; atualização no segundo aparelho e push; aviso de proximidade; filtros de alagamento e vias obstruídas; rota desviada; interrupção de worker/nó e recuperação; retry/DLQ e convergência do cache.

Entregar código, instruções, configurações de exemplo, migrações, fixtures identificadas, scripts de teste, evidências, APK Android, build iOS instalado/testado e vídeo de apoio. Registrar cada requisito como Validado somente depois da evidência correspondente; instalações e arquivos gerados não significam que o app completo está pronto.


## Validação de proximidade em 05/10/2026

A falha que apagava a faixa após sincronizar foi reproduzida e corrigida: aviso independente, fechamento próprio e expiração offline. Passaram 45 testes Flutter, análise estática e cenário no emulador Android com menu real do mapa/SQLite e API fake isolada. Saída/retorno, reabertura offline, nova versão e vencimento foram conferidos. O APK Firebase versão 1.0.0 (2) tem pacote/assinatura compatíveis para atualização. [PROXIMIDADE.md](docs/PROXIMIDADE.md) registra os limites: o usuário confirmou instalação desse build e aviso local com pontos manuais no mapa. Esse aviso local não comprova movimento GPS físico ou FCM; o teste geográfico separado está abaixo. Os critérios da proposta permanecem integrais.

## Ensaio geográfico full em 05/10/2026

No projeto isolado `ecopulse-fcm-test`, foi criado **um único relato fictício**, em uma grade de 0,01° próxima da referência manual, sem publicar coordenadas do celular. O POST retornou 201 e o replay idêntico 200. Ficaram um relato, um incidente, um evento de cada tipo na outbox, ambos publicados, e um processamento de risco e um de alertas. O Android com posição recente dentro do raio foi selecionado e teve uma entrega aceita pelo FCM. A prova do pipeline e da seleção está em [docs/evidence/geographic-push.json](docs/evidence/geographic-push.json).

O ensaio tinha três cadastros: Android físico dentro, web sintético dentro e web sintético fora. O web dentro ficou `unsupported`, sem chamada ao provedor; o web fora não foi selecionado nem teve entrega. Houve duas linhas de entrega (`accepted` e `unsupported`), com **somente um alerta enviado ao celular**. Não foram injetadas falhas/retries neste ensaio; as evidências anteriores do broker permanecem separadas.

Após confirmar o app em segundo plano, o usuário informou **“Recebi e o app abriu ao tocar”** no APK atual. [docs/evidence/geographic-push-phone-receipt.json](docs/evidence/geographic-push-phone-receipt.json) registra `human_user_in_chat`, sem observação independente do aparelho. Essa confirmação é separada do aceite FCM. O cenário valida o backend full e o recebimento Android dentro do raio em segundo plano; não testa um segundo telefone físico fora, GPS em movimento, FCM em primeiro plano ou iOS/APNs. Esses limites e o relatório formal APS permanecem pendentes.

## Atualização do escopo em 06/10/2026

Push em primeiro plano confirmado pelo usuário na versão +3. O mesmo Android,
em etapa distinta com GPS recente e APK +4 instalado conforme confirmação humana,
foi excluído fora do raio; risco e alertas processaram o relato fictício e não
criaram entrega para ele. O usuário confirmou nenhum novo recebimento. Carga
isolada de 1.000 relatos, cache coerente e replay passaram. O percurso físico
por GPS foi dispensado pela equipe sem execução; sua tarefa está encerrada como
dispensada, mantendo o limite de validação. iOS/APNs e múltiplos hosts seguem
adiados. As etapas restantes são conferência manual dos registros acadêmicos,
assinaturas e ensaio presencial de dez minutos. Não foram preenchidas horas reais
sem informação dos integrantes. Evidências em TESTES_FINAIS_ANDROID.md.



Atualização documental em 06/10/2026: responsabilidades definitivas e horas confirmadas pela equipe (Vitória 21 h, Alessandro 23 h, Augusto 30 h). A equipe também declarou aprovação manual de iOS/APNs e do deslocamento físico por GPS, além da conclusão das revisões finais. Esses resultados são confirmações humanas, sem novos logs ou observação independente; datas de execução e detalhes do iPhone/APNs não foram informados. O relatório conserva as datas das provas técnicas e mantém assinaturas em branco. Registro: docs/evidence/academic-team-confirmation-20261006.json.
