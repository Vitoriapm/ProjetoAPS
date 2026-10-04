# Rastreabilidade da proposta EcoPulse

Referência conferida: `Proposta_APS_DSD_EcoPulse.docx`, seções III–VI, requisitos reintegrados pelo usuário e [plano atual](../PLANO_EXECUCAO_ECOPULSE.md). Auditoria: **03/10/2026**. Evidências em [VALIDACAO.md](VALIDACAO.md), [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md) e [VALIDACAO_INTEGRACOES.md](VALIDACAO_INTEGRACOES.md).

| Requisito | Estado | Evidência e limite |
|---|---|---|
| Android e iOS | **Parcial** | APK e SQLite/API em Android emulado passaram; iOS sem build/instalação por falta de Mac/Xcode/iPhone |
| Design simples | **Implementado e testado** | Duas telas, verde discreto, português, testes de widget e inspeção visual |
| Mapa: alagamento e vias obstruídas | **Implementado e testado** | Incidentes/polígonos, filtros, detalhes e legenda; zonas aproximadas, relatos de ensaio fictícios |
| AQI | **Consulta real validada** | Open-Meteo/CAMS e tela full com escala/fonte/horário; previsão de grade ~45 km, não estação local |
| Ilhas de calor | **Parcial — fonte real falta** | Camada poligonal simulada identificada; fonte espacial real ainda não implementada |
| GPS e metadados | **Testado no emulador** | Geolocator, manual, precisão/origem, UTC e UUID; leitura emulada passou; aparelhos físicos pendentes |
| Validação colaborativa | **Testada** | Três instalações, distância e janela temporal; cluster criou incidente colaborativo versão 3 |
| Offline-first | **Testado em Android e web** | SQLite antes de POST, reabertura e reenvio; navegador usa armazenamento próprio; iOS pendente |
| Sincronização automática | **Testada** | Reconexão, retomada e reenvio idempotente; servidor confirma antes de marcar envio |
| Mensageria assíncrona EDA | **Validada no cluster local** | PostGIS/outbox → RabbitMQ → workers; API persiste relatos com workers parados |
| Persistência/retry/DLQ | **Validada no cluster local** | Quorum/confirm/ack, três retries e preservação em DLQ; detalhes de replay no relatório infra; push real pendente |
| GeoHash/partições | **Implementado e testado** | Filas por GeoHash e consumidores concorrentes; recuperação com worker parado; sem sharding físico PostgreSQL |
| WebSocket bidirecional | **Validado no cluster local** | Assinatura por área, ping/pong e dois sockets recebendo o mesmo evento via APIs/Redis |
| Push por raio | **Implementado, integração real pendente** | Seleção, expiração/deduplicação e adaptador testados; faltam Firebase/APNs e recebimento em aparelhos |
| Alertas de proximidade | **Testados em lógica/UI** | Entrada no raio e supressão por versão; GPS físico e comportamento nas duas plataformas pendentes |
| Roteamento evitando riscos | **Adaptador testado; serviço real pendente** | ORS avoid_polygons/interseção/resumo em testes controlados; sem chave retorna 503 |
| PostgreSQL/PostGIS | **Validado no cluster local** | PostGIS 3.5, geometrias, índice/consulta espacial, observações e transações em execução |
| Redis Cluster e cache de incidentes | **Validado no cluster local** | 16.384 slots, três primários/três réplicas, pub/sub, versões convergentes e promoção após falha |
| Redis para mapas de calor/camadas ambientais | **Não implementado** | Redis hoje guarda incidentes; AQI cacheado no PostgreSQL por 15 min; eventos ambientais usam pub/sub; calor é fixture |
| Microsserviços e Docker | **Executados** | API, risco e alertas separados; cluster com 19 serviços incluindo inicializadores |
| Balanceamento e falha de nós | **Ensaiados no mesmo host** | API/worker/Rabbit/Redis, reinício e promoção PostgreSQL; réplica PG assíncrona; não sobrevive à perda do notebook |
| Grandes volumes | **Capacidade não comprovada** | Rajada de 60 relatos/concorrência 4 passou; benchmark representativo ainda necessário |
| Relatório final/ficha APS | **Ainda não produzido** | Há documentação técnica e roteiro; faltam documento formal, bibliografia e ficha conforme seção VI |

A interface permanece pequena. Nenhum requisito obrigatório foi retirado; o quadro distingue implementação, testes e pendências. Simulações e respostas controladas de provedores não comprovam monitoramento ou recebimento real.
