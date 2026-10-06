# Relatório APS — EcoPulse

UNIP — UNIVERSIDADE PAULISTA

CIÊNCIA DA COMPUTAÇÃO
8º SEMESTRE

Vitória Pandolfo Marturano
RA: RA-OMITIDO — Turma: CC8P18

Alessandro Damázio Pereira
RA: RA-OMITIDO — Turma: CC8Q18

Augusto Flávio Murari
RA: RA-OMITIDO — Turma: CC8P18

ECOPULSE

Plataforma distribuída móvel para monitoramento colaborativo
de riscos ambientais urbanos e qualidade do ar

Atividades Práticas Supervisionadas
Desenvolvimento de Sistemas Distribuídos

RIBEIRÃO PRETO
2026

Vitória Pandolfo Marturano

Alessandro Damázio Pereira

Augusto Flávio Murari

ECOPULSE

Plataforma distribuída móvel para monitoramento colaborativo
de riscos ambientais urbanos e qualidade do ar

Relatório das Atividades Práticas Supervisionadas apresentado ao curso de Ciência da Computação da Universidade Paulista — UNIP, no 8º semestre de 2026/2, relacionado à disciplina Desenvolvimento de Sistemas Distribuídos.

Professor: Jean Miler Scatena

RIBEIRÃO PRETO
2026

## RESUMO

Este trabalho apresenta o EcoPulse, um protótipo acadêmico de aplicação móvel distribuída para compartilhar ocorrências ambientais urbanas em Ribeirão Preto. A solução reúne relatos de alagamento e obstrução de vias, qualidade do ar modelada, temperatura histórica de superfície e rotas que consideram incidentes registrados. O aplicativo utiliza Flutter e armazenamento local; o backend reúne FastAPI, PostgreSQL/PostGIS, RabbitMQ e Redis Cluster. A arquitetura orientada a eventos separa recepção, processamento de risco e alertas. Transações, outbox, identificação única e versões sustentam reenvio e recuperação de falhas. A avaliação inclui recuperação de componentes, convergência de dados e carga isolada de 1.000 relatos fictícios. Em Android, foram confirmados push em primeiro e segundo plano, seleção geográfica fora do raio e proximidade por pontos manuais. A equipe também confirmou aprovação de iOS/APNs e deslocamento físico por GPS em validações manuais. Os resultados demonstram um protótipo funcional em infraestrutura local e relacionam os conceitos de sistemas distribuídos ao fluxo de colaboração urbana. O alcance dos ensaios e a procedência das informações ambientais delimitam sua utilização acadêmica.

Palavras-chave: Sistemas distribuídos; Aplicação móvel; Arquitetura orientada a eventos; Geoprocessamento; Monitoramento colaborativo.

Consolidação dos registros: 06 de outubro de 2026.
Prazo de entrega acadêmica: 30 de outubro de 2026.

## SUMÁRIO

1 OBJETIVO E MOTIVAÇÃO	5

2 INTRODUÇÃO	6

2.1 Informação urbana e colaboração	6

2.2 Recorte, método e organização do trabalho	7

3 FUNDAMENTOS DAS TECNOLOGIAS ESCOLHIDAS	8

3.1 Flutter, localização e persistência no aparelho	8

3.2 FastAPI, PostgreSQL e PostGIS	9

3.3 RabbitMQ, Redis e processamento distribuído	10

3.4 WebSocket, push, rotas e fontes ambientais	11

4 PLANO DE DESENVOLVIMENTO DA APLICAÇÃO	13

4.1 Requisitos, entregas e critérios de aceite	13

4.2 Planejamento da interação e do fluxo móvel	14

4.3 Etapas técnicas e divisão de responsabilidades da equipe	15

4.4 Conclusão das etapas e entrega	16

4.5 Estratégia de validação e controle de mudanças	16

## SUMÁRIO (CONTINUAÇÃO)

5 PROJETO E ARQUITETURA DO PROGRAMA	18

5.1 Componentes e circulação de um relato	18

5.2 Modelo de dados, contratos e consistência	19

5.3 Topologias, recuperação e limites arquiteturais	20

6 RELATÓRIO DE CÓDIGO	22

6.1 Organização e validação dos contratos	22

6.2 Outbox, confirmação e tratamento de falhas	23

6.3 Fila local e reconciliação de relatos	24

6.4 Proximidade, versões e dados ambientais	25

7 FUNCIONAMENTO E RESULTADOS	26

7.1 Percurso demonstrável no aplicativo	26

7.2 Resultados de processamento e recuperação	27

7.3 Push geográfico e validação manual	28

8 CONSIDERAÇÕES FINAIS	30

REFERÊNCIAS	31

APÊNDICE A — REGISTRO DE ATIVIDADES APS	33

APÊNDICE B — ARQUITETURA E TELAS	34

## 1 OBJETIVO E MOTIVAÇÃO

O objetivo geral do EcoPulse é desenvolver e demonstrar uma aplicação móvel integrada a um sistema distribuído para registrar, processar e apresentar informações ambientais urbanas. O recorte territorial é Ribeirão Preto, com entrega acadêmica em 30 de outubro de 2026. O projeto relaciona comunicação assíncrona, persistência, particionamento e recuperação de falhas a uma situação cotidiana: encontrar uma ocorrência no caminho e compartilhar sua localização.

A motivação é reunir informações dispersas sobre alagamentos e vias obstruídas. Uma pessoa pode conhecer um problema enquanto outra segue sem essa informação. O mapa colaborativo organiza relatos por posição e horário e oferece rotas que consideram as ocorrências registradas. A cobertura e a atualização dependem dos participantes. O protótipo é acadêmico e não se apresenta como serviço oficial de emergência ou certificação das condições de uma via.

Os objetivos específicos incluem salvar relatos antes do envio, recuperar pendências após reabertura, evitar duplicação no reenvio e processar eventos de forma assíncrona. Incluem ainda quatro camadas ambientais, WebSocket, push geográfico e recuperação de componentes. Fonte e data acompanham o AQI modelado e a aquisição histórica de temperatura da superfície, preservando o significado de cada informação.

O interesse acadêmico está em observar decisões que alteram a confiabilidade do conjunto. Uma resposta perdida exige repetição segura; um worker parado exige persistência até a retomada; um cache indisponível exige consulta à referência durável. O relatório descreve evidências até 06 de outubro de 2026 e distingue implementação, testes, confirmação humana e aprovação manual declarada pela equipe. As conclusões permanecem vinculadas ao que foi demonstrado.

## 2 INTRODUÇÃO

### 2.1 Informação urbana e colaboração

A informação ambiental urbana possui características que dificultam seu tratamento por uma única tela ou fonte. Um alagamento pode surgir em um trecho específico, uma obstrução pode ser temporária e uma estimativa de qualidade do ar pode representar uma área muito maior que o bairro exibido no mapa. Essas diferenças envolvem localização, tempo e forma de obtenção. O EcoPulse reúne os dados em uma interface comum, mas conserva sua procedência e seu significado. A proximidade visual entre camadas não torna equivalentes um relato colaborativo, uma previsão atmosférica e uma imagem de satélite.

O dispositivo móvel participa do projeto como cliente e como origem de relatos. A pessoa seleciona o tipo de ocorrência, informa uma gravidade e usa uma posição obtida por GPS ou escolhida manualmente. A aplicação associa um identificador e um horário ao registro. Não há necessidade de digitar uma descrição extensa para concluir a operação. Essa redução de esforço é importante porque o relato pode ocorrer durante um deslocamento ou em uma conexão instável. O mesmo dispositivo também consulta incidentes, recebe atualizações e pode ser selecionado para uma notificação conforme sua última referência geográfica válida.

A colaboração precisa de regras explícitas. O protótipo agrupa relatos próximos e recentes, separa dados fictícios de dados não marcados como demonstração e conserva o vínculo de cada relato com o incidente resultante. Três instalações diferentes, dentro da janela de dez minutos e da distância configurada de 200 metros, podem elevar o estado para colaborativo. Esse critério é uma escolha de engenharia para o trabalho acadêmico. Instalações distintas não comprovam pessoas distintas, e concordância entre relatos não substitui verificação de campo. A gravidade continua sendo uma informação fornecida pelo participante.

