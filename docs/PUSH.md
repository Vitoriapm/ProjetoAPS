# Push do EcoPulse

Atualizado em **05/10/2026**. O cliente Android já está configurado: `mobile/android/app/google-services.json` está presente, válido e corresponde ao pacote EcoPulse. O [EcoPulse-Firebase.apk](../entregas/EcoPulse-Firebase.apk), usado no ensaio já confirmado, é a versão **1.0.0+2**, compilada em **05/10 às 00:17**, horário de São Paulo, com `FIREBASE_ENABLED=true` e recursos Firebase nativos incorporados. Os dados estão em [firebase-apk-info.json](../entregas/firebase-apk-info.json). O [APK demo](../entregas/EcoPulse-demo.apk) permanece com Firebase desligado e avisos no app.

**O push geográfico pelo backend full passou em 05/10**, após o usuário informar a instalação da versão 1.0.0+2: um relato fictício percorreu PostgreSQL/outbox → RabbitMQ → worker → alertas → FCM. O servidor confirmou um Android dentro do raio e um envio aceito; o usuário confirmou chegada em segundo plano e abertura ao tocar. [geographic-push.json](evidence/geographic-push.json) registra a execução do servidor e [geographic-push-phone-receipt.json](evidence/geographic-push-phone-receipt.json) registra a confirmação humana, sem observação independente do celular. O controle fora do raio foi um cadastro web sintético; não houve segundo aparelho físico fora da área. O teste direto do APK anterior permanece registrado separadamente em [fcm-phone-receipt.json](evidence/fcm-phone-receipt.json).

`secrets/fcm.json` está presente, estruturalmente válido e pertence ao mesmo projeto da configuração Android. Somente a linha `FCM_CREDENTIALS_FILE` foi configurada no `.env`, preservando as demais linhas. A autenticação OAuth Google passou, conforme [firebase-server-auth.json](evidence/firebase-server-auth.json). O FCM aceitou um **dry-run real**, com `provider_accepted=true` e `dry_run=true`, conforme [fcm-dry-run.json](evidence/fcm-dry-run.json): a mensagem foi validada pelo provedor, sem entrega ao aparelho. Depois foi enviado um único alerta fictício, aceito com `dry_run=false` e `provider_accepted=true`, conforme [fcm-phone-send.json](evidence/fcm-phone-send.json). Esse arquivo mantém `device_receipt_verified=false`, porque o script não observa o celular; a confirmação humana de chegada e toque fica na evidência de recepção.

A API demo foi reiniciada saudável com `fcm_configured=true` e preservou os 18 IDs de relatos do SQLite; essa etapa histórica está em [firebase-demo-runtime.json](evidence/firebase-demo-runtime.json). [firebase-phone-registration.json](evidence/firebase-phone-registration.json) também é um **snapshot histórico** de um único Android com token e ainda sem posição naquela captura. No envio direto do APK anterior, GPS não foi exercitado. **Depois dessa captura**, o usuário confirmou aquisição GPS e offline/reabertura/reenvio; o banco confirmou posição/precisão e um relato novo sem duplicação em [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json). Em 05/10, o novo ambiente full recebeu token e posição recente, exercitou a seleção geográfica e enviou o alerta pelo dispatcher real. Movimento GPS físico e FCM em primeiro plano ainda não foram ensaiados. No iOS, Apple Developer, APNs, Mac e iPhone permanecem pendentes. A preparação do cliente está em [firebase-android-preparation.json](evidence/firebase-android-preparation.json).

## O que está implementado

