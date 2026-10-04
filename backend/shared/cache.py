import json
from urllib.parse import urlparse
from redis.cluster import ClusterNode, RedisCluster
from .db import parse_time, utc_now
from .geo import geohash

CHANNEL = "ecopulse:events"


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
