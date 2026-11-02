# EcoPulse — roteiro da apresentação

ECOPULSE — ROTEIRO DA APRESENTAÇÃO

## 1. Preparação e cronograma de 10 minutos

UNIP — Universidade Paulista • Ciência da Computação • 8º semestre • Desenvolvimento de Sistemas Distribuídos • APS 2026/2. Professor: Jean Miler Scatena. Escopo funcional revisado em 02/11/2026: Alagamento e Vias; resultados técnicos históricos de outubro. Duração confirmada: 10 minutos. As falas entre aspas são prontas para ensaio; as instruções de tela não precisam ser lidas.

Equipe e divisão da apresentação: Vitória Pandolfo Marturano, RA RA-OMITIDO, turma CC8P18; Alessandro Damázio Pereira, RA RA-OMITIDO, turma CC8Q18; Augusto Flávio Murari, RA RA-OMITIDO, turma CC8P18. Cada integrante apresenta por 3 minutos e 20 segundos. O cronograma abaixo organiza as falas e as trocas de controle do telefone.

| Cronômetro | Responsável | Conteúdo |
| --- | --- | --- |
| 0:00–0:45 | Vitória | Problema e proposta |
| 0:45–2:05 | Vitória | Mapa, Alagamento e Vias |
| 2:05–3:20 | Vitória | Um relato fictício: offline e reconexão |
| 3:20–4:30 | Alessandro | Arquitetura e caminho do evento |
| 4:30–6:10 | Alessandro | Proximidade: referência distante → próxima |
| 6:10–6:40 | Alessandro | Testes e recuperação de falhas |
| 6:40–7:35 | Augusto | Rota e zonas informadas |
| 7:35–8:45 | Augusto | Push Android dentro e fora do raio |
| 8:45–9:35 | Augusto | Resultados e validações concluídas |
| 9:35–10:00 | Augusto | Conclusão |

Cronograma planejado: 10:00; cada integrante tem 3:20. Reservar aproximadamente quatro minutos para navegação, sincronização e trocas de tela. Perguntas ficam após o cronômetro, salvo orientação diferente do professor.

## Preparação da demonstração — checklist

• Executar o código atual de 02/11/2026 ou gerar e instalar um novo APK antes da apresentação. Os APKs +2/+3/+4 de outubro em `entregas/` são históricos e ainda podem mostrar Ar e Calor. Conferir Firebase habilitado para demonstrar push e o endereço do servidor na rede do dia.

• Abrir mapa, lista e detalhes das ocorrências com internet; separar evidências sanitizadas e diagrama. Confirmar alimentação, bateria, projeção e legibilidade.

• Preparar Exemplo • Centro e uma referência manual distante mais de 1,2 km dele, fora das demais ocorrências ativas. Após qualquer GPS preparatório, selecionar Usar como ponto de partida para manter a referência distante.

• Único relato novo: Relatar uma ocorrência aqui → Usar ponto de exemplo → Exemplo • Centro. A etiqueta de simulação deve aparecer antes de salvar; ponto manual e texto fictício sozinhos não marcam demonstração.

• Ensaiar uma perda de conexão somente no telefone, sem parar serviços Docker; restaurar a conexão com o app aberto. Não desinstalar nem limpar os dados.

• Usar as evidências registradas para apresentar o push. Se houver um envio ao vivo, preparar previamente o aparelho, as permissões e a conexão; criar apenas uma ocorrência fictícia para esse teste.

## 2. Vitória — problema, mapa e relato

0:00–0:45 • Fala pronta: “Bom dia. Somos Vitória, Alessandro e Augusto. Nosso projeto é o EcoPulse, uma aplicação móvel para compartilhar ocorrências ambientais urbanas, com foco em Ribeirão Preto. Uma pessoa pode registrar um alagamento ou uma via obstruída, e outras acompanham a informação no mapa. Para a APS de Sistemas Distribuídos, estudamos como receber, processar e distribuir esses relatos mesmo quando há falhas de conexão. Os exemplos desta apresentação são fictícios.”

0:45–2:05 • Fala pronta: “O mapa reúne os relatos de alagamento e de vias obstruídas. Podemos ativar cada filtro para consultar o tipo de ocorrência desejado. A lista oferece outra forma de consultar os mesmos dados. As cores indicam gravidade; os detalhes mostram horário e relatos agrupados. A área de influência é uma aproximação do sistema e não mede a extensão real do problema. Os dados de exemplo permanecem identificados como simulação acadêmica.”

