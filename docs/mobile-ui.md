# Interface e demonstração do EcoPulse

O app tem duas telas principais: **Mapa/Lista** e **Novo relato**. O visual usa Material 3, cores discretas, ícones conhecidos e a fonte do sistema. A interface mostra Ribeirão Preto e evita apresentar os exemplos acadêmicos como ocorrências reais.

## Percurso da apresentação

1. Abra o painel de conexão pelo ícone ao lado de EcoPulse e informe o endereço do computador que executa o servidor. Para um aparelho físico, use o IP do computador na mesma rede Wi-Fi, não `localhost`.
2. Confira o aviso **Simulação acadêmica** quando o servidor está em modo de demonstração ou há algum dado identificado como exemplo. A lista, os detalhes e o formulário também identificam esses dados.
3. No mapa, ligue/desligue Alagamento, Vias, Ar e Calor. Toque em uma ocorrência para ver gravidade, horário e número de relatos. A legenda explica os símbolos; detalhes de Ar/Calor mostram fonte, escala e data.
4. Toque em **Relatar**. O app tenta obter o GPS; se não conseguir, selecione um ponto no mapa ou **Usar ponto de exemplo**. Os pontos de exemplo são coordenadas de referência para a apresentação, não ocorrências verificadas. Escolha o tipo, a gravidade e, se desejar, uma descrição.
5. Salve o relato. Ele aparece imediatamente como pendente no aparelho. Depois da confirmação do servidor, o indicador de pendência desaparece. Outro aparelho pode consultar o relato e receber a atualização do incidente processado.
6. Para demonstrar falha de conexão, interrompa o acesso ao servidor e salve outro relato. A lista permite consultar as pendências mesmo sem o mapa de ruas. Restabeleça a conexão com o app aberto: a lógica tenta sincronizar automaticamente; o botão Atualizar também permite nova tentativa. Apagar dados locais do aplicativo apaga o cache e as pendências, por isso não faz parte deste teste.
7. Para consultar uma rota, toque em um ponto e escolha **Usar como ponto de partida**, ou obtenha sua posição pelo GPS. Toque no destino e escolha carro ou caminhada. Uma linha só aparece quando o serviço de rotas retorna um trajeto; falta de credenciais/provedor gera um aviso. As zonas consideradas não garantem a segurança real da viagem.

## Estados e textos

- Nuvem indica a disponibilidade do servidor e o envio das pendências. A identificação de falha é sobre a conexão com esse servidor, não uma garantia de diagnóstico de toda a internet.
- Relógio identifica um relato que já foi salvo localmente e ainda espera confirmação.
- Ponto azul representa o GPS ou uma origem escolhida manualmente; o rótulo informa a origem.
- A área colorida de uma ocorrência é uma zona de influência aproximada dos relatos, não a extensão medida de uma inundação.
- Alertas e erros aparecem em uma faixa com botão para fechar. A tela de conexão informa o estado de configuração das notificações push.

## Mapa e modo offline

O mapa de ruas usa tiles do OpenStreetMap, com atribuição visível e identificação do aplicativo nas requisições compatíveis. Há somente o cache normal das áreas visualizadas oferecido pelo `flutter_map`; não há prefetch, download em massa, pacote de mapas offline nem promessa de cobertura persistente. Uma área ainda não carregada pode ficar sem ruas quando a conexão falha. Marcadores, relatos e camadas já obtidos continuam disponíveis a partir do armazenamento do app, e a Lista e os pontos de exemplo permitem apresentar o fluxo sem depender das ruas.

Em Android/iOS, o armazenamento do app usa SQLite. A prévia no navegador usa armazenamento do navegador para inspeção da interface e não comprova o comportamento de SQLite em aparelho físico. Dados ambientais e incidentes só são exibidos se vierem do controlador/cache; a interface não fabrica uma resposta do servidor.

## Verificação da interface

`mobile/test/ui_test.dart` cobre a identificação de uma pendência offline e de um exemplo na largura 360 px, além de gravidade, tipo, coordenadas manuais e descrição preservados pelo formulário. Os testes do core cobrem fila, confirmação e falhas da API. A avaliação de cores, toque no mapa, permissão de GPS, push e teclado deve ser complementada por teste no aparelho.
