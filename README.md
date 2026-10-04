# Mandato Aberto — Maranhão 2026

Painel estático de candidaturas do Maranhão nas Eleições 2026. Funciona no navegador com a base incluída e também oferece os arquivos processados para download.

## Abrir o app

https://assishenriques.github.io/mandato-aberto-ma-2026/

## Arquivos de dados

- `data/initial-candidates.json`: base pronta que o app usa para exibir e filtrar as candidaturas.
- `data/producao-legislativa.json`: proposições registradas em nome dos candidatos nas bases da Câmara dos Deputados e do Senado, incluindo totais/status por candidatura, data da coleta e links para os registros oficiais. A coleta abrange as legislaturas federais 52ª–57ª e roda junto da sincronização diária. A vinculação é por nome e pode haver homônimos; os links oficiais devem ser usados para conferir cada matéria.
- `data/consulta_cand_2026_MA.csv`: recorte do arquivo de candidaturas do TSE para o Maranhão.
- `data/consulta_cand_complementar_2026_MA.csv`: dados complementares correspondentes às candidaturas do Maranhão.
- `data/meta.json`: fontes, horário da atualização e contagens dos arquivos.

Os arquivos CSV publicados foram reduzidos a campos públicos usados no painel. Identificadores pessoais e informações de contato não são incluídos. Os dados são sincronizados diariamente pelo GitHub Actions; também podem ser atualizados manualmente pelo workflow do repositório.

## Fontes oficiais

- [TSE — Candidatos 2026](https://dadosabertos.tse.jus.br/pt_BR/dataset/candidatos-2026)
- [Arquivo principal de candidaturas do TSE](https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip)
- [Arquivo complementar de candidaturas do TSE](https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand_complementar/consulta_cand_complementar_2026.zip)
- [Câmara dos Deputados — Dados Abertos](https://dadosabertos.camara.leg.br/swagger/api.html)
- [Senado Federal — Dados Abertos](https://www12.senado.leg.br/dados-abertos/conjuntos)

Os dados de candidatura vêm dos arquivos do TSE. A produção legislativa cobre Câmara dos Deputados e Senado Federal; a ALEMA e câmaras municipais ainda não estão integradas. Ausência de registro na base federal não significa ausência de produção legislativa.

## Atualização

O workflow `.github/workflows/sync-data.yml` baixa os dois ZIPs oficiais, filtra o Maranhão, mantém somente as colunas necessárias, atualiza os CSVs, JSONs e os dados incorporados ao HTML, e então o GitHub Pages publica a nova versão.

## Limites da cobertura legislativa

A coleta de produção legislativa cobre Câmara dos Deputados e Senado Federal. Ainda não integra ALEMA nem câmaras municipais; portanto, ausência de registro no arquivo federal não significa ausência de produção legislativa. A lista de matérias reúne proposições de autoria/coautoria encontradas nas fontes, não representa por si só posicionamento temático, voto ou relatoria.