Tela: alternar Mapa/Lista, ativar Alagamento e Vias e abrir uma ocorrência. Mostrar tipo, gravidade, horário, número de relatos e a identificação de simulação.

2:05–3:20 • Fala pronta: “Agora vamos registrar uma via obstruída simulada. A opção Usar ponto de exemplo, com Exemplo • Centro, marca a simulação. Primeiro retiramos a conexão e salvamos. O Android guarda o registro em SQLite, e a lista mostra que ele aguarda envio. Ao reconectar, com o aplicativo aberto, a fila tenta sincronizar. O mesmo identificador acompanha as novas tentativas, permitindo reconhecer um reenvio sem criar outro relato. Também validamos a persistência após reabrir o aplicativo offline. As ruas ainda não carregadas podem faltar: o projeto não baixa um mapa offline completo.”

• Abrir o mapa → Relatar uma ocorrência aqui, evitando GPS inicial. O botão flutuante Relatar solicita GPS e pode trocar a origem; evitá-lo neste ensaio.

• Escolher Via obstruída, Média, Usar ponto de exemplo → Exemplo • Centro; conferir a etiqueta de simulação. Descrição: Simulação acadêmica — exemplo da apresentação. Não mudar o ponto depois: position_source=demo.

• Desconectar, salvar uma vez e mostrar Salvo • aguardando envio. Reconectar com o app aberto e observar a confirmação; usar Atualizar se necessário.

• Se demorar, mostrar a pendência e seguir. Alessandro usará a mesma ocorrência após a sincronização; não salvar cópias para apressar o resultado.

Passar o controle a Alessandro às 3:20. Demonstrar reabertura no ensaio prévio ou vídeo de apoio.

## 3. Alessandro — distribuição e proximidade

3:20–4:30 • Fala pronta: “O cliente Flutter guarda a fila local, mas o ambiente full separa os serviços no servidor. A API FastAPI grava o relato e um evento na mesma transação em PostgreSQL com PostGIS. A outbox encaminha o evento ao RabbitMQ; os consumidores processam risco e alertas. Redis mantém dados para consulta rápida, e WebSocket atualiza os clientes conectados. Essa separação permite repetir uma etapa que falhou. Como banco, processamento e cache não mudam ao mesmo tempo, trabalhamos com consistência eventual e versões. O GeoHash distribui eventos por região; nesta implementação, o PostgreSQL continua compartilhado.”

Tela: mostrar um diagrama simples com Flutter/SQLite → API → PostGIS/outbox → RabbitMQ → processamento/alertas → Redis/WebSocket/FCM. Explicar seguindo um único relato. O demo antigo na porta 8000 tem processamento local e não executa o serviço separado de alertas.

4:30–6:10 • Fala pronta: “Agora usamos a ocorrência recém-criada para mostrar o aviso local. Após sincronizar, definimos novamente a referência de partida distante. Ao escolher um ponto próximo, simulamos a entrada no raio de um quilômetro até o centro da ocorrência. A faixa permanece durante a sincronização. Podemos fechá-la; sair e voltar não repete a mesma versão. Uma versão nova pode gerar outro aviso. A chave de deduplicação fica salva no aparelho. Este movimento é uma seleção manual no mapa. A influência de duzentos metros do incidente é usada no servidor e é uma regra diferente deste aviso local.”

• Após enviar/sincronizar o relato Centro, selecionar Usar como ponto de partida na referência distante; depois selecionar um ponto próximo ao Centro. Mostrar a faixa e atualizar.

• Fechar a faixa; selecionar a referência distante e depois a próxima. A mesma versão não deve repetir o aviso.

• Durante distante → próximo, não tocar em Usar GPS: ele substitui a referência manual pela posição real. Não confundir a faixa no app com a notificação da barra do Android.

• Se a ocorrência já tiver sido avisada ou expirado, mostrar a evidência. Não limpar deduplicação nem criar relatos sucessivos para obter a faixa.

6:10–6:40 • Fala pronta: “A revisão de seis de outubro passou com quarenta e sete testes Flutter. O backend tem cento e sessenta e dois testes registrados em quatro de outubro. No cluster, ensaiamos falhas de API, worker, RabbitMQ e Redis, além de promoção planejada do PostgreSQL. Retries e DLQ permitem analisar mensagens que falham. Os ensaios ocorreram no mesmo computador.”

