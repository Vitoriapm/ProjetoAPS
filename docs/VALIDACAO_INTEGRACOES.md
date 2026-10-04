# Auditoria das integrações externas do EcoPulse

Validação em **03/10/2026**, horário de São Paulo. A consulta pública de AQI ocorreu às **22:32**, registrada em UTC como 2026-10-04T01:32. Esta auditoria verifica os adaptadores e suas dependências; a execução do cluster e os testes de aparelhos constam na validação geral.

| Integração | Resultado observado | Dependência restante |
|---|---|---|
| AQI Open-Meteo/CAMS Global | **Consulta pública e exibição no app ligado ao servidor full passaram**; escrita concorrente entre duas APIs também passou | Dado modelado de grade, não medição local; servidor demo usa fixture |
| Ilhas de calor | Polígonos e contrato funcionam; valores **1,8 °C e 3,2 °C são simulados** | Fonte espacial real e método de comparação ainda precisam ser integrados |
| OpenRouteService | Contrato e exclusão de polígonos passaram em testes controlados | `ORS_API_KEY` ausente; rota real ainda não foi consultada |
| Firebase/FCM Android | Seleção geográfica, deduplicação, mensagem e tratamento de falha testados | Configuração do Firebase, conta de serviço e recebimento em aparelho pendentes |
| Firebase/FCM/APNs iOS | Adaptador prepara expiração APNs; configuração e recebimento permanecem pendentes | Mac/Xcode, app Firebase, APNs, assinatura e iPhone |

## Evidência do AQI real

[aqi-live.json](evidence/aqi-live.json) registra **US AQI 77**, observado pelo provedor em **03/10 às 22:00**. A consulta pediu o centro de Ribeirão Preto (-21,1775; -47,8101) e recebeu a célula da grade centrada aproximadamente em (-21,2000; -47,8000). O GeoJSON preservou `source`, `scale`, `updated_at`, `label` e `is_demo=false`. As duas camadas de calor permaneceram `is_demo=true`.