A proposta original relaciona o tema aos desafios ambientais de grandes centros e solicita uma aplicação distribuída com comunicação em tempo real e tolerância a falhas. O planejamento local transforma essa direção em funcionalidades verificáveis. A interface concentra mapa, filtros, legenda, ocorrências e pendências na tela principal, com um formulário separado para o relato. Informações de origem, validade e demonstração aparecem junto aos dados. Assim, a simplicidade da interação resulta de organizar o conteúdo e reduzir passos, enquanto a infraestrutura mantém a complexidade necessária ao estudo de sistemas distribuídos.

### 2.2 Recorte, método e organização do trabalho

O desenvolvimento adotou um método incremental: definir contratos, construir um fluxo completo, verificar seu comportamento e ampliar as integrações. O fluxo inicial conecta relato persistido no aparelho, API e incidente. Em seguida, foram incorporados broker, cache, comunicação ao vivo, fontes ambientais, rotas e push. Essa sequência permitiu localizar problemas por etapa e verificar cada integração.

A avaliação reúne registros técnicos de 03 a 06 de outubro de 2026 e validações manuais da equipe. A documentação do repositório relaciona requisitos, implementação, ensaios e fontes ambientais. Os integrantes confirmaram a aprovação de iOS/APNs, deslocamento físico por GPS e revisões finais. Essa declaração foi consolidada em 06/10/2026, sem atribuir a data à execução dos testes. As datas individuais, o modelo do iPhone e os detalhes do recebimento via APNs não constam dos registros fornecidos. A declaração da equipe é a fonte desses resultados, distinta dos registros instrumentados.

As verificações combinaram testes de regras e interface, navegador, emulador, chamadas reais a provedores e validações em aparelho. Cada modalidade possui alcance próprio. Os testes controlados verificaram o tratamento de falhas; o recebimento de push e a abertura por toque foram confirmados separadamente no Android. O aceite do Firebase e o recebimento no telefone constituem etapas diferentes. Os resultados identificam ambiente e fonte para permitir sua análise.

O relatório apresenta fundamentos, desenvolvimento, arquitetura, código e resultados. A execução em um único notebook permitiu observar comunicação entre serviços, persistência e recuperação de falhas controladas. O recorte relaciona requisitos, decisões e resultados, mantendo os limites da infraestrutura e dos dados ambientais.

## 3 FUNDAMENTOS DAS TECNOLOGIAS ESCOLHIDAS

### 3.1 Flutter, localização e persistência no aparelho

Flutter foi escolhido para compartilhar a maior parte do código de interface e comportamento entre Android e iOS. O framework organiza a interface em widgets e utiliza Dart como linguagem. No EcoPulse, modelos, serviços e controle de estado ficam separados das telas, facilitando a substituição de dependências em testes. A documentação oficial apresenta as diferenças de configuração e integração por plataforma, o que sustenta uma distinção importante: compartilhar código reduz trabalho duplicado, mas não elimina a necessidade de compilar, instalar e verificar cada sistema operacional (Flutter, s.d.a).

O mapa utiliza flutter_map e uma base cartográfica associada ao OpenStreetMap. Pontos, polígonos e linhas representam relatos, incidentes, dados ambientais e rotas. A aplicação transporta geometrias em GeoJSON e mantém as coordenadas de latitude e longitude explícitas nos modelos. Essa organização evita uma inversão frequente entre APIs de mapa e contratos geográficos. A legenda esclarece o tipo de elemento e o estado de demonstração. O mapa funciona como meio de consulta e seleção; a lista de ocorrências oferece uma alternativa para reconhecer informações sem depender somente da leitura espacial.

A obtenção de posição utiliza geolocator. Uma posição contém origem, horário e precisão quando disponível. O pedido de permissão pode ser negado, o serviço de localização pode estar desligado e a aquisição pode falhar. O ponto manual permite completar o relato nesses casos. A referência geográfica da aplicação também pode acompanhar atualizações com o aplicativo ativo. O projeto não implementa rastreamento permanente em segundo plano. Logo, a última posição enviada ao servidor é uma referência datada, cuja validade precisa ser considerada na seleção de destinatários.

SQLite, acessado no cliente nativo por sqflite, mantém a fila local e os dados consultados. Sua função é preservar informações quando a rede falha ou a aplicação fecha. O relato é gravado antes da tentativa HTTP, e a confirmação também é persistida antes de remover o indicador de pendência. A conectividade apenas motiva uma nova tentativa; ela não garante acesso à API. O aplicativo sincroniza ao recuperar conexão enquanto está ativo ou ao abrir e retomar. A versão web usa armazenamento do navegador e, portanto, seu teste offline não comprova SQLite nativo. As provas Android e web precisam permanecer separadas. A persistência local utiliza a abordagem documentada para SQLite (Flutter, s.d.b).

### 3.2 FastAPI, PostgreSQL e PostGIS

FastAPI fornece a camada HTTP do backend em Python. Os contratos são definidos por modelos que validam tipos, campos e restrições antes da execução das regras de negócio. Essa validação é útil para impedir coordenadas inválidas, horários sem fuso e categorias inexistentes. A documentação gerada a partir dos modelos ajuda a alinhar o aplicativo, os scripts e os serviços. As rotinas de persistência e domínio permanecem em módulos compartilhados, permitindo exercitá-las diretamente sem repetir toda a comunicação HTTP em cada teste (FastAPI, s.d.).

PostgreSQL é o estado principal do ambiente distribuído. Relatos, incidentes, observações ambientais, eventos pendentes e controles de processamento são armazenados de forma durável. A transação permite registrar o relato e o evento da outbox como uma única operação. Se a transação falhar, nenhum dos dois fica confirmado isoladamente. Esse vínculo enfrenta o problema de salvar no banco e publicar no broker em ações independentes, nas quais uma falha intermediária poderia deixar dados sem processamento. O banco também mantém os registros usados para reconhecer reenvios e eventos já processados (PostgreSQL Global Development Group, s.d.a).

PostGIS acrescenta tipos, funções e índices espaciais ao PostgreSQL. O EcoPulse utiliza pontos e polígonos com referência EPSG:4326. A ordem de coordenadas do GeoJSON é longitude e latitude. Para comparar distâncias em metros, as consultas utilizam geography quando adequado, como no predicado ST_DWithin. Essa escolha evita tratar graus como se fossem metros. Índices espaciais reduzem o conjunto de candidatos, e a regra de negócio completa a avaliação. Um círculo de influência construído a partir de um relato indica a área adotada pelo protótipo; não corresponde ao levantamento do contorno real de uma inundação (PostGIS Project, s.d.).

A replicação PostgreSQL foi incluída no perfil de demonstração da infraestrutura, com uma réplica assíncrona e promoção controlada. O modo assíncrono exige cuidado na interpretação dos resultados: uma réplica pode estar atualizada no instante observado e ainda existir risco de atraso em outra situação. No ensaio registrado, os escritores foram pausados, a posição de replicação foi conferida e o primário anterior foi isolado antes da promoção. Esse procedimento demonstra recuperação planejada. Não permite declarar perda zero para qualquer falha inesperada ou independência da máquina que hospeda todos os contêineres. A documentação descreve as condições da replicação e promoção (PostgreSQL Global Development Group, s.d.b).

### 3.3 RabbitMQ, Redis e processamento distribuído

RabbitMQ transporta os eventos entre serviços. A API pode confirmar a persistência do relato antes de o worker concluir a agregação. Esse desacoplamento reduz a dependência entre a interação do usuário e o tempo de processamento posterior. As filas do projeto são duráveis, as mensagens são persistentes e a publicação usa confirmação do broker. O consumidor reconhece a entrega somente depois de concluir o efeito necessário. As filas de quorum, distribuídas em três nós no ensaio completo, acrescentam replicação à mensageria (RabbitMQ, s.d.c).