Apoio: filas quorum e confirmações do broker protegem o processamento; falhas persistentes vão à DLQ para análise e reprocessamento. Esses ensaios são anteriores ao push geográfico, que não injetou novas falhas.

## 4. Augusto — rotas, push e conclusão

6:40–7:35 • Fala pronta: “Escolhemos uma origem e um destino no mapa para calcular uma rota. A integração OpenRouteService foi consultada de verdade pelo adaptador e pela API, e a visualização no Android foi confirmada pela equipe. O adaptador também foi ensaiado com um bloqueio fictício. A rota considera as zonas informadas ao sistema; como os relatos podem estar incompletos ou desatualizados, ela é apoio à navegação e não certificação de segurança.”

Tela: Usar como ponto de partida → selecionar destino → Calcular rota a pé até aqui. Mostrar percurso, distância e origem do resultado. Reservar uma única tentativa; se o provedor não responder, passar à evidência da rota validada.

7:35–8:45 • Fala pronta: “Em cinco de outubro, um relato fictício percorreu o backend até o Firebase, e a equipe confirmou a notificação em segundo plano e a abertura por toque. Em seis de outubro, a equipe também confirmou o recebimento com o app aberto. Depois, o mesmo Android, com GPS recente fora do raio, foi excluído do envio e não recebeu nova mensagem. O servidor usa a última posição válida, mil metros do aparelho e duzentos metros de influência. Foram etapas distintas com um telefone. O app atualiza a posição enquanto está aberto.”

Tela: mostrar as evidências do pipeline e recebimento de 05/10, callback em primeiro plano de 06/10 e exclusão do mesmo Android fora do raio. A recepção e a ausência de novo recebimento são confirmações humanas; o banco registra o processamento e as entregas. No código atual, conferir o estado “Push registrado no servidor” antes do ensaio. A apresentação pode usar os registros já obtidos; um novo push ao vivo exige preparo do telefone e uma única ocorrência fictícia.

8:45–9:35 • Fala pronta: “O resultado reúne relato offline, sincronização, proximidade, filtros de ocorrências, rotas e push. Na carga isolada, mil relatos foram processados, com banco e cache coerentes e sem duplicação nos reenvios. A média de entrada foi vinte vírgula quatorze relatos por segundo, em um computador; isso não mede a capacidade máxima. A equipe também aprovou iOS/APNs e deslocamento físico por GPS em testes manuais. Durante a apresentação, usamos pontos no mapa para simular o deslocamento. Os registros técnicos e as validações manuais estão identificados no relatório.”

9:35–10:00 • Fala pronta: “Com o EcoPulse, conseguimos ligar a experiência do usuário aos conceitos de Sistemas Distribuídos: eventos, processamento separado, repetição de tentativas, cache e consistência eventual. A contribuição é um protótipo colaborativo com resultados documentados. Os exemplos são acadêmicos, e os avisos não substituem alertas oficiais. Obrigado.”

Encerrar em 10:00. Perguntas durante a fala: substituir a navegação de rota pela evidência, preservando DSD e a conclusão.

## 5. Planos de apoio e perguntas prováveis

| Situação | Ação e fala curta |
| --- | --- |
| Rede ou API indisponível | Mostrar Lista e o relato pendente: O registro ficou salvo no aparelho; a confirmação do servidor aguarda conexão. Usar capturas e evidências, sem reiniciar Docker durante a fala. |
| Mapa sem ruas | Usar Lista e detalhes já consultados; explicar o limite do cache de mapas. Não prometer mapa offline completo. |
| ORS sem resposta | Mostrar a evidência da rota validada e informar que o provedor não respondeu nesta tentativa. |
| GPS sem permissão | Usar referência manual identificada. No ensaio de proximidade, manter os pontos manuais já planejados. |
| Faixa ou push não aparecem | Conferir se a ocorrência está ativa e se a versão já foi avisada. Mostrar evidências. Dizer o que ocorreu nesta tentativa; aceite FCM sozinho não prova chegada no celular. |

## 5. Perguntas prováveis — continuação

