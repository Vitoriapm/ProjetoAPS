"""Validação estrutural sem expandir/imprimir .env. Não executa Docker."""
from copy import deepcopy
from pathlib import Path
import json
import yaml


class Override(dict):
    pass


class ComposeLoader(yaml.SafeLoader):
    pass


ComposeLoader.add_constructor("!override", lambda loader, node: Override(loader.construct_mapping(node, deep=True)))


def merge(left, right, key=None):
    if isinstance(right, Override):
        return dict(right)
    if isinstance(left, dict) and isinstance(right, dict):
        result = deepcopy(left)
        for child_key, value in right.items():
            result[child_key] = merge(result[child_key], value, child_key) if child_key in result else deepcopy(value)
        return result
    if isinstance(left, list) and isinstance(right, list):
        if key == "volumes":
            result = {item.split(":")[1]: item for item in left}
            result.update({item.split(":")[1]: item for item in right})
            return list(result.values())
        if key in {"command", "entrypoint"}:
            return deepcopy(right)
        return left + [item for item in right if item not in left]
    return deepcopy(right)


def validate():
    directory = Path(__file__).resolve().parent
    base = yaml.load((directory / "compose.yaml").read_text(encoding="utf-8"), Loader=ComposeLoader)
    overlay = yaml.load((directory / "compose.cluster.yaml").read_text(encoding="utf-8"), Loader=ComposeLoader)
    failover = yaml.load((directory / "compose.failover.yaml").read_text(encoding="utf-8"), Loader=ComposeLoader)
    cluster = merge(base, overlay)
    promoted = merge(cluster, failover)
    for configuration in (base, cluster, promoted):
        services = configuration["services"]
        for name, service in services.items():
            assert set(service.get("depends_on", {})) <= set(services), f"Dependência ausente: {name}"
            for mount in service.get("volumes", []):
                source = mount.split(":")[0]
                if source.startswith("."):
                    assert (directory / source).exists(), f"Mount ausente: {source}"
    assert cluster["services"]["redis-init"]["environment"]["REDIS_NODE_COUNT"] == "6"
    assert cluster["services"]["redis-init"]["environment"]["REDIS_REPLICAS"] == "1"
    assert cluster["services"]["rabbit-init"]["environment"]["RABBIT_EXPECTED_NODES"] == "3"
    assert base["services"]["rabbit-init"]["environment"]["RABBIT_EXPECTED_NODES"] == "1"
    for name in ("api", "api2", "worker", "worker2", "alerts"):
        service = cluster["services"][name]
        assert service["environment"]["RABBIT_QUORUM_SIZE"] == "3"
        assert service["depends_on"]["rabbit-init"]["condition"] == "service_completed_successfully"
        assert service["depends_on"]["redis-init"]["condition"] == "service_completed_successfully"
        assert "@db-replica:5432/" in promoted["services"][name]["environment"]["DATABASE_URL"]
        assert "db" not in promoted["services"][name]["depends_on"]
    assert promoted["services"]["db"]["profiles"] == ["primary-fenced"]
    assert promoted["services"]["db-replica"]["depends_on"] == {}
    for config in (base, cluster):
        gateway_mounts = config["services"]["nginx"]["volumes"]
        assert len(gateway_mounts) == 1
    assert "cluster.conf" in cluster["services"]["nginx"]["volumes"][0]
    policies = json.loads((directory / "rabbit/definitions.json").read_text())["policies"]
    assert any(p["pattern"] == r"^ecopulse.*\.retry$" and p["definition"]["dead-letter-strategy"] == "at-least-once" for p in policies)
    assert all(p["definition"]["overflow"] == "reject-publish" for p in policies)
    for path in directory.rglob("*.sh"):
        raw = path.read_bytes()
        assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), f"Shell exige LF sem BOM: {path}"
    print(f"Validação estrutural OK: base {len(base['services'])} serviços; cluster {len(cluster['services'])}; overlay failover preserva isolamento/dependências.")
    print("Não executa Docker nem comprova replicação, quorum, failover ou conectividade.")


if __name__ == "__main__":
    validate()
