# Rotas do EcoPulse

O app solicita uma rota real ao OpenRouteService pelo backend. A chave fica no servidor; o APK não recebe essa chave. Foram mantidos os dois perfis simples, carro e caminhada, e o limite de 50 km entre origem e destino. O desenho da rota no mapa usa o `LineString` devolvido pelo provedor, com distância em metros e duração em segundos.

Todos os polígonos das ocorrências ativas entram em `options.avoid_polygons`, unidos para eliminar sobreposições. A solicitação usa POST GeoJSON, porque o GET simples não permite opções avançadas. O backend rejeita geometria de bloqueio inválida, origem ou destino dentro de risco, rota que cruze algum bloqueio, coordenadas inválidas, resumos inválidos e respostas que não correspondam aos extremos solicitados. Uma falha nunca provoca uma nova tentativa removendo os bloqueios.

O encaixe dos pontos em ruas próximas foi limitado a 200 m. Também são verificados os segmentos entre os pontos escolhidos e a rua. O cálculo confere novamente as ocorrências antes de devolver a resposta, para detectar um bloqueio publicado durante a consulta. Esses segmentos de acesso são uma verificação geométrica conservadora, sem navegação detalhada a pé até a rua. As zonas dos relatos representam influência didática; não comprovam a extensão de uma inundação nem a segurança absoluta de um trajeto.

## Configurar e provar uma rota real

A chave ORS da equipe já está configurada localmente e a consulta real pelo adaptador passou. Em 04/10/2026, o ORS retornou um percurso de **3.035,2 m**, duração estimada de **432,8 s** e **46 pontos**, evitando uma exclusão fictícia em Ribeirão Preto. Os extremos, o resumo e as interseções foram conferidos. A prova sanitizada está em [evidence/routes-live.json](evidence/routes-live.json).

O endpoint `POST /v1/rotas` da API também passou com **HTTP 200**, retornando **3.035,2 m**, **432,8 s** e **46 pontos**. Nesse teste, o servidor não tinha ocorrências ativas, portanto a resposta informou zero incidentes evitados; a exclusão fictícia foi exercitada na prova do adaptador. A evidência está em [evidence/routes-api-live.json](evidence/routes-api-live.json).

As duas provas não modificam relatos ou o banco do app. **O usuário confirmou que a linha da rota apareceu no Android físico**, após realizar o fluxo orientado: “Fiz isso e apareceu”. O registro está em [evidence/routes-phone-confirmation.json](evidence/routes-phone-confirmation.json). Essa é uma confirmação humana da exibição; não houve observação independente da tela. A chave fica no servidor; não foi exibida no chat ou incorporada ao APK.

Os pontos escolhidos e os valores exibidos no telefone não foram informados. As métricas acima pertencem às consultas controladas do adaptador e da API. Continuam pendentes a conferência dos demais campos da UI, a integração do GPS em movimento com proximidade, os demais cenários de rota e iOS. A aquisição GPS básica e o offline Android foram confirmados pelo usuário em [android-physical-gps-offline.json](evidence/android-physical-gps-offline.json).

Para configurar outro ambiente, use o [portal oficial HeiGIT](https://account.heigit.org/) e uma chave com acesso a Directions. O [guia de configuração](CONFIGURAR_SERVICOS.md) mostra os passos. Grave localmente `ORS_API_KEY` no `.env` da raiz e reinicie o iniciador demo ou recrie os serviços API Docker para que recebam o valor. Não inclua `.env` no ZIP ou no repositório.

Na raiz do projeto, execute o diagnóstico:

```powershell
& .\backend\.venv\Scripts\python.exe .\scripts\validate_routes_live.py
```

Sem chave, o resultado será `awaiting_ors_key`, sem contato com o provedor, com código de saída 2. Com chave, o diagnóstico informa `configuration_ready`; isso confirma apenas a presença da configuração.

Para fazer uma consulta real e salvar uma prova sem credenciais:

```powershell
& .\backend\.venv\Scripts\python.exe .\scripts\validate_routes_live.py --live --output .\docs\evidence\routes-live.json
```

O teste usa dois pontos públicos de Ribeirão Preto e um bloqueio circular fictício entre eles. A rota será calculada pelo ORS, enquanto o bloqueio estará identificado como simulado. Nenhum relato será gravado no app. A prova só informa `passed` quando o provedor responde e a geometria, os extremos, o resumo e a exclusão passam pelas verificações. Conta sem permissão, cota esgotada, indisponibilidade, timeout ou ausência de alternativa aparecem como falha; a saída não contém a chave.

O adaptador e o endpoint API já foram validados, e a linha no Android físico foi confirmada pelo usuário. Nos próximos cenários, registre origem, destino e perfil e confira também distância, tempo e fonte para comparar a resposta da API com o que o app exibe.

## Validação já executada

Os testes controlados cobrem os dois perfis, união de bloqueios sobrepostos e separados, coordenadas e polígonos inválidos, resposta vazia, valores não finitos, extremos fora de posição, cruzamento do acesso à rua, ocorrência criada durante a consulta, erros 400/404/422/401/403/429/503, timeout e ausência de chave. Esses testes usam respostas controladas e não substituem a consulta real.

A consulta real de 04/10/2026 complementa esses testes para o perfil carro com uma exclusão fictícia; a chamada pelo endpoint API passou em seguida, sem ocorrências ativas naquele estado do servidor. Elas validam esses cenários, sem comprovar caminhada real, navegação no aparelho ou todos os percursos possíveis. A primeira tentativa ficou limitada pelo acesso de rede do ambiente; a mesma prova passou quando a consulta externa foi autorizada.

## Referências

- [ORS: opções e polígonos de exclusão](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options).
- [ORS: POST, formato GeoJSON e unidades do resumo](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types).
