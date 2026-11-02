> **Arquivo histórico:** Ar (AQI) e Calor foram retirados do projeto em **02/11/2026**, por solicitação do usuário. Este documento preserva a implementação e os resultados da versão de outubro; não descreve o escopo atual de Alagamento e Vias nem comprova a suíte atual. Evidências e entregas antigas foram mantidas.

# Validação do EcoPulse

Atualização em **05/10/2026**, horário de São Paulo, comparada com `Proposta_APS_DSD_EcoPulse.docx` e o plano integrado. Os ensaios anteriores permanecem registrados abaixo; a revisão atual inclui o fluxo geográfico de push pelo backend full, com confirmação humana de recebimento Android em segundo plano. O projeto completo para ambas as plataformas ainda não está validado.

| Verificação | Resultado |
|---|---|
| Backend: API, domínio, geografia, idempotência, outbox, retries, adaptadores, calor, cache, concorrência e configuração | **162 testes passaram em 04/10**, incluindo nove novos casos do iniciador demo |
| Flutter: análise estática | **Sem problemas encontrados** |
| Flutter: modelos, fila offline, reconexão, proximidade, interface, calor histórico e push/APNs | **45 testes passaram em 05/10**, incluindo 14 de proximidade e um da faixa na interface |
| Compilação Android/web | Builds atualizados; informações do APK em [apk-info.json](../entregas/apk-info.json) |
| Android: SQLite nativo → API | **Passou** no emulador Android API 35; persistência após reabertura e sincronização |
| APK demo no emulador | **Passou em 04/10**: instalação, abertura/UI sem exceção fatal e canal `ecopulse_alertas` com importância HIGH; Firebase desligado, sem prova de recebimento |
| APK Firebase Android | **Atualizado em 05/10, versão 1.0.0 (2)**, com correção de proximidade, `FIREBASE_ENABLED=true` e assinatura compatível com o anterior; hash/tamanho conferidos. Usuário confirmou instalação, aviso local com pontos manuais e, no ensaio full posterior, recebimento de um push geográfico em segundo plano e abertura por toque; sem observação independente do telefone. O teste direto do build anterior permanece histórico |
| Proximidade Android | **Confirmada pelo usuário em Android físico com pontos manuais no mapa**, incluindo entrada no raio, fechar e sair/voltar sem repetição; [confirmação humana](evidence/proximity-phone-confirmation.json). **Passou em 05/10** no emulador: menu do mapa, aviso preservado no sync online/offline, fechamento, dedup após saída/retorno e reabertura SQLite, versão nova e expiração; API fake isolada, sem observação do telefone ou FCM |
| GPS Android | Posição simulada reconhecida; **aquisição em aparelho físico confirmada pelo usuário em 04/10**; banco registra posição e `accuracy_m` para um Android, sem observação independente de coordenadas ou valores de precisão |
| Android físico: offline/reabertura/reenvio | **Confirmado pelo usuário e pelo banco demo em 04/10**: um relato fictício persistiu após reabertura offline e foi recebido ao reconectar; banco de 18 para 19 relatos, um único UUID novo de via obstruída simulada ligado a um incidente com `report_count=1`, sem novo relato duplicado |
| Navegador: formulário, mapa e offline → reconexão | **Passou**, incluindo envio único e confirmação na API demo |
| Cluster Docker completo | **Executado** com PostgreSQL/PostGIS e réplica, RabbitMQ de três nós, Redis de seis nós, duas APIs e dois workers |
| Fluxo distribuído | POST → PostGIS/outbox → RabbitMQ → worker → Redis → dois WebSockets: **0,641 s** nesta execução |
| Consenso colaborativo | Três instalações fictícias produziram o mesmo incidente colaborativo, versão 3 |
| Falhas controladas | API, worker, RabbitMQ e primário Redis: fluxo recuperou; reinício PostgreSQL preservou os IDs verificados |
| Retry e DLQ reais | Mensagem inválida preservada na DLQ; falha FCM percorreu três retries e DLQ, sem simular recebimento |
| Reprocessamento DLQ | Republicação confirmada antes de ack; replay e duplicata deixaram um único registro processado |
| Promoção planejada PostgreSQL | **Passou** em 14,852 s; primário antigo isolado; 60 IDs da carga preservados e novos relatos/WS funcionaram |
| Carga pequena local | 60 relatos fictícios, concorrência 4, todos HTTP 201; entrada 1,328 s, cerca de 45/s; p95 297 ms |
| Convergência da carga | Processamento/outbox em 2,469 s; versões do cache verificadas em 3,86 s |
| AQI real | Open-Meteo/CAMS consultado e exibido no app full; duas APIs concorrentes responderam 200 sem duplicar a observação |
| Calor espacial real | Recorte Landsat de 17/09/2025 processado em 32 polígonos; proveniência/checksums e 28 testes de calor passaram |
| Cache ambiental Redis | **Passou em 04/10**: 33 camadas iguais no PostgreSQL/Redis, outbox/broker/consumidor confirmados, duas APIs e dois WebSockets; reconstrução em 1,578 s, fallback/retomada dos seis Redis passaram |
| Consulta real ORS e API | **Passou em 04/10**: adaptador com um bloqueio fictício; API HTTP 200 com zero bloqueios ativos, 3.035,2 m / 432,8 s; usuário confirmou rota aparecendo no celular, sem informar pontos ou valores desse trajeto |
| Push geográfico: backend full | **Passou em 05/10** no projeto isolado `ecopulse-fcm-test`: relato HTTP 201 e replay idêntico 200; um relato/um incidente, eventos publicados e consumidores de risco/alertas processados; Android dentro selecionado, uma entrega aceita pelo FCM; web sintético dentro marcado unsupported sem envio ao provedor; web sintético fora não selecionado e sem entrega |
| Push geográfico: recepção Android | **Confirmada pelo usuário em 05/10** no APK atual 1.0.0 (2): chegou em segundo plano e abriu ao tocar. Fonte `human_user_in_chat`, sem observação independente do celular; não houve telefone físico fora do raio, movimento GPS ou teste iOS/APNs |
| Push direto e rotas anteriores | Dry-run e envio direto FCM de 04/10 aceitos, com chegada/toque Android confirmados pelo usuário no APK anterior; usuário confirmou rota na tela. ORS real pelo adaptador e API passou. Essas provas históricas permanecem separadas do ensaio geográfico full |
| Interface web atual | **Passou em 04/10**, viewport 390 × 844: mapa/controles e detalhes históricos de calor legíveis; sem erros de página ou console |
| Configuração local de serviços | Demo lê somente os quatro providers do `.env`, prioriza ambiente explícito e mantém SQLite local; caminho FCM Docker convertido para host; subprocesso com configuração full inválida passou |