| Pergunta | Resposta curta |
| --- | --- |
| Onde está o sistema distribuído? | No modo full: APIs e consumidores separados, PostGIS, RabbitMQ e Redis. O cliente mantém sua fila local. |
| Como evitam duplicação? | UUID preservado no reenvio, idempotência na API e registro de eventos processados. Efeitos externos como push não têm garantia absoluta de entrega única. |
| Por que usar RabbitMQ? | Para desacoplar recebimento e processamento, confirmar mensagens e recuperar falhas com retries e DLQ. |
| Aviso local e push têm o mesmo raio? | Local: 1 km até o centro. Push atual: raio do aparelho de 1.000 m mais 200 m do incidente, com posição de até uma hora. |
| Três relatos são três pessoas? | O agrupamento considera instalações distintas, posição e tempo. Instalação não equivale a pessoa verificada. |
| Já funciona no iPhone? | A equipe confirmou aprovação de iOS/APNs em validação manual. O relatório identifica a declaração dos integrantes como fonte; não inclui captura instrumentada do iPhone. |
| A réplica garante perda zero? | É assíncrona. A promoção planejada foi ensaiada; não prova perda zero em falha inesperada nem tolerância à perda do notebook. |
| Qual prova existe fora do raio? | O mesmo Android com GPS recente foi excluído em etapa distinta, sem entrega no banco; a equipe confirmou nenhum novo recebimento. Não houve dois telefones simultâneos. |

Para uma pergunta sem evidência: “Esse cenário ainda não foi validado. O que conseguimos demonstrar até agora é [resultado documentado].” Responder primeiro em uma frase; detalhar somente se solicitado.

## 6. Versão de 6 minutos e ajustes finais

Se a duração autorizada for seis minutos, usar trechos das mesmas falas e o cronograma abaixo. Manter um único relato fictício; apresentar o offline e o push por evidência, sem executar reabertura, saída/retorno ou envio adicional.

| Cronômetro | Responsável e corte |
| --- | --- |
| 0:00–0:35 | Vitória: problema e proposta |
| 0:35–1:20 | Vitória: mapa, filtros de Alagamento e Vias |
| 1:20–2:00 | Vitória: formulário e evidência da fila offline |
| 2:00–2:55 | Alessandro: caminho API → outbox → fila → consumidores |
| 2:55–3:40 | Alessandro: faixa de 1 km com ponto manual |
| 3:40–4:00 | Alessandro: 47 Flutter, 162 backend históricos e falhas locais |
| 4:00–4:35 | Augusto: rota validada, sem nova consulta |
| 4:35–5:15 | Augusto: push Android de 05–06/10 e evidências dentro/fora |
| 5:15–6:00 | Augusto: resultados, limites e conclusão |

Cronograma reduzido: 6:00; 2:00 por integrante. Sugestão de oito slides ou telas de apoio, sem necessidade de produzir um deck novo:

## Telas de apoio e ajustes finais

| Tela | Conteúdo visual |
| --- | --- |
| 1 | Título, equipe e problema urbano |
| 2 | Mapa/lista com relato e legenda |
| 3 | Detalhes de Alagamento e Vias: gravidade, horário e relatos |
| 4 | Formulário simulado e fila pendente/confirmada |
| 5 | Diagrama do caminho de um evento |
| 6 | Faixa de proximidade e regra de 1 km |
| 7 | Rota e evidências Android dentro/fora e primeiro plano |
| 8 | Resultados, validações manuais e conclusão |

• Conferir sala, projeção e conexão antes da apresentação. O roteiro reserva dez minutos de fala; organizar as perguntas conforme a orientação do professor.

• Controle do telefone: Vitória no mapa e relato; Alessandro na arquitetura e proximidade; Augusto na rota e conclusão. Augusto confere a rede e as evidências antes do início. Referência de exemplo: Exemplo • Centro.

• Relatório final revisado, com registro de participação confirmado: Vitória, 21 horas; Alessandro, 23 horas; Augusto, 30 horas. Total da equipe: 74 horas. As assinaturas dos integrantes e a validação do professor serão preenchidas manualmente.

• [Ensaiar] Tempo de sincronização e troca entre integrantes; ter capturas legíveis e evidências sanitizadas disponíveis offline.

Fontes internas: Relatorio_APS_EcoPulse.docx; Proposta_APS_DSD_EcoPulse.docx; docs/VALIDACAO.md, PROXIMIDADE.md, PUSH.md e TESTES_FINAIS_ANDROID.md; geographic-push.json, geographic-push-phone-receipt.json, android-foreground-open-map-receipt-20261006.json, android-outside-radius-20261006.json, load-extended.json e academic-team-confirmation-20261006.json. As aprovações manuais de iOS/APNs e percurso físico por GPS têm como fonte a declaração da equipe. Resultados históricos: 06/10/2026. Escopo e roteiro atualizados: 02/11/2026.
