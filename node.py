import grpc, time, threading, hashlib
from concurrent import futures
import kv_pb2, kv_pb2_grpc
from config import NODES

NODE_ID = int(input("Node ID (0/1/2): "))
ADDRESS = NODES[NODE_ID]

data_store = {}
alive_nodes = set(NODES.keys())
lock = threading.Lock()

# ---------- HASH ----------
def hash_key(key: str) -> int:
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % len(NODES)

def get_replicas(nid: int):
    return [(nid + 1) % len(NODES), (nid + 2) % len(NODES)]

# ---------- SERVICE ----------
class KVNode(kv_pb2_grpc.KVServiceServicer):

    def Put(self, request, context):
        owner = hash_key(request.key)
        if owner != NODE_ID:
            return forward(owner, "Put", request)

        success_count = 1
        with lock:
            data_store[request.key] = request.value

        for replica in get_replicas(NODE_ID):
            if replica in alive_nodes:
                try:
                    stub(replica).ReplicaPut(request, timeout=2)
                    success_count += 1
                except:
                    alive_nodes.discard(replica)

        return kv_pb2.Reply(
            success=(success_count >= 2),
            message="OK" if success_count >= 2 else "Replica failed"
        )

    def Get(self, request, context):
        owner = hash_key(request.key)
        if owner != NODE_ID:
            return forward(owner, "Get", request)

        with lock:
            if request.key in data_store:
                return kv_pb2.ValueReply(found=True, value=data_store[request.key])

        for replica in get_replicas(NODE_ID):
            if replica in alive_nodes:
                try:
                    res = stub(replica).Get(request, timeout=2)
                    if res.found:
                        return res
                except:
                    pass

        return kv_pb2.ValueReply(found=False, value="")


    def Delete(self, request, context):
        owner = hash_key(request.key)
        if owner != NODE_ID:
            return forward(owner, "Delete", request)

        with lock:
            data_store.pop(request.key, None)

        for replica in get_replicas(NODE_ID):
            if replica in alive_nodes:
                try:
                    stub(replica).ReplicaDelete(request, timeout=2)
                except:
                    alive_nodes.discard(replica)

        return kv_pb2.Reply(success=True, message="DELETED")

    def ReplicaPut(self, request, context):
        with lock:
            data_store[request.key] = request.value
        return kv_pb2.Reply(success=True, message="REPLICA_OK")

    def ReplicaDelete(self, request, context):
        with lock:
            data_store.pop(request.key, None)
        return kv_pb2.Reply(success=True, message="REPLICA_DEL")

    def Ping(self, request, context):
        return kv_pb2.Reply(success=True, message="PONG")

    def Recover(self, request, context):
        partition_id = request.partition_id
        snapshot = {}
        with lock:
            for k, v in data_store.items():
                if hash_key(k) == partition_id:
                    snapshot[k] = v
        return kv_pb2.DataDump(data=snapshot)

# ---------- HELPERS ----------
def stub(nid):
    ch = grpc.insecure_channel(NODES[nid])
    return kv_pb2_grpc.KVServiceStub(ch)

def forward(nid, method, req):
    try:
        return getattr(stub(nid), method)(req, timeout=2)
    except Exception as e:
        alive_nodes.discard(nid)
        return kv_pb2.Reply(success=False, message=f"FAIL ({e})")

# ---------- HEARTBEAT THREAD ----------
def heartbeat():
    while True:
        time.sleep(5)
        for nid in NODES:
            if nid == NODE_ID:
                continue
            try:
                stub(nid).Ping(kv_pb2.Empty(), timeout=2)
                alive_nodes.add(nid)
            except:
                alive_nodes.discard(nid)

# ---------- RECOVERY ----------
def recover():
    time.sleep(1)
    for nid in alive_nodes:
        if nid != NODE_ID:
            try:
                dump = stub(nid).Recover(
                    kv_pb2.PartitionRequest(partition_id=NODE_ID),
                    timeout=2
                )
                with lock:
                    data_store.update(dump.data)
                print("[*] Recovery done")
                break
            except:
                pass

# ---------- START ----------
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
kv_pb2_grpc.add_KVServiceServicer_to_server(KVNode(), server)
server.add_insecure_port(ADDRESS)

threading.Thread(target=heartbeat, daemon=True).start()
recover()

print(f"[Node {NODE_ID}] running at {ADDRESS}")
server.start()
server.wait_for_termination()