O benchmark mede uma rajada pequena neste notebook. Não demonstra capacidade para grandes volumes, disponibilidade de produção ou sobrevivência à perda do computador. Partições GeoHash distribuem processamento; não há sharding físico do PostgreSQL. A réplica PostgreSQL é assíncrona; a promoção planejada não prova perda zero em falha inesperada. O antigo primário foi isolado e o novo ainda exige reconstrução de uma réplica. Detalhes ficam no relatório da infraestrutura.

Os testes Python tiveram um aviso de depreciação de `BlockingPortal` na dependência Starlette/AnyIO, sem falhas. Os testes de espera de APNs usam funções controladas e não comprovam Firebase/APNs real.

## Push geográfico de 05/10: alcance da prova

No ambiente full isolado, foi criado **um único relato fictício**, em um ponto de grade de 0,01° próximo da referência manual escolhida, sem publicar coordenadas do aparelho. O POST retornou 201 e seu replay idêntico retornou 200. PostgreSQL manteve um relato e um incidente, com um evento de cada tipo na outbox, ambos publicados; houve um processamento de risco e um de alertas. O Android com posição recente ficou dentro da seleção por raio de dispositivo de 1.000 m mais influência de 200 m do incidente, e a entrega foi aceita pelo FCM.

Havia três cadastros: um Android real dentro, um web sintético dentro e um web sintético fora. O web dentro resultou em `unsupported`, sem chamada ao provedor; o web fora não foi selecionado e não teve entrega. Foram duas linhas de entrega (`accepted` e `unsupported`), mas **somente um alerta foi enviado ao celular**. A prova do backend está em [geographic-push.json](evidence/geographic-push.json). Esse teste não injetou falha de broker/retry; as provas anteriores de retries/DLQ são independentes.

