# Plano de execução do EcoPulse com interface simples

Entregar até **30/10/2026** um protótipo acadêmico do EcoPulse para **Android e iOS**, com demonstração em **Ribeirão Preto** e trabalho dividido entre três desenvolvedores.

Esta revisão integra ao plano todos os requisitos de sistemas distribuídos, funcionalidades mobile e tecnologias confirmados pelo usuário. A referência é [Proposta_APS_DSD_EcoPulse.docx](<C:/Users/usuario/Desktop/APS APP/Proposta_APS_DSD_EcoPulse.docx>), especialmente as seções III, IV e V. Substitui a versão que previa somente uma API com SQLite no servidor.

**Diretriz:** manter duas telas principais, linguagem clara e visual discreto, com a arquitetura necessária para demonstrar os requisitos da disciplina. A simplicidade será aplicada à interface, às regras e ao tamanho da demonstração. Todos os itens da matriz abaixo fazem parte da entrega; GPS, WebSocket e push deixam de ser opcionais.

A inclusão neste documento significa **Planejado**, não Implementado ou Validado. O estado atual por requisito está em [docs/REQUISITOS.md](docs/REQUISITOS.md), com resultados em [docs/VALIDACAO.md](docs/VALIDACAO.md). Simulação deve ser identificada separadamente e não comprova uma integração real.

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
| Qualidade do ar | Camada AQI com escala, origem e validade | Consulta da fonte e apresentação rastreável |
| Ilhas de calor | Camada geográfica de calor com origem, data e legenda | Áreas apresentadas; simulações identificadas |
| Relato colaborativo | Validação, GPS pontual e metadados | Captura automática e fallback quando a permissão é negada |
| Proximidade e roteamento | Entrada no raio do risco e rota evitando incidentes conhecidos | Alerta de proximidade e trajeto sem interseção com bloqueio |
| Offline-first | SQLite local, fila persistente e envio ao recuperar conexão | Reinício não perde pendências; reconexão inicia sincronização |
| Backend em Docker | FastAPI e workers conteinerizados com Compose | Ambiente sobe por comando documentado e preserva volumes |
| Disponibilidade e recuperação | Serviços redundantes, réplica PostgreSQL e failover controlado | Falha de instância e recuperação testadas, com tempo e estado dos dados registrados |
| Duas plataformas | Projeto Flutter com configurações e testes separados | Instalação e cenários comprovados em Android e iOS |

## 2 Interface simples e humanizada

Usar cores discretas, componentes nativos do Flutter, fonte padrão legível, ícones comuns e textos em português. Evitar dashboards, estatísticas decorativas, animações elaboradas e excesso de telas.

**Tela principal:** mapa de Ribeirão Preto; seleção das camadas Alagamentos, Obstruções, Ar e Calor; legenda; lista acessível de ocorrências; indicador de pendências e botão Reportar. Detalhes, preferências de alerta, configuração de servidor e seleção de destino ficam em painéis pequenos sobre essa tela.

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

## 7 Camadas ambientais e roteamento

Todas as quatro camadas são obrigatórias no app. Exibir origem, horário, validade e legenda. Relatos incluem alagamento e via obstruída; manchas/zonas refletem a regra documentada.

