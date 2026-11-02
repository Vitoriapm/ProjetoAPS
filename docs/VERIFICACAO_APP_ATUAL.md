# Verificação do EcoPulse em 02/11/2026

Aplicativo Android 1.0.0+5, conectado por Wi-Fi ao backend demo em `http://198.51.100.22:8000`.

| Funcionalidade | Resultado observado |
| --- | --- |
| API e banco | `/health` retornou HTTP 200 e banco disponível. |
| Rotas de carro | HTTP 200; 3.035,2 m, 46 pontos e 4 zonas consideradas na exclusão. |
| Rotas a pé | HTTP 200; 3.020,5 m, 59 pontos e 4 zonas consideradas na exclusão. |
| Envio e sincronização | Teste integrado criou um relato explicitamente fictício; reenvio foi idempotente e conteúdo conflitante foi rejeitado. |
| Ocorrências no mapa | GeoJSON disponível e mapa com ruas e marcadores observado no Android. |
| Tempo real | WebSocket passou em assinatura, recebimento do evento e ping/pong. |
| Localização | Serviço de localização e permissões precisa/aproximada habilitados no aparelho; posição registrada recentemente no servidor. |
| Persistência local | Banco SQLite acessível; relato pendente preservado. A atualização anterior do APK também preservou os relatos existentes. |
| Firebase | Aparelho cadastrado e validação FCM aceita em dry-run, sem envio de notificação. |

## Correção das rotas

O processo anterior da API executava em um ambiente com acesso externo bloqueado. A mesma consulta ao OpenRouteService funcionou fora desse isolamento. A API foi reiniciada com acesso externo, e os dois perfis de rota passaram pelo endpoint usado pelo aplicativo. Não houve alteração de chave, APK, firewall ou configuração do roteador nesta correção.

## Limites encontrados

- **Um relato pendente está fora do raio de 50 km de Ribeirão Preto.** A API o rejeita com HTTP 422; ele continua salvo no aparelho. Esse limite é uma regra atual da demonstração. Para um novo teste de envio válido, use um ponto de exemplo dentro de Ribeirão Preto.
- **Push automático não está ativo no modo demo.** A configuração e a validação do Firebase passaram, mas esse modo não executa os serviços separados de processamento e alertas. Esta verificação não enviou notificação nem comprovou recebimento em primeiro ou segundo plano.
- O modo demo não valida RabbitMQ, Redis Cluster, PostgreSQL/PostGIS ou failover. Eles não são dependências ativas desse modo.

Resultados sanitizados: [auditoria dos serviços](evidence/app-services-20261102.json) e [teste integrado](evidence/app-smoke-20261102.json). Os testes de código da revisão anterior passaram com 45 testes Flutter e 114 verificações de backend; essas suítes não foram repetidas nesta auditoria sem mudanças de código.