O usuário, que havia confirmado o app em segundo plano, respondeu **“Recebi e o app abriu ao tocar”**. [geographic-push-phone-receipt.json](evidence/geographic-push-phone-receipt.json) registra a confirmação humana para o APK atual; não houve observação independente do celular. Aceite FCM e confirmação de recepção ficam em evidências distintas. O cenário não testou GPS físico em movimento, FCM em primeiro plano, segundo telefone físico fora do raio ou iOS/APNs.

## Evidências

- [PROXIMIDADE.md](PROXIMIDADE.md), [proximity-validation.json](evidence/proximity-validation.json), [android-proximity.json](evidence/android-proximity.json) e [captura](evidence/android-proximity.png): falha reproduzida, correção, 45 testes Flutter e cenário Android/SQLite isolado; sem validar push geográfico ou GPS físico em movimento.

- [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md): cluster, falhas, carga, promoção e evidências sanitizadas.
- [validation-summary.json](evidence/validation-summary.json): resumo final dos testes, builds e pendências.
- [VALIDACAO_INTEGRACOES.md](VALIDACAO_INTEGRACOES.md): AQI real, correções e serviços externos pendentes.
- [aqi-live.json](evidence/aqi-live.json), [aqi-full-web.json](evidence/aqi-full-web.json) e [aqi-full-web.png](evidence/aqi-full-web.png): consulta e exibição de AQI 77 com escala, fonte e horário. É previsão modelada (~45 km), não estação local.
- [api-smoke.json](evidence/api-smoke.json): HTTP e WebSocket na API demo; não é evidência do cluster.
- [home-web.png](evidence/home-web.png), [form-web.png](evidence/form-web.png), [offline-web.png](evidence/offline-web.png) e [web-offline-flow.json](evidence/web-offline-flow.json): interface e fila no navegador.
- [android-integration.json](evidence/android-integration.json), [home-android.png](evidence/home-android.png) e [gps-android.png](evidence/gps-android.png): SQLite/API, instalação e GPS emulado Android.
- [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json): o usuário respondeu “tudo funcionou” ao roteiro de aquisição GPS, salvar um relato fictício offline, reabrir ainda offline e reconectar/reenviar. A conferência do banco demo encontrou 18 → 19 relatos e um único novo relato simulado ligado a um incidente com `report_count=1`; um Android tinha posição e `accuracy_m` registradas, sem divulgar seus valores. A identificação usou a diferença em relação à baseline, pois a descrição não coincidiu exatamente com o marcador sugerido. Não houve observação independente da tela, das coordenadas ou da precisão no celular; movimento/proximidade não foram exercitados.
- [android-current-smoke.json](evidence/android-current-smoke.json): APK recompilado, abertura e canal Android HIGH; o ensaio não enviou push.
- [firebase-android-preparation.json](evidence/firebase-android-preparation.json): etapa histórica da configuração Android e APK Firebase separado. A preparação do servidor posterior está em [firebase-server-auth.json](evidence/firebase-server-auth.json) e [firebase-demo-runtime.json](evidence/firebase-demo-runtime.json): OAuth autenticado e API demo saudável, com 18 IDs preservados; nenhum envio/recebimento comprovado.
- [VALIDACAO_IOS_PENDENTE.md](VALIDACAO_IOS_PENDENTE.md): revisão iOS e passos ainda não executados.
- [heat-live.json](evidence/heat-live.json) e [CALOR_HISTORICO.md](CALOR_HISTORICO.md): dados históricos Landsat, processamento e limites.
- [heat-web-current.json](evidence/heat-web-current.json), [mapa atual](evidence/home-web-current.png) e [detalhe de calor](evidence/heat-web-current.png): versão web recompilada, fonte/valores e aviso histórico legíveis.
- [CACHE_AMBIENTAL.md](CACHE_AMBIENTAL.md) e [environment-cache.json](evidence/environment-cache.json): versão, validade, reconstrução e ensaio real do cache ambiental.
- [routes-phone-confirmation.json](evidence/routes-phone-confirmation.json): usuário confirmou a rota aparecendo no Android; sem observação independente ou coleta de valores/pontos no telefone.
- [PUSH.md](PUSH.md) e [ROTAS.md](ROTAS.md): preparo e validação das integrações. [fcm-phone-receipt.json](evidence/fcm-phone-receipt.json) registra a confirmação humana Android; [routes-live.json](evidence/routes-live.json) e [routes-api-live.json](evidence/routes-api-live.json) registram consultas ORS reais.
- [geographic-push.json](evidence/geographic-push.json): processamento full, replay, seleção geográfica, uma entrega FCM aceita e cadastros web sintéticos dentro/fora. [geographic-push-phone-receipt.json](evidence/geographic-push-phone-receipt.json): chegada em segundo plano e abertura por toque no APK atual, confirmadas pelo usuário, sem observação independente.

