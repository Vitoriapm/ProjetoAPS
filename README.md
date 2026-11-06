# EcoPulse

Aplicativo acadêmico para registrar alagamentos e vias obstruídas em Ribeirão Preto. O cliente Flutter oferece mapa, relatos com GPS ou posição manual, fila offline, sincronização, avisos de proximidade e consulta de rotas.

Documentação revisada em **06/11/2026**. A versão do aplicativo é **1.0.0+5**. A [identificação dos integrantes, a divisão de responsabilidades e a carga horária da equipe](docs/DIVISAO_EQUIPE.md) acompanham esta versão.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `mobile/` | Aplicativo Flutter para Android, iOS e prévia web; testes unitários e de integração |
| `backend/` | API FastAPI, processamento de risco, alertas, persistência e testes |
| `infra/` | Docker Compose, PostgreSQL/PostGIS, RabbitMQ, Redis e Nginx |
| `scripts/` | Inicialização, dados de exemplo e verificações |
| `contracts/` | [API HTTP e WebSocket](contracts/API.md) e [interfaces mobile](contracts/MOBILE.md) |

Este repositório reúne os fontes e as instruções técnicas. O relatório acadêmico, o roteiro e a ficha APS devem ser revisados e entregues separadamente conforme as exigências da disciplina.

## Requisitos

- Python 3.11 ou superior.
- Flutter com Dart compatível com `mobile/pubspec.yaml` e dependências de `mobile/pubspec.lock`.
- Chrome para a prévia web ou Android SDK e dispositivo/emulador para Android.
- Docker com contêineres Linux e Docker Compose 2.24.4 ou superior para a infraestrutura distribuída.
- Mac e Xcode para compilar e validar iOS.

Execute os comandos abaixo na raiz do repositório, em PowerShell. O projeto Flutter está em `mobile/`.

## Demonstração local

Inicie a API; o script prepara o ambiente Python e instala as dependências quando necessário:

```powershell
.\scripts\run_demo.ps1
```

Mantenha o servidor aberto. Em outro terminal, carregue relatos fictícios identificados como simulação e abra o aplicativo:

```powershell
.\backend\.venv\Scripts\python.exe scripts/seed_demo.py
.\scripts\run_mobile.ps1 -Device chrome
```

No emulador Android:

```powershell
.\scripts\run_mobile.ps1 -Device emulator-5554 -ApiUrl http://10.0.2.2:8000
```

Para um celular físico, consulte `flutter devices`, use o identificador correspondente em `-Device` e informe em `-ApiUrl` o IP do computador, por exemplo `http://192.168.1.10:8000`. Computador e celular precisam estar na mesma rede, com acesso à porta 8000. O endereço também pode ser salvo no painel **Conexão e informações** do app.

O modo `demo` usa SQLite no servidor e processamento local. Permite demonstrar interface, relatos, sincronização e WebSocket em uma API; o fluxo distribuído e o envio automático de push dependem do modo completo. Os relatos novos devem estar no raio de 50 km do centro de Ribeirão Preto.

## Infraestrutura distribuída

O fluxo completo usa API → PostgreSQL/PostGIS e outbox → RabbitMQ → workers de risco → alertas → Redis/WebSocket e FCM. GeoHash distribui eventos entre partições; o PostgreSQL permanece um banco principal compartilhado. Consumidores tratam repetição de eventos, tentativas e filas de mensagens mortas.

Encerre a API demo antes de usar a mesma porta para o Docker. Prepare o `.env` com segredos locais aleatórios:

```powershell
.\scripts\start_cluster.ps1 -PrepareOnly
```

Revise as variáveis conforme [.env.example](.env.example). Para acesso pelo celular, configure `ECOPULSE_BIND_ADDRESS=0.0.0.0` no `.env`. Inicie um dos ambientes:

```powershell
# Ambiente de desenvolvimento
.\scripts\start_cluster.ps1 -Development

# Cluster de demonstração; use após encerrar o ambiente de desenvolvimento
.\scripts\start_cluster.ps1
```

O cluster usa duas APIs, dois workers de risco, um serviço de alertas, PostgreSQL principal e réplica, três RabbitMQ e seis Redis. A API fica na porta 8000; o painel RabbitMQ fica em `http://127.0.0.1:15672`. Use `GET /health` para consultar o modo e o estado dos componentes.

