from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, text, update
from .db import (relatos, incidentes, links, outbox, processed, iso, parse_time, utc_now)
from .geo import circle_polygon, distance_m, geohash, partition
from .models import Event


def make_event(tipo, aggregate_id, version, region_id, payload, trace_id=None, now=None):
    return {"event_id": str(uuid4()), "schema_version": 1, "tipo": tipo,
            "aggregate_id": aggregate_id, "aggregate_version": version,
            "occurred_at": iso(now or utc_now()), "region_id": region_id,
            "trace_id": trace_id or str(uuid4()), "payload": payload}


def save_event(conn, event, shard_count):
    route = f"relato.{partition(event['region_id'], shard_count)}" if event["tipo"] == "relato.criado" else event["tipo"]
    conn.execute(outbox.insert().values(id=event["event_id"], route=route, event=event, published=False, created_at=event["occurred_at"]))


class ConflictError(Exception):
    pass


def ingest(store, request, installation_id, now=None):
    now = now or utc_now()
    data = request.model_dump(mode="json")
    data["occurred_at"] = iso(request.occurred_at)
    if request.occurred_at > now + timedelta(minutes=5):
        raise ValueError("O horário do relato está no futuro. Confira o relógio do aparelho.")
    if request.occurred_at < now - timedelta(days=30):
        raise ValueError("Relatos devem ter no máximo 30 dias para esta demonstração.")
    with store.transaction(risk_lock=True) as conn:
        existing = conn.execute(select(relatos).where(relatos.c.id == data["id"])).mappings().first()
        if existing:
            original = {key: existing["data"][key] for key in data}
            if original != data or existing["installation_id"] != installation_id:
                raise ConflictError("Este identificador já foi usado com outros dados.")
            return existing["data"], False, None
        row = {**data, "received_at": iso(now), "region_id": geohash(data["latitude"], data["longitude"])}
        conn.execute(relatos.insert().values(id=row["id"], installation_id=installation_id,
            latitude=row["latitude"], longitude=row["longitude"], tipo=row["tipo"], occurred_at=row["occurred_at"], data=row))
        if store.pg:
            conn.execute(text("UPDATE relatos SET geom=ST_SetSRID(ST_MakePoint(:lon,:lat),4326) WHERE id=:id"), {"lon": row["longitude"], "lat": row["latitude"], "id": row["id"]})
        # Installation IDs and FCM tokens never enter public events.
        evt = make_event("relato.criado", row["id"], 1, row["region_id"], {"relato_id": row["id"]}, now=now)
        save_event(conn, evt, store.settings.shard_count)
        return row, True, evt


