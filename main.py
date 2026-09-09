import json

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc


def ler_nfe(caminho: str):
    try:
        return NfeProc.from_path(caminho)

    except Exception as e:
        print(f"Erro ao ler XML da NFe: {e}")
        return None


def extrair_dados(nfe_proc):
    try:
        inf_nfe = nfe_proc.NFe.infNFe
        inf_prot = nfe_proc.protNFe.infProt

        ide = inf_nfe.ide
        emit = inf_nfe.emit
        dest = inf_nfe.dest

    except AttributeError as e:
        print(f"Estrutura da NFe incompleta: {e}")
        return None

    return {
        "nfe": {
            "chave": str(inf_prot.chNFe),
            "numero": str(ide.nNF),
            "serie": str(ide.serie),
            "data_emissao": str(ide.dhEmi),
        },
        "emitente": {
            "cnpj": str(emit.CNPJ),
            "razao_social": str(emit.xNome),
            "endereco": {
                "uf": emit.enderEmit.UF.value,
            },
        },
        "destinatario": {
            "cnpj": str(dest.CNPJ),
            "razao_social": str(dest.xNome),
            "endereco": {
                "uf": dest.enderDest.UF.value,
            },
        },
    }


for i in range(5):
    nfe_proc = ler_nfe(f"data/nota{i + 1}.xml")

    data = extrair_dados(nfe_proc)

    if data:
        data_json = json.dumps(data, indent=4, ensure_ascii=False)
        print(f"Nota {i + 1}: \n{data_json}")
