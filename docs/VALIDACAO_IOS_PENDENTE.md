# Auditoria iOS e notificações mobile — 03/10/2026

**Estado:** revisão estática dos arquivos concluída; compilação, assinatura, instalação em iPhone e recebimento real de push **não executados**. A revisão foi feita em Windows, sem Mac/Xcode. Não há IPA validado por esta auditoria. As evidências Android executadas pela equipe ficam em [VALIDACAO.md](VALIDACAO.md), que este documento não altera.

## Projeto iOS encontrado

| Item | Resultado da revisão |
| --- | --- |
| Projeto e workspace | `mobile/ios/Runner.xcodeproj` e `Runner.xcworkspace` existem, com target Runner, testes, recursos e scripts Flutter. |
| Bundle ID | `br.edu.ecopulse.ecopulse` em Debug, Profile e Release. Testes usam `br.edu.ecopulse.ecopulse.RunnerTests`. O ID deve coincidir com o registro Apple/Firebase escolhido pela equipe. |
| Versão mínima | Projeto configurado para iOS 15.0, compatível com o mínimo declarado pelos pacotes locais Firebase Core 4.15.0 e Messaging 16.7.0. Isso não comprova a resolução/compilação dos pacotes. |
| AppDelegate/SceneDelegate | Template Flutter com registro de plugins no engine implícito e cenas. Não foi compilado em Xcode. |
| Localização | `NSLocationWhenInUseUsageDescription` em português. A lógica solicita posição e acompanha mudanças com o app em primeiro plano; não há promessa de rastreamento contínuo em segundo plano. |
| Rede local | `NSLocalNetworkUsageDescription` em português e `NSAllowsLocalNetworking=true`. Permissão e conexão real por IP precisam ser exercitadas em iPhone. |
| Modos em segundo plano | `remote-notification` já existia. Esta auditoria acrescentou `fetch` ao mesmo array, conforme a preparação indicada pelo Firebase. Isso não cria um job de sincronização offline em segundo plano. |
| Assinatura | Não há `DEVELOPMENT_TEAM` configurado no projeto. Certificados, perfil de provisionamento e dispositivo são responsabilidade da conta Apple da equipe e ainda não foram verificados. |
| Entitlements e Push capability | Não há arquivo `.entitlements`, referência `CODE_SIGN_ENTITLEMENTS` nem declaração de Push Notifications em `SystemCapabilities`. O projeto ainda não está habilitado para APNs. |
| Firebase iOS | `Runner/GoogleService-Info.plist` ausente e sem referência no projeto/resources. Quando obtido, deve ser adicionado ao target Runner no Xcode; copiar para o diretório isoladamente não comprova inclusão no app. |

A única alteração nativa realizada foi acrescentar `fetch` a `UIBackgroundModes`. Não foram inseridos Apple Team ID, certificados, entitlements fictícios ou arquivos Firebase sem credenciais reais.

## Swift Package Manager e arquivos gerados