- Permissão de notificações, incluindo Android 13+, sem pedir novamente a cada sincronização. Ao voltar ao app, a permissão é consultada outra vez, permitindo recuperar uma autorização feita nas configurações do aparelho.
- Inicialização automática de tokens desativada nas configurações nativas. O cliente habilita FCM somente depois da permissão; no iOS, espera APNs antes de solicitar token FCM.
- Registro autenticado do token e da plataforma em `/v1/dispositivos/push`, associado à instalação. Atualização de token pelo stream Firebase, tentativas após conexão/retomada e registro serializado para evitar que chamadas simultâneas sobrescrevam o token mais recente.
- Aviso em primeiro plano atualiza os dados no mapa. Toque na notificação, tanto com app em segundo plano como encerrado, abre o app e solicita sincronização. Eventos repetidos são ignorados por caminho, com memória limitada a 128 IDs; o mesmo evento pode atualizar ao ser recebido e ao ser aberto. Essa deduplicação dura o processo atual.
- Canal Android `ecopulse_alertas`, com importância alta e ícone branco próprio. O usuário pode alterar a importância do canal nas configurações do Android.
- Seleção geográfica pela última posição registrada, obtida por GPS ou escolhida manualmente, com idade de até uma hora. O app envia raio de dispositivo de **1.000 m**; o servidor acrescenta a influência de **200 m** do incidente, selecionando dispositivos a até 1.200 m do centro nas configurações atuais. A regra usa o raio registrado e a influência do incidente, sem exigir que a origem seja GPS. Não há rastreamento permanente em segundo plano.
- Todos os incidentes ativos podem gerar push, incluindo gravidade **baixa**; o dispatcher não restringe o envio a gravidade alta. Incidentes expirados não são enviados. O **aviso local de proximidade de 1.000 m no app** é um fluxo separado da seleção FCM do servidor; a confirmação de um aviso local não comprova entrega por push.
- Envio pelo Admin SDK com TTL limitado ao vencimento do incidente e a 30 minutos. Android utiliza o ID do incidente como tag; APNs usa o mesmo ID para agrupamento e substituição de notificações pendentes. Ocorrências fictícias trazem “demonstração” e “alerta simulado” no próprio texto do sistema.
- Envio registrado no banco, proteção contra reenvio já aceito, retries/DLQ via RabbitMQ e descarte de tokens não registrados, preservando tokens renovados durante o envio.

`accepted` no banco significa aceitação pelo FCM. Não confirma que um aparelho recebeu, exibiu ou abriu o aviso. Uma queda entre a aceitação pelo provedor e a gravação no banco pode causar repetição; tag/agrupamento e deduplicação reduzem esse efeito, sem prometer entrega exatamente uma vez.

## Configuração aplicada e teste atual

O cadastro Android, o arquivo nativo e a conta de serviço já estão preparados no **mesmo projeto Firebase**. Não é necessário baixar outra chave para continuar. Os arquivos iOS não são exigidos para testar Android. O `.env` já contém `FCM_CREDENTIALS_FILE=/run/secrets/fcm.json`; o iniciador demo converte esse caminho para `secrets/fcm.json` no computador e mantém o banco SQLite local.

O usuário informou a instalação da atualização **1.0.0+2** no celular, confirmou a preparação para um único aviso e respondeu **“Recebi e o app abriu ao tocar”**. O ensaio geográfico da nova versão utilizou posição recente e o serviço de alertas full; suas evidências são separadas do envio direto anterior. Os indicadores de envio e recepção foram atualizados em [firebase-apk-info.json](../entregas/firebase-apk-info.json), mantendo `independent_device_observation=false` e preservando o histórico anterior.

Os endereços de referência em **Conexão e informações** são:

- Celular na mesma rede Wi-Fi: **http://198.51.100.22:8011** — ambiente full ativo utilizado no ensaio geográfico.
- Demo local: **http://198.51.100.22:8000** — referência dos ensaios anteriores; não executa o dispatcher separado.
- Emulador Android: **http://10.0.2.2:8000**.

O demo permite registrar token e posição; a posição GPS do Android foi confirmada no teste posterior ao snapshot inicial. **O envio automático por raio exige o serviço de alertas em modo full**, utilizado no ensaio de 05/10. A mensagem direta pode testar o token sem posição e não comprova a seleção geográfica. O ensaio atual validou essa seleção com uma posição registrada recente; não demonstrou rastreamento ou entrada no raio com GPS em segundo plano.