A confirmação de publicação e o reconhecimento de consumo são etapas diferentes. Se o publicador confirmar no broker e falhar antes de marcar a outbox, poderá publicar novamente. Se o consumidor persistir o resultado e perder a conexão antes do reconhecimento, poderá receber novamente. O projeto assume essas repetições e usa identificadores de evento e registros por consumidor para neutralizar efeitos duplicados. Falhas transitórias recebem tentativas limitadas com espera crescente. Mensagens inválidas ou tentativas esgotadas seguem para a DLQ, mantendo material rastreável para investigação e reprocessamento controlado. Esses mecanismos seguem confirmações e dead lettering do broker (RabbitMQ, s.d.a, s.d.b).

Redis Cluster mantém cópias de incidentes e observações ambientais e distribui mensagens entre instâncias da API. O perfil completo utiliza três primários e três réplicas, com os 16.384 slots do cluster. O cliente precisa lidar com redirecionamentos para o nó responsável por uma chave. Versões permitem comparar um evento recebido com o conteúdo já armazenado; uma operação atômica impede que uma mensagem antiga substitua uma versão mais recente. A validade restante determina o TTL. O PostgreSQL conserva a referência durável e permite reconstruir o cache (Redis, s.d.).

A consistência eventual aparece quando banco, cache e clientes refletem uma atualização em momentos diferentes e depois convergem. Isso não significa aceitar regressão de versão ou perda de pendências. O GeoHash organiza regiões e auxilia a atribuição de eventos a filas. A partição é derivada de forma estável, e os dois workers do perfil completo consomem as filas, permitindo continuidade quando um deles para. Trata-se de distribuição de processamento. O banco PostgreSQL permanece centralizado; o trabalho não realizou fragmentação física dos dados em servidores independentes. A consulta espacial considera células vizinhas e confirma a distância real, evitando usar a célula isolada como limite do raio.

### 3.4 WebSocket, push, rotas e fontes ambientais

WebSocket mantém um canal bidirecional entre cliente e servidor. O aplicativo envia a assinatura de uma área e recebe confirmação, além de atualizações dos incidentes. Redis Pub/Sub permite que instâncias distintas da API distribuam o mesmo evento aos clientes conectados. Esse canal não constitui uma fila durável por usuário. Depois de uma desconexão, a consulta REST recupera o estado atual. O push pelo Firebase Cloud Messaging atende outro contexto: avisar o aparelho inclusive quando a aplicação está em segundo plano, conforme permissões e condições da plataforma (Firebase, s.d.).

O token push identifica um destino no provedor e precisa ser registrado e renovado. A seleção geográfica depende da posição válida armazenada pelo backend. O projeto admite uma referência GPS ou manual recente, sem presumir rastreamento contínuo. No iOS, a integração também envolve APNs e recursos próprios de configuração e assinatura. A documentação Firebase orienta esses passos, mas testes de funções controladas não comprovam entrega real. No Android, a aceitação pelo FCM e a confirmação de recebimento pela equipe são evidências complementares, registradas separadamente (Firebase, s.d.; Flutter, s.d.c).

OpenRouteService calcula trajetos a partir de origem e destino. Seu adaptador recebe as exclusões derivadas dos incidentes ativos e valida o resultado. As opções de roteamento permitem considerar polígonos a evitar, mas o provedor pode não encontrar alternativa ou ficar indisponível. O aplicativo apresenta esse resultado como rota alternativa evitando ocorrências registradas. A chave permanece no backend, e as exclusões não são retiradas silenciosamente apenas para obter uma linha no mapa. A validação de interseções complementa a resposta do serviço (OpenRouteService, s.d.).

A camada AQI consulta Open-Meteo, com informação atmosférica modelada CAMS em grade de aproximadamente 45 quilômetros. Sua escala e origem devem acompanhar o valor apresentado; ele não representa medição de uma estação no bairro (Open-Meteo, s.d.). O calor utiliza o produto Landsat Collection 2 de temperatura da superfície, com aquisição em 17 de setembro de 2025. As conversões e máscaras seguem a documentação USGS, enquanto os critérios de seleção de células são escolhas acadêmicas. Uma cena histórica mostra contraste espacial naquele momento e não comprova calor atual, temperatura do ar ou ilha de calor climatológica (USGS, s.d.).

## 4 PLANO DE DESENVOLVIMENTO DA APLICAÇÃO

### 4.1 Requisitos, entregas e critérios de aceite

O plano de desenvolvimento transforma a proposta APS em entregas observáveis. A documentação inicial foi revisada para incluir PostgreSQL/PostGIS no servidor, mensageria distribuída, Redis Cluster, GPS, WebSocket e push como requisitos do protótipo. A simplicidade da interface orienta a utilização, mas não retira as exigências da disciplina. Cada item recebe um estado e uma evidência correspondente na matriz REQUISITOS.md. O termo planejado indica intenção; implementado indica existência de código; validado exige um cenário executado que sustente a conclusão.

Os critérios foram definidos para alcançar resultados específicos, como preservar uma pendência após reinício, receber o mesmo evento em dois clientes ou recuperar uma publicação após parar um worker. A avaliação acompanhou a integração do aplicativo com os serviços e os provedores. A seleção geográfica de um dispositivo, o aceite pelo Firebase e o recebimento no aparelho foram verificados separadamente. A tabela sintetiza os grupos de entrega; os cenários e resultados são detalhados na seção de funcionamento e na documentação de validação.

| Grupo | Entrega | Critério de aceite |
| --- | --- | --- |
| Aplicativo | Mapa, relato e quatro camadas | Fonte, horário, legenda e simulação visíveis |
| Persistência | Fila local e reenvio | Reabertura preserva UUID e envio não duplica |
| Eventos | Outbox, RabbitMQ e workers | Persistência continua com processamento parado |
| Comunicação | WebSocket e push por raio | Atualização automática e recepção por plataforma |
| Geografia | Partições e rotas | Fronteiras cobertas e trajeto evita bloqueio |
| Recuperação | Nós redundantes e cache | Falhas controladas e versões conferidas |

As entregas finais incluem código, configurações de exemplo, instruções de execução, fontes e fixtures identificadas, scripts de validação, registros sanitizados, build Android e a validação iOS declarada pela equipe. O relatório e a ficha APS completam o pacote acadêmico. Não se planejou login com senha, reputação, envio de vídeos, painel administrativo completo ou navegação curva a curva, porque essas funcionalidades não são dependências dos requisitos definidos. Essa delimitação concentra o esforço nos fluxos distribuídos e nas provas de funcionamento, mantendo explícito o escopo definido.

### 4.2 Planejamento da interação e do fluxo móvel

A aplicação foi planejada em torno de duas telas principais. A primeira concentra mapa, seleção de camadas, legenda, lista de ocorrências e situação da sincronização. A segunda reúne os campos do relato. Detalhes, configurações do servidor e destino de rota aparecem em painéis associados à tela principal. Essa organização evita exigir que a pessoa navegue por várias páginas para entender o que está perto ou registrar um problema. Textos em português, ícones conhecidos e cores discretas acompanham os estados do sistema sem esconder dados pendentes.

O fluxo de relato começa pela escolha de posição. O botão flutuante solicita automaticamente a localização GPS e pode alterar a referência global usada pela aplicação. Já a opção “Relatar uma ocorrência aqui”, no menu do mapa, preserva o ponto escolhido manualmente para aquele formulário. Essa diferença é relevante tanto para a experiência quanto para os ensaios: selecionar um ponto no mapa permite controlar o cenário sem atribuí-lo ao deslocamento físico do aparelho. A interface informa a origem da posição e permite corrigir o local antes de salvar.

Depois de validar tipo, gravidade e campos, o relato é persistido localmente. A mensagem de sucesso distingue salvar no aparelho de confirmar no servidor. Sem conexão, a pendência continua disponível após reabertura. Com o aplicativo ativo, a reconexão inicia nova tentativa; a retomada também solicita sincronização. Um processo único evita que diferentes gatilhos enviem a mesma fila simultaneamente. Como a internet pode estar acessível sem que a API responda, falhas e timeouts preservam o registro. O UUID permanece estável em todas as tentativas.