def process_report(store, event_data, now=None):
    evt = Event.model_validate(event_data)
    if evt.tipo != "relato.criado":
        raise ValueError("Worker de risco aceita apenas relato.criado")
    now = now or utc_now()
    event_id = str(evt.event_id)
    emitted = []
    with store.transaction(risk_lock=True) as conn:
        if conn.execute(select(processed.c.event_id).where(processed.c.consumer == "risk", processed.c.event_id == event_id)).first():
            return []
        row = conn.execute(select(relatos).where(relatos.c.id == str(evt.aggregate_id))).mappings().first()
        if row is None:
            raise ValueError("Relato do evento não existe")
        data = row["data"]
        report_time = parse_time(data["occurred_at"])
        if report_time > now + timedelta(minutes=5):
            raise ValueError("Relato com horário futuro")
        if report_time + timedelta(seconds=store.settings.expiration_s) > now:
            if conn.execute(select(links).where(links.c.relato_id == row["id"])).first():
                conn.execute(processed.insert().values(consumer="risk", event_id=event_id, processed_at=iso(now)))
                return []
            candidate_stmt = select(incidentes).where(incidentes.c.active.is_(True), incidentes.c.tipo == row["tipo"], incidentes.c.expires_at > iso(now))
            if store.pg:
                candidate_stmt = candidate_stmt.where(text("ST_DWithin(ST_SetSRID(ST_MakePoint(longitude,latitude),4326)::geography,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)")).params(lon=row["longitude"], lat=row["latitude"], radius=store.settings.influence_m)
            candidates = list(conn.execute(candidate_stmt).mappings())
            nearby = [x for x in candidates if distance_m(row["latitude"], row["longitude"], x["latitude"], x["longitude"]) <= store.settings.influence_m and x["data"]["properties"]["is_demo"] == data["is_demo"]]
            nearest = min(nearby, key=lambda x: distance_m(row["latitude"], row["longitude"], x["latitude"], x["longitude"])) if nearby else None
            incident_id = nearest["id"] if nearest else str(uuid4())
            lat, lon = (nearest["latitude"], nearest["longitude"]) if nearest else (row["latitude"], row["longitude"])
            recent_stmt = select(relatos).where(relatos.c.tipo == row["tipo"], relatos.c.occurred_at >= iso(now - timedelta(seconds=store.settings.collaborative_window_s)))
            if store.pg:
                recent_stmt = recent_stmt.where(text("ST_DWithin(geom::geography,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)")).params(lat=lat, lon=lon, radius=store.settings.influence_m)
            recent = [x for x in conn.execute(recent_stmt).mappings() if x["data"]["is_demo"] == data["is_demo"] and distance_m(lat, lon, x["latitude"], x["longitude"]) <= store.settings.influence_m]
            distinct = len({x["installation_id"] for x in recent})
            version = nearest["version"] + 1 if nearest else 1
            oldprops = nearest["data"]["properties"] if nearest else {}
            severity = max([data["gravidade"], oldprops.get("gravidade", "baixa")], key={"baixa": 0, "media": 1, "alta": 2}.get)
            updated_at = max(data["occurred_at"], oldprops.get("updated_at", data["occurred_at"]))
            expires_at = iso(parse_time(updated_at) + timedelta(seconds=store.settings.expiration_s))
            props = {"id": incident_id, "tipo": row["tipo"], "gravidade": severity,
                "estado": "colaborativo" if distinct >= 3 else "relatado", "version": version,
                "report_count": oldprops.get("report_count", 0) + 1, "center_latitude": lat,
                "center_longitude": lon, "radius_m": store.settings.influence_m,
                "updated_at": updated_at, "expires_at": expires_at, "is_demo": data["is_demo"]}
            feature = {"type": "Feature", "id": incident_id, "geometry": circle_polygon(lat, lon, store.settings.influence_m), "properties": props}
            values = dict(latitude=lat, longitude=lon, tipo=row["tipo"], expires_at=expires_at, version=version, active=True, data=feature)
            if nearest:
                conn.execute(update(incidentes).where(incidentes.c.id == incident_id).values(**values))
            else:
                conn.execute(incidentes.insert().values(id=incident_id, **values))
            if store.pg:
                import json
                conn.execute(text("UPDATE incidentes SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:geom),4326) WHERE id=:id"), {"geom": json.dumps(feature["geometry"]), "id": incident_id})
            conn.execute(links.insert().values(relato_id=row["id"], incidente_id=incident_id))
            new_evt = make_event("incidente.atualizado" if nearest else "incidente.criado", incident_id, version, geohash(lat, lon), feature, str(evt.trace_id), now)
            save_event(conn, new_evt, store.settings.shard_count)
            emitted.append(new_evt)
        conn.execute(processed.insert().values(consumer="risk", event_id=event_id, processed_at=iso(now)))
    return emitted


def expire_incidents(store, now=None):
    now = now or utc_now()
    emitted = []
    with store.transaction(risk_lock=True) as conn:
        rows = conn.execute(select(incidentes).where(incidentes.c.active.is_(True), incidentes.c.expires_at <= iso(now))).mappings().all()
        for row in rows:
            feature = dict(row["data"])
            feature["properties"] = {**feature["properties"], "version": row["version"] + 1}
            conn.execute(update(incidentes).where(incidentes.c.id == row["id"]).values(active=False, version=row["version"] + 1, data=feature))
            evt = make_event("incidente.expirado", row["id"], row["version"] + 1, geohash(row["latitude"], row["longitude"]), feature, now=now)
            save_event(conn, evt, store.settings.shard_count)
            emitted.append(evt)
    return emitted
