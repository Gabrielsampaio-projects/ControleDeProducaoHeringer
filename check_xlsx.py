from pathlib import Path
import pandas as pd

arquivo = Path('/home/ubuntu/controleproducao_inspecao/Emissao.XLSX')
df = pd.read_excel(arquivo, dtype=str, nrows=0)
print('COLUNAS_PLANILHA')
for coluna in df.columns:
    print(repr(str(coluna)))

esperadas = [
    'Planta',
    'Data da nova criação',
    'Hora de criação',
    'Descrição do Cliente',
    'Código de Material',
    'Descrição do Materia',
    'Tipo de Emabalagem',
    'Ord. Proc. – Qtd',
    'Mot. Caminhão',
    'Placa do Caminhão',
    'Tipo de Frete',
    'Qtd. da Remessa',
    'Contrato SF',
    'Ordem de Venda',
    'Ordem de Processo',
    'Remessa',
]
print('ESPERADAS_AUSENTES')
for coluna in esperadas:
    if coluna not in df.columns:
        print(repr(coluna))
