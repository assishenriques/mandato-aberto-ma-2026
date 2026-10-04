import datetime
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request


CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
TERMS = range(52, 58)
HEADERS = {"Accept": "application/json", "User-Agent": "MandatoAbertoMA/1.0 (dados públicos)"}


def get_json(url):
    error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error = exc
            # A malformed query or missing record will not improve by retrying.
            if exc.code != 429 and exc.code < 500:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            time.sleep(int(retry_after) if retry_after.isdigit() else 2 + attempt)
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise error


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c)).upper()
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()


STOP = {"DA", "DE", "DO", "DAS", "DOS", "E", "DR", "DRA", "PROF", "PROFESSOR", "PROFESSORA", "JR", "JUNIOR", "FILHO", "NETO"}


def tokens(value):
    return {part for part in normalize(value).split() if part not in STOP and len(part) > 1}


def name_match(candidate, member_names):
    aliases = {normalize(candidate.get("name")), normalize(candidate.get("civil"))}
    aliases.discard("")
    member_names = [str(n) for n in member_names if n]
    exact = [name for name in member_names if normalize(name) in aliases]
    unique = {normalize(x): x for x in exact}
    return next(iter(unique.values())) if len(unique) == 1 else None


def camara_members(term):
    people = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"idLegislatura": term, "itens": 100, "pagina": page, "ordem": "ASC", "ordenarPor": "nome"})
        payload = get_json(f"{CAMARA}/deputados?{query}")
        people.extend(payload.get("dados", []))
        links = payload.get("links", [])
        if not any(link.get("rel") == "next" for link in links):
            break
        page += 1
        if page > 20:
            break
    return people


def senate_nodes(value):
    if isinstance(value, dict):
        if any(k.lower() in {"codigoparlamentar", "codigo parlamentar"} for k in value) and any(k.lower() in {"nomeparlamentar", "nome parlamentar"} for k in value):
            yield value
        for child in value.values():
            yield from senate_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from senate_nodes(child)


def get_ci(item, *names):
    wanted = {n.lower().replace("_", "") for n in names}
    for key, value in item.items():
        if key.lower().replace("_", "") in wanted and value not in (None, ""):
            return value
    return ""


def unique_candidate_matches(candidates, people, name_getter):
    result = {}
    for person in people:
        names = name_getter(person)
        for candidate in candidates:
            matched = name_match(candidate, names)
            if matched:
                result.setdefault(candidate["id"], {})[str(get_ci(person, "id", "uri", "codigoParlamentar", "idParlamentar") or matched)] = (person, matched)
    return result


def camara_propositions(deputy_id):
    records = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"idDeputadoAutor": deputy_id, "itens": 100, "pagina": page, "ordem": "DESC", "ordenarPor": "id"})
        payload = get_json(f"{CAMARA}/proposicoes?{query}")
        records.extend(payload.get("dados", []))
        if not any(link.get("rel") == "next" for link in payload.get("links", [])):
            break
        page += 1
        if page > 100:
            break
    return records


def senate_matter_nodes(value):
    nodes = []
    def walk(item):
        if isinstance(item, dict):
            title = get_ci(item, "ementaMateria", "ementa", "descricaoMateria")
            number = get_ci(item, "numeroMateria", "numero", "numeroAutuacao")
            year = get_ci(item, "anoMateria", "ano")
            code = get_ci(item, "codigoMateria", "codigo", "idMateria")
            if title and (number or code):
                nodes.append(item)
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)
    walk(value)
    return nodes


