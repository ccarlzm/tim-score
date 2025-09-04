from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.apps import apps
from django.urls import get_resolver, URLResolver, URLPattern, RegexPattern


BAD_TEMPLATE_PATTERNS = [
    r"\b3\|\s*\+\s*[\w\.]+\|\|length",   # 3| + block.workouts||length (ejemplo roto)
    r"\|\|\s*length",                    # '||length' (filtro mal escrito)
]
SUSPICIOUS_ATTRS = [
    r"\b(?P<var>\w+)\.title\b",          # d.title (rompe si no existe)
]


def iter_urlpatterns(resolver, prefix="") -> List[str]:
    results = []
    for p in resolver.url_patterns:
        if isinstance(p, URLPattern):
            # Django 5 usa route en vez de regex
            route = getattr(p.pattern, "route", None)
            if route is None and isinstance(p.pattern, RegexPattern):
                route = p.pattern.regex.pattern
            results.append(prefix + route)
        elif isinstance(p, URLResolver):
            route = getattr(p.pattern, "route", "")
            results.extend(iter_urlpatterns(p, prefix + route))
    return results


def list_templates(root: str) -> List[str]:
    # Busca todas las plantillas .html dentro de /templates
    out = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".html"):
                out.append(os.path.join(dirpath, fn))
    return out


def scan_templates(templates: List[str]) -> Dict[str, Dict[str, List[str]]]:
    report: Dict[str, Dict[str, List[str]]] = {}
    for path in templates:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        hits_bad = []
        for rx in BAD_TEMPLATE_PATTERNS:
            if re.search(rx, text):
                hits_bad.append(rx)
        hits_attrs = []
        for rx in SUSPICIOUS_ATTRS:
            if re.search(rx, text):
                hits_attrs.append(rx)
        if hits_bad or hits_attrs:
            report[path] = {"bad_patterns": hits_bad, "suspicious_attrs": hits_attrs}
    return report


class Command(BaseCommand):
    help = "Genera diagnóstico del proyecto: modelos/fields, URLs y chequeo de plantillas problemáticas."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Imprime salida en JSON")
        parser.add_argument("--output", type=str, default="", help="Ruta de archivo para guardar JSON")

    def handle(self, *args, **opts):
        # 1) Modelos y campos
        models_info = {}
        for model in apps.get_models():
            app_label = model._meta.app_label
            model_name = model.__name__
            fields = []
            for f in model._meta.get_fields():
                try:
                    fname = f.name
                    ftype = f.get_internal_type()
                except Exception:
                    continue
                fields.append({"name": fname, "type": ftype})
            models_info[f"{app_label}.{model_name}"] = fields

        # 2) URLs registradas
        try:
            resolver = get_resolver()
            url_list = iter_urlpatterns(resolver)
        except Exception as e:
            url_list = [f"<<error collecting urls: {e}>>"]

        # 3) Scan de plantillas
        root_templates = []
        # a) carpeta global "templates" (si existe)
        if os.path.isdir("templates"):
            root_templates.append("templates")
        # b) templates dentro de las apps
        for app in apps.get_app_configs():
            tdir = os.path.join(app.path, "templates")
            if os.path.isdir(tdir):
                root_templates.append(tdir)

        templates = []
        for root in root_templates:
            templates.extend(list_templates(root))
        template_report = scan_templates(templates)

        data = {
            "models": models_info,
            "urls": sorted(url_list),
            "templates_scanned": len(templates),
            "templates_with_findings": template_report,
        }

        if opts["json"]:
            output = json.dumps(data, indent=2, ensure_ascii=False)
            if opts["output"]:
                with open(opts["output"], "w", encoding="utf-8") as f:
                    f.write(output)
                self.stdout.write(self.style.SUCCESS(f"✓ Diagnóstico guardado en {opts['output']}"))
            else:
                self.stdout.write(output)
        else:
            self.stdout.write(self.style.SUCCESS("Modelos:"))
            for k in sorted(models_info.keys()):
                self.stdout.write(f" - {k}: {[f['name'] for f in models_info[k]]}")
            self.stdout.write(self.style.SUCCESS("\nURLs:"))
            for u in sorted(url_list):
                self.stdout.write(f" - /{u}")
            self.stdout.write(self.style.SUCCESS(f"\nPlantillas escaneadas: {len(templates)}"))
            if template_report:
                self.stdout.write(self.style.WARNING("Plantillas con hallazgos:"))
                for path, info in template_report.items():
                    self.stdout.write(f" - {path}: {info}")
            else:
                self.stdout.write(self.style.SUCCESS("Sin patrones peligrosos en plantillas."))