O valor vem de uma **previsão modelada CAMS Global**, com resolução aproximada de 45 km, e não de uma estação local. A API pública acadêmica não exige chave; o produto usa a escala US AQI. A documentação admite índices superiores a 500. [Documentação oficial Open-Meteo](https://open-meteo.com/en/docs/air-quality-api).

O script [validate_aqi_live.py](../scripts/validate_aqi_live.py) chama a função real `environmental_layers`, incluindo validação do dado e gravação da observação. Usa SQLite temporário apenas para isolar o teste do adaptador. **Não comprova PostgreSQL, RabbitMQ, Redis nem a integração completa do app com o modo distribuído.**

A verificação adicional [aqi-full-web.json](evidence/aqi-full-web.json) e a [captura da interface](evidence/aqi-full-web.png) mostram o app consultando o cluster `ecopulse-validation` na porta 8001 e exibindo AQI 77, escala, fonte, data e rótulo de previsão modelada. Duas APIs também consultaram simultaneamente uma célula ainda ausente: ambas responderam 200 e ficou uma observação persistida no PostgreSQL. Consulte [VALIDACAO_INFRA.md](VALIDACAO_INFRA.md) para essa execução. A prévia habitual na porta 5173 continua apontando por padrão para o servidor demo na porta 8000; a troca de servidor foi feita apenas na sessão isolada da auditoria.

Em `ECOPULSE_MODE=demo`, o AQI continua sendo a fixture 58. Em `full`, `ENVIRONMENT_SOURCE=open-meteo` consulta o provedor; `ENVIRONMENT_SOURCE=fixtures` mantém simulação explícita. Falha do provedor retorna erro e preserva o cache do cliente, sem converter um número fictício em dado real.

## Correções comprovadas nesta auditoria

1. **Push de demonstração:** o sistema operacional podia mostrar uma ocorrência fictícia com o mesmo título e texto de um alerta real. `FcmAdapter` agora usa o título “EcoPulse — demonstração” e texto explícito de ocorrência fictícia. O payload de eventos e a mensagem de alertas reais foram preservados.
2. **AQI acima de 500:** o adaptador rejeitava valores admitidos pelo contrato oficial do provedor. Passou a aceitar valores numéricos finitos e não negativos, incluindo 510, e a rejeitar coordenadas de grade inválidas.
3. **Resumo de rota inválido:** um retorno com distância negativa, booleana, ausente ou textual podia chegar ao contrato público. O adaptador valida distância e duração antes de apresentar a geometria.
4. **Consulta inicial concorrente de AQI:** duas instâncias podiam consultar a mesma célula ainda ausente e falhar ao inserir a observação. Um teste com duas conexões, respostas simultâneas e leitura sincronizada reproduziu a violação da chave única em banco isolado. A escrita agora usa `INSERT ... ON CONFLICT DO UPDATE` em PostgreSQL/SQLite, na mesma transação da outbox. O teste concorrente confirma duas respostas, uma observação durável e dois eventos; outro teste verifica o SQL do dialeto PostgreSQL. A prova em duas APIs do cluster é registrada separadamente pela validação de runtime.

Os testes usam transporte HTTP controlado e Firebase SDK com envio substituído. **26 testes de adaptadores e concorrência passaram; a suíte final completa do backend passou com 60 testes**, com um aviso de depreciação já existente em Starlette/AnyIO. Nenhum push real foi enviado.

## Credenciais e configuração

[integration-config.json](evidence/integration-config.json) e [check_integration_config.py](../scripts/check_integration_config.py) contêm apenas verificações booleanas. Na execução, estavam ausentes:

- Chave `ORS_API_KEY`.
- `FCM_CREDENTIALS_FILE` e arquivo de conta de serviço correspondente.
- `mobile/android/app/google-services.json`.
- `mobile/ios/Runner/GoogleService-Info.plist`.

O `.env` existe e seleciona Open-Meteo. O `/health` da API demo confirmou `routes_configured=false`, `fcm_configured=false` e `heat_source=fixture_simulada`. Presença de um arquivo não comprova validade da credencial ou entrega de mensagem. O diagnóstico não imprime conteúdo de chaves, tokens ou contas.

Para FCM, registre o aplicativo **br.edu.ecopulse.ecopulse** no projeto Firebase. Coloque os arquivos de plataforma nos caminhos acima; no iOS, o plist também precisa pertencer ao target Runner. Monte a conta de serviço em `secrets/` e configure o caminho do contêiner, por exemplo `FCM_CREDENTIALS_FILE=/run/secrets/firebase-service-account.json`. Esses arquivos estão excluídos do pacote/Git. Compile o aplicativo com `--dart-define=FIREBASE_ENABLED=true` depois de configurá-los.

No iOS, habilite as capacidades de push e notificações remotas, configure a chave APNs no Firebase e aguarde a disponibilidade do token APNs antes de obter o token FCM. O Android precisa de Google Play Services compatível. [Requisitos oficiais do Firebase para Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

Para concluir o recebimento, use aparelhos de teste autorizados, com permissões de notificação e posição recente: um na região do incidente e outro fora do raio. Gere um relato **simulado**, registre o recebimento em primeiro plano e com o app em segundo plano, confira a rotulagem da simulação e verifique a reentrega do mesmo evento. Confirme que aparelho distante e posição vencida não são selecionados. A aceitação pelo FCM sozinha não comprova recebimento.

## Rota real que ainda precisa ser validada

Depois de fornecer a chave ao servidor, selecione origem e destino de Ribeirão Preto fora dos incidentes e execute `/v1/rotas`. O adaptador envia os polígonos ativos em `options.avoid_polygons`, conforme o [contrato oficial do ORS](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options), e verifica se a linha retornada cruza algum deles.

Registre a geometria, distância, duração, fonte e incidentes evitados. Teste também origem/destino dentro de um incidente, indisponibilidade do provedor e falta de rota. As falhas devem mostrar mensagem legível, mantendo os bloqueios. Sem chave, o comportamento esperado é HTTP 503, sem trajeto inventado.

## Como validar calor sem apresentar simulação como medição

Uma temperatura única da previsão meteorológica da cidade não comprova contraste térmico entre bairros. Para a camada real, uma opção é **Landsat Collection 2 Level-2 Surface Temperature**, apropriado para estudar temperatura de superfície e ilhas de calor. O produto tem escala própria, pode sofrer interferência de nuvens e mede superfície, não a temperatura do ar. [Descrição e limitações oficiais do USGS](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature).

O procedimento de integração ainda pendente é selecionar uma cena de Ribeirão Preto, aplicar escala/unidades e máscara de qualidade, recortar a região e calcular o contraste com uma referência definida na mesma cena. A comparação com área verde/rural é uma proposta de método do projeto, que deve ser documentada e discutida com a avaliação da APS. Exponha áreas em GeoJSON com horário da aquisição, fonte, unidade, critério e `is_demo=false`; identifique a camada como **temperatura de superfície/contraste térmico**. Confira amostras e geometria antes de integrar ao mapa.

Até essa fonte ser integrada, mantenha os polígonos atuais como **dados simulados para demonstração**. A camada existe na interface, mas a medição real de ilhas de calor continua pendente.

## Reproduzir a auditoria

```powershell
.\backend\.venv\Scripts\python.exe scripts/check_integration_config.py
.\backend\.venv\Scripts\python.exe scripts/validate_aqi_live.py --output docs/evidence/aqi-live.json
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_providers.py -q
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_provider_concurrency.py -q
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

O primeiro comando é local e imprime apenas booleanos. O segundo consulta a API pública e atualiza a evidência; o resultado pode variar com o horário e a rede. Os testes não consultam ORS nem enviam mensagens Firebase reais.
