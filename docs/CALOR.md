# Camada histórica de calor do EcoPulse

A camada usa um recorte real de temperatura da **superfície** de Ribeirão Preto,
obtido do Landsat 9. Ela permite mostrar diferenças espaciais na apresentação;
não informa a temperatura do ar, o calor atual ou um risco iminente. O aplicativo
identifica todos os polígonos como **Histórico — 17/09/2025**.

## Aquisição e fonte

| Item | Valor |
| --- | --- |
| Cena | `LC09_L2SP_220075_20250917_02_T1` |
| Aquisição | 17/09/2025, 13:10:21 UTC; 10:10:21 em Ribeirão Preto |
| Produto | USGS Landsat 9 Collection 2 Level-2 Surface Temperature, L2SP, Tier 1 |
| Nuvens no conjunto da cena | 0,05%; a máscara por pixel é aplicada adicionalmente |
| Recorte | Longitude −47,88 a −47,72; latitude −21,25 a −21,105 |
| Grades lidas | 545 × 564 pixels, sete bandas; leitura parcial de COG com HTTP Range |
| Espaçamento dos dados | 30 m; sensor térmico de 100 m reamostrado para a grade de 30 m |
| Camada exibida | 32 células de até 0,01°; polígonos simples, sem buracos |
| Pixéis válidos | 284.838 de 307.380 |

O [catálogo público STAC da cena](https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2/items/LC09_L2SP_220075_20250917_02_T1)
registra as URLs das bandas. O acesso aos COGs usa uma assinatura temporária
obtida anonimamente na [API de acesso do Planetary Computer](https://planetarycomputer.microsoft.com/docs/concepts/sas/).
O importador mantém essa assinatura somente em memória. Os arquivos de origem
e a proveniência contêm URLs sem tokens e nenhum segredo.

## Método acadêmico

1. Converter ST_B10: `DN × 0,00341802 + 149 − 273,15`, em °C.
2. Excluir preenchimento, nuvens dilatadas, cirrus, nuvens, sombras, neve e água
   pelos bits 0, 1, 2, 3, 4, 5 e 7 de QA_PIXEL. Excluir também confiança média
   ou alta nas combinações de nuvem, sombra, neve e cirrus; exigir QA_RADSAT=0.
3. Exigir incerteza ST_QA de no máximo 3 K e distância de nuvens ST_CDIST de
   pelo menos 1 km. Pixéis sem temperatura ou refletância são descartados.
4. Converter vermelho e infravermelho próximo de refletância da superfície
   (`DN × 0,0000275 − 0,2`) e calcular NDVI=(NIR−R)/(NIR+R).
5. Usar como referência a mediana térmica dos pixéis válidos com NDVI≥0,5
   no anel externo do recorte, fora do retângulo de análise. Exigir pelo menos
   500 pixéis de referência. Os limites de ambos os retângulos estão na proveniência.
6. Para cada célula do retângulo de análise, exigir ≥100 pixéis válidos e ≥70%
   de cobertura válida. Exibir até 32 células com NDVI mediano≤0,35 e contraste
   térmico mediano≥2 °C em relação à referência, ordenadas pelo maior contraste.

As conversões seguem a [documentação do produto USGS](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature).
A máscara usa a [documentação oficial de QA](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands)
e o índice segue a [definição USGS de NDVI](https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index).
A diferença entre a grade de 30 m e a aquisição térmica de 100 m está na
[tabela oficial das bandas Landsat](https://www.usgs.gov/faqs/what-are-band-designations-landsat-satellites).
Os limites de seleção das células e da vegetação são escolhas explícitas do
projeto acadêmico, não limiares oficiais de alerta.

O processamento encontrou referência de **36,743 °C** e contrastes de
**6,26 a 9,21 °C** nas células selecionadas. O valor exibido é o contraste;
`surface_temperature_c` conserva a mediana de temperatura absoluta da célula.
Solo exposto e pavimentos também podem aquecer. Não há classificação cadastral
do uso do solo, climatologia rural, comparação temporal ou validação em campo:
o resultado mostra áreas com superfície mais quente e não comprova, sozinho,
uma ilha de calor urbana climatológica.

## Reproduzir e conferir

Na raiz do projeto, usando o ambiente Python do backend:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\scripts\requirements-heat.txt
.\backend\.venv\Scripts\python.exe .\scripts\import_heat_landsat.py
```

Para repetir o cálculo a partir do recorte de origem já incluído, sem internet:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\import_heat_landsat.py --from-crop
.\backend\.venv\Scripts\python.exe -m pytest .\backend\tests\test_heat.py -q
```

O importador grava `backend/datasets/heat-ribeirao-preto.geojson`,
`heat-provenance.json`, o item STAC original e `heat_source/landsat-crop.npz`
(aproximadamente 1,83 MB). O manifesto contém SHA-256 dos três arquivos e
URLs públicas de todas as bandas. Novas importações atualizam o horário do
processamento e os hashes; a aquisição e os IDs das mesmas células permanecem.
Uma cena diferente pode ser escolhida com `--scene`, desde que seja L2SP,
cubra o mesmo recorte e cumpra os critérios de qualidade e referência.

## Contrato da API e do cache

`backend.shared.heat.heat_layers(now=None, path=None)` lê e valida o GeoJSON.
O runtime do backend não depende de rasterio, numpy ou GDAL. Erros de arquivo,
checksum, origem, geometria ou qualidade geram `HeatDataError`; dados simulados
não são substituídos silenciosamente por dados reais.

Cada feature possui `kind=calor`, `unit=°C`, `is_demo=false`,
`observation_type=historic`, fonte, cena e data de aquisição. `updated_at`
**continua sendo a aquisição de 2025**. `expires_at` indica uma janela de 24 horas
para reler o arquivo e atualizar o cache; não transforma a aquisição em
observação atual. O backend pode servir a cena histórica após atualizar seu
cache mantendo o aviso de data. A camada não cria alertas críticos de proximidade.

Os IDs são UUIDs estáveis da cena e da célula. `center_latitude`,
`center_longitude` e `radius_m` permitem assinatura geográfica dos eventos
da camada; a geometria do mapa continua sendo o polígono real da célula.

Referência bibliográfica: Earth Resources Observation and Science (EROS) Center.
(2020). Landsat 8–9 Operational Land Imager / Thermal Infrared Sensor Level-2,
Collection 2 [dataset]. U.S. Geological Survey. [DOI 10.5066/P9OGBGM6](https://doi.org/10.5066/P9OGBGM6).
