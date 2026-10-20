import logging
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum

from schemas.nfe import (
    COFINS,
    IBSCBS,
    ICMS,
    IPI,
    PIS,
    Taxation,
)

logger = logging.getLogger(__name__)


class TaxParser:
    @staticmethod
    def _get_value(value):
        """Obtém o valor de um Enum ou mantém o valor original."""
        if isinstance(value, Enum):
            return value.value
        return value

    @classmethod
    def _convert_decimal(cls, value):
        """Converte valores para Decimal sem utilizar float."""
        value = cls._get_value(value)

        if value is None:
            return None

        return Decimal(str(value))

    @staticmethod
    def _get_fields(obj):
        """Retorna os campos de uma dataclass, quando aplicável."""
        if obj is None or isinstance(obj, type):
            return ()

        if not is_dataclass(obj):
            return ()

        return fields(obj)

    @classmethod
    def _get_attr(cls, obj, name):
        """
        Obtém um atributo ignorando diferenças entre maiúsculas
        e minúsculas, preservando o nome original do campo.
        """
        if obj is None:
            return None

        value = getattr(obj, name, None)
        if value is not None:
            return value

        normalized_name = name.casefold()

        for field in cls._get_fields(obj):
            if field.name.casefold() == normalized_name:
                return getattr(obj, field.name, None)

        return None

    @classmethod
    def _find_group(cls, structure):
        """Encontra a variante tributária preenchida."""
        if structure is None:
            return None

        for field in cls._get_fields(structure):
            value = cls._get_attr(structure, field.name)

            if value is not None and cls._get_fields(value):
                return value

        return None

    @classmethod
    def _get_tax_value(cls, group, field_name):
        """Obtém um campo opcional de uma variante tributária."""
        if group is None:
            return None

        return cls._get_value(cls._get_attr(group, field_name))

    @classmethod
    def _extract_icms(cls, tax):
        group = cls._find_group(cls._get_attr(tax, "ICMS"))

        if group is None:
            return None

        cst = cls._get_tax_value(group, "CST")
        csosn = cls._get_tax_value(group, "CSOSN")
        orig = cls._get_tax_value(group, "orig")

        return ICMS(
            orig=int(orig) if orig is not None else None,
            cst=str(cst) if cst is not None else None,
            csosn=str(csosn) if csosn is not None else None,
            v_bc=cls._convert_decimal(cls._get_tax_value(group, "vBC")),
            p_icms=cls._convert_decimal(cls._get_tax_value(group, "pICMS")),
            v_icms=cls._convert_decimal(cls._get_tax_value(group, "vICMS")),
            v_bc_st=cls._convert_decimal(cls._get_tax_value(group, "vBCST")),
            p_icms_st=cls._convert_decimal(cls._get_tax_value(group, "pICMSST")),
            v_icms_st=cls._convert_decimal(cls._get_tax_value(group, "vICMSST")),
        )

    @classmethod
    def _extract_pis(cls, tax):
        group = cls._find_group(cls._get_attr(tax, "PIS"))

        if group is None:
            return None

        cst = cls._get_tax_value(group, "CST")

        return PIS(
            cst=str(cst) if cst is not None else None,
            v_bc=cls._convert_decimal(cls._get_tax_value(group, "vBC")),
            p_pis=cls._convert_decimal(cls._get_tax_value(group, "pPIS")),
            v_pis=cls._convert_decimal(cls._get_tax_value(group, "vPIS")),
            q_bc_prod=cls._convert_decimal(cls._get_tax_value(group, "qBCProd")),
            v_aliq_prod=cls._convert_decimal(cls._get_tax_value(group, "vAliqProd")),
        )

    @classmethod
    def _extract_cofins(cls, tax):
        group = cls._find_group(cls._get_attr(tax, "COFINS"))

        if group is None:
            return None

        cst = cls._get_tax_value(group, "CST")

        return COFINS(
            cst=str(cst) if cst is not None else None,
            v_bc=cls._convert_decimal(cls._get_tax_value(group, "vBC")),
            p_cofins=cls._convert_decimal(cls._get_tax_value(group, "pCOFINS")),
            v_cofins=cls._convert_decimal(cls._get_tax_value(group, "vCOFINS")),
            q_bc_prod=cls._convert_decimal(cls._get_tax_value(group, "qBCProd")),
            v_aliq_prod=cls._convert_decimal(cls._get_tax_value(group, "vAliqProd")),
        )

    @classmethod
    def _extract_ipi(cls, tax):
        group = cls._find_group(cls._get_attr(tax, "IPI"))

        if group is None:
            return None

        cst = cls._get_tax_value(group, "CST")

        return IPI(
            cst=str(cst) if cst is not None else None,
            v_bc=cls._convert_decimal(cls._get_tax_value(group, "vBC")),
            p_ipi=cls._convert_decimal(cls._get_tax_value(group, "pIPI")),
            v_ipi=cls._convert_decimal(cls._get_tax_value(group, "vIPI")),
            q_unid=cls._convert_decimal(cls._get_tax_value(group, "qUnid")),
            v_unid=cls._convert_decimal(cls._get_tax_value(group, "vUnid")),
        )

    @classmethod
    def _extract_ibs_cbs(cls, tax):
        group = cls._get_attr(tax, "IBSCBS")

        if group is None:
            return None

        cst = cls._get_tax_value(group, "CST")
        c_class_trib = cls._get_tax_value(group, "cClassTrib")

        if cst is None and c_class_trib is None:
            return None

        return IBSCBS(
            cst=str(cst) if cst is not None else None,
            c_class_trib=(str(c_class_trib) if c_class_trib is not None else None),
        )

    def _extract_taxation(self, tax):
        """Extrai os impostos presentes no item da NF-e."""
        if tax is None:
            return None

        taxation = Taxation(
            icms=self._extract_icms(tax),
            pis=self._extract_pis(tax),
            cofins=self._extract_cofins(tax),
            ipi=self._extract_ipi(tax),
            ibs_cbs=self._extract_ibs_cbs(tax),
        )

        if not any(
            getattr(taxation, name) is not None
            for name in (
                "icms",
                "pis",
                "cofins",
                "ipi",
                "ibs_cbs",
            )
        ):
            return None

        return taxation
