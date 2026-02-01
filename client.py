import grpc, hashlib
import kv_pb2, kv_pb2_grpc
from config import NODES

def hash_key(key):
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % len(NODES)

channels = {nid: grpc.insecure_channel(addr) for nid, addr in NODES.items()}
stubs = {nid: kv_pb2_grpc.KVServiceStub(channels[nid]) for nid in NODES}

def send(method, req, key=None):
    if key:
        owner = hash_key(key)
        targets = [owner, (owner+1)%len(NODES), (owner+2)%len(NODES)]
    else:
        targets = list(NODES.keys())

    for nid in targets:
        try:
            res = getattr(stubs[nid], method)(req, timeout=2)
            if hasattr(res, "success"):
                print(f"[Node {nid}] success={res.success}, message={res.message}")
            elif hasattr(res, "found"):
                print(f"[Node {nid}] {'FOUND' if res.found else 'NOT FOUND'} value={res.value}")
            else:
                print(f"[Node {nid}] message={res.message}")
            return
        except Exception as e:
            print(f"[!] Node {nid} down ({e})")
    print("[X] All replicas failed")

print("Commands: put <k> <v> | get <k> | delete <k>")

while True:
    cmd = input(">> ").split()
    if not cmd:
        continue

    if cmd[0] == "put" and len(cmd) == 3:
        send("Put", kv_pb2.PutRequest(key=cmd[1], value=cmd[2]), key=cmd[1])
    elif cmd[0] == "get" and len(cmd) == 2:
        send("Get", kv_pb2.KeyRequest(key=cmd[1]), key=cmd[1])
    elif cmd[0] == "delete" and len(cmd) == 2:
        send("Delete", kv_pb2.KeyRequest(key=cmd[1]), key=cmd[1])
    else:
        print("[!] Invalid command")
