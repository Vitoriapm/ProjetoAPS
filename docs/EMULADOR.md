# Abertura do EcoPulse no emulador

Na investigação de 05/10/2026, o computador tinha aproximadamente 8 GB de RAM, com 180–300 MB livres durante as tentativas. O Windows mantinha cerca de 1,4 GB de memória comprimida. O Android exibiu avisos de Pixel Launcher e System UI sem resposta. A instância anterior também registrou `NoSuchFieldError` no Google Play Services.

Os APKs entregues foram preservados. Ambos contêm a entrada normal `package:ecopulse/main.dart`; não contêm a entrada temporária de captura. A inspeção do Dart VM do APK Firebase confirmou a isolate principal executando, sem pausa. O APK original abriu no novo emulador Android 14, com mapa de ruas carregado. Sua abertura após reiniciar o emulador também foi observada. O comando Android `am start -W` excedeu seu tempo de espera, embora a interface tenha aparecido depois; não se deve tratar esse retorno como medição de abertura rápida.

Foram encerrados os compiladores da captura e um compilador Kotlin órfão, após confirmar ausência de compilação Gradle ativa. O teste também suspendeu temporariamente os serviços EcoPulse e o Docker Desktop para reduzir concorrência por RAM. O emulador anterior foi preservado. Ao concluir, os 15 conteineres foram restaurados; o gateway em 8011 respondeu HTTP 200, com banco, broker e cache disponiveis e nenhuma pendencia na outbox.

## Iniciar a instância preparada

Na raiz do projeto, execute em PowerShell:

```powershell
pwsh -File scripts/iniciar_emulador.ps1
```

O script usa Android 14 Google APIs x86_64 já instalado no SDK, cria ou reutiliza `EcoPulse_APS_Estavel` na pasta `.runtime`, usa tela de 720 × 1600, dois núcleos e GPU do computador, instala o APK entregue e solicita a abertura. Na primeira abertura, conclua a permissão de notificações. Ele não apaga a instância antiga nem encerra outros programas.

Em computadores com 8 GB, evite compilar o app enquanto o emulador e a topologia distribuída completa estão ativos. As primeiras inicializações podem continuar lentas sob pressão de memória. O script não altera limites do Windows ou do Docker e não garante ausência de lentidão em todas as máquinas.

Para conectar essa instância ao backend completo do computador, use `http://10.0.2.2:8011` em Conexão e informações. Esse endereço é próprio do emulador Android; o celular físico usa o IP da rede local. Se o backend estiver desligado, a interface abre, mas informa ausência de conexão.

## Captura do relatório

A Figura 2 utiliza `docs/evidence/android-proximity-map-loaded.png`, obtida numa simulação isolada Android com dados fictícios e mapa online carregado. É uma captura da interface real, não uma montagem. Não comprova GPS em movimento ou recebimento de push.