A prévia web usa armazenamento do navegador. A confirmação de SQLite vem do teste nativo Android. A versão iOS ainda não foi compilada ou instalada.

## O que ainda precisa ser concluído

| Prioridade | Pendência | Critério de conclusão |
|---|---|---|
| Alta | **iOS**: obter Mac/Xcode, iPhone e assinatura | Compilar, instalar e testar GPS/permissões, SQLite/reinício, reconexão, mapa e WebSocket no iPhone |
| Alta | **Push iOS/APNs e demais cenários Android** | Android dentro do raio em segundo plano foi confirmado no fluxo full; faltam APNs/iPhone, teste com telefone físico fora do raio (primeiro plano confirmado pelo usuário em 06/10); exclusão fora foi verificada apenas com cadastro web sintético |
| Média | **Movimento GPS e proximidade no Android físico** | Aquisição GPS pontual, offline/reabertura/reenvio, aviso local com pontos manuais e push geográfico em segundo plano já confirmados; falta exercitar mudanças de posição por GPS físico, entrada/saída do raio e supressão de avisos nesse percurso |
| Média | **Registro APS e ensaio** | Relatório e roteiro Word produzidos em 05/10; preencher datas/horas/assinaturas reais, conferir formulário institucional, ensaiar 10 minutos e preparar apoio |
| Antes de alegar alta vazão | **Capacidade máxima e escala entre hosts** | Rodada adicional de 1.000 relatos passou em 05/10; ainda faltam carga representativa, capacidade máxima e múltiplos hosts |

O relatório formal Word e o roteiro Word foram produzidos e revisados em 05/10. Incluem capa, sumário, capítulos, bibliografia, registro APS e capturas. O registro de atividades precisa receber dados e assinaturas efetivos; conferir eventual formulário próprio da instituição. A proposta pede Objetivo/Motivação (1–2 páginas), Introdução (2–4), Fundamentos (4–8), Plano (5–15), Projeto/Arquitetura (3–8) e Relatório de Código (máximo 10).

As pendências mantêm os requisitos do plano. A fonte de calor histórica e o cache ambiental estão implementados. A camada de calor é uma aquisição real de 2025 e não representa monitoramento atual ou validação climatológica. Rota, push direto anterior, aviso local manual e push geográfico full Android em segundo plano possuem confirmação humana, com provas do backend separadas. Continuam pendentes movimento GPS físico, FCM em primeiro plano, telefone físico fora do raio, iOS/APNs. A conclusão administrativa da ficha APS e o ensaio da apresentação ainda dependem da equipe.

## Rodada final Android e carga em 05/10/2026

O usuário informou ter um Android e um computador e pediu adiar iOS. O requisito
original permanece documentado, mas iOS/APNs ficam fora desta rodada. Não há
segundo computador para executar o cluster entre hosts físicos.

O ensaio adicional de carga passou: 1.000 POSTs HTTP 201 em 49,641 s, média de
20,14/s, p95 de 969 ms. Banco, vínculos, 20 incidentes e versões/conteúdo no cache
convergiram; 20 reenvios retornaram 200 sem duplicação. A fase com alvo de 20/s
teve vazão efetiva de 16,32/s. Evidência: [load-extended.json](evidence/load-extended.json).
O projeto isolado tinha FCM/ORS desligados, zero celulares e zero entregas. Foi
parado ao final, preservando seus volumes e o projeto do telefone. A carga maior
continua limitada e não comprova grandes volumes de produção, capacidade máxima,
WebSocket nesta rodada, replicação PostgreSQL ou perda do host.

O [APK de testes 1.0.0+3](../entregas/EcoPulse-Firebase-testes.apk) adiciona um
indicador local de push recebido com app aberto, independente de WebSocket. Os
45 testes Flutter, análise estática e três testes dos guardas de envio passaram.
O usuário confirmou instalação do APK +3 e app aberto. Um envio FCM direto foi
aceito em 05/10 às 19:54 UTC; a recepção em primeiro plano ainda depende da
confirmação do indicador no app. Evidência: [android-foreground-push-send.json](evidence/android-foreground-push-send.json).
O teste por raio e o deslocamento GPS físico permanecem pendentes.

