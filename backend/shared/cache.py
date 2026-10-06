import json
from urllib.parse import urlparse
from redis.cluster import ClusterNode, RedisCluster
from .db import parse_time, utc_now
from .geo import geohash

CHANNEL = "ecopulse:events"


def environment_region(feature):
    props = feature["properties"]
    if props.get("region_id"):
        return props["region_id"]
    if "center_latitude" in props:
        return geohash(props["center_latitude"], props["center_longitude"])
    geometry = feature["geometry"]
    coordinates = geometry["coordinates"]
    lon, lat = coordinates if geometry["type"] == "Point" else coordinates[0][0]
    return geohash(lat, lon)


def environment_key(feature):
    props = feature["properties"]
    return f"ecopulse:environment:{{{environment_region(feature)}}}:{props['kind']}:{props['id']}"


def environment_version(feature):
    props = feature["properties"]
    # Also rebuild pre-existing observations written before version metadata.
    return props.get("version") or int(parse_time(props["updated_at"]).timestamp() * 1_000_000)


def cached_environment_features(client, authoritative):
    result = []
    for feature in authoritative:
        raw = client.get(environment_key(feature))
        try:
            cached = json.loads(raw) if raw else None
            cached_feature = cached["feature"] if cached else None
            if (cached and cached["version"] == environment_version(feature)
                    and cached_feature["properties"]["id"] == feature["properties"]["id"]
                    and parse_time(cached_feature["properties"]["expires_at"]) > utc_now()):
                result.append(cached_feature)
                continue
        except (TypeError, ValueError, KeyError):
            pass
        # Redis is eventually consistent; PostgreSQL remains authoritative.
        result.append(feature)
    return result


def update_environment_cache(client, event):
    feature = event["payload"]
    expires = parse_time(feature["properties"]["expires_at"])
    remaining = int((expires - utc_now()).total_seconds())
    if remaining <= 0:
        return False
    version = environment_version(feature)
    if feature["properties"].get("version") and version != event["aggregate_version"]:
        raise ValueError("Versão da camada não corresponde ao evento")
    value = {"version": version, "feature": feature}
    script = """
    local old=redis.call('GET',KEYS[1])
    if old then
      local ok,decoded=pcall(cjson.decode,old)
      if ok and type(decoded)=='table' and tonumber(decoded.version)
         and tonumber(decoded.version) >= tonumber(ARGV[1]) then return 0 end
    end
    redis.call('SET',KEYS[1],ARGV[2],'EX',ARGV[3]); return 1
    """
    updated = client.eval(script, 1, environment_key(feature), version,
        json.dumps(value, allow_nan=False), remaining)
    # Re-delivery may publish again; clients reconcile IDs/versions over REST.
    client.publish(CHANNEL, json.dumps(event, allow_nan=False))
    return bool(updated)


def cached_features(client, authoritative):
    result = []
    for feature in authoritative:
        props = feature["properties"]
        region = geohash(props["center_latitude"], props["center_longitude"])
        key = f"ecopulse:incident:{{{region}}}:{props['id']}"
        raw = client.get(key)
        cached = json.loads(raw) if raw else None
        if cached and not cached["expired"] and cached["version"] == props["version"]:
            result.append(cached["feature"])
        else:
            # A miss/late cache must never regress the state already committed.
            result.append(feature)
    return result


def cluster_client(settings):
    nodes = []
    password = None
    for url in settings.redis_urls:
        parsed = urlparse(url.strip())
        nodes.append(ClusterNode(parsed.hostname, parsed.port or 6379))
        password = parsed.password or password
    return RedisCluster(startup_nodes=nodes, password=password, decode_responses=True,
        socket_connect_timeout=3, socket_timeout=3, require_full_coverage=True)


def update_cache(client, event):
    feature = event["payload"]
    props = feature["properties"]
    key = f"ecopulse:incident:{{{event['region_id']}}}:{event['aggregate_id']}"
    ttl = max(1, int((parse_time(props["expires_at"]) - utc_now()).total_seconds()))
    # Atomic version comparison in one Redis Cluster slot. A late old event
    # never overwrites the current value, including expired tombstones.
    ttl = 3600 if event["tipo"] == "incidente.expirado" else ttl
    value = {"version": event["aggregate_version"], "expired": event["tipo"] == "incidente.expirado", "feature": feature}
    script = """
    local old=redis.call('GET',KEYS[1])
    if old and cjson.decode(old).version >= tonumber(ARGV[1]) then return 0 end
    redis.call('SET',KEYS[1],ARGV[2],'EX',ARGV[3]); return 1
    """
    client.eval(script, 1, key, event["aggregate_version"], json.dumps(value), ttl)
    client.publish(CHANNEL, json.dumps(event))


def rebuild_cache(client, store):
    from .domain import make_event
    from .geo import geohash
    for feature in store.active_features():
        props = feature["properties"]
        evt = make_event("incidente.atualizado", props["id"], props["version"],
            geohash(props["center_latitude"], props["center_longitude"]), feature)
        update_cache(client, evt)
    from sqlalchemy import select
    from .db import environment
    with store.engine.connect() as connection:
        observations = list(connection.execute(select(environment.c.data)).scalars())
    for feature in observations:
        if parse_time(feature["properties"]["expires_at"]) > utc_now():
            evt = make_event("camada.atualizada", feature["properties"]["id"],
                environment_version(feature), environment_region(feature), feature)
            update_environment_cache(client, evt)
