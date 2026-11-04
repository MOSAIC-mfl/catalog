#!/usr/bin/env python3
"""Generate the field reference from the schemas, so it cannot drift from them:

* docs/fields.xlsx           every field (nested ones too): level, type, values, meaning,
                              equivalents in CDH and in MOSAIC schema 1;
* docs/record-reference.yaml a record with EVERY field, each with a comment saying its level
                              and what it is.

    python3 scripts/build_reference.py

Needs openpyxl (dev dependency).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema"
DOCS = ROOT / "docs"

MIN, REC, PROF, OPT, AUTO = "Mínimo", "Recomendado", "Perfil mosaic", "Opcional", "Automático"

# Level of nested fields, where the level schemas set one (top-level fields are read from the schemas).
NESTED_LEVELS = {
    "license.spdx": (MIN, "spdx o text: al menos uno"),
    "license.text": (MIN, "spdx o text: al menos uno"),
    "license.url": (REC, "recomendado cuando spdx está vacío"),
    "contacts[].roles": (REC, "recomendado: algún contacto con rol licensor"),
    "data[].kind": (MIN, ""),
    "data[].method": (MIN, ""),
    "data[].url": (MIN, "si access es public, al menos un punto con url"),
    "temporal.start": (REC, ""),
    "spatial.bbox": (REC, ""),
    "keywords[].uri": (REC, "recomendado: al menos una keyword enlazada (p. ej. AGROVOC)"),
    "citation.authors": (REC, "recomendado: cita con autores, o un DOI"),
    "mosaic.landscapes": (PROF, "obligatorio si se activa el perfil mosaic"),
    "data[].vector.geometry_type": (REC, "si kind es vector; lo infiere `infer` cuando puede leer el archivo"),
    "data[].tabular.spatial": (REC, "si kind es tabular; lo infiere `infer` cuando puede leer el archivo"),
}
EXAMPLES = {  # for fields the complete test fixture does not use
    "note": "Pixel area shrinks with latitude; reproject before computing areas.",
    "access_note": "Write to the point of contact; data shared under a data-sharing agreement.",
    "doi": "10.5061/dryad.6djh9w18f",
    "version": "v2",
    "language": ["en", "es"],
    "funding": [{"name": "CGIAR Trust Fund", "url": "https://www.cgiar.org/funders/", "award": "MFL-2026"}],
    "related": [
        {
            "relation": "IsSupplementTo",
            "scheme": "doi",
            "value": "10.1016/j.agee.2025.109966",
            "title": "Journal article",
        }
    ],
    "extensions": ["soil@0.1.0"],
    "source_updated": "2025-10-01",
    "derived": ["spatial.bbox"],
    "data[].derived": ["vector.geometry_type"],
    "data[].tabular.spatial": True,
    "data[].tabular.coordinate_columns.x": "lon",
    "data[].tabular.coordinate_columns.y": "lat",
    "data[].vector.geometry_type": "point",
}


@dataclass
class Row:
    path: str
    depth: int
    type: str
    level: str
    condition: str
    required_in_object: bool
    values: str
    description: str
    example: Any
    cdh: str
    schema1: str
    is_object: bool


def load(rel: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMA / rel).read_text(encoding="utf-8"))
    return data


class Walker:
    def __init__(self) -> None:
        self.rec = load("record.schema.json")
        self.defs = self.rec["$defs"]
        self.vocab = load("vocab.schema.json")["$defs"]
        self.vocab_files = {
            "theme": "themes", "landscape": "landscapes", "geography": "geography", "resourceType": "resource_type",
            "access": "access", "dataKind": "data_kind", "accessMethod": "access_method",
            "contactRole": "contact_role", "relation": "relation", "updateFrequency": "update_frequency",
        }  # fmt: skip
        self.min = load("levels/minimum.schema.json")
        self.recm = load("levels/recommended.schema.json")
        self.example = yaml.safe_load((ROOT / "tests" / "fixtures" / "valid" / "complete.yaml").read_text("utf-8"))
        self.cdh = self._reverse(ROOT / "crosswalks" / "cdh.yaml", "cdh")
        self.s1 = self._reverse(ROOT / "crosswalks" / "mosaic-schema1.yaml", "s1")
        self.rows: list[Row] = []

    @staticmethod
    def _reverse(path: Path, kind: str) -> dict[str, list[str]]:
        fields: dict[str, str] = yaml.safe_load(path.read_text(encoding="utf-8"))["fields"]
        out: dict[str, list[str]] = {}
        for src, dst in fields.items():
            for target in re.split(r"\s*[/,]\s*", str(dst)):
                target = target.split(" ")[0].replace("[0]", "[]")
                if target:
                    out.setdefault(target, []).append(src)
        return out

    def resolve(self, node: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        ref = node.get("$ref")
        if ref and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[1]
            target = self.defs[name]
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return merged, name
        return node, None

    def type_and_values(self, node: dict[str, Any]) -> tuple[str, str]:
        ref = node.get("$ref", "")
        if ref.startswith("vocab.schema.json"):
            name = ref.rsplit("/", 1)[1]
            enum = self.vocab[name]["enum"]
            shown = ", ".join(enum) if len(enum) <= 20 else f"{len(enum)} códigos (ver hoja Vocabularios)"
            return "texto (vocabulario)", f"vocab/{self.vocab_files[name]}.json: {shown}"
        node, defname = self.resolve(node)
        if "oneOf" in node:
            parts = [self.type_and_values(n)[0] for n in node["oneOf"]]
            nullable = "null" in parts
            label = " o ".join(dict.fromkeys(p for p in parts if p != "null"))
            return label + (" (puede ser null)" if nullable else ""), ""
        t = node.get("type")
        names = {"string": "texto", "object": "objeto", "number": "número", "integer": "entero", "boolean": "sí/no"}
        if isinstance(t, list):
            t = " / ".join(names.get(x, x) for x in t if x != "null") + (" (puede ser null)" if "null" in t else "")
        if t == "array":
            inner, values = self.type_and_values(node.get("items", {}))
            if "prefixItems" in node:
                return "lista de 4 números", "[oeste, sur, este, norte] en grados WGS84"
            return f"lista de {inner}", values
        if "enum" in node:
            return "texto (lista cerrada)", ", ".join(map(str, node["enum"]))
        hint = {"date": "YYYY, YYYY-MM o YYYY-MM-DD", "doi": "10.xxxx/sufijo", "url": "URL absoluta",
                "ror": "https://ror.org/0xxxxxxxx", "orcid": "https://orcid.org/0000-0000-0000-0000",
                "crs": "EPSG:4326", "language": "código BCP 47 (en, es-PE)"}.get(defname or "", "")  # fmt: skip
        names = {"string": "texto", "object": "objeto", "number": "número", "integer": "entero", "boolean": "sí/no"}
        if t == "null":
            return "null", ""
        label = names.get(str(t), str(t) if t else ("objeto" if "properties" in node else "texto"))
        return label, hint

    def top_level(self, name: str) -> tuple[str, str]:
        if name in ("created", "updated"):
            return AUTO, "lo llena el build con el historial de git si no está"
        if name in ("citation", "doi"):
            return MIN, "citation o doi: al menos uno"
        if name == "access_note":
            return MIN, "obligatorio si access es restricted o internal"
        if name in self.min["required"]:
            return MIN, ""
        if name in self.recm["required"]:
            return REC, ""
        if name == "mosaic":
            return PROF, "aviso en v0.1; obligatorio si se activa el perfil"
        return OPT, ""

    def example_at(self, path: str) -> Any:
        node: Any = self.example
        for part in path.split("."):
            list_part = part.endswith("[]")
            key = part.removesuffix("[]")
            if isinstance(node, list):
                node = next((x for x in node if isinstance(x, dict) and key in x), None)
            if not isinstance(node, dict) or key not in node:
                return EXAMPLES.get(path)
            node = node[key]
            if list_part and isinstance(node, list) and node and isinstance(node[0], dict):
                continue
        return node

    def walk(self, props: dict[str, Any], prefix: str, depth: int, required: set[str]) -> None:
        for name, raw in props.items():
            path = f"{prefix}{name}"
            node, _ = self.resolve(raw)
            typ, values = self.type_and_values(raw)
            if depth == 0:
                level, cond = self.top_level(name)
            else:
                level, cond = NESTED_LEVELS.get(path.replace("[]", "[]"), (OPT, ""))
            desc = raw.get("description") or node.get("description") or ""
            item = node.get("items", {}) if node.get("type") == "array" else None
            item_node = self.resolve(item)[0] if isinstance(item, dict) else None
            child = item_node if item_node and "properties" in item_node else (node if "properties" in node else None)
            if node.get("oneOf"):  # e.g. citation: text or object -> document the object form
                objs = [self.resolve(o)[0] for o in node["oneOf"]]
                child = next((o for o in objs if "properties" in o), child)
            key_path = path + ("[]" if item_node is not None and child is item_node else "")
            row = Row(
                path=key_path,
                depth=depth,
                type=typ,
                level=level,
                condition=cond,
                required_in_object=name in required,
                values=values,
                description=desc,
                example=self.example_at(key_path),
                cdh=", ".join(self.cdh.get(key_path, self.cdh.get(path, []))),
                schema1=", ".join(self.s1.get(key_path, self.s1.get(path, []))),
                is_object=child is not None,
            )
            self.rows.append(row)
            if child is not None:
                self.walk(child["properties"], key_path + ".", depth + 1, set(child.get("required", [])))


def write_xlsx(rows: list[Row], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    font, bold = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
    head_fill = PatternFill("solid", fgColor="1F4E5A")
    level_fill = {
        MIN: PatternFill("solid", fgColor="F8D7D3"),
        REC: PatternFill("solid", fgColor="FCEBC6"),
        PROF: PatternFill("solid", fgColor="D9EAF7"),
        AUTO: PatternFill("solid", fgColor="E8E8E8"),
    }
    thin = Border(bottom=Side(style="thin", color="DDDDDD"))
    wb = Workbook()

    readme = wb.active
    readme.title = "Léeme"
    text = [
        ("MOSAIC — campos del estándar de metadatos v0.1", True),
        ("Generado por scripts/build_reference.py desde schema/. No editar a mano: cambiar el esquema y regenerar.", False),
        ("", False),
        ("Niveles", True),
        ("Mínimo: obligatorio. Si falta, el registro queda INCOMPLETO y aparece en review/minimum_gaps.", False),
        ("Recomendado: si falta, solo es un aviso.", False),
        ("Perfil mosaic: aviso en v0.1; pasa a obligatorio con profiles.mosaic.enforce: true en mosaic.config.yaml.", False),
        ("Opcional: sin control.", False),
        ("Automático: lo llena el build (historial de git); no lo escribe una persona.", False),
        ("", False),
        ("Columnas de la hoja Campos", True),
        ("Campo: ruta del campo. [] = lista; un punto = campo dentro de un objeto (p. ej. data[].kind).", False),
        ("Obligatorio en el objeto: el campo es obligatorio cuando su objeto existe (forma, no completitud).", False),
        ("Condición: cuándo aplica el nivel.", False),
        ("CDH: campo del Climate Data Hub del que se lee (crosswalks/cdh.yaml). Esquema 1: campo del catálogo actual (crosswalks/mosaic-schema1.yaml).", False),
        ("", False),
        ("Un campo con forma incorrecta (tipo, vocabulario, fecha) hace el registro INVÁLIDO sin importar su nivel.", False),
    ]  # fmt: skip
    for i, (t, b) in enumerate(text, 1):
        readme.cell(i, 1, t).font = Font(name="Arial", size=12 if i == 1 else 10, bold=b)
    readme.column_dimensions["A"].width = 120

    ws = wb.create_sheet("Campos")
    headers = ["Campo", "Nivel", "Condición", "Obligatorio en el objeto", "Tipo", "Valores / formato",
               "Qué es (EN)", "Ejemplo", "CDH", "Esquema 1 (catalog actual)"]  # fmt: skip
    widths = [30, 14, 34, 12, 22, 40, 60, 40, 26, 26]
    for c, (h, w) in enumerate(zip(headers, widths, strict=True), 1):
        cell = ws.cell(1, c, h)
        cell.font, cell.fill = Font(name="Arial", size=10, bold=True, color="FFFFFF"), head_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = w
    for r, row in enumerate(rows, 2):
        ex = row.example
        ex_text = (
            ""
            if ex is None or row.is_object
            else (json.dumps(ex, ensure_ascii=False) if not isinstance(ex, str) else ex)
        )
        vals = ["  " * row.depth + row.path, row.level, row.condition, "sí" if row.required_in_object else "",
                row.type, row.values, row.description, ex_text, row.cdh, row.schema1]  # fmt: skip
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c, v)
            cell.font = bold if (c == 1 and row.depth == 0) else font
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = thin
        if row.level in level_fill:
            ws.cell(r, 2).fill = level_fill[row.level]
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    summ = wb.create_sheet("Resumen", 1)
    summ["A1"], summ["B1"], summ["C1"] = "Nivel", "Campos de primer nivel", "Todos los campos (incl. anidados)"
    for c in "ABC":
        summ[f"{c}1"].font, summ[f"{c}1"].fill = Font(name="Arial", size=10, bold=True, color="FFFFFF"), head_fill
    last = len(rows) + 1
    top_flags = ["sí" if row.depth == 0 else "" for row in rows]
    ws.cell(1, 11, "Primer nivel").font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    ws.cell(1, 11).fill = head_fill
    for r, flag in enumerate(top_flags, 2):
        ws.cell(r, 11, flag).font = font
    for i, level in enumerate((MIN, REC, PROF, AUTO, OPT), 2):
        summ.cell(i, 1, level).font = font
        summ.cell(i, 2, f'=COUNTIFS(Campos!$B$2:$B${last},A{i},Campos!$K$2:$K${last},"sí")').font = font
        summ.cell(i, 3, f"=COUNTIF(Campos!$B$2:$B${last},A{i})").font = font
        if level in level_fill:
            summ.cell(i, 1).fill = level_fill[level]
    summ.cell(7, 1, "Total").font = bold
    summ.cell(7, 2, "=SUM(B2:B6)").font = bold
    summ.cell(7, 3, "=SUM(C2:C6)").font = bold
    summ.column_dimensions["A"].width, summ.column_dimensions["B"].width = 18, 24
    summ.column_dimensions["C"].width = 34

    voc = wb.create_sheet("Vocabularios")
    for c, h in enumerate(["Vocabulario", "id", "Etiqueta", "Descripción / código"], 1):
        cell = voc.cell(1, c, h)
        cell.font, cell.fill = Font(name="Arial", size=10, bold=True, color="FFFFFF"), head_fill
    r = 2
    for f in sorted((ROOT / "vocab").glob("*.json")):
        for concept in json.loads(f.read_text(encoding="utf-8"))["concepts"]:
            extra = concept.get("description") or ", ".join(
                f"{k}: {v}" for k, v in concept.items() if k not in ("id", "label")
            )
            for c, v in enumerate([f.stem, concept["id"], concept["label"], extra], 1):
                voc.cell(r, c, v).font = font
            r += 1
    for col, w in zip("ABCD", (18, 30, 40, 80), strict=True):
        voc.column_dimensions[col].width = w
    voc.freeze_panes = "A2"
    voc.auto_filter.ref = f"A1:D{r - 1}"
    wb.save(path)


def write_reference_yaml(rows: list[Row], path: Path) -> None:
    out = [
        "# MOSAIC record — every field of the standard v0.1, with its level and meaning.",
        "# Generated by scripts/build_reference.py from schema/. Reference only: a real record uses",
        "# only the fields it knows (template: docs/record-template.yaml). Values are examples",
        "# (mostly from the synthetic test record tests/fixtures/valid/complete.yaml).",
        "#",
        "# [MÍNIMO] required to be complete · [RECOMENDADO] warning if missing",
        "# [PERFIL MOSAIC] warning in v0.1 · [OPCIONAL] · [AUTOMÁTICO] filled by the build",
        "",
    ]

    def children(parent: str) -> list[Row]:
        prefix = parent + "." if parent else ""
        return [r for r in rows if r.path.startswith(prefix) and "." not in r.path[len(prefix) :]]

    def emit(parent: str, indent: str) -> None:
        for row in children(parent):
            name = row.path.rsplit(".", 1)[-1]
            is_list = name.endswith("[]")
            name = name.removesuffix("[]")
            tag = f"[{row.level.upper()}]" + (f" ({row.condition})" if row.condition else "")
            req = " · obligatorio en su objeto" if row.depth and row.required_in_object else ""
            desc = (row.description or "").rstrip(".")
            values = f" · {row.values}" if row.values and len(row.values) < 140 else ""
            out.append(f"{indent}# {tag}{req} — {row.type}{values}" + (f". {desc}" if desc else ""))
            if row.is_object:
                out.append(f"{indent}{name}:")
                if is_list:
                    out.append(f"{indent}  -")  # one example item; its fields follow
                    emit(row.path, indent + "    ")
                else:
                    emit(row.path, indent + "  ")
            else:
                ex = row.example
                if ex is None and "texto" in row.type and "lista" not in row.type:
                    ex = ""
                out.append(f"{indent}{name}: {json.dumps(ex, ensure_ascii=False)}")

    emit("", "")
    text = "\n".join(out) + "\n"
    yaml.safe_load(text)  # must stay valid YAML
    path.write_text(text, encoding="utf-8")


def main() -> int:
    w = Walker()
    w.walk(w.rec["properties"], "", 0, set())
    write_xlsx(w.rows, DOCS / "fields.xlsx")
    write_reference_yaml(w.rows, DOCS / "record-reference.yaml")
    print(f"{len(w.rows)} fields -> docs/fields.xlsx, docs/record-reference.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
