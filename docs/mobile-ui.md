# Interface e demonstração do EcoPulse

O app tem duas telas principais: **Mapa/Lista** e **Novo relato**. O visual usa Material 3, cores discretas, ícones conhecidos e a fonte do sistema. A interface mostra Ribeirão Preto e evita apresentar os exemplos acadêmicos como ocorrências reais.

## Percurso da apresentação

1. Abra o painel de conexão pelo ícone ao lado de EcoPulse e informe o endereço do computador que executa o servidor. Para um aparelho físico, use o IP do computador na mesma rede Wi-Fi, não `localhost`.
2. Confira o aviso **Simulação acadêmica** quando o servidor está em modo de demonstração ou há algum dado identificado como exemplo. A lista, os detalhes e o formulário também identificam esses dados.
3. No mapa, ligue/desligue Alagamento, Vias, Ar e Calor. Toque em uma ocorrência para ver gravidade, horário e número de relatos. A legenda explica os símbolos; detalhes de Ar/Calor mostram fonte, escala e data. A camada Landsat aparece como **Histórico — 17/09/2025**: é contraste de temperatura da superfície, sem medição do calor atual.
4. Toque em **Relatar**. O app tenta obter o GPS; se não conseguir, selecione um ponto no mapa ou **Usar ponto de exemplo**. Os pontos de exemplo são coordenadas de referência para a apresentação, não ocorrências verificadas. Escolha o tipo, a gravidade e, se desejar, uma descrição.
5. Salve o relato. Ele aparece imediatamente como pendente no aparelho. Depois da confirmação do servidor, o indicador de pendência desaparece. Outro aparelho pode consultar o relato e receber a atualização do incidente processado.
6. Para demonstrar falha de conexão, interrompa o acesso ao servidor e salve outro relato. A lista permite consultar as pendências mesmo sem o mapa de ruas. Restabeleça a conexão com o app aberto: a lógica tenta sincronizar automaticamente; o botão Atualizar também permite nova tentativa. Apagar dados locais do aplicativo apaga o cache e as pendências, por isso não faz parte deste teste.
7. Para consultar uma rota, toque em um ponto e escolha **Usar como ponto de partida**, ou obtenha sua posição pelo GPS. Toque no destino e escolha carro ou caminhada. Uma linha só aparece quando o OpenRouteService retorna um trajeto que passa nas verificações de bloqueios, extremos e resumo. A chave da equipe já está configurada: o adaptador passou evitando um bloqueio fictício de Ribeirão Preto e o endpoint API passou com HTTP 200. **O usuário confirmou que a linha apareceu no Android físico.** Essa confirmação não informa os pontos nem os valores daquele percurso, e não houve observação independente da tela. Configuração e provas estão em [ROTAS.md](ROTAS.md) e [evidence/routes-phone-confirmation.json](evidence/routes-phone-confirmation.json). As zonas consideradas não garantem a segurança real da viagem.

## Estados e textos

- Nuvem indica a disponibilidade do servidor e o envio das pendências. A identificação de falha é sobre a conexão com esse servidor, não uma garantia de diagnóstico de toda a internet.
- Relógio identifica um relato que já foi salvo localmente e ainda espera confirmação.
- Ponto azul representa o GPS ou uma origem escolhida manualmente; o rótulo informa a origem.
- A área colorida de uma ocorrência é uma zona de influência aproximada dos relatos, não a extensão medida de uma inundação.
- Alertas e erros aparecem em uma faixa com botão para fechar. A tela de conexão informa o estado de configuração das notificações push.

Com a configuração padrão, a demonstração usa AQI simulado identificado e 32 polígonos históricos reais Landsat. O modo distribuído combina AQI modelado CAMS com o mesmo calor histórico. O servidor só usa todas as camadas simuladas quando `ENVIRONMENT_SOURCE=fixtures` é escolhido explicitamente. Data de aquisição e aviso histórico permanecem nos detalhes mesmo após atualizar o cache; a camada histórica não dispara alertas críticos de proximidade. Fonte e método estão em [CALOR.md](CALOR.md).