O aviso local de proximidade foi planejado como uma faixa independente das mensagens de sincronização ou rota. Seu conteúdo considera o ponto de referência, a distância de um quilômetro, a validade do incidente e a versão já avisada. O fechamento, a saída da área e o vencimento possuem comportamentos próprios. O push é outro fluxo, executado no servidor, com raio de dispositivo e influência do incidente. Manter os dois conceitos separados ajuda a interpretar um teste manual da faixa sem concluir que houve push ou movimento GPS. O offline cobre relatos e dados previamente consultados; novos tiles e novas rotas continuam dependentes de rede. Quando as ruas do mapa não carregam, a interface orienta a usar a lista ou os pontos de exemplo do formulário. Essa alternativa permite consultar os registros disponíveis e preparar um relato simulado sem depender do fundo cartográfico.

### 4.3 Etapas técnicas e divisão de responsabilidades da equipe

A primeira etapa técnica define os contratos de relato, incidente, observação ambiental e evento. Em seguida, o fluxo atravessa cliente, API, banco, outbox, broker e worker. Essa sequência cria uma base para agregar relatos e apresentar resultados antes de acrescentar notificações e rotas. A integração frequente reduz a chance de cada parte funcionar apenas com dados próprios. Os contratos compartilhados delimitam nomes, tipos, horários e versões, e os testes verificam o comportamento das fronteiras entre componentes.

Vitória, Alessandro e Augusto organizaram as responsabilidades conforme os objetivos técnicos do projeto. A integração, a revisão e a documentação envolveram os três integrantes. A tabela apresenta a atuação principal de cada responsável e os pontos de colaboração. O Apêndice A consolida o registro de participação e a carga horária confirmada pela equipe.

| Responsável | Atuação principal | Apoio |
| --- | --- | --- |
| Vitória Pandolfo Marturano | Interface Flutter, formulário, detalhes e fluxo de rota | Textos, revisão do relatório e evidências visuais |
| Alessandro Damázio Pereira | Mapa, GPS, SQLite, sincronização e comunicação móvel | Validação móvel em Android e iOS/APNs |
| Augusto Flávio Murari | FastAPI, PostGIS, RabbitMQ, Redis, workers e provedores | Docker, contratos e diagnóstico de integrações |
| Equipe | Integração, revisão e rastreabilidade | Documentação e verificação ponta a ponta |

A organização por módulos reduziu conflitos de integração, enquanto as revisões cruzadas acompanharam as mudanças nos contratos. A outbox exigiu coordenação entre persistência e consumo dos eventos; o push reuniu configuração móvel, cadastro do dispositivo, seleção geográfica e comunicação com o provedor. A equipe conferiu esses fluxos completos e relacionou os resultados à documentação. O registro de participação consolida as atividades realizadas e as horas confirmadas pelos integrantes.

### 4.4 Conclusão das etapas e entrega

O desenvolvimento foi organizado em implementação, integração, validação e revisão. A equipe concluiu as etapas previstas para o protótipo e consolidou os resultados no relatório. Os ensaios de Android, carga e recuperação possuem registros técnicos e confirmações de utilização; iOS/APNs e percurso físico por GPS foram aprovados em validação manual pela equipe. A tabela apresenta a situação final das etapas, com prazo de entrega acadêmica em 30 de outubro de 2026.

| Etapa | Situação registrada |
| --- | --- |
| App e backend | Implementação concluída; registros técnicos de 03–06/10/2026 |
| Revisão técnica | Concluída pela equipe |
| iOS/APNs | Concluído e aprovado em validação manual pela equipe |
| Percurso GPS | Concluído e aprovado em validação manual pela equipe |
| Registro APS | Atividades e cargas horárias confirmadas: 21 h, 23 h e 30 h |
| Revisões finais | Concluídas pela equipe |
| Entrega acadêmica | Prazo de entrega: 30/10/2026 |

As integrações Firebase Android e OpenRouteService foram exercitadas em ensaios registrados. As validações manuais de iOS/APNs e do percurso físico por GPS complementaram a avaliação do cliente móvel. O conjunto relaciona os resultados da infraestrutura, as chamadas aos provedores e as confirmações em aparelho, conforme as fontes descritas na metodologia.

A entrega foi organizada com o aplicativo Android, o código-fonte, os arquivos de configuração de exemplo e a documentação técnica. As evidências mantêm a origem e os parâmetros dos ensaios, permitindo consultar os resultados junto à implementação. O registro de participação integra o Apêndice A.

### 4.5 Estratégia de validação e controle de mudanças

A estratégia de validação combina verificações rápidas de regra com cenários integrados. No backend, os testes abrangem contratos, geografia, persistência, idempotência, agregação, outbox, tentativas, provedores e cache. No cliente, abrangem modelos, fila offline, reconexão, proximidade e interface. Esses testes localizam regressões sem exigir um aparelho em cada execução. Os cenários integrados confirmam que as partes utilizam os mesmos contratos e que o efeito aparece no banco, no cache e nos clientes. As duas formas de verificação são necessárias, mas sustentam conclusões diferentes.

A prova de idempotência repete um UUID com conteúdo igual e verifica ausência de novo registro. A prova de durabilidade interrompe processamento, envia um relato e observa a retomada. A prova de cache confere IDs, versões e validade, inclusive depois de uma chave inválida ou de uma indisponibilidade. A prova espacial considera fronteiras de células e rotas que não intersectem os bloqueios. Para comunicação, dois WebSockets devem receber o mesmo evento, enquanto push exige verificar seleção, chamada ao provedor e recepção em aparelho. Um resultado não é transferido automaticamente para outro cenário.

Os registros dos ensaios identificam ambiente, data, entradas, resultado e limitações. Os relatos utilizados são fictícios e marcados como demonstração. As evidências públicas excluem tokens, senhas e coordenadas privadas do aparelho. As confirmações em dispositivo são identificadas como validações manuais da equipe. A avaliação distingue Android físico, emulador e navegador, especialmente quanto ao armazenamento local, à localização e à execução em segundo plano.

O controle de mudanças utilizou a matriz de requisitos para avaliar o impacto das correções. A faixa local de proximidade, por exemplo, recebeu ajustes de sincronização e expiração acompanhados por testes de interface. Os números históricos de testes mantêm as datas de suas execuções; as medições do cluster descrevem o comportamento observado no protótipo. A revisão final conferiu a correspondência entre funcionalidades, resultados e documentação. A recuperação controlada de componentes e a circulação dos eventos foram analisadas com seus parâmetros e ambientes registrados. Esses critérios permitem reproduzir os cenários e avaliar alterações posteriores nos módulos. O encerramento da revisão foi confirmado pela equipe e consolidado junto ao registro de participação, preservando as fontes dos resultados apresentados.

## 5 PROJETO E ARQUITETURA DO PROGRAMA

### 5.1 Componentes e circulação de um relato

A arquitetura separa três responsabilidades centrais: receber e consultar dados, transformar relatos em incidentes e disseminar mudanças. A API valida o contrato, autentica a sessão de instalação e grava o relato com o evento. O worker de risco consome eventos particionados, aplica distância, janela temporal e expiração e grava a mudança resultante. O serviço de alertas atualiza Redis, publica para os canais ao vivo e prepara entregas push. Essa separação permite parar o processamento sem impedir que a API persista novos relatos, desde que o banco principal continue acessível. Cada instalação recebe um UUID local e inicia uma sessão automaticamente, sem cadastro ou senha. A API emite um token JWT com validade limitada, usado nas operações autenticadas; o cliente tenta renovar a sessão quando recebe HTTP 401. Essa identificação vincula a origem dos relatos à instalação e não comprova a identidade de uma pessoa.

| Componente | Responsabilidade | Estado ou comunicação |
| --- | --- | --- |
| Flutter | Coleta, consulta e apresentação | SQLite, HTTP, WebSocket e FCM |
| API FastAPI | Validação e acesso aos dados | PostgreSQL/PostGIS e adaptadores |
| Relay da outbox | Publicação confirmada | Banco para RabbitMQ |
| Worker de risco | Agregação e expiração | Evento para incidente e nova outbox |
| Serviço de alertas | Cache e destinatários | Redis, WebSocket e provedor push |

