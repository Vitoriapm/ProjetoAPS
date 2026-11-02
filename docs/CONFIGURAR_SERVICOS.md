# Configurar Firebase, APNs e OpenRouteService

> **Versão atual:** o código de 02/11/2026 oferece Alagamento e Vias. Os APKs de outubro mencionados neste guia são históricos e ainda podem mostrar Ar e Calor. Para testar a alteração, execute o código atual ou gere um novo APK.

Guia do EcoPulse, conferido em **04/10/2026**. A equipe tem conta Google, mas ainda não tem Apple Developer, Mac ou iPhone. Comece por Android e rotas. Nenhuma conta ou chave foi criada pelo assistente.

**Cliente e servidor Android preparados, celular registrado:** `mobile/android/app/google-services.json` e `secrets/fcm.json` estão presentes, estruturalmente válidos e pertencem ao mesmo projeto. O [APK Firebase](../entregas/EcoPulse-Firebase.apk) compilou às **15:58**, horário de São Paulo, com Firebase ativado, e o usuário informou sua instalação no celular. O servidor vê um único Android com token registrado, sem posição registrada naquela etapa inicial, conforme [firebase-phone-registration.json](evidence/firebase-phone-registration.json). O APK demo permanece com Firebase desligado. A chave ORS está configurada e a prova real do adaptador passou; os acessos iOS continuam pendentes. Preparação do cliente em [firebase-android-preparation.json](evidence/firebase-android-preparation.json).

A linha `FCM_CREDENTIALS_FILE` do `.env` foi configurada, sem alterar as demais. A autenticação OAuth Google passou, conforme [firebase-server-auth.json](evidence/firebase-server-auth.json), e o **dry-run real foi aceito pelo FCM**, com `provider_accepted=true` e `dry_run=true`, conforme [fcm-dry-run.json](evidence/fcm-dry-run.json). Isso comprova a validação da mensagem pelo provedor, sem entrega ao celular. Depois de o usuário confirmar o app em segundo plano, **um único alerta fictício foi enviado e aceito pelo FCM**, com `dry_run=false` e `provider_accepted=true`, conforme [fcm-phone-send.json](evidence/fcm-phone-send.json). O usuário confirmou a chegada e a abertura do EcoPulse ao tocar: **o teste direto de push Android passou por confirmação humana**, registrada em [fcm-phone-receipt.json](evidence/fcm-phone-receipt.json), com `confirmation_source=human_user_in_chat` e sem observação independente. O JSON de envio mantém `device_receipt_verified=false`, porque o script não observa o celular. Depois, o usuário confirmou aquisição GPS, offline, reabertura e reenvio no Android, com posição/precisão recebidas e um único relato novo sem duplicação no banco, conforme [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json). Seleção geográfica e dispatcher full continuam sem ensaio. A API demo reiniciou saudável com `fcm_configured=true`, preservando os 18 IDs de relatos do SQLite; evidência desse reinício em [firebase-demo-runtime.json](evidence/firebase-demo-runtime.json).

## 1. Firebase para Android

O projeto atual já concluiu o cadastro e o preparo da conta de serviço. Os passos de criação e download abaixo são referência para outro ambiente; não é necessário gerar ou baixar outra chave para continuar o teste atual.

1. Entre no [console Firebase](https://console.firebase.google.com/) com sua conta Google.
2. Crie um projeto com nome **EcoPulse APS**. Google Analytics é opcional; pode ficar desabilitado nesta apresentação. Mantenha o plano Spark: [Cloud Messaging é gratuito](https://firebase.google.com/products/cloud-messaging).
3. Em **Adicionar app → Android**, preencha o pacote exatamente assim: `br.edu.ecopulse.ecopulse`. Apelido sugerido: **EcoPulse Android**. Se a tela pedir SHA-1, ele não é necessário para este fluxo de notificações.
4. Baixe `google-services.json`. Guarde o arquivo original, sem colar seu conteúdo no chat.
5. As dependências Flutter e o plugin Google Services já estão preparados no EcoPulse. Não substitua os arquivos Gradle com o código de exemplo do assistente de cadastro.

O registro e o download seguem a [configuração oficial Android](https://firebase.google.com/docs/android/setup). Não é necessário criar Firestore, Storage, autenticação de usuários ou Cloud Functions para o fluxo implementado.

Em outro ambiente ainda sem a credencial do backend, no mesmo projeto Firebase, abra **Configurações do projeto → Contas de serviço → Firebase Admin SDK → Gerar nova chave privada**. Faça o download JSON e guarde-o localmente. No projeto atual, o arquivo já está em `secrets/fcm.json`. Essa é uma credencial privada do servidor e não pertence ao APK. [Orientação Firebase Admin](https://firebase.google.com/docs/admin/setup).

Na raiz `C:\Users\usuario\Desktop\APS APP`, valide e copie os dois downloads com o script existente. Substitua somente os caminhos pelos seus arquivos:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\prepare_firebase.py --android-file 'C:\caminho\google-services.json' --service-account-file 'C:\caminho\chave-do-servidor.json' --apply
.\backend\.venv\Scripts\python.exe .\scripts\check_push_setup.py
```

Os destinos são `mobile/android/app/google-services.json` e `secrets/fcm.json`. O script confere pacote/projeto e protege arquivos diferentes já existentes. Nesta etapa o iOS continuará incompleto; isso não impede preparar Android.

O `.env` da raiz já foi configurado com:

```dotenv
FCM_CREDENTIALS_FILE=/run/secrets/fcm.json
```

Esse caminho é o do contêiner Docker; o iniciador demo o converte para o caminho local do projeto. O arquivo `.env` já existente deve ser preservado: altere somente a linha necessária, mantendo as senhas de infraestrutura.

O APK Firebase está instalado no celular, com registro confirmado pelo servidor; não é necessário recompilar apenas para configurar a conta de serviço. Como referência para outro dispositivo, em **Conexão e informações**, use **http://198.51.100.22:8000** no celular conectado à mesma rede Wi-Fi do computador, ou **http://10.0.2.2:8000** no emulador Android. O APK demo tem Firebase desligado. Com o EcoPulse em segundo plano, o usuário confirmou a chegada do alerta fictício e a abertura do app após tocar. [Pré-requisitos Flutter/FCM](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

O modo demo permite registrar token e posição; o Android atual ainda não enviou posição. **O envio automático por raio acontece no serviço de alertas do modo full**, via RabbitMQ. Não é necessário iniciar o cluster para o ensaio direto atual. O script de mensagem direta em [PUSH.md](PUSH.md) testa um token escolhido, sem comprovar a seleção geográfica, mensageria, retries ou DLQ. `accepted` pelo FCM e o dry-run aceito não comprovam recebimento no aparelho.

## 2. OpenRouteService

`ORS_API_KEY` já está preenchida localmente. Não é necessário obter outra chave. A consulta real do adaptador **passou**, conforme [routes-live.json](evidence/routes-live.json): percurso de **3.035,2 m**, duração de **432,8 s**, evitando um bloqueio fictício em Ribeirão Preto. A API atual também **passou**, conforme [routes-api-live.json](evidence/routes-api-live.json): HTTP 200 com os mesmos valores, zero bloqueios ativos e nenhum novo relato, preservando os 18 IDs anteriores após o ajuste de acesso à rede do processo. O usuário confirmou que a rota apareceu no Android após escolher origem/destino, conforme [routes-phone-confirmation.json](evidence/routes-phone-confirmation.json). A confirmação é humana, sem observação independente; os pontos e valores desse percurso no celular não foram informados.

Os passos de cadastro e criação de chave abaixo são referência para outro ambiente ainda sem configuração:

1. Abra o [portal HeiGIT](https://account.heigit.org/), responsável pelas contas ORS. Escolha **Go sign up now** se ainda não tiver conta e confirme o e-mail solicitado.
2. No painel autenticado, abra o gerenciamento de API keys e obtenha a chave para OpenRouteService. O plano **Standard** é gratuito; a página oficial consultada mostra Directions V2 com 2.000 consultas/dia e 40/minuto. [Planos oficiais](https://account.heigit.org/info/plans).
3. Copie a chave **somente para a linha `ORS_API_KEY` do `.env` local**, sem enviá-la no chat. Não a coloque em Dart nem no APK. Chaves recentes podem parecer um JWT e começar com `eyJ`; ainda são chaves ORS válidas. [FAQ oficial](https://giscience.github.io/openrouteservice/frequently-asked-questions).

Formato local:

```dotenv
ORS_API_KEY=cole_a_chave_apenas_no_arquivo_local
```

Para reproduzir a validação na raiz do projeto:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\validate_routes_live.py
.\backend\.venv\Scripts\python.exe .\scripts\validate_routes_live.py --live --output .\docs\evidence\routes-live.json
```

`configuration_ready` confirma somente a presença da chave. `passed` no segundo comando exige resposta real e aprovação das verificações geométricas, usando um bloqueio fictício de Ribeirão Preto. O resultado não exibe a chave.

Pare e inicie novamente a API demo com `scripts/run_demo.ps1` para carregar o `.env` atualizado. No modo full, **recrie** os serviços API/alertas com Compose: apenas `restart` não atualiza variáveis do contêiner. Não use o projeto antigo de validação promovido como se fosse um cluster novo; siga [infra.md](infra.md).

Abra o app, escolha origem/destino e confira trajeto, distância e duração. A rota considera os riscos conhecidos; não certifica a segurança real da viagem. Detalhes em [ROTAS.md](ROTAS.md).

## 3. APNs e iOS

APNs é o serviço Apple que entrega notificações no iPhone. O Firebase encaminha notificações para ele. A conta Apple gratuita/Personal Team **não inclui Push Notifications**; é necessário acesso a uma equipe Apple Developer Program habilitada. [Capacidades oficiais](https://developer.apple.com/help/account/reference/supported-capabilities-ios/).

Antes de contratar uma conta individual, pergunte à faculdade se há uma equipe Apple Developer e Mac/iPhone para o trabalho. A taxa normal é US$99/ano ou valor local; instituições educacionais elegíveis podem solicitar isenção, sujeita à aprovação Apple. A isenção institucional não é concedida ao aluno individual. [Programa Apple](https://developer.apple.com/programs/), [isenção](https://developer.apple.com/help/account/membership/fee-waivers/).

Quando houver acesso autorizado à equipe:

1. No mesmo projeto Firebase, adicione app iOS com Bundle ID `br.edu.ecopulse.ecopulse` e baixe `GoogleService-Info.plist`.
2. Um Account Holder/Admin registra um App ID explícito com esse Bundle ID e Push Notifications no portal Apple. [Registrar App ID](https://developer.apple.com/help/account/identifiers/register-an-app-id/).
3. Em **Keys → + → APNs → Configure**, prepare a chave e o ambiente correspondente ao teste. A interface atual distingue ambiente e escopo; não presuma que qualquer chave serve para desenvolvimento e produção. Baixe o `.p8`, disponível uma única vez, e guarde seu Key ID/Team ID. [Criar chave APNs](https://developer.apple.com/help/account/keys/create-a-private-key/).
4. Em **Firebase → Configurações do projeto → Cloud Messaging → configuração iOS → chave APNs**, envie o `.p8` e informe Key ID/Team ID no campo do ambiente correspondente. [Configuração FCM Apple](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).
5. No Mac/Xcode, adicione o plist ao target Runner, selecione Team/assinatura e habilite Push Notifications/Background Modes. Compile e teste em iPhone; os passos detalhados estão em [VALIDACAO_IOS_PENDENTE.md](VALIDACAO_IOS_PENDENTE.md).

É possível preparar cadastros pelo navegador no Windows, mas isso não produz um IPA nem comprova recebimento APNs. A validação continua pendente até obter os acessos e o aparelho.

## Próximo passo com o assistente

O teste direto de push Android está concluído por confirmação do usuário: o alerta chegou com o app preparado em segundo plano e tocar abriu o EcoPulse. A rota também apareceu no Android segundo a confirmação humana, após escolher origem/destino; o adaptador e a API reais já passaram. Permanecem pendentes GPS físico, aviso em primeiro plano, seleção geográfica/dispatcher full, iOS/APNs e relatório APS. A conta de serviço, a chave ORS e o APK permanecem preparados; não envie chaves ou tokens no chat.