**AQI:** implementar um adaptador para uma fonte verificada que atenda Ribeirão Preto, com escala explícita. Open-Meteo Air Quality pode ser avaliado como fonte de dados modelados; informar o modelo/origem e não rotular seus resultados como medição de uma estação local. [Documentação da Air Quality API](https://open-meteo.com/en/docs/air-quality-api).

**Calor:** usar conjunto geoespacial de áreas de calor com origem e data verificáveis. Uma temperatura meteorológica única não comprova ilha de calor urbana. A identificação de fonte adequada deve ocorrer no primeiro marco.

Fixtures de AQI/calor ficam disponíveis para desenvolver e ensaiar, com o rótulo permanente “Dados simulados para demonstração”. Isso testa a interface e a cadeia de eventos, não comprova monitoramento ambiental real. Se somente simulação for possível, registrar o item real como pendente e conferir sua aceitação na avaliação; não marcar como Validado por existir uma camada fictícia.

**Rotas:** escolher destino no mapa, enviar origem/destino à API e calcular rota que evita polígonos de incidentes ativos. Guardar a chave do provedor no servidor, validar geometrias/limites e testar indisponibilidade, origem dentro de bloqueio e ausência de alternativa. Verificar que o trajeto não intersecta os bloqueios. Não remover exclusões silenciosamente para obter uma resposta. Usar “Rota alternativa evitando ocorrências registradas”. [Opções do OpenRouteService](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options).

## 8 GPS, tempo real, push e offline

Capturar GPS pontualmente ao criar o relato, com permissão, horário e precisão quando disponível. O ponto manual é fallback. Para proximidade com app ativo, acompanhar mudanças de posição e testar entrada/saída do raio, validade e supressão de alertas repetidos.

WebSocket permite enviar a assinatura/área de interesse e receber confirmação; o servidor envia alterações de incidentes. Reconexão inclui consulta REST para recuperar eventos perdidos. Atualizar continua como apoio, sem substituir a atualização automática.

Push é implementado por FCM/APNs, com registro/renovação de token, seleção geográfica e expiração. Em segundo plano, usar área escolhida ou última localização válida, com horário; não presumir GPS continuamente atualizado. Android e iOS físicos devem receber uma notificação de teste. FCM aceito pelo servidor não comprova recebimento no aparelho. [Configuração FCM para Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

Salvar o relato no SQLite antes de enviar. Ao recuperar conectividade com app ativo, sincronizar automaticamente; também retomar ao abrir/voltar ao app. A conectividade é um sinal para tentar: confirmar alcance da API. Tarefas oportunistas de fundo podem ajudar, mas a execução é controlada pelo sistema operacional e não tem prazo imediato garantido.

Não apagar pendências ao atualizar: mesclar por UUID. Timeout, GET vazio, reinício e falha de envio preservam dados locais. Usar um único processo de sincronização por aparelho. Marcar Enviado somente após confirmação. O offline cobre relatos e dados consultados; novas áreas do mapa e novas rotas dependem de rede.

## 9 Contratos de API e eventos

Definir no primeiro marco: POST /v1/relatos; GET /v1/incidentes/ativos; GET /v1/camadas/ambientais; POST /v1/rotas; PUT /v1/dispositivos/push; atualização de posição/área de interesse; GET /health; WebSocket /v1/ws.

Relato: UUID, tipo, gravidade, latitude, longitude, origem da posição, precisão quando disponível, descrição opcional, occurred_at e indicador de demonstração. O servidor acrescenta received_at e GeoHash. Usar UTC/ISO 8601 no transporte, horário local na interface e nomes explícitos das coordenadas.

Evento: event_id, schema_version, tipo, aggregate_id, aggregate_version, occurred_at, region_id, trace_id e payload. Tipos iniciais: relato.criado, incidente.criado, incidente.atualizado, incidente.expirado, camada.atualizada e notificacao.solicitada.

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
| **03–05/10** | Contratos, estrutura, fontes ambientais, prova de rotas, Docker disponível e acesso macOS/iPhone/credenciais encaminhado |
| **06–11/10** | Fluxo GPS/SQLite → API/PostGIS/outbox → RabbitMQ → worker → mapa; duas partições/workers e perfil cluster iniciados |
| **12–18/10** | Regras, retries/DLQ, Redis, WS, push Android/iOS, proximidade e reconexão automática |
| **19–23/10** | Quatro camadas e rotas integradas; cluster, balanceamento, réplica PostgreSQL e failover controlado demonstrados |
| **24–27/10** | Matriz de testes nas plataformas, carga controlada, correções, evidências e relatório; escopo congelado |
| **28–29/10** | Builds instalados, ensaio, vídeo de apoio e pacote final |
| **30/10** | Entrega e apresentação; reserva para falhas críticas |

O escopo aumentou; a estimativa anterior de 90–130 horas deixa de valer. Reestimar após as provas do primeiro marco, por tarefa e disponibilidade real dos três integrantes. O cronograma é uma meta de execução com risco elevado, especialmente para iOS, push, fontes ambientais e cluster. Dependências sem acesso devem aparecer como pendentes, sem transformar requisito obrigatório em opcional.

## 11 Dependências que precisam ser resolvidas

A equipe informou que não dispõe de Mac nem iPhone. Obter acesso a macOS/Xcode, assinatura, aparelho físico e conta/capabilities necessárias para APNs. Fazer uma primeira execução e prova de push cedo. Flutter compartilhado não valida iOS. [Configuração iOS](https://docs.flutter.dev/platform-integration/ios/setup).

Na auditoria de 03/10, Docker Desktop foi localizado fora do PATH e o cluster completo executou testes reais de processamento, replicação e falha de nós. Os scripts passaram a localizar essa instalação. Resultados e limites ficam em [docs/VALIDACAO_INFRA.md](docs/VALIDACAO_INFRA.md); a execução no mesmo notebook não comprova sobrevivência à perda do host.

Resolver Firebase/APNs, chave do provedor de rotas e fontes ambientais. Não inserir segredos no código. Eventuais contas, contratações ou equipamentos dependem de acesso providenciado pela equipe. Enquanto isso, mocks identificados permitem construir partes independentes, mantendo as integrações reais como pendentes.

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
| Quatro camadas | Origem/horário/legenda presentes; simulação visível e separada de dados reais |
| Roteamento | Trajeto evita bloqueio; falta de alternativa/serviço é tratada |
| Docker/persistência | Ambiente sobe com healthchecks e mantém dados após reiniciar |
| Disponibilidade/recuperação | Interromper instância de serviço e banco principal; executar failover, verificar eventos confirmados e registrar tempo de recuperação |
| Duas plataformas | Compilar, instalar e executar os cenários em Android e iOS |

Executar carga crescente de teste e registrar volume, latência, fila acumulada, hardware e rede. Não inventar SLA ou alegar grandes volumes sem medição. Monitorar pendências da outbox, retries, DLQ e entregas de alerta. Persistência e reprocessamento reduzem perdas nos cenários testados; a entrega de push ao aparelho depende também de sistemas externos e permissões.

Relatório conforme a seção VI da proposta e manual UNIP: capa; índice; objetivo e motivação (1–2 páginas); introdução (2–4); fundamentos tecnológicos (4–8); plano de desenvolvimento (5–15); projeto e arquitetura (3–8); relatório de código (máximo 10); apresentação em funcionamento; bibliografia e ficha APS. Explicar a arquitetura realmente executada, parâmetros, fontes, simulações e limites.

Demonstração: GPS e relato; persistência offline/reinício; sincronização; processamento pelo broker; atualização no segundo aparelho e push; aviso de proximidade; camadas AQI/calor/obstrução; rota desviada; interrupção de worker/nó e recuperação; retry/DLQ e convergência do cache.

Entregar código, instruções, configurações de exemplo, migrações, fixtures identificadas, scripts de teste, evidências, APK Android, build iOS instalado/testado e vídeo de apoio. Registrar cada requisito como Validado somente depois da evidência correspondente; instalações e arquivos gerados não significam que o app completo está pronto.