O fluxo completo parte da gravação no SQLite. A API confirma o relato e sua outbox na mesma transação. O relay publica no RabbitMQ e marca a linha após confirmação. O worker registra o incidente, seu vínculo e o controle de processamento; a nova outbox propaga a alteração. Depois, o serviço de alertas atualiza cópias e comunica clientes. O aplicativo pode mostrar a confirmação do relato antes de receber o incidente. Esse intervalo é esperado e precisa ser compreendido como processamento assíncrono, sem remover a pendência antes do aceite persistido.

O modo demo oferece execução simplificada e fixtures rotuladas para desenvolver interface e cenários controlados. O modo full utiliza os serviços reais e configurações distribuídas. Um healthcheck informa modo, estado de dependências e pendências da outbox. Essa distinção impede que uma resposta visualmente correta no demo seja usada como prova de broker ou cluster. A configuração seleciona fontes e provedores, enquanto segredos ficam fora do código apresentado. Cada evidência registra o perfil utilizado para que a topologia da execução possa ser relacionada ao resultado.

### 5.2 Modelo de dados, contratos e consistência

O relato possui UUID, tipo, gravidade, coordenadas, descrição opcional, horário de ocorrência, origem da posição e indicador de demonstração. O backend acrescenta horário de recepção e região GeoHash. Separar ocorrência e recepção permite interpretar um registro sincronizado depois de permanecer offline. Um relato antigo pode ser armazenado sem originar risco atual quando sua validade já terminou. A instalação identifica a origem para deduplicação e colaboração, mas seus identificadores e os tokens de dispositivo não seguem nos eventos públicos.

O incidente agrega relatos compatíveis e mantém ID, versão, contador, centro, raio de influência, estado e prazo de validade. Alagamento e obstrução permanecem categorias distintas. A geometria é apresentada como polígono de influência, e o vínculo conserva os relatos que sustentaram a atualização. A agregação verifica candidatos próximos, separa demonstrações e eleva a versão a cada mudança. A expiração gera nova alteração e retira o incidente ativo das consultas. Vencimento indica falta de atualização segundo a regra do sistema; não comprova que o problema físico foi resolvido.

Os eventos transportam identificador próprio, versão de esquema, tipo, agregado, versão do agregado, região, horário e identificador de rastreamento. O payload varia conforme o tipo. Esse envelope permite acompanhar uma mudança através dos serviços e rejeitar contratos inválidos. A idempotência do relato compara o conteúdo persistido quando encontra um UUID existente: conteúdo igual retorna o registro; conteúdo diferente produz conflito. Para os consumidores, o controle por serviço e evento permite reconhecer entregas repetidas. Essas duas medidas tratam repetições em fronteiras diferentes da arquitetura.

Observações ambientais incluem origem, unidade, data, natureza da observação, validade e versão. O cache utiliza chaves por região, tipo e identificador, com comparação atômica de versão. Uma observação durável pode reconstruir uma chave expirada sem nova consulta ao provedor. Para a cena Landsat, o prazo de reconstrução do cache é separado da data de aquisição. Para o AQI, a validade limita o reaproveitamento da previsão. A consulta conserva o banco como referência e usa o cache somente quando o conteúdo corresponde à versão esperada. Essa opção prioriza coerência e recuperação; o ensaio realizado não comprova redução de carga de consultas ao PostgreSQL.

### 5.3 Topologias, recuperação e limites arquiteturais

O perfil completo ensaiado em outubro reúne duas APIs, dois workers de risco, serviço de alertas, PostgreSQL/PostGIS com réplica no ensaio inicial, três RabbitMQ e seis Redis, além de gateway e inicializadores. O balanceador mantém acesso quando uma API é interrompida. Os workers compartilham as filas de partição e recebem mensagens sem reconhecimento após a falha de outro consumidor. RabbitMQ e Redis foram submetidos a interrupções controladas de nós. Todos esses processos executaram no mesmo notebook, em contêineres Linux, e compartilham o domínio de falha da máquina.

As partições derivadas de GeoHash organizam eventos em filas, enquanto a consulta espacial considera a distância real e as regiões cobertas pelo raio. O PostgreSQL permanece um único estado lógico principal. Portanto, a arquitetura demonstra distribuição de trabalho e indexação geográfica, sem comprovar sharding físico em bancos independentes. A escalabilidade potencial depende de novas medições, do custo da agregação, de concorrência no banco e de dependências externas. A rajada local disponível é suficiente para observar o fluxo, mas insuficiente para avaliar carga sustentada ou capacidade máxima.

A promoção PostgreSQL foi planejada e executada com pausa de escritores, verificação de replicação e isolamento do primário antigo. Depois da promoção, o novo primário funcionou, mas ficou necessária a reconstrução de uma réplica. O ambiente anterior foi parado preservando volumes e mantendo o primário antigo isolado. No ensaio específico de push geográfico de 05 de outubro, foi utilizada uma topologia isolada na porta 8011, com duas APIs, um worker, um PostgreSQL, três RabbitMQ e seis Redis. Esse ensaio não incluiu réplica PostgreSQL e não deve ser descrito como repetição integral da prova de failover.

A recuperação inclui mais que reiniciar serviços. Mensagens pendentes precisam manter identidade; versões antigas não podem regredir o cache; um cliente reconectado deve consultar o estado atual; entregas push precisam ter situação rastreável. O projeto implementa essas medidas nos cenários documentados, mas não garante ausência de perda em toda combinação de falhas. A dependência de rede, dos provedores e do host continua relevante. Uma implantação futura exigiria múltiplos domínios de falha, transporte seguro, observabilidade e testes representativos. Essas condições são extensões do protótipo e não resultados atribuídos ao ambiente local.

## 6 RELATÓRIO DE CÓDIGO

### 6.1 Organização e validação dos contratos

O código é organizado em módulos de aplicativo, API, worker, alertas e componentes compartilhados. No cliente, modelos representam relatos, posições, incidentes, camadas e rotas; serviços encapsulam localização, push e comunicação ao vivo; o controller coordena persistência e sincronização. No backend, o módulo models define contratos, domain reúne regras, db trata persistência, broker controla mensagens e cache gerencia as cópias Redis. Os trechos apresentados nesta seção foram selecionados da implementação para explicar decisões específicas; não constituem uma transcrição de todos os arquivos.

Trecho do contrato RelatoRequest, em backend/shared/models.py.

class RelatoRequest(StrictModel):
    id: UUID
    tipo: Literal["alagamento", "obstrucao"]
    gravidade: Literal["baixa", "media", "alta"]
    latitude: Latitude
    longitude: Longitude
    descricao: str = Field(default="", max_length=500)
    occurred_at: AwareDatetime
    position_source: Literal["gps", "manual", "demo"] = "manual"
    accuracy_m: Accuracy | None = None
    is_demo: bool = Field(default=False, strict=True)

Latitude e longitude possuem limites e rejeitam valores não finitos. StrictModel impede campos extras. occurred_at exige informação de fuso e é normalizado para UTC. Outro validador exige que uma posição de demonstração tenha is_demo verdadeiro. O contrato evita que cada consumidor interprete categorias ou horários à sua maneira. Na API, os relatos são aceitos até 50 quilômetros do ponto central de referência de Ribeirão Preto, tanto no modo demo quanto no full. Pontos fora desse raio recebem HTTP 422 e uma orientação para selecionar um local na região. Erros de conteúdo produzem respostas que o aplicativo pode traduzir em orientação, preservando o registro local quando ainda não há confirmação.

A ingestão verifica a faixa temporal e procura o UUID dentro da transação. Se o conteúdo e a instalação coincidem com o registro existente, devolve a mesma informação sem criar outro evento. Se diferem, sinaliza conflito. Quando é novo, insere o relato, prepara a geometria e grava a outbox na mesma transação. O primeiro envio retorna HTTP 201; o replay igual retorna 200. Essa distinção está presente na execução geográfica de 05 de outubro e conecta diretamente uma regra do código ao resultado observado.

### 6.2 Outbox, confirmação e tratamento de falhas

