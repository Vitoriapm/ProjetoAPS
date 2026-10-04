# Validação do EcoPulse

Auditoria em **03/10/2026**, horário de São Paulo, comparada com `Proposta_APS_DSD_EcoPulse.docx` e o plano integrado. O app e a infraestrutura foram exercitados no Windows da equipe. O projeto completo para ambas as plataformas ainda não está validado.

| Verificação | Resultado |
|---|---|
| Backend: API, domínio, geografia, idempotência, outbox, retries, adaptadores e concorrência | **60 testes passaram** |
| Flutter: análise estática | **Sem problemas encontrados** |
| Flutter: modelos, fila offline, reconexão, proximidade, interface e espera de APNs | **22 testes passaram** |
| Compilação Android/web | Builds atualizados; informações do APK em [apk-info.json](../entregas/apk-info.json) |
| Android: SQLite nativo → API | **Passou** no emulador Android API 35; persistência após reabertura e sincronização |
| GPS Android | Posição simulada reconhecida; aparelho físico pendente |
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

O benchmark mede uma rajada pequena neste notebook. Não demonstra capacidade para grandes volumes, disponibilidade de produção ou sobrevivência à perda do computador. Partições GeoHash distribuem processamento; não há sharding físico do PostgreSQL. A réplica PostgreSQL é assíncrona; a promoção planejada não prova perda zero em falha inesperada. O antigo primário foi isolado e o novo ainda exige reconstrução de uma réplica. Detalhes ficam no relatório da infraestrutura.

Os testes Python tiveram um aviso de depreciação de `BlockingPortal` na dependência Starlette/AnyIO, sem falhas. Os testes de espera de APNs usam funções controladas e não comprovam Firebase/APNs real.

## Evidências

- [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md): cluster, falhas, carga, promoção e evidências sanitizadas.
- [validation-summary.json](evidence/validation-summary.json): resumo final dos testes, builds e pendências.
- [VALIDACAO_INTEGRACOES.md](VALIDACAO_INTEGRACOES.md): AQI real, correções e serviços externos pendentes.
- [aqi-live.json](evidence/aqi-live.json), [aqi-full-web.json](evidence/aqi-full-web.json) e [aqi-full-web.png](evidence/aqi-full-web.png): consulta e exibição de AQI 77 com escala, fonte e horário. É previsão modelada (~45 km), não estação local.
- [api-smoke.json](evidence/api-smoke.json): HTTP e WebSocket na API demo; não é evidência do cluster.
- [home-web.png](evidence/home-web.png), [form-web.png](evidence/form-web.png), [offline-web.png](evidence/offline-web.png) e [web-offline-flow.json](evidence/web-offline-flow.json): interface e fila no navegador.
- [android-integration.json](evidence/android-integration.json), [home-android.png](evidence/home-android.png) e [gps-android.png](evidence/gps-android.png): SQLite/API, instalação e GPS emulado Android.
- [VALIDACAO_IOS_PENDENTE.md](VALIDACAO_IOS_PENDENTE.md): revisão iOS e passos ainda não executados.

A prévia web usa armazenamento do navegador. A confirmação de SQLite vem do teste nativo Android. A versão iOS ainda não foi compilada ou instalada.

## O que ainda precisa ser concluído

| Prioridade | Pendência | Critério de conclusão |
|---|---|---|
| Alta | **iOS**: obter Mac/Xcode, iPhone e assinatura | Compilar, instalar e testar GPS/permissões, SQLite/reinício, reconexão, mapa e WebSocket no iPhone |
| Alta | **Push real Android/iOS**: equipe ainda não possui Firebase | Configurar apps/conta de serviço/APNs e comprovar recebimento em aparelhos dentro do raio, em primeiro e segundo plano; excluir aparelho distante |
| Alta | **Rotas reais**: equipe ainda não possui chave OpenRouteService | Consultar rota em Ribeirão Preto, confirmar exclusão dos polígonos e testar ausência de alternativa/indisponibilidade |
| Alta | **Ilhas de calor reais** | Integrar fonte espacial com data, unidade e método de contraste; polígonos atuais são simulados |
| Alta | **Cache Redis das camadas ambientais** | Hoje Redis cacheia incidentes e distribui eventos. AQI usa cache PostgreSQL; calor é fixture. Implementar cache ambiental Redis com validade, reconstrução e convergência de versão |
| Média | **Aparelho Android físico** | Instalar APK e testar permissões GPS/notificações, LAN, localização real e offline/reabertura; teste emulado já passou |
| Média | **Relatório final da APS, ficha e apresentação** | Produzir documento da seção VI, bibliografia e ficha APS; ensaiar o roteiro e gravar o vídeo de apoio previsto no plano |
| Antes de alegar alta vazão | **Carga e escala** | Executar carga maior representativa e registrar limites; 60 relatos não comprovam grandes volumes |

O relatório formal ainda não foi produzido: a documentação técnica e o roteiro não substituem capa, índice, capítulos, bibliografia e ficha APS. A proposta pede Objetivo/Motivação (1–2 páginas), Introdução (2–4), Fundamentos (4–8), Plano (5–15), Projeto/Arquitetura (3–8) e Relatório de Código (máximo 10).

As pendências mantêm os requisitos do plano. Calor real e cache ambiental ainda requerem implementação; iOS, push e rotas requerem acesso/configuração e testes reais.

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