[TESTES_FINAIS_ANDROID.md](TESTES_FINAIS_ANDROID.md) descreve os próximos passos:
push em primeiro plano, exclusão do mesmo Android fora do raio em outra etapa e
entrada/saída com GPS real. Um ensaio sequencial com um telefone será identificado
como tal; não será apresentado como dois aparelhos simultâneos. O Word produzido
antes desta rodada mantém as evidências anteriores; sua atualização com resultados
novos deve ocorrer depois dos testes físicos.

## Reproduzir

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
.\backend\.venv\Scripts\python.exe infra/validate_static.py
.\backend\.venv\Scripts\python.exe scripts/smoke_api.py
cd mobile
flutter analyze
flutter test
flutter test integration_test/android_flow_test.dart -d emulator-5554
```

Smoke e integração Android usam a API demo na porta 8000; no emulador, `http://10.0.2.2:8000`. Para repetir testes distribuídos, siga [infra.md](infra.md) e a validação da infraestrutura. Todos os relatos de teste são fictícios e identificados.

## Atualização de 06/10: primeiro plano Android

Um novo envio direto FCM foi aceito após confirmar o EcoPulse aberto no mapa.
O usuário informou o indicador “Push recebido com o app aberto às 10:10:58
(1 nesta sessão)”. [Confirmação humana](evidence/android-foreground-open-map-receipt-20261006.json)
e [aceite do provedor](evidence/android-foreground-open-map-send-20261006.json)
ficam separados. O primeiro plano passa a ter essa confirmação no APK +3, sem
observação independente do celular. Não foi um novo teste do fluxo geográfico.
O aviso de falha de registro também informado será investigado separadamente;
backend saudável e cadastro com token ativo foram conferidos. Fora do raio,
movimento GPS físico, iOS adiado e múltiplos hosts seguem pendentes. As seções
anteriores preservam os estados das execuções de 05/10.

## Cadastro e posição recuperados em 06/10/2026

O usuário confirmou que `/health` abriu no navegador do Android. O diagnóstico
temporário do gateway observou HTTP 200 no PUT de cadastro push e no POST de
posição; a consulta ao banco confirmou um Android com token ativo, posição com
menos de 120 segundos e metadado de precisão. Ao fechar e reabrir a ficha, o
usuário confirmou “Push registrado; teste de recebimento em aparelho ainda
necessário”. Esse complemento é texto fixo da versão +3; não invalida a recepção
em primeiro plano já confirmada às 10:10:58.

Evidência: [android-registration-recovery-20261006.json](evidence/android-registration-recovery-20261006.json).
O motivo da falha anterior permanece indeterminado: o gateway foi recriado antes
das solicitações bem-sucedidas e não houve inspeção independente do telefone.
O diagnóstico foi encerrado e não registrou tokens, coordenadas, IPs ou corpos.
Nenhum novo push foi enviado nesta conferência. Posição recente não comprova
deslocamento físico; os ensaios fora do raio e de entrada/saída continuam separados.

## Android fora do raio: seleção validada em 06/10/2026

Após confirmar a instalação +4 e a preparação com “Usar GPS”, o usuário manteve
o app aberto. A consulta técnica confirmou um Android com token ativo, posição
recente (menos de 120 s), precisão presente e distância além do raio de
1.000 m + 200 m de influência + 200 m de margem do ensaio em relação ao Centro.
Um único relato fictício de alagamento no ponto público central retornou HTTP
201; repetir o mesmo UUID/conteúdo retornou HTTP 200. O processamento produziu
um vínculo, um evento de relato, um evento de incidente, dois eventos publicados
e uma execução de cada consumidor (risco e alertas). O Android ficou fora da
seleção geográfica, sem linha de entrega para esse evento.

Evidência: [android-outside-radius-20261006.json](evidence/android-outside-radius-20261006.json).
O teste passou no backend, e o usuário confirmou **“Não apareceu nenhum novo
recebimento”** no telefone. Essa confirmação é humana, sem inspeção independente. Nenhuma nova chamada FCM para esse Android
foi feita pelo caso. Foi usado o mesmo telefone em momentos distintos; não houve
teste simultâneo com dois Androids, observação independente do aparelho nem
deslocamento GPS físico de entrada/saída. iOS/APNs e múltiplos hosts seguem adiados.