O relay da outbox lê eventos não publicados e utiliza bloqueio de linhas no PostgreSQL para permitir publicadores concorrentes. A seleção usa skip_locked, evitando que duas instâncias aguardem a mesma linha quando há outras disponíveis. O registro permanece bloqueado até confirmação e commit. O trecho abaixo mostra a fronteira crítica entre RabbitMQ e banco. Se a publicação falhar, a linha continua pendente. Se o processo falhar depois da confirmação, a repetição é absorvida pela idempotência dos consumidores.

Trecho de publicação confirmada em backend/shared/broker.py.

confirmed = await exchange.publish(
    message, routing_key=row["route"],
    mandatory=True, timeout=10
)
if confirmed is False:
    raise ConnectionError("Publicação não confirmada pelo RabbitMQ")
conn.execute(
    update(outbox).where(outbox.c.id == row["id"])
    .values(published=True)
)

As mensagens utilizam modo persistente e identificação própria. O consumidor chama a regra antes de executar ack. No tratamento de exceções, erros de formato e validação vão diretamente à DLQ. Falhas transitórias recebem até três tentativas com esperas de um, cinco e quinze segundos. A republicação para retry ou DLQ também exige confirmação antes do reconhecimento da mensagem original. Se a republicação não for confirmada, o código solicita reentrada da original. Essa ordem evita declarar concluída uma entrega cuja próxima etapa ainda não ficou persistida no broker.

O worker de risco consulta o registro de eventos processados antes de agregar. Depois grava vínculo, incidente e controle de processamento na mesma transação, incluindo o evento resultante. Os dois workers consomem as filas de partição, e o broker distribui entregas entre os consumidores. O projeto não depende de atribuição exclusiva permanente de uma fila a uma instância. A paralisação de um worker permite ao outro continuar, enquanto mensagens sem reconhecimento podem retornar. Os testes de falha, retry e replay documentados verificaram esses caminhos em cenários próprios, separados do ensaio normal de push.

### 6.3 Fila local e reconciliação de relatos

O controller do aplicativo mantém a identidade dos relatos entre armazenamento local e resposta remota. A função mergeReports começa pelo conteúdo do aparelho, que pode incluir registros ainda desconhecidos pelo servidor. Em seguida incorpora os registros confirmados. Uma resposta GET vazia ou atrasada não pode apagar o que acabou de ser salvo. Essa decisão é importante porque a leitura pode acontecer durante uma retomada ou logo após um POST cujo resultado ainda está sendo persistido localmente.

Trecho de reconciliação em mobile/lib/state/report_controller.dart.

static List<Report> mergeReports(
  Iterable<Report> local,
  Iterable<Report> remote,
) {
  final merged = {for (final report in local) report.id: report};
  for (final report in remote) {
    if (merged[report.id]?.isPending == true) continue;
    merged[report.id] = report.confirmed();
  }
  return merged.values.toList();
}

No envio, o UUID criado no aparelho permanece imutável. A tentativa HTTP usa esse identificador, e a confirmação recebida é gravada antes da atualização visual. Falhas temporárias encerram a rodada sem apagar as pendências. Conflitos e validações são tratados para permitir que o usuário compreenda o problema. O controller evita sincronizações concorrentes e preserva relatos criados enquanto outra operação aguarda entrada e saída de dados. As consultas de incidentes e ambiente são independentes, de modo que uma falha em uma camada não elimine automaticamente o último conteúdo da outra.

A abstração LocalStore permite testar a fila com dependências controladas e utilizar armazenamento persistente no cliente nativo. Configurações conservam dados consultados, horário de atualização e versões já avisadas. No Android, a reabertura com SQLite foi verificada em emulador e o fluxo físico básico foi confirmado pela equipe com conferência do banco. No navegador, o armazenamento é próprio dessa plataforma. O código aciona sincronização com a aplicação aberta ou retomada; não inclui WorkManager nem promete envio imediato com o processo fechado. Essa limitação orienta a mensagem apresentada sobre pendências.

### 6.4 Proximidade, versões e dados ambientais

A avaliação local de proximidade filtra incidentes não vencidos e compara a distância do centro com a referência da aplicação. A chave combina ID e versão. Dessa forma, a mesma atualização não precisa gerar avisos repetidos após sair e retornar à área, enquanto uma nova versão pode ser tratada novamente. O histórico das últimas chaves é persistido. O trecho mostra parte da seleção e da identidade usada para esse controle; as mensagens distinguem GPS de ponto escolhido manualmente.

Trecho do controle de versões no aviso local.

final nearbyKeys = {
  for (final incident in nearby)
    '${incident.id}:${incident.version}',
};
_proximityAlerts.removeWhere(
  (key, _) => !nearbyKeys.contains(key),
);
for (final incident in nearby) {
  final key = '${incident.id}:${incident.version}';
  if (_alertedVersions.contains(key) &&
      !_proximityAlerts.containsKey(key)) {
    continue;
  }
  // Continuação da avaliação omitida neste recorte.
}

Uma falha observada fazia a faixa desaparecer quando a sincronização atualizava mensagens gerais. A correção separou o estado do aviso e acrescentou fechamento próprio e Timer até o próximo vencimento, inclusive offline. A faixa agora termina pelos critérios de proximidade, remoção, expiração ou ação do usuário. Os testes verificaram preservação durante sincronização, reabertura, nova versão e supressão de repetição. A confirmação física com pontos manuais sustenta esse fluxo local, sem equivaler ao recebimento FCM ou a um percurso GPS real.

No backend, Redis compara versões por Lua atômico. O importador Landsat valida fonte, checksum, qualidade e geometria antes de gerar GeoJSON. A aquisição histórica permanece identificada, mesmo com cache renovado. O adaptador de rotas valida exclusões e interseções. Esses módulos concentram regras específicas e permitem testes isolados.

## 7 FUNCIONAMENTO E RESULTADOS

### 7.1 Percurso demonstrável no aplicativo

A tela principal reúne o mapa de Ribeirão Preto e os controles de camadas. Legendas, horários e identificação dos dados de demonstração acompanham os detalhes. O formulário de relato inclui tipo, gravidade e posição. O botão flutuante usa GPS e pode atualizar a referência global; o menu do mapa permite relatar no ponto escolhido. A origem da posição sustenta o formulário e distingue um ponto manual do deslocamento físico do aparelho. Relatos usados em testes devem permanecer explicitamente fictícios. Para um novo exemplo no modo completo, o formulário deve usar “Usar ponto de exemplo” e “Exemplo • Centro”; a posição manual e a descrição, sozinhas, não definem o indicador de demonstração.

Na visualização em lista, “Relatos recebidos e pendentes” apresenta os registros individuais e indica quais ainda aguardam envio. “Ocorrências compartilhadas” apresenta os incidentes gerados pelo processamento, com a quantidade de relatos agrupados. Um mesmo caso pode aparecer nas duas seções: uma mostra o registro enviado e a outra, seu resultado processado. Isso não representa duplicação do envio.

O painel “Conexão e informações” permite salvar o endereço do servidor, consultar notificações e verificar a última atualização. O APK Android 1.0.0+4 acompanha as mudanças enquanto a ficha está aberta e mostra “Push registrado no servidor” após cadastro bem-sucedido. Falha do Firebase e falha no cadastro do backend possuem mensagens distintas. Um campo separado registra o último callback de push nesta sessão. O Wi-Fi comum é necessário para acessar o servidor local; o aviso de proximidade usa GPS e incidentes ativos já salvos no aparelho. Novas consultas e rotas dependem de conexão.

O teste offline verificou o armazenamento de um relato com a rede indisponível, sua preservação após reabertura e o envio ao reconectar com o aplicativo aberto. O fluxo físico básico em Android foi confirmado pela equipe em 04 de outubro. A conferência do banco de demonstração registrou a passagem de 18 para 19 relatos, com um único novo relato fictício de obstrução e um incidente com report_count igual a um. A identificação por UUID também foi verificada em reenvios controlados, sem duplicar o relato. A conferência no aparelho é um registro manual, complementado pela consulta ao banco.

