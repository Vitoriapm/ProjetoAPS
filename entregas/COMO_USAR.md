# Usar o EcoPulse na apresentação

Versão atual: **EcoPulse-Firebase-testes.apk — 1.0.0+4**, de 06/10/2026. Instale
como atualização para preservar endereço, relatos e configurações. O pacote e
o certificado são iguais aos da versão +3. Os APKs demo e EcoPulse-Firebase.apk
são entregas anteriores; o demo mantém Firebase desligado.

## Computador da equipe já configurado

1. Abra o Docker Desktop e aguarde o mecanismo ficar disponível.
2. No PowerShell, na pasta do projeto, execute:

~~~powershell
$env:ECOPULSE_IMAGE_TAG = 'fcm-test'
docker compose -p ecopulse-fcm-test --env-file .env -f infra/compose.yaml -f infra/compose.cluster.yaml -f infra/compose.phone-test.yaml up -d --no-build nginx worker alerts
~~~

3. Abra `http://198.51.100.22:8011/health`: deve retornar `"status": "ok"`.
   Se o IP mudar, use o novo IP no teste e no app.
4. No mesmo Wi-Fi, salve `http://198.51.100.22:8011` em **Conexão e informações**,
   sem acrescentar `/health`. Volte ao mapa e atualize.
5. Confira **Push registrado no servidor**, ocorrências e fonte/data das camadas.
   O cadastro e o indicador de recebimento são informações separadas.
6. Use o roteiro Word e `docs/ENSAIO_APRESENTACAO.md`. Para um novo relato,
   selecione **Usar ponto de exemplo → Exemplo • Centro**, com simulação visível.

Confirme o IP no dia. Os serviços ficam ativos durante a apresentação. O comando
usa apenas `ecopulse-fcm-test`; não inicie o projeto antigo `ecopulse-validation`,
cujo primário PostgreSQL antigo permanece isolado. O perfil do telefone usa duas
APIs e um worker de risco, sem réplica PostgreSQL ou segundo worker nesse ensaio.

## Evidências para apresentar

- Push em segundo plano e abertura por toque: ensaio de 05/10.
- Push com o app aberto: confirmação humana de 06/10 na versão +3.
- Android fora do raio: seleção conferida no backend em 06/10, sem entrega e
  sem novo recebimento confirmado pelo usuário no mesmo Android, em etapa distinta.
- Carga isolada de 1.000 relatos, sem Firebase/ORS: consumidores, banco, cache e
  reenvio idempotente conferidos.
- APK +4: instalação confirmada pelo usuário; 47 testes Flutter e análise sem
  problemas. Não houve novo push direto apenas para repetir a validação.

Veja `docs/TESTES_FINAIS_ANDROID.md` e `docs/evidence`. O percurso físico por GPS
foi **dispensado sem execução**. iOS/APNs continuam pendentes. Infraestrutura e
carga foram testadas no mesmo computador.

## Alternativa de demonstração simples

Em outra máquina, extraia EcoPulse-fonte.zip e, com Python 3.11+, execute:

~~~powershell
.\scripts\run_demo.ps1
~~~

Em outro terminal, para criar exemplos identificados:

~~~powershell
.\backend\.venv\Scripts\python.exe scripts/seed_demo.py
~~~

Esse modo usa **EcoPulse-demo.apk** e a porta **8000**, sem o cluster completo ou
Firebase. Com Flutter instalado, abra a prévia por
`.\scripts\run_mobile.ps1 -Device chrome`.

O ZIP inclui fontes e documentos, mas não `.env`, credenciais, bancos ou imagens
Docker. Outro computador exige preparar o ambiente completo conforme
`docs/CONFIGURAR_SERVICOS.md` e os arquivos de `infra/`.

## Documentos acadêmicos

Abra **Relatorio_APS_EcoPulse.docx** e **Roteiro_Apresentacao_EcoPulse.docx**.
O roteiro distribui dez minutos entre Vitória, Alessandro e Augusto. A divisão
de responsabilidades está marcada como sugerida para conferência dos integrantes.
Datas, horas reais e assinaturas serão preenchidas manualmente. Campus e data
da apresentação permanecem editáveis.

O APK usa assinatura de desenvolvimento. AQI full é modelado; calor reúne
32 polígonos Landsat de 17/09/2025 e está identificado como histórico. Mantenha
fonte e data visíveis na apresentação.



Atualização documental em 06/10/2026: responsabilidades definitivas e horas confirmadas pela equipe (Vitória 21 h, Alessandro 23 h, Augusto 30 h). A equipe também declarou aprovação manual de iOS/APNs e do deslocamento físico por GPS, além da conclusão das revisões finais. Esses resultados são confirmações humanas, sem novos logs ou observação independente; datas de execução e detalhes do iPhone/APNs não foram informados. O relatório conserva as datas das provas técnicas e mantém assinaturas em branco. Registro: docs/evidence/academic-team-confirmation-20261006.json.