def main():
    with open("data/initial-candidates.json", encoding="utf-8") as stream:
        candidates = json.load(stream)
    matches = {}
    warnings = []

    federal_people = []
    for term in TERMS:
        try:
            for person in camara_members(term):
                person["_term"] = term
                federal_people.append(person)
        except Exception as exc:
            warnings.append(f"Câmara, legislatura {term}: {type(exc).__name__}")
    for person in federal_people:
        official_name = person.get("nome", "")
        if not official_name:
            continue
        hits = [(candidate, name_match(candidate, [official_name])) for candidate in candidates]
        hits = [(candidate, matched) for candidate, matched in hits if matched]
        if len(hits) == 1:
            candidate, matched = hits[0]
            deputy_id = str(person.get("id", ""))
            if deputy_id:
                matches.setdefault(candidate["id"], {}).setdefault("camara", {})[deputy_id] = {
                    "id": deputy_id, "name": matched, "term": person.get("_term"), "uf": person.get("siglaUf", "")
                }

    senate_people = []
    for term in TERMS:
        try:
            payload = get_json(f"{SENADO}/senador/lista/legislatura/{term}.json")
            for person in senate_nodes(payload):
                person["_term"] = term
                senate_people.append(person)
        except Exception as exc:
            warnings.append(f"Senado, legislatura {term}: {type(exc).__name__}")
    for person in senate_people:
        name = get_ci(person, "NomeParlamentar", "NomeCompletoParlamentar")
        code = str(get_ci(person, "CodigoParlamentar"))
        if not name or not code:
            continue
        member_names = [name, get_ci(person, "NomeCompletoParlamentar")]
        hits = [(candidate, name_match(candidate, member_names)) for candidate in candidates]
        hits = [(candidate, matched) for candidate, matched in hits if matched]
        if len(hits) == 1:
            candidate, matched = hits[0]
            matches.setdefault(candidate["id"], {}).setdefault("senado", {})[code] = {
                "id": code, "name": matched, "term": person.get("_term"), "uf": get_ci(person, "UfParlamentar")
            }

    output = []
    seen = set()
    for candidate in candidates:
        candidate_id = candidate["id"]
        member_groups = matches.get(candidate_id, {})
        for deputy_id, member in member_groups.get("camara", {}).items():
            try:
                for item in camara_propositions(deputy_id):
                    prop_id = str(item.get("id", ""))
                    key = (candidate_id, "Câmara", prop_id)
                    if not prop_id or key in seen:
                        continue
                    seen.add(key)
                    status = (item.get("statusProposicao") or {}).get("descricaoSituacao", "")
                    output.append({
                        "candidateId": candidate_id, "institution": "Câmara dos Deputados", "memberName": member["name"],
                        "role": "Autor/coautor registrado pela Câmara", "kind": item.get("siglaTipo", "Proposição"),
                        "number": item.get("numero", ""), "year": item.get("ano", ""),
                        "title": item.get("ementa", "Ementa não informada"), "date": item.get("dataApresentacao", ""),
                        "status": status, "url": f"https://www.camara.leg.br/propostas-legislativas/{prop_id}",
                        "source": "Dados Abertos da Câmara dos Deputados"
                    })
            except Exception as exc:
                warnings.append(f"Câmara, parlamentar {deputy_id}: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
        for senator_id, member in member_groups.get("senado", {}).items():
            try:
                payload = get_json(f"{SENADO}/senador/{senator_id}/autorias.json")
                for item in senate_matter_nodes(payload):
                    number = get_ci(item, "NumeroMateria", "Numero", "NumeroAutuacao")
                    year = get_ci(item, "AnoMateria", "Ano")
                    code = str(get_ci(item, "CodigoMateria", "Codigo", "IdMateria"))
                    identity = code or f"{get_ci(item,'SiglaMateria')}:{number}:{year}"
                    key = (candidate_id, "Senado", identity)
                    if not identity or key in seen:
                        continue
                    seen.add(key)
                    title = get_ci(item, "EmentaMateria", "Ementa", "DescricaoMateria")
                    label = get_ci(item, "SiglaMateria", "SiglaSubtipoMateria", "DescricaoSubtipoMateria")
                    outurl = get_ci(item, "UrlMateria", "UrlMateriaPortal") or (f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{code}" if code else "https://www12.senado.leg.br/dados-abertos/")
                    output.append({
                        "candidateId": candidate_id, "institution": "Senado Federal", "memberName": member["name"],
                        "role": "Autor/coautor conforme catálogo do Senado", "kind": str(label or "Matéria"),
                        "number": str(number), "year": str(year), "title": str(title or "Ementa não informada"),
                        "date": str(get_ci(item, "DataApresentacao", "DataAutuacao")),
                        "status": str(get_ci(item, "DescricaoSituacao", "SituacaoMateria")), "url": str(outurl),
                        "source": "Dados Abertos do Senado Federal"
                    })
            except Exception as exc:
                warnings.append(f"Senado, parlamentar {senator_id}: {type(exc).__name__}")

    output.sort(key=lambda row: (str(row["candidateId"]), str(row.get("date", "") or ""), str(row.get("year", "") or "")), reverse=True)
    records_by_candidate = {}
    for row in output:
        records_by_candidate.setdefault(row["candidateId"], 0)
        records_by_candidate[row["candidateId"]] += 1
    candidate_statuses = []
    for candidate in candidates:
        member_groups = matches.get(candidate["id"], {})
        houses = [house for house, members in member_groups.items() if members]
        candidate_statuses.append({
            "candidateId": candidate["id"],
            "candidateName": candidate.get("name", ""),
            "cargo": candidate.get("cargo", ""),
            "status": "records_found" if records_by_candidate.get(candidate["id"]) else ("member_matched_no_records" if houses else "no_federal_match"),
            "records": records_by_candidate.get(candidate["id"], 0),
            "matchedHouses": houses,
        })
    payload = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "candidateCount": len(candidates), "matchedCandidateCount": len({row["candidateId"] for row in output}),
        "recordCount": len(output), "scope": "Câmara dos Deputados e Senado Federal; mandatos 52ª a 57ª legislaturas; nomes públicos completos normalizados e correspondência única.",
        "coverageNote": "Não localizado nessas duas Casas não significa ausência de produção em assembleias estaduais ou câmaras municipais. A produção da ALEMA ainda não está integrada.",
        "sources": [
            {"name": "Dados Abertos da Câmara dos Deputados", "url": "https://dadosabertos.camara.leg.br/swagger/api.html"},
            {"name": "Dados Abertos do Senado Federal", "url": "https://www12.senado.leg.br/dados-abertos/"},
        ],
        "warnings": warnings, "candidateStatuses": candidate_statuses, "records": output
    }
    os.makedirs("data", exist_ok=True)
    with open("data/producao-legislativa.json", "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    print(f"Candidaturas: {len(candidates)}; com proposições federais: {payload['matchedCandidateCount']}; registros: {len(output)}; alertas: {len(warnings)}")
    for institution in sorted({row["institution"] for row in output}):
        print(f"{institution}: {sum(1 for row in output if row['institution'] == institution)} registros")
    for warning in warnings:
        print("AVISO", warning)


if __name__ == "__main__":
    main()

