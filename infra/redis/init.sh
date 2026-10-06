#!/bin/sh
set -eu

node_count="${REDIS_NODE_COUNT:-3}"
replicas="${REDIS_REPLICAS:-0}"
nodes=""
for number in $(seq 1 "$node_count"); do
    nodes="$nodes redis$number:6379"
done

all_ready() {
    for number in $(seq 1 "$node_count"); do
        info=$(redis-cli --no-auth-warning -h "redis$number" cluster info 2>/dev/null | tr -d '\r') || return 1
        echo "$info" | grep -q '^cluster_state:ok$' || return 1
        echo "$info" | grep -q '^cluster_slots_assigned:16384$' || return 1
        echo "$info" | grep -q '^cluster_slots_ok:16384$' || return 1
        echo "$info" | grep -q '^cluster_slots_fail:0$' || return 1
        echo "$info" | grep -q '^cluster_slots_pfail:0$' || return 1
        echo "$info" | grep -q "^cluster_known_nodes:$node_count$" || return 1
        members=$(redis-cli --no-auth-warning -h "redis$number" cluster nodes 2>/dev/null | tr -d '\r') || return 1
        echo "$members" | awk -v expected="$node_count" '
            NF { count++ }
            $2 ~ /:0@|@0(,|$)/ { bad=1 }
            $3 ~ /(^|,)(fail|fail[?]|handshake|noaddr)(,|$)/ { bad=1 }
            NF && $8 != "connected" { bad=1 }
            END { exit (bad || count != expected) ? 1 : 0 }
        ' || return 1
    done
}

pristine=true
for number in $(seq 1 "$node_count"); do
    info=$(redis-cli --no-auth-warning -h "redis$number" cluster info | tr -d '\r')
    echo "$info" | grep -q '^cluster_slots_assigned:0$' || pristine=false
    echo "$info" | grep -q '^cluster_known_nodes:1$' || pristine=false
done

if [ "$pristine" = true ]; then
    echo "Criando Redis Cluster: $node_count nós, $replicas réplica(s) por primário."
    # Splitting this generated host list is intentional; it contains no user data.
    # shellcheck disable=SC2086
    redis-cli --no-auth-warning --cluster create $nodes --cluster-replicas "$replicas" --cluster-yes
else
    echo 'Reconciliando endereços atuais dos peers; dados e slots existentes preservados.'
    # nodes.conf persists old IPs. Docker may assign different addresses after
    # a restart: a peer can become noaddr/port 0 even while cluster_state is ok.
    # Reintroduce the same node IDs through current DNS addresses. MEET does
    # not erase values, reset nodes, assign slots or change replication roles.
    for target in $(seq 1 "$node_count"); do
        address=$(getent hosts "redis$target" | awk '/^[0-9]+\./ { print $1; exit }')
        if [ -z "$address" ]; then
            echo "Não foi possível resolver o endereço IPv4 de redis$target." >&2
            exit 1
        fi
        for source in $(seq 1 "$node_count"); do
            if [ "$source" != "$target" ]; then
                redis-cli --no-auth-warning -h "redis$source" cluster meet "$address" 6379 >/dev/null
            fi
        done
    done
fi

for attempt in $(seq 1 90); do
    if all_ready; then
        echo 'Redis Cluster pronto com 16384 slots.'
        exit 0
    fi
    sleep 1
done
echo 'Cluster não convergiu. Inspecione os nós/volumes; nenhum dado foi removido.' >&2
exit 1