Há duas versões Android para a apresentação: `entregas/EcoPulse-demo.apk` mantém Firebase desligado e `entregas/EcoPulse-Firebase.apk` foi compilado com Firebase ativado e a configuração Android da equipe. Com Firebase configurado, o app verifica permissão, espera APNs no iOS, registra/renova token e atualiza os dados ao receber em primeiro plano ou abrir uma notificação. No Android há canal `ecopulse_alertas` e ícone próprio.

O usuário confirmou o recebimento de um **push direto fictício no Android físico** e a abertura do app ao tocar no aviso; o registro está em [evidence/fcm-phone-receipt.json](evidence/fcm-phone-receipt.json). Essa confirmação é do teste direto ao aparelho. **O fluxo de seleção por raio geográfico a partir de um relato ainda está pendente**, incluindo o envio pelo serviço de alertas no modo distribuído, assim como o recebimento iOS/APNs. O status de registro do token, sozinho, não comprova recebimento. O desenho das duas telas permanece simples; configuração e limites estão em [PUSH.md](PUSH.md).

## Mapa e modo offline

O mapa de ruas usa tiles do OpenStreetMap, com atribuição visível e identificação do aplicativo nas requisições compatíveis. Há somente o cache normal das áreas visualizadas oferecido pelo `flutter_map`; não há prefetch, download em massa, pacote de mapas offline nem promessa de cobertura persistente. Uma área ainda não carregada pode ficar sem ruas quando a conexão falha. Marcadores, relatos e camadas já obtidos continuam disponíveis a partir do armazenamento do app, e a Lista e os pontos de exemplo permitem apresentar o fluxo sem depender das ruas.

Em Android/iOS, o armazenamento do app usa SQLite. A prévia no navegador usa armazenamento do navegador para inspeção da interface e não comprova o comportamento de SQLite em aparelho físico. Dados ambientais e incidentes só são exibidos se vierem do controlador/cache; a interface não fabrica uma resposta do servidor.

O cache Redis ambiental pertence ao servidor distribuído e mantém versão/validade das observações duráveis; o armazenamento offline no aparelho mantém os dados já recebidos. Esses dois fluxos não permitem prometer AQI atual sem rede. O prazo de atualização do calor histórico também não muda sua data de aquisição.

## Verificação da interface

`mobile/test/ui_test.dart` cobre a identificação de uma pendência offline e de um exemplo na largura 360 px, além de gravidade, tipo, coordenadas manuais e descrição preservados pelo formulário. Os testes do core cobrem fila, confirmação e falhas da API. A avaliação de cores, toque no mapa, permissão de GPS, push e teclado deve ser complementada por teste no aparelho.

Na atualização de 05/10/2026, **45 testes Flutter passaram** e a análise estática não encontrou problemas. O [aviso de proximidade](PROXIMIDADE.md) ganhou faixa própria, persistente durante sync e com expiração offline; o menu do mapa, fechamento, dedup e reabertura SQLite passaram no emulador Android usando API fake isolada. A suíte inclui leitura da geometria/metadados históricos e 11 testes controlados de push. O APK atualizado também abriu no emulador Android 35, sem exceção fatal, com canal de notificações HIGH; isso não substitui prova de recebimento. Depois, o usuário confirmou a chegada e o toque do push direto em Android físico. A rota real pelo adaptador ORS passou com um bloqueio fictício e [o endpoint API passou com HTTP 200](evidence/routes-api-live.json), sem ocorrências ativas naquele teste. O usuário também confirmou [a linha da rota visível no Android](evidence/routes-phone-confirmation.json), sem informar pontos ou valores. O usuário confirmou depois a aquisição GPS básica e o offline/reabertura/reenvio Android; o banco registrou um único relato novo, ligado a uma ocorrência, sem duplicação, conforme [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json). Permanecem pendentes o ensaio de proximidade com posição em movimento, a conferência dos demais campos e cenários de rota, o fluxo completo de push por raio/serviço distribuído e iOS/APNs. Builds e demais evidências estão em [VALIDACAO.md](VALIDACAO.md).
