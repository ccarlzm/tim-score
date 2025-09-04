from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.apps import apps
from django.urls import get_resolver, URLResolver, URLPattern


BAD_TEMPLATE_PATTERNS = [
    r"\b3\|\s*\+\s*[\w\.]+\|\|length",   # p.ej.: 3| + block.workouts||length (inválido)
    r"\|\|\s*length",                    # '||length' (filtro mal escrito)
]
SUSPICIOUS_ATTRS = [
    r"\b(?P<var>\w+)\.title\b",          # d.title (rompe si el atributo no existe)
]


def _pattern_to_route(pat) -> str:
    """
    Django 5 usa RoutePattern con atributo 'route'.
    Si no existe (compatibilidad), intentamos 'regex' o devolvemos un str seguro.
    """
    # Django 2.0+ (incluye Django 5): RoutePattern tiene 'route'
    route = getattr(pat, "route", None)
    if route:
        return route

    # Muy antiguo: RegexPattern con 'regex'
    regex = getattr(pat, "regex", None)
    if regex is not None:
        try:
            return str(regex.pattern)
        except Exception:
            return str(regex)

    # Fallback genérico
    return str(pat)


def iter_urlpatterns(resolver, prefix="") -> List[str]:
    results: List[str] = []
    for p in resolver.url_patterns:
        if isinstance(p, URLPattern):
            route = _pattern_to_route(p.pattern)
            results.append(prefix + route)
        elif isinstance(p, URLResolver):
            route = _pattern_to_route(p.pattern)
            results.extend(iter_urlpatterns(p, prefix + route))
    return results


def list_templates(root: str) -> List[str]:
    out: List[str] = []
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

        hits_bad: List[str] = []
        for rx in BAD_TEMPLATE_PATTERNS:
            if re.search(rx, text):
                hits_bad.append(rx)

        hits_attrs: List[str] = []
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
        models_info: Dict[str, List[Dict[str, Any]]] = {}
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
        root_templates: List[str] = []
        if os.path.isdir("templates"):
            root_templates.append("templates")
        for app in apps.get_app_configs():
            tdir = os.path.join(app.path, "templates")
            if os.path.isdir(tdir):
                root_templates.append(tdir)

        templates: List[str] = []
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