O projeto gerado pelo Flutter 3.47 usa Swift Package Manager: há `FlutterGeneratedPluginSwiftPackage` no Xcode e a pre-action **Run Prepare Flutter Framework Script** no scheme. A ausência de `Podfile`, Pods e `Podfile.lock` não é, por si só, uma falha nessa configuração. O Flutter usa SwiftPM por padrão nas versões atuais e pode recorrer ao CocoaPods para plugins incompatíveis. [Documentação Flutter](https://docs.flutter.dev/packages-and-plugins/swift-package-manager/for-app-developers).

Foram encontrados manifests SwiftPM nos plugins nativos iOS atuais: connectivity, Firebase Core/Messaging, Geolocator, integration_test, SharedPreferences e Sqflite. `path_provider_foundation` 2.6.0 declara implementação Dart/FFI; não se espera um target nativo registrado da mesma forma.

`ios/Flutter/Generated.xcconfig` e arquivos efêmeros ainda contêm caminhos Windows, e o pacote agregado atual está vazio. Eles são gerados e ignorados no Git. Ao preparar o projeto no Mac, execute o fluxo Flutter para regenerar dependências e caminhos locais; não copie caminhos Windows para um build Xcode nem edite o pacote efêmero manualmente. Resolução SwiftPM, downloads do Firebase iOS SDK e eventual fallback CocoaPods permanecem sem validação.

## Permissões de GPS e rede

- O código local do Geolocator solicita **When In Use** quando essa descrição existe no Info.plist. Não há necessidade funcional de inventar uma descrição “Always” para o fluxo atual. Para uma futura submissão à loja, revisar a configuração `BYPASS_PERMISSION_LOCATION_ALWAYS` do plugin e as declarações de privacidade conforme o método de dependências usado; adicionar uma macro somente ao Runner não comprova que ela chegou ao target SwiftPM do plugin.
- Testar localização precisa, localização aproximada, recusa da permissão, GPS desligado e retorno do app. A seleção manual deve continuar disponível. Não registrar manual como GPS.
- ATS e a permissão de Rede Local são mecanismos diferentes. O projeto declara intenção de acessar recursos locais, mas isso não substitui autorização do usuário nem teste real de HTTP/WebSocket por IP. Não foi adicionada exceção geral `NSAllowsArbitraryLoads`. [ATS local da Apple](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking).
- O app recebe endereço manualmente e usa comunicação unicast. Não há descoberta Bonjour implementada; não foram adicionados serviços Bonjour ou permissões multicast sem necessidade.

## Push: configurações e comportamento encontrado

`PushService` está protegido por `FIREBASE_ENABLED`, cujo padrão é `false`. Nesse estado, informa “Push pendente” e não chama a inicialização Firebase pelo Dart. O navegador também retorna com aviso de que push nativo depende das plataformas mobile. A ativação pelo define não cria arquivos, permissões, conta Apple ou credenciais de servidor.

Quando ativado, o serviço inicializa Firebase, solicita permissão, observa renovação do token, eventos em primeiro plano, abertura por toque e mensagem inicial. Registra o token pela sessão de instalação no backend e tenta o registro novamente na retomada. O código usa a configuração nativa para `Firebase.initializeApp()`, sem `firebase_options.dart`; por isso os arquivos nativos reais precisam estar incluídos no build.

**Guarda APNs corrigida no Dart:** o serviço verifica `getAPNSToken()` antes de pedir `getToken()` no iOS. Quando APNs ainda não está disponível, mantém os listeners ativos, informa o estado de espera e tenta novamente na retomada. A inicialização usa esse mesmo caminho de registro e mantém a consulta da mensagem inicial. Android não depende da consulta APNs, e Firebase desligado continua sem iniciar o SDK pelo Dart. A ordem segue a [preparação FCM Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started). Method swizzling deve permanecer habilitado para esse fluxo.

Cinco testes isolados em `mobile/test/push_service_test.dart` verificam APNs ausente sem chamada FCM, APNs disponível após nova tentativa, Android sem consulta APNs, FCM ainda indisponível e Firebase desligado. A raiz executou **22 testes Flutter, todos aprovados**, incluindo esses cinco. Eles usam respostas controladas e comprovam a regra do código; **não comprovam registro APNs real, assinatura iOS nem recebimento de push no aparelho**.

Em primeiro plano, `alert=false` e `sound=false` deixam a atualização no app, sem prometer banner do sistema. Não há handler Dart de `onBackgroundMessage`. O backend envia payload com `notification` e `data`; recebimento visual em segundo plano e atualização ao tocar precisam ser testados. Sincronização silenciosa de dados e fila offline com o app encerrado não estão implementadas por esse fluxo. [Estados de recebimento FCM](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages).

Não anexamos um entitlement APNs genérico ao projeto: ele depende do perfil real. No Xcode, habilitar Push Notifications deve gerar/vincular `aps-environment` compatível com a assinatura e o ambiente de desenvolvimento/produção. [Entitlement APNs da Apple](https://developer.apple.com/documentation/BundleResources/Entitlements/aps-environment).

## Auditoria Android, sem alteração de arquivos

- Namespace e applicationId: `br.edu.ecopulse.ecopulse`, consistentes com a pasta/package da MainActivity.
- Manifest declara INTERNET, localização FINE/COARSE e POST_NOTIFICATIONS. Há permissão para HTTP local no protótipo. GPS e notificações dependem também da autorização em tempo de execução e do estado do aparelho.
- `settings.gradle.kts` declara Google Services 4.5.0 com `apply false`. `app/build.gradle.kts` aplica o plugin somente se `google-services.json` existir. O arquivo não foi encontrado nesta revisão; o APK demo pode funcionar com Firebase desligado, mas isso não valida o build Firebase ativado.
- FCM precisa de aparelho com serviços Google compatíveis ou emulador com Google APIs. A configuração do app deve ter esse applicationId e pertencer ao mesmo projeto Firebase usado pelas credenciais do backend. [Requisitos FCM por plataforma](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).
- Recebimento em primeiro plano, segundo plano, após toque, renovação de token e recusa de permissão ainda precisam de ensaio com push real. O status “registrado” indica envio do token ao backend, não prova de uma notificação recebida.
- Release continua com assinatura de desenvolvimento no Gradle. É suficiente para o cenário acadêmico local previsto; não representa configuração de publicação em loja.

Esta auditoria não mudou Android nem repetiu build/instalação. Use os resultados concretos registrados pela raiz para informar o estado Android.

## Como desbloquear e validar iOS

1. Obter Mac com Xcode compatível com o SDK Flutter usado e iPhone de teste. Configurar Flutter/Xcode e verificar o ambiente no Mac. Registrar versões e dispositivo.
2. No diretório `mobile`, executar `flutter pub get` e preparar um primeiro build iOS com Firebase desligado. Abrir `ios/Runner.xcworkspace`; conferir a resolução SwiftPM e as pre-actions. Se houver plugin incompatível, seguir o fallback informado pelo Flutter, sem criar um Podfile arbitrário neste Windows.
3. Selecionar conta/Team, Bundle ID autorizado e assinatura/provisionamento no target Runner. Instalar a versão sem Firebase no iPhone e verificar abertura, mapa/lista, recusa de GPS, ponto manual, banco local, fechamento/reabertura e reenvio de pendência ao servidor na LAN.
4. Para push, registrar o app iOS no Firebase com o Bundle ID escolhido, adicionar o `GoogleService-Info.plist` ao target e aos recursos do build, habilitar Push Notifications e conferir `aps-environment` no perfil assinado. Conferir Background Modes (fetch/remote notifications), sem habilitar GPS background desnecessário.
5. Obter/configurar chave APNs e Team/Key ID no Firebase. A chave privada e a credencial Firebase Admin permanecem fora do repositório. Configurar o arquivo de credenciais no backend full/serviço de alertas.
6. Compilar com `--dart-define=FIREBASE_ENABLED=true` após concluir as configurações nativas. Exercitar no iPhone a guarda APNs já implementada, confirmar permissão, token associado à sessão e posição/raio válidos para a seleção geográfica.
7. Produzir um alerta fictício elegível e registrar recebimento no iPhone, horário/evento, estado do app e ação após toque. Repetir em primeiro plano e segundo plano, com a versão assinada correspondente. Registrar separadamente aceitação pelo FCM e recebimento no aparelho.

Os comandos acima são passos futuros no Mac; não foram executados nesta revisão. Dados de dispositivos, tokens e credenciais não devem ser publicados como evidência.

## O que ainda impede afirmar “ambas as plataformas validadas”

| Evidência necessária | Impedimento concreto atual |
| --- | --- |
| Build/instalação iOS | Sem Mac/Xcode/iPhone e sem assinatura Apple configurada. |
| Dependências nativas iOS | Agregador SwiftPM e caminhos ainda gerados em Windows; resolução e compilação no Mac não executadas. |
| APNs/FCM iOS | Sem plist Firebase no target, capability/entitlement/perfil Push e chave APNs verificados. A guarda do token APNs está corrigida e coberta por testes isolados, mas o registro real ainda não foi exercitado. |
| FCM Android ativado | Sem `google-services.json` nesta revisão e sem teste de build/recebimento com Firebase ativado. |
| Push geográfico nas duas plataformas | Credenciais backend e recebimento em aparelhos ainda sem evidência; status/token e testes controlados não substituem esse ensaio. |
| GPS/LAN/permissões em iPhone | Os textos/configuração existem, mas comportamento com autorização, recusa e reconexão não foi exercitado no iPhone. |

**Conclusão:** a revisão encontrou um projeto iOS preparado para o fluxo Flutter moderno, com permissões básicas e um ajuste mínimo de Background Modes. Ela não elimina os impeditivos de ambiente, assinatura e configuração de push. A marca “validado em Android e iOS” só deve ser usada após registrar os testes reais de cada plataforma.