O failover planejado está em `scripts/failover_postgres.ps1`. Após a promoção, utilize os arquivos `infra/compose.yaml`, `infra/compose.cluster.yaml` e `infra/compose.failover.yaml`, nessa ordem. Preserve o estado e o registro de isolamento do primário antigo; não o reinicie como escritor. A replicação é assíncrona e os contêineres executam no mesmo host.

## Rotas e notificações

As integrações exigem configuração própria; credenciais e arquivos Firebase ficam fora do Git.

- **Rotas:** configure `ORS_API_KEY` no `.env`. O backend consulta o OpenRouteService para carro ou caminhada, envia os polígonos de incidentes como exclusões e verifica o trajeto retornado. É necessário acesso à internet no servidor. Ausência de configuração ou indisponibilidade do provedor produz erro explícito.
- **Firebase Android:** adicione `mobile/android/app/google-services.json` para o pacote `br.edu.ecopulse.ecopulse`.
- **Firebase iOS:** adicione `GoogleService-Info.plist` ao target Runner e configure assinatura, capacidades de push e APNs no Mac.
- **Servidor FCM:** guarde a conta de serviço em `secrets/fcm.json`. No Docker, configure `FCM_CREDENTIALS_FILE=/run/secrets/fcm.json`; a execução local traduz esse caminho para o arquivo do projeto.
- **Cliente com push:** execute Flutter com `--dart-define=FIREBASE_ENABLED=true` após configurar os arquivos nativos. O registro do token e o aceite do FCM são etapas distintas do recebimento no aparelho.

O mapa de ruas e as rotas dependem de serviços externos. A fila de relatos é persistida em SQLite no Android/iOS; a prévia web usa armazenamento do navegador. O mapa não oferece download completo para uso offline. As ocorrências são colaborativas ou simuladas e não constituem confirmação oficial nem certificação de segurança de um trajeto.

## Testes e compilação

Na raiz:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
.\backend\.venv\Scripts\python.exe infra/validate_static.py
```

Na pasta Flutter:

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Para o teste de integração Android, mantenha a API demo disponível na porta 8000:

```powershell
flutter test integration_test/android_flow_test.dart -d emulator-5554
```

O APK é gerado em `mobile/build/app/outputs/flutter-apk/app-debug.apk`. Para instalar em celular físico, substitua o endereço de compilação pelo IP do computador. A compilação usa assinatura de desenvolvimento. Push requer os arquivos Firebase e a opção `FIREBASE_ENABLED=true`.

Para verificar a API em execução, a partir da raiz:

```powershell
.\backend\.venv\Scripts\python.exe scripts/smoke_api.py --url http://127.0.0.1:8000 --output .runtime/api-smoke.json
```

Esse teste cria um relato fictício e verifica HTTP, repetição idempotente, conflito, GeoJSON e WebSocket. Testes com respostas simuladas não comprovam disponibilidade de serviços externos; notificações e GPS precisam de verificação no aparelho. Não há build iOS validado por este repositório.

## Demonstração de RabbitMQ e Redis

O perfil de apresentação usa um projeto Docker separado, `ecopulse-apresentacao`, com API em `http://127.0.0.1:8011` e painel RabbitMQ em `http://127.0.0.1:15674`. Prepare o ambiente e abra o painel local:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\scripts\preparar_apresentacao.ps1
.\backend\.venv\Scripts\python.exe scripts/apresentacao_dsd.py painel
```

Abra `http://127.0.0.1:8765`. O painel consulta as filas reais e o cache real; as credenciais permanecem no servidor local. Pause os consumidores, envie um relato fictício, observe a mensagem pronta no RabbitMQ e retome o processamento para conferir a chave, a versão e o TTL no Redis. O relay independente continua publicando a outbox enquanto os consumidores de risco estão pausados.

O comando `scripts/apresentacao_dsd.py validar` executa um ensaio completo com um relato simulado e grava somente resultados locais em `.runtime/`. No celular, configure o IP do computador com a porta 8011 para usar esse ambiente. Os comandos do painel operam exclusivamente o projeto `ecopulse-apresentacao` e preservam seus volumes.

## Arquivos locais

O `.gitignore` exclui `.env`, credenciais, bancos, logs, caches, compilações, APKs e registros locais de execução. Mantenha esses arquivos no ambiente de desenvolvimento. Para baixar os fontes publicados, use `git clone` ou **Code → Download ZIP** no GitHub.