A faixa de proximidade foi validada com pontos manuais para entrada no raio, fechamento do aviso e saída e retorno sem repetição. Os testes de interface, controller e emulador verificaram sincronização e expiração; a aquisição GPS pontual foi confirmada em aparelho, com posição e precisão registradas no banco. A equipe também aprovou o percurso físico por GPS em validação manual. Os ensaios de push em primeiro plano e de seleção fora do raio possuem seus próprios registros de 06 de outubro, descritos na seção 7.3.

Ao escolher um destino no mapa, a pessoa pode calcular uma rota a pé ou de carro. O resumo informa distância, tempo estimado, quantidade de zonas evitadas e fonte do percurso. O botão “Limpar rota” remove o trajeto exibido. O adaptador ORS real evitou um bloqueio fictício; outra chamada da API retornou HTTP 200 com zero bloqueios ativos e percurso de 3.035,2 metros, estimado em 432,8 segundos. A equipe confirmou que uma rota apareceu no Android, sem informar seus pontos e valores; essa confirmação não é atribuída ao mesmo percurso mensurado. Nas camadas ambientais, o aplicativo identifica AQI modelado e calor histórico, com detalhes de fonte e aquisição. A distinção entre os dados integra a demonstração funcional.

### 7.2 Resultados de processamento e recuperação

Os registros históricos mostram 162 testes de backend aprovados em 04 de outubro. A revisão Android de 06 de outubro passou com 47 testes Flutter e análise sem problemas; três testes adicionais protegem os scripts de envio. Essas contagens têm datas e escopos próprios. O cluster demonstrou a circulação de eventos por banco, outbox, broker, workers, cache e WebSocket. A tabela reúne ensaios de recuperação e a carga ampliada, todos no mesmo computador.

| Cenário histórico | Resultado observado | Alcance |
| --- | --- | --- |
| Fluxo distribuído | Mesmo ID e versão em dois WS; 0,641 s | Uma execução local |
| Workers parados | API persistiu e backlog foi retomado | Falha controlada de processos |
| RabbitMQ/Redis | Continuidade e promoção de réplica Redis | Nós lógicos no mesmo host |
| Promoção PostgreSQL | 14,852 s; 60 IDs preservados | Planejada, com escritores pausados |
| Carga ampliada | 1.000 relatos; p95 969 ms; 20,14/s | Um host; sem FCM/ORS; capacidade máxima não medida |
| Cache ambiental | 33 camadas coerentes; reconstrução 1,578 s | Um AQI e 32 polígonos históricos |

Em 05 de outubro, um projeto isolado recebeu 1.000 relatos fictícios com HTTP 201 e 20 reenvios idênticos com HTTP 200. Houve 1.000 vínculos, 20 incidentes, 1.000 processamentos de risco e 1.000 de alertas. A outbox ficou sem pendências e os 20 incidentes convergiram entre banco e Redis. A entrada levou 49,641 s, média de 20,14 relatos/s e p95 HTTP de 969 ms; a convergência foi conferida em 52,016 s desde o primeiro envio. A fase com alvo de 20/s atingiu 16,32/s; a rajada com concorrência 8, 26,32/s. FCM e ORS estavam desligados, sem dispositivos ou chamadas externas. O ensaio não mede capacidade máxima ou resistência à perda do host.

O cache ambiental conservou IDs, versões e validade em duas APIs e dois WebSockets. A interrupção dos seis Redis manteve consultas pelo PostgreSQL, e a retomada permitiu reconstruir as cópias. A seleção de calor reúne 32 polígonos reais de temperatura de superfície de 17 de setembro de 2025. O AQI full provém de CAMS via Open-Meteo, em grade ampla; fixtures demo continuam identificadas. Esses resultados demonstram circulação e apresentação dos dados, sem validar monitoramento ambiental local, calor atual ou desempenho de produção.

### 7.3 Push geográfico e validação manual

Em 05 de outubro, um relato fictício percorreu o backend full até uma entrega FCM aceita para um Android dentro do raio. O POST retornou 201 e o replay idêntico, 200; risco e alertas processaram os dois eventos publicados. Um web sintético dentro ficou unsupported, sem chamada ao provedor, e outro fora foi excluído. A equipe confirmou a chegada em segundo plano e a abertura por toque no APK +2. geographic-push.json e geographic-push-phone-receipt.json separam a prova técnica da confirmação humana. O ensaio seguiu o fluxo normal, sem nova injeção de falhas.

Em 06 de outubro, a equipe confirmou “Push recebido com o app aberto às 10:10:58 (1 nesta sessão)” no APK +3. O envio foi direto pelo FCM, separado do ensaio geográfico. Uma tentativa anterior ocorreu com o app fechado e não foi usada como prova de primeiro plano. O cadastro e a posição foram depois confirmados por HTTP 200; a equipe também confirmou o estado registrado. O motivo da falha transitória anterior não ficou determinado. O APK +4 corrigiu a atualização da ficha e os textos de cadastro, preservando o pacote e a assinatura. Sua instalação foi confirmada pela equipe.

Ainda em 06 de outubro, o mesmo Android, agora com GPS recente fora do raio, participou de outra etapa. Um alagamento fictício no Centro retornou HTTP 201 e replay 200; foram conferidos um vínculo, um evento de relato, um de incidente e ambos os consumidores. O aparelho foi excluído pela distância, sem linha de entrega para o evento, e a equipe confirmou nenhum novo recebimento. A seleção usa 1.000 m do aparelho mais 200 m de influência; o aviso local usa 1.000 m até o centro. android-outside-radius-20261006.json registra o caso. Foi um ensaio sequencial com um telefone, sem observação independente ou deslocamento físico.

A equipe aprovou iOS/APNs e deslocamento físico por GPS em validações manuais, conforme a metodologia. Esses resultados complementam os ensaios documentados de Android e infraestrutura. Os testes de carga e recuperação ocorreram em um único computador; seu alcance corresponde a falhas controladas de componentes e convergência local. A distribuição entre computadores independentes, a perda abrupta do host e a capacidade de produção não foram objeto desses ensaios.

## 8 CONSIDERAÇÕES FINAIS

O EcoPulse aproxima o estudo de sistemas distribuídos de um fluxo concreto de colaboração urbana. O relato salvo no aparelho, recebido pela API e processado por eventos torna visíveis decisões sobre durabilidade, comunicação e recuperação. A interface pequena reúne componentes com responsabilidades próprias. Identificação e versões permitem tratar repetições sem reproduzir o mesmo efeito nos cenários documentados.

As provas sustentam fila local, geoprocessamento, outbox, mensageria, cache e atualização de clientes. Os ensaios observaram recuperação controlada e convergência, inclusive na carga isolada de 1.000 relatos. A equipe confirmou push Android em segundo plano e por toque em 05 de outubro, além de primeiro plano em 06 de outubro. A seleção fora do raio foi conferida no backend com o mesmo aparelho em etapa distinta, acompanhada da confirmação de nenhum novo recebimento. Medições e confirmações humanas conservam seus escopos próprios.

Os dados ambientais também exigem interpretação: AQI modelado em grade ampla não equivale a medição local; Landsat apresenta temperatura histórica da superfície, sem demonstrar calor atual ou ilha de calor climatológica. Círculos de influência não medem a extensão física de uma inundação. A rota considera relatos conhecidos e não certifica segurança. Fonte, natureza e horário permitem consultar as informações com seu significado preservado.

O projeto concluiu o fluxo previsto para o protótipo acadêmico, com aplicativo, serviços integrados e documentação dos resultados. As validações manuais da equipe complementam os registros técnicos, e o Apêndice A consolida a participação dos integrantes. Como continuidade, a execução entre computadores independentes e a ampliação das fontes e dos cenários de carga permitiriam avaliar o sistema em outras condições. Os resultados obtidos sustentam a aplicação dos conceitos estudados na disciplina ao problema de colaboração ambiental urbana.

## REFERÊNCIAS

