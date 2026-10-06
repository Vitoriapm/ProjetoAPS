# Testes finais Android — 05/10/2026

Escopo acordado: um Android físico e um computador. iOS/APNs ficam adiados por
decisão da equipe, sem remover a exigência original de duas plataformas da APS.
Não há um segundo computador para comprovar distribuição entre hosts.

## Concluído nesta rodada

- Carga isolada: **1.000 relatos fictícios**, todos com HTTP 201, 1.000 vínculos,
  20 incidentes, 1.000 processamentos de risco e 1.000 de alertas. Zero outbox
  pendente; versões e conteúdo dos 20 incidentes iguais no banco/cache.
- Entrada: 49,641 s, média 20,14 relatos/s; p95 HTTP 969 ms. Convergência conferida
  em 52,016 s desde o início. Primeira fase: 500 envios com alvo de 20/s, mas a
  vazão efetiva foi 16,32/s; segunda fase: 500 com concorrência máxima 8, 26,32/s.
- 20 reenvios do mesmo UUID/conteúdo retornaram HTTP 200 sem duplicação.
- Cluster separado `ecopulse-load-test`: duas APIs, dois workers, três RabbitMQ,
  seis Redis e PostGIS; sem réplica PostgreSQL neste ensaio. FCM e ORS desligados,
  sem dispositivos, entregas ou chamadas externas. Containers da carga parados
  ao final, com volumes preservados. O projeto do celular permaneceu ativo.
- 45 testes Flutter e análise estática passaram após o indicador de recebimento.
- APK de testes **1.0.0+3**, Firebase ligado, com assinatura igual à versão +2.
  A instalação e o recebimento nesta versão dependem da confirmação do usuário.

Evidência: [load-extended.json](evidence/load-extended.json). Essa carga limitada
é maior que a rodada anterior de 60; ainda não mede capacidade máxima, produção,
grandes volumes representativos ou resistência à perda do computador. Não houve
ensaio de WebSocket ou replicação PostgreSQL nesta carga.

## 1. Push com o app aberto

1. Instalar [EcoPulse-Firebase-testes.apk](../entregas/EcoPulse-Firebase-testes.apk)
   como atualização, sem desinstalar nem limpar dados.
2. No mesmo Wi-Fi, salvar `http://198.51.100.22:8011` em Conexão e informações.
3. Voltar ao mapa e manter o EcoPulse visível. Confirmar a preparação no chat.
4. O assistente enviará **um** push direto e fictício, com duração de cinco
   minutos. Nenhum relato será criado para esta etapa.
5. Após o envio, abrir novamente Conexão e informações e verificar **“Push
   recebido com o app aberto”**, horário e contagem nesta sessão. Uma atualização
   de WebSocket não produz esse registro. O app não cria um aviso na barra do
   Android em primeiro plano; a confirmação é o callback mostrado no aplicativo.
6. Informar se o registro apareceu. O aceite do FCM é uma prova separada da
   confirmação de recepção. O registro é local desta execução, não um histórico
   persistente; reabrir a ficha após o envio atualiza a leitura.

## 2. Mesmo Android fora do raio

Depois da etapa 1, usar GPS e aguardar o registro da posição. O assistente fará
uma inspeção que retorna somente indicadores, sem publicar coordenadas/token.
Se o aparelho estiver a mais de 1,4 km do ponto público central de Ribeirão
Preto, um novo relato fictício de alagamento nesse centro poderá testar a
exclusão. A regra normal é 1.000 m do dispositivo + 200 m de influência; os 200 m
extras são uma margem do ensaio, não uma mudança no produto.

Se o GPS real estiver dentro dessa área, a equipe pode escolher uma referência
manual distante para testar a seleção. Nesse caso, registrar expressamente
**Android real com posição manual**, sem afirmar deslocamento GPS físico.

Após confirmar a posição recente fora, o assistente criará um único relato
fictício. A conclusão exige processamento de risco/alertas, exclusão pelo raio e
**ausência de linha de entrega para esse Android**. Apenas “não chegou” não prova
exclusão. O mesmo aparelho participa em etapas distintas; não é um ensaio
simultâneo com dois celulares. Não alterar a posição durante a conferência.

## 3. Entrada e saída por GPS real

Planejar depois das etapas de push, com um ponto fictício próximo do local da
equipe, sem divulgar a posição pessoal. O teste usa a faixa **dentro do app**:

1. Carregar a ocorrência fictícia ativa e manter o EcoPulse aberto, com GPS
   habilitado e o ponto de referência indicado como GPS.
2. Escolher um percurso a pé conhecido que cruze a distância de **1 km do centro
   da ocorrência**; iniciar fora, entrar, sair e retornar. Não escolher novamente
   um ponto de partida manual durante o percurso.
3. Conferir que o marcador acompanha o deslocamento. O serviço pede atualizações
   com filtro de 30 m; precisão e intervalo dependem do aparelho.
4. Ao entrar, verificar a faixa; fechar, sair e retornar sem repetir a mesma
   versão. O incidente precisa continuar ativo (validade normal de 30 minutos).
5. Informar a sequência observada e eventuais falhas. Se perder o Wi-Fi, o teste
   local pode continuar com o incidente já carregado; isso não comprova que o
   servidor recebeu cada posição ou que houve push durante o percurso.

