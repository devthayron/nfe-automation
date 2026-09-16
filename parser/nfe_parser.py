from datetime import datetime
from decimal import Decimal

from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

from schemas.nfe import (
    COFINS,
    IBSCBS,
    ICMS,
    IPI,
    PIS,
    NFe,
    NFeItem,
    Person,
    Product,
    Taxation,
)


class NFeParser:
    def __init__(self, path: str):
        self.path = path
        self.nfe_proc = None
        self.inf_nfe = None
        self.inf_prot = None

    def read_nfe(self):
        try:
            self.nfe_proc = NfeProc.from_path(self.path)

            self.inf_nfe = self.nfe_proc.NFe.infNFe
            self.inf_prot = self.nfe_proc.protNFe.infProt

        except Exception as e:  # noqa: BLE001
            print(f"Erro ao ler XML da NFe: {e}")

    def extract_nfe(self):
        ide = self.inf_nfe.ide

        return {
            "ch_nfe": str(self.inf_prot.chNFe),
            "n_nf": int(ide.nNF),
            "serie": int(ide.serie),
            "dh_emi": datetime.fromisoformat(str(ide.dhEmi)),
        }

    def extract_emit(self):
        emit = self.inf_nfe.emit

        return Person(
            cnpj=str(emit.CNPJ),
            x_nome=str(emit.xNome),
            uf=str(emit.enderEmit.UF.value),
        )

    def extract_dest(self):
        dest = self.inf_nfe.dest

        return Person(
            cnpj=str(dest.CNPJ),
            x_nome=str(dest.xNome),
            uf=str(dest.enderDest.UF.value),
        )

    def extract_product(self, product):
        v_desc = getattr(product, "vDesc", None)

        return Product(
            c_prod=str(product.cProd),
            c_ean=str(product.cEAN) if product.cEAN else None,
            x_prod=str(product.xProd),
            ncm=str(product.NCM),
            cest=str(product.CEST) if product.CEST else None,
            cfop=str(product.CFOP),
            u_com=str(product.uCom),
            q_com=Decimal(str(product.qCom)),
            v_un_com=Decimal(str(product.vUnCom)),
            v_prod=Decimal(str(product.vProd)),
            v_desc=Decimal(str(v_desc)) if v_desc else None,
        )

    def find_group(self, structure):
        for group in vars(structure).values():
            if group is not None:
                return group

        return None

    def convert_decimal(self, value):
        if value is None:
            return None

        return Decimal(str(value))

    def extract_icms(self, tax):
        icms = tax.ICMS

        if icms is None:
            return None

        group = self.find_group(icms)

        if group is None:
            return None

        cst = getattr(group, "CST", None)
        csosn = getattr(group, "CSOSN", None)

        if cst is not None:
            cst_csosn = str(cst.value)
        elif csosn is not None:
            cst_csosn = str(csosn.value)
        else:
            cst_csosn = None

        orig = getattr(group, "orig", None)
        v_bc = getattr(group, "vBC", None)
        p_icms = getattr(group, "pICMS", None)
        v_icms = getattr(group, "vICMS", None)
        v_bc_st = getattr(group, "vBCST", None)
        p_icms_st = getattr(group, "pICMSST", None)
        v_icms_st = getattr(group, "vICMSST", None)

        return ICMS(
            orig=int(orig.value) if orig is not None else None,
            cst_csosn=cst_csosn,
            v_bc=self.convert_decimal(v_bc),
            p_icms=self.convert_decimal(p_icms),
            v_icms=self.convert_decimal(v_icms),
            v_bc_st=self.convert_decimal(v_bc_st),
            p_icms_st=self.convert_decimal(p_icms_st),
            v_icms_st=self.convert_decimal(v_icms_st),
        )

    def extract_pis(self, tax):
        pis = tax.PIS

        if pis is None:
            return None

        group = self.find_group(pis)

        if group is None:
            return None

        group_name = type(group).__name__

        if group_name not in {"Pisaliq", "Pisoutr", "Pisnt"}:
            print(f"Tipo de PIS não tratado: {group_name}")

        cst = getattr(group, "CST", None)
        v_bc = getattr(group, "vBC", None)
        p_pis = getattr(group, "pPIS", None)
        v_pis = getattr(group, "vPIS", None)

        return PIS(
            cst=str(cst.value) if cst is not None else None,
            v_bc=self.convert_decimal(v_bc),
            p_pis=self.convert_decimal(p_pis),
            v_pis=self.convert_decimal(v_pis),
        )

    def extract_cofins(self, tax):
        cofins = tax.COFINS

        if cofins is None:
            return None

        group = self.find_group(cofins)

        if group is None:
            return None

        group_name = type(group).__name__

        if group_name not in {"Cofinsaliq", "Cofinsoutr", "Cofinsnt"}:
            print(f"Tipo de COFINS não tratado: {group_name}")

        cst = getattr(group, "CST", None)
        v_bc = getattr(group, "vBC", None)
        p_cofins = getattr(group, "pCOFINS", None)
        v_cofins = getattr(group, "vCOFINS", None)

        return COFINS(
            cst=str(cst.value) if cst is not None else None,
            v_bc=self.convert_decimal(v_bc),
            p_cofins=self.convert_decimal(p_cofins),
            v_cofins=self.convert_decimal(v_cofins),
        )

    def extract_ipi(self, tax):
        ipi = tax.IPI

        if ipi is None:
            return None

        if ipi.IPITrib is not None:
            group = ipi.IPITrib

            cst = getattr(group, "CST", None)
            v_bc = getattr(group, "vBC", None)
            p_ipi = getattr(group, "pIPI", None)
            v_ipi = getattr(group, "vIPI", None)

            return IPI(
                cst=str(cst.value) if cst is not None else None,
                v_bc=self.convert_decimal(v_bc),
                p_ipi=self.convert_decimal(p_ipi),
                v_ipi=self.convert_decimal(v_ipi),
            )

        elif ipi.IPINT is not None:
            group = ipi.IPINT

            cst = getattr(group, "CST", None)

            return IPI(
                cst=str(cst.value) if cst is not None else None,
            )

        else:
            print(f"Tipo de IPI não tratado: {type(ipi).__name__}")
            return None

    def extract_ibs_cbs(self, tax):
        ibs_cbs = tax.IBSCBS

        if ibs_cbs is None:
            return None

        cst = getattr(ibs_cbs, "CST", None)
        c_class_trib = getattr(ibs_cbs, "cClassTrib", None)

        return IBSCBS(
            cst=str(cst) if cst is not None else None,
            c_class_trib=str(c_class_trib) if c_class_trib is not None else None,
        )

    def extract_taxation(self, tax):
        taxation = Taxation()

        if tax.ICMS:
            taxation.icms = self.extract_icms(tax)

        if tax.PIS:
            taxation.pis = self.extract_pis(tax)

        if tax.COFINS:
            taxation.cofins = self.extract_cofins(tax)

        if tax.IPI:
            taxation.ipi = self.extract_ipi(tax)

        if tax.IBSCBS:
            taxation.ibs_cbs = self.extract_ibs_cbs(tax)

        return taxation

    def extract_items(self):
        items = []

        for item in self.inf_nfe.det:
            items.append(
                NFeItem(
                    n_item=int(item.nItem),
                    product=self.extract_product(item.prod),
                    taxation=self.extract_taxation(item.imposto),
                )
            )

        return items

    def extract_data(self):
        try:
            nfe_data = self.extract_nfe()

            return NFe(
                **nfe_data,
                emit=self.extract_emit(),
                dest=self.extract_dest(),
                items=self.extract_items(),
            )

        except AttributeError as e:
            print(f"Estrutura da NFe incompleta: {e}")
            return None
