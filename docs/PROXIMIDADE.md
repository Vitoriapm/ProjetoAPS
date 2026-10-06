# Aviso de proximidade

O diagnóstico confirmou que a sincronização substituía a mensagem geral do controller. Como a ocorrência já estava registrada na deduplicação por `id:versão`, o aviso desaparecia e não era mostrado novamente na atualização seguinte.

A correção usa `controller.proximityMessage` e uma faixa própria na interface, separada das mensagens de sincronização e de erro. O aviso permanece durante as atualizações até ser fechado, o ponto de referência sair do raio, a ocorrência expirar ou ser removida. Um Timer remove os avisos vencidos mesmo offline, sem depender de nova posição ou sincronização.

## Regra do aviso local

- O raio é fixo: **1 km até o centro da ocorrência**, usando GPS ou o ponto de partida selecionado no mapa. Não exige gravidade alta.
- O raio de influência de **200 m** da ocorrência é outra regra: serve à agregação e à seleção geográfica no backend, não limita esse aviso local.
- A chave `id:versão` fica persistida no armazenamento local. Fechar o aviso ou sair e voltar ao raio não repete a mesma versão; uma versão nova pode gerar outro aviso.

Esse fluxo é um aviso dentro do app. O servidor em modo demo não executa o dispatcher FCM do ambiente distribuído completo. A faixa local não comprova envio de push nem funcionamento do GPS físico.

## Snapshot do servidor

A [auditoria somente de leitura](evidence/proximity-server-state.json), feita em **04/10/2026 às 23:53:40 de São Paulo**, encontrou 21 relatos fictícios e uma ocorrência relacionada de versão 3, gravidade baixa, com três relatos e influência de 200 m. Ela estava ativa naquele instante, com aproximadamente 26 minutos de validade restante. Isso é um snapshot; não comprova que um aviso apareceu no celular nem que a ocorrência continua ativa agora.

## Validação da correção

Os testes de controller e interface cobrem permanência após sincronização, erro de conexão, fechamento, saída do raio, deduplicação, versão nova, expiração e remoção. Executar a partir de `mobile`:

```powershell
flutter test test/proximity_test.dart test/proximity_ui_test.dart
```

O novo teste Android usa o menu real do mapa, a interface e SQLite nativo, com uma API fake isolada. Executar somente no emulador de teste; ele prepara o estado local de deduplicação:

```powershell
flutter drive --driver=test_driver/proximity_driver.dart --target=integration_test/android_proximity_test.dart -d emulator-5554 --dart-define=FIREBASE_ENABLED=false
```

O driver está preparado para gravar `docs/evidence/android-proximity.json` e uma captura da faixa. Esse teste não envia FCM, não altera o servidor demo e não observa um telefone físico. **Passou em 05/10/2026:** 45 testes Flutter (14 de proximidade e um de interface), análise sem problemas e cenário Android com nove verificações aprovadas. Evidências: [resultado consolidado](evidence/proximity-validation.json), [Android/SQLite](evidence/android-proximity.json) e [captura do aviso](evidence/android-proximity.png). A expiração sem rede/sync também passou. O emulador foi encerrado; o telefone físico e o push geográfico não foram observados nesse ensaio.


## Confirmação no celular em 05/10/2026

O usuário informou instalação do novo APK e respondeu **‘fiz todos os passos de 1 a 7 e deu certo’** ao roteiro manual: origem distante, novo relato fictício pela opção **Relatar uma ocorrência aqui**, referência próxima, faixa visível, fechar e sair/voltar sem repetir a mesma versão. [proximity-phone-confirmation.json](evidence/proximity-phone-confirmation.json) registra essa confirmação humana, sem observação independente da tela ou medições de distância. Reabertura offline e expiração no telefone, deslocamento GPS físico e FCM não foram exercitados nesse roteiro.

O ponto de partida representa a posição simulada do usuário para rota/proximidade. **Usar GPS** substitui essa referência pela localização real do aparelho. Para criar o relato sem essa troca automática, abrir a ficha pela opção **Relatar uma ocorrência aqui** do próprio mapa. A faixa dentro do EcoPulse é diferente da notificação da barra do Android; o aviso local não chama o envio FCM.