Em 06/10, a equipe dispensou esta etapa sem executá-la. A tarefa está encerrada como dispensada; o percurso físico não foi validado. As instruções ficam disponíveis para uma futura retomada. Os testes anteriores
com pontos manuais não substituem o deslocamento GPS.

## Ferramentas do assistente

`scripts/validate_android_push.py` usa `plan` sem efeitos por padrão; `inspect`
faz leituras, `foreground-send --allow-send` realiza um envio direto único e
`outside-trigger --allow-send` cria um relato após verificar a exclusão. Os
estados privados ficam em `.runtime`, sem tokens. Uma tentativa FCM com resultado
incerto não é repetida automaticamente. Nunca apagar o estado para repetir um
aviso sem combinar novo teste com o usuário.

Para repetir a carga, iniciar projeto isolado com os três arquivos Compose e a
imagem local validada. Executar `scripts/validate_load.py --execute` somente com
banco vazio. O script não apaga dados para poder repetir um teste. O resultado
documentado é da execução inicial de 05/10; os comandos não comprovam nova rodada.

## Andamento do teste de primeiro plano

O usuário confirmou instalação do APK +3 e app aberto no mapa. O primeiro
comando foi interrompido pelo guarda antes de chamar FCM porque havia dois
cadastros Android com tokens distintos. Validação sem entrega confirmou um
token válido e um antigo `Unregistered`; somente o token definitivamente inválido
foi limpo, sem remover dispositivos/relatos. Evidência:
[android-push-token-recovery.json](evidence/android-push-token-recovery.json).

Após o diagnóstico, um único envio direto foi aceito pelo Firebase às 19:54 UTC
(16:54 de Brasília), conforme [android-foreground-push-send.json](evidence/android-foreground-push-send.json).
O recebimento em primeiro plano ainda depende da resposta do usuário sobre o
indicador no aplicativo. Não confundir a tentativa inicial sem chamada ao provedor
com dois envios. O telefone atual ainda não tinha posição na inspeção do envio;
isso não impede push direto, mas a próxima etapa por raio exige uma posição nova.

## Repetição solicitada em 06/10/2026

O primeiro ensaio de primeiro plano não teve recepção confirmada: o usuário não
viu o indicador, mesmo após reabrir a ficha. A observação está em
[evidência separada](evidence/android-foreground-first-observation.json).
O teste de interface reproduziu e corrigiu a falta de atualização da ficha já
aberta no código; essa correção não prova recepção na versão +3 instalada.

Em 06/10, o usuário pediu novo envio. O Docker estava desligado; após iniciá-lo,
o projeto do celular retomou saudável. Uma nova mensagem fictícia, com IDs novos
e estado separado do anterior, foi aceita pelo Firebase. Evidência:
[android-foreground-push-retry-send-20261006.json](evidence/android-foreground-push-retry-send-20261006.json).
A recepção deste segundo ensaio ainda depende da confirmação do usuário; não
foi criado relato nem exercitada seleção por raio nesta etapa.

### Correção do contexto da repetição

Depois do envio de 06/10, o usuário informou que o EcoPulse estava fechado.
Essa repetição não valida primeiro plano. O aceite FCM continua comprovado,
mas não há confirmação de recepção em primeiro ou segundo plano nessa rodada.
A correção está em [android-foreground-retry-context-20261006.json](evidence/android-foreground-retry-context-20261006.json).
Uma nova mensagem foi preparada em estado separado; o envio aguardará o usuário
confirmar que o mapa inicial está visível com a tela ligada. A ficha de conexão
será aberta depois para ler o indicador.

O usuário confirmou o mapa aberto antes do novo envio. Uma mensagem fictícia
foi aceita às 13:10 UTC (10:10 de Brasília), conforme
[android-foreground-open-map-send-20261006.json](evidence/android-foreground-open-map-send-20261006.json).
Essa rodada mantém preparação e recepção em registros separados; aguarda
confirmação do indicador.

## Recepção em primeiro plano confirmada em 06/10/2026

O usuário informou **“Push recebido com o app aberto às 10:10:58 (1 nesta
sessão)”**. Preparação do mapa aberto, aceite FCM e confirmação humana de callback
sustentam o teste de primeiro plano. Evidência:
[android-foreground-open-map-receipt-20261006.json](evidence/android-foreground-open-map-receipt-20261006.json).
Não houve observação independente do aparelho; o envio foi direto e não testou
raio ou mensageria. As tentativas anteriores permanecem com seus contextos.

A mesma ficha mostrava “Push aguardando conexão ou configuração do Firebase”.
Esse estado vem da tentativa de obter/registrar token, separada do callback de
recepção. O servidor respondeu saudável e tem um Android com token ativo, mas
isso não comprova por que a tentativa no cliente falhou. A renovação do cadastro
será conferida após salvar a URL correta e obter uma posição GPS nova. Não
descartar a confirmação de recepção por causa desse outro estado.

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

## Decisão da equipe em 06/10/2026

O percurso físico por GPS foi dispensado sem execução. A decisão encerra a tarefa de planejamento; não transforma a ausência de teste em aprovação técnica. iOS/APNs permanecem pendentes. Datas, horas e assinaturas serão preenchidas manualmente.