BIBLIOTECA DA UNIVERSIDADE PAULISTA - UNIP. Guia de normalização para apresentação de trabalhos acadêmicos da Universidade Paulista: ABNT. São Paulo: UNIP, 2025. Disponível em: https://unip.br/servicos/biblioteca/assets/download/manual_de_normalizacao_abnt.pdf. Acesso em: 06 out. 2026.

ECOPULSE. Evidências e documentação técnica do protótipo. 2026. Conjunto local: docs/VALIDACAO.md, REQUISITOS.md, PROXIMIDADE.md, CALOR.md, CACHE_AMBIENTAL.md, PUSH.md, TESTES_FINAIS_ANDROID.md; docs/evidence e infra/evidence. Registros de 03–06 out. 2026.

FASTAPI. FastAPI: documentação oficial. [S. l.], [s. d.]. Disponível em: https://fastapi.tiangolo.com/. Acesso em: 05 out. 2026.

FIREBASE. Receive messages in Flutter apps. [S. l.], [s. d.]. Disponível em: https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages. Acesso em: 05 out. 2026.

FLUTTER. Flutter architectural overview. [S. l.], [s. d.]a. Disponível em: https://docs.flutter.dev/resources/architectural-overview. Acesso em: 05 out. 2026.

FLUTTER. Persist data with SQLite. [S. l.], [s. d.]b. Disponível em: https://docs.flutter.dev/cookbook/persistence/sqlite. Acesso em: 05 out. 2026.

FLUTTER. Set up iOS development. [S. l.], [s. d.]c. Disponível em: https://docs.flutter.dev/platform-integration/ios/setup. Acesso em: 05 out. 2026.

OPEN-METEO. Air Quality API. [S. l.], [s. d.]. Disponível em: https://open-meteo.com/en/docs/air-quality-api. Acesso em: 05 out. 2026.

OPENROUTESERVICE. Routing options. [S. l.], [s. d.]. Disponível em: https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options. Acesso em: 05 out. 2026.

## REFERÊNCIAS (CONTINUAÇÃO)

PLANO DE AÇÃO do aplicativo de alagamentos para três desenvolvedores. 2026. Documento de planejamento fornecido à equipe; arquivo plano_de_acao_app_alagamentos_3_devs.docx.

POSTGIS PROJECT. ST_DWithin. [S. l.], [s. d.]. Disponível em: https://postgis.net/docs/ST_DWithin.html. Acesso em: 05 out. 2026.

POSTGRESQL GLOBAL DEVELOPMENT GROUP. Log-shipping standby servers: PostgreSQL 17 documentation. [S. l.], [s. d.]b. Disponível em: https://www.postgresql.org/docs/17/warm-standby.html. Acesso em: 05 out. 2026.

POSTGRESQL GLOBAL DEVELOPMENT GROUP. Transactions: PostgreSQL 17 documentation. [S. l.], [s. d.]a. Disponível em: https://www.postgresql.org/docs/17/tutorial-transactions.html. Acesso em: 05 out. 2026.

PROPOSTA APS DSD EcoPulse. 2026. Documento de referência fornecido à equipe; arquivo Proposta_APS_DSD_EcoPulse.docx.

RABBITMQ. Consumer acknowledgements and publisher confirms. [S. l.], [s. d.]a. Disponível em: https://www.rabbitmq.com/docs/confirms. Acesso em: 05 out. 2026.

RABBITMQ. Dead letter exchanges. [S. l.], [s. d.]b. Disponível em: https://www.rabbitmq.com/docs/dlx. Acesso em: 05 out. 2026.

RABBITMQ. Quorum queues. [S. l.], [s. d.]c. Disponível em: https://www.rabbitmq.com/docs/quorum-queues. Acesso em: 05 out. 2026.

REDIS. Scale with Redis Cluster. [S. l.], [s. d.]. Disponível em: https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/. Acesso em: 05 out. 2026.

USGS. Landsat Collection 2 Surface Temperature. [S. l.], [s. d.]. Disponível em: https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature. Acesso em: 05 out. 2026.

## APÊNDICE A — REGISTRO DE ATIVIDADES APS

Curso: Ciência da Computação • 8º semestre • UNIP • 2026/2
Professor: Jean Miler Scatena
Projeto: EcoPulse • Prazo de entrega: 30/10/2026

| Integrante | RA | Turma |
| --- | --- | --- |
| Vitória Pandolfo Marturano | RA-OMITIDO | CC8P18 |
| Alessandro Damázio Pereira | RA-OMITIDO | CC8Q18 |
| Augusto Flávio Murari | RA-OMITIDO | CC8P18 |

Registro de participação da equipe, consolidado em 06/10/2026. As atividades e as cargas horárias abaixo foram confirmadas pelos integrantes. A coluna “Registro” indica a consolidação documental, sem atribuir essa data à realização de cada atividade.

| Responsável | Atividades realizadas | Carga horária | Registro<br>(2026) |
| --- | --- | --- | --- |
| Vitória | Interface Flutter, formulário, detalhes, fluxo de rota e revisão do relatório. | 21 h | 06/10 |
| Alessandro | Mapa, GPS, SQLite, fila offline, sincronização e conferência Android. | 23 h | 06/10 |
| Augusto | FastAPI, PostGIS, RabbitMQ, Redis, workers, Firebase/ORS e infraestrutura Docker. | 30 h | 06/10 |

Carga horária total da equipe: 74 horas-pessoa, sendo 21 horas de Vitória, 23 horas de Alessandro e 30 horas de Augusto.

Assinaturas dos integrantes:
Vitória ______________________
Alessandro ___________________
Augusto _____________________

Validação do professor: ________________________  Data: ____/____/2026

## APÊNDICE B — ARQUITETURA E TELAS

Figura 1 — Caminho simplificado de um relato no ambiente completo.

Fonte: elaboração para este relatório, a partir da implementação e das evidências do EcoPulse (2026).

O relay publica eventos da outbox e o worker devolve alterações ao banco. O desenho resume a circulação de informações; não representa todos os nós, réplicas ou conexões. O ensaio de push de 05/10 utilizou o perfil específico descrito no capítulo 5.

## APÊNDICE B — TELAS (CONTINUAÇÃO)

Figura 2 — Aviso local de proximidade em cenário Android emulado e simulado.

Fonte: docs/evidence/android-proximity-map-loaded.png (2026). Captura de simulação isolada no emulador Android, com mapa online carregado. A faixa é um aviso no aplicativo, distinto da notificação FCM do Android.

## APÊNDICE B — CAMADAS AMBIENTAIS

Figura 3 — Detalhes de AQI modelado (esquerda) e calor histórico (direita) na versão web.

Fonte: docs/evidence/aqi-full-web.png e heat-web-current.png (2026). Valores correspondem às capturas dos ensaios. O calor refere-se à aquisição de 17/09/2025; o AQI exibido não constitui uma leitura atual nem medição de estação local.

## APÊNDICE B — FORMULÁRIO DE RELATO

Figura 4 — Formulário de relato em duas posições de rolagem na versão web.

Fonte: docs/evidence/report-form-top-web.png e report-form-bottom-web.png (2026). Capturas da interface atual em uma prévia web isolada, com ponto de exemplo e dados fictícios. À esquerda aparecem tipo, gravidade e posição; à direita, descrição opcional e botão de salvar. Nenhum relato foi enviado nesta captura.

## APÊNDICE B — ROTA E PENDÊNCIA OFFLINE

| Figura 5 — Rota ilustrativa na interface web.<br> | Figura 6 — Lista com uma pendência de envio.<br> |
| --- | --- |

Fonte da Figura 5: docs/evidence/report-route-illustration-web.png (2026). Resposta controlada para ilustrar linha, distância, tempo e limpeza da rota; os valores são simulados. Esta captura não representa uma nova chamada ao OpenRouteService nem uma prova de desvio de bloqueios.

Fonte da Figura 6: docs/evidence/report-offline-illustration-web.png (2026). Pendência fictícia pré-carregada em armazenamento de memória, com a API de teste configurada como indisponível. A imagem ilustra os estados “Sem conexão” e “Salvo • aguardando envio”; não comprova SQLite, reabertura ou sincronização em aparelho. Essas provas permanecem descritas no capítulo 7.