### Ensaio geográfico concluído em 05/10/2026

O ambiente separado `ecopulse-fcm-test` foi iniciado e respondeu saudável em **http://198.51.100.22:8011**. Ele utiliza PostgreSQL/PostGIS novo, duas APIs, um worker, três nós RabbitMQ e seis nós Redis. A réplica PostgreSQL e o segundo worker não participam deste ensaio. O projeto anterior `ecopulse-validation` permanece parado, com seus volumes preservados. A [evidência de preparação](evidence/geographic-push-preparation.json) registra o estado inicial sem relatos nem entregas e a leitura da configuração FCM dentro do contêiner.

O dispatcher de alertas foi **pausado durante a preparação do celular** e retomado após a confirmação humana. O app registrou seu próprio token e a posição escolhida na região de Ribeirão Preto. Como essa referência ficava fora do raio do ponto fixo inicial, o relato utilizou um ponto fictício arredondado em grade de 0,01 grau próximo da referência. As evidências públicas omitem coordenadas, tokens e chaves. O estado local com o ponto aproximado fica em `.runtime`, excluído do ZIP de fontes.

Dois cadastros sintéticos `platform=web`, um dentro e outro fora do raio, verificaram seleção sem contactar FCM para esses cadastros. O cadastro dentro foi selecionado e registrado como `unsupported`; o de fora não foi selecionado nem gerou entrega. O Android real dentro gerou exatamente uma entrega `accepted`. Um POST HTTP 201 criou um relato e um incidente fictícios; o replay idêntico retornou HTTP 200, mantendo um relato, um vínculo e um evento de cada tipo na outbox. Ambos os eventos foram publicados e processados por `risk` e `alerts`, com zero eventos pendentes na conferência.

O usuário confirmou chegada em segundo plano e abertura por toque. Este ensaio não injetou falhas/retries, não testou um segundo telefone físico fora do raio, movimento GPS real, FCM em primeiro plano ou APNs/iOS.

A configuração reproduzível está em [compose.phone-test.yaml](../infra/compose.phone-test.yaml). O [script de validação](../scripts/validate_geographic_push.py) usa `plan` sem efeitos por padrão; `inspect` lê o estado, `prepare --allow-registration` registra somente cadastros web fictícios e `trigger --allow-send` cria um único relato simulado. A opção de preparação `--use-coarse-demo-grid` escolhe a grade aproximada dentro da região e do raio. O envio exige telefone preparado e configuração full no projeto isolado. Repetir o mesmo payload/UUID preserva a idempotência; não substituir o estado para gerar avisos adicionais inadvertidamente.

### Rodada adicional preparada em 05/10

O [APK de testes 1.0.0+3](../entregas/EcoPulse-Firebase-testes.apk), de mesma
assinatura, acrescenta em Conexão e informações o último callback de push. A
indicação de primeiro plano contém horário e contagem desta execução; não é
gerada por WebSocket e não persiste após encerramento do processo. Reabrir a
ficha após receber lê o indicador atualizado. O recebimento nesta nova versão
ainda depende do teste físico. As provas anteriores são da versão +2 e permanecem
preservadas. iOS/APNs ficam adiados conforme pedido da equipe.

Veja [TESTES_FINAIS_ANDROID.md](TESTES_FINAIS_ANDROID.md), os metadados
[firebase-tests-apk-info.json](../entregas/firebase-tests-apk-info.json) e
`scripts/validate_android_push.py`. O teste em primeiro plano usa um envio FCM
direto, sem criar incidente. A exclusão por raio usa o fluxo de relato e workers,
com o mesmo aparelho em outra etapa; nenhuma posição/token do celular é alterada
pelo script. Aceite FCM, recepção humana e seleção por raio são provas separadas.

### Referência para reproduzir em outro ambiente

Os passos abaixo documentam a preparação já concluída. Use-os em um ambiente ainda sem os arquivos, mantendo o mesmo projeto e sem substituir a chave existente inadvertidamente:

1. No [console Firebase](https://console.firebase.google.com/), abrir **Configurações do projeto → Contas de serviço → Firebase Admin SDK → Gerar nova chave privada**. Guardar o JSON no computador. Ele é uma credencial do servidor e não pertence ao APK. [Orientação Firebase Admin](https://firebase.google.com/docs/admin/setup).
2. Validar o download junto com a configuração Android já existente, sem copiar:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\prepare_firebase.py --android-file .\mobile\android\app\google-services.json --service-account-file 'C:\caminho\firebase-admin.json'
```

3. Repetir com `--apply` para gravar a conta de serviço em `secrets/fcm.json`. O script confere projeto/pacote, preserva o arquivo Android já validado e protege configurações locais diferentes. Ele não cria contas nem modifica `.env`.
4. Definir **localmente** `FCM_CREDENTIALS_FILE=/run/secrets/fcm.json` no `.env`, preservando as outras linhas. No demo, iniciar novamente `scripts/run_demo.ps1` para carregar a configuração. No modo full, recriar o serviço de alertas conforme o guia de infraestrutura; `secrets` é montado somente para leitura. Não colocar a conta de serviço no app.
5. Instalar o APK Firebase já compilado e configurar uma API alcançável em **Conexão e informações**. Usar um aparelho com Google Play Services e permitir notificações. O envio automático por raio ocorre no serviço de alertas do modo full; o modo demo permite registrar o token e ensaiar o cliente.

Para reproduzir o build Firebase após uma alteração futura de fonte/configuração:

```powershell
Set-Location mobile
flutter build apk --debug --dart-define=FIREBASE_ENABLED=true --dart-define=API_BASE_URL=http://IP_DO_COMPUTADOR:8000
```

O Android aplica o plugin Google Services quando o arquivo existe; isso ocorreu no APK anterior e na versão atual 1.0.0+2. O comando de build não instala o app nem envia automaticamente notificações.

No Mac, adicionar `GoogleService-Info.plist` ao target Runner no Xcode, selecionar o Apple Team correto, habilitar **Push Notifications**, **Background fetch** e **Remote notifications** e configurar a assinatura. Enviar a chave APNs `.p8`, seu Key ID e Team ID ao Firebase. Guardar a chave privada em `secrets`, fora dos fontes distribuídos. As entradas de background e o swizzling padrão já foram preservados; não foi inventado certificado, Team ou entitlement.

Essas exigências e a ordem APNs/FCM são descritas na [configuração oficial Firebase para Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started). Os caminhos de toque seguem [recebimento oficial Firebase](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages), e o canal segue [documentação Android](https://developer.android.com/develop/ui/compose/notifications/channels).

## Diagnóstico e prova de recebimento

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\check_push_setup.py
```

O diagnóstico lê arquivos locais e imprime apenas estados booleanos. Não envia mensagens nem mostra chave, token ou ID do projeto. [push-setup.json](evidence/push-setup.json) é a evidência histórica anterior ao cadastro Android. A preparação do servidor está em [firebase-server-auth.json](evidence/firebase-server-auth.json) e [firebase-demo-runtime.json](evidence/firebase-demo-runtime.json); [firebase-phone-registration.json](evidence/firebase-phone-registration.json) registra a captura inicial do token sem posição, complementada depois pela prova GPS. Os indicadores `fcm_configured` e `android_ready_for_real_test` não comprovam envio ou recebimento.

Para validar uma mensagem no FCM, guardar somente o token do aparelho em um arquivo local dentro de `secrets`, obtido durante o teste local controlado. Não usar o token como argumento nem compartilhá-lo:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\send_test_push.py --token-file .\secrets\device-token.txt --output .\docs\evidence\fcm-dry-run.json
```

O padrão é **dry-run**: autentica e valida a mensagem no provedor, sem entrega. Esse ensaio já passou com o token do Android registrado, conforme [fcm-dry-run.json](evidence/fcm-dry-run.json). Não é prova de chegada, exibição ou toque. No **APK anterior**, a opção `--send` foi usada uma vez após a confirmação do app em segundo plano; o FCM aceitou **um aviso explicitamente fictício**, conforme [fcm-phone-send.json](evidence/fcm-phone-send.json). A resposta do script continua marcando `device_receipt_verified=false`, pois ele não observa o celular. O usuário confirmou separadamente a chegada e a abertura ao tocar, conforme [fcm-phone-receipt.json](evidence/fcm-phone-receipt.json). O ensaio direto anterior passou por essa confirmação humana e não comprova seleção por raio, mensageria, retries ou DLQ. Nenhuma mensagem foi enviada para testar a build 1.0.0+2 até o registro atual deste guia.

O cenário confirmado no APK anterior foi Android com app em segundo plano e abertura por toque. Na build atual, esse cenário ainda precisa ser repetido; app aberto, encerrado normalmente, reconexão após falha de registro e permissão negada e posteriormente autorizada também são cenários a ensaiar. No iPhone, o teste depende dos acessos pendentes. Não confundir encerramento normal com “forçar parada” no Android ou restrições de bateria/rede, que podem impedir a entrega. Para provar a seleção por raio, utilizar o fluxo normal de um relato fictício, uma posição GPS ou manual recente na área e outra fora dela, considerando os 1.000 m do dispositivo mais a influência do incidente. Incidente de gravidade baixa também pode disparar esse envio.

As mensagens têm texto de notificação; o sistema cuida da exibição em segundo plano. O projeto não promete execução permanente de Dart nem atualização silenciosa do mapa com app fechado.

## Validação feita sem credenciais

- 11 testes Flutter de push passaram: ordem APNs, Firebase desligado, navegador, permissão, retry, token renovado durante chamada em andamento, deduplicação, toque/abertura e descarte do serviço.
- 11 testes backend/preparo passaram: registro de aceite, retry pendente, limpeza de token inválido com renovação concorrente, navegador, posição/expiração, payload nativo, validação/cópia controlada dos arquivos.
- Testes usam gateway/adaptador controlado. Não substituem o recebimento FCM/APNs em aparelho físico. A referência do payload é a [API oficial Python do Firebase](https://firebase.google.com/docs/reference/admin/python/firebase_admin.messaging).

## Primeiro plano Android em 06/10/2026

**Confirmado pelo usuário** no APK +3: app visível no mapa, um envio FCM direto
aceito e indicador de callback às 10:10:58, uma mensagem nesta sessão. Evidências
de [envio](evidence/android-foreground-open-map-send-20261006.json) e
[recepção humana](evidence/android-foreground-open-map-receipt-20261006.json)
separadas; sem observação independente do celular ou teste de raio nesta etapa.
A ficha também mostrou falha na tentativa de registro. Os caminhos são distintos:
um token já cadastrado permite enviar enquanto uma nova tentativa do cliente
pode falhar. A causa dessa falha ainda não foi comprovada; salvar a URL e retomar
uma sincronização/posição será usado para conferir a recuperação.

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

## APK +4: atualização da ficha e mensagens de cadastro

`entregas/EcoPulse-Firebase-testes.apk` foi atualizado para **1.0.0+4**, com o
mesmo pacote e certificado da versão +3. Pode ser instalado como atualização,
preservando os dados. A ficha agora acompanha o controlador enquanto permanece
aberta, e o cadastro bem-sucedido mostra **“Push registrado no servidor.”**.
Falhas na leitura do token Firebase e no cadastro no backend têm avisos distintos.
A mudança foi verificada por **47 testes Flutter** e análise sem problemas.

A instalação e recepção no Android físico para +4 ainda não foram confirmadas.
O push em primeiro plano e a recuperação do cadastro registrados nesta rodada
ocorreram na versão **+3**; suas evidências continuam preservadas em arquivos
próprios. Não é necessário reenviar push para demonstrar a correção do texto.

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
