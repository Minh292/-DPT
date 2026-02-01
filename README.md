# Distributed Key-Value Store

## Tổng quan
Hệ thống lưu trữ dạng key–value theo mô hình phân tán, triển khai bằng Python và gRPC.  
- Có ít nhất 3 node tạo thành cụm lưu trữ.  
- Mỗi node lưu một phần dữ liệu và sao lưu sang 2 node khác (replication factor = 3).  
- Client có thể kết nối tới bất kỳ node nào để thực hiện các thao tác `PUT, GET, DELETE`.  
- Các node giao tiếp qua TCP với gRPC, dữ liệu tuần tự hóa bằng Protocol Buffers (Protobuf).  
- Hệ thống hỗ trợ phát hiện node hỏng (heartbeat) và khôi phục dữ liệu (recover snapshot).

---

## Cấu trúc thư mục
ƯDPT/

├── kv.proto           # Định nghĩa service và message

├── kv_pb2.py          # Sinh ra từ protoc

├── kv_pb2_grpc.py     # Sinh ra từ protoc

├── node.py            # Triển khai node

├── client.py          # Triển khai client CLI

├── config.py          # Cấu hình địa chỉ các node

├── images             # Ảnh

└── README.md          # Tài liệu hướng dẫn

---

## Cách xây dựng

1. Cài đặt Python >= 3.8 và pip.  
2. Cài đặt thư viện gRPC:
   ```bash
   pip install grpcio grpcio-tools
   ```
3. Biên dịch file proto
``` 
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. kv.proto 
```

## Cách chạy hệ thôngs
1. Khởi động các node  
+ Mở 3 terminal khác nhau, chạy:
```
bash
python node.py
```
+ Sau đó nhập Node ID (0, 1, hoặc 2).
 - Mỗi node sẽ chạy ở địa chỉ được cấu hình trong config.py:
```
Node 0: localhost:5000
Node 1: localhost:5001
Node 2: localhost:5002
```
2. Khởi động client  
 - Mở một terminal khác, chạy:
```
python client.py
```
 - Client sẽ hiển thị prompt:
```
Code
Commands: put <k> <v> | get <k> | delete <k>
```

+ Ví dụ sử dụng
```
>> put a 123
[Node 0] success=True, message=OK

>> get a
[Node 0] FOUND value=123

>> delete a
[Node 0] success=True, message=DELETED
```

3. Kiểm thử chịu lỗi

Trường hợp 1: Owner node bị tắt
 - Ghi dữ liệu vào hệ thống
 - Thực hiện: put b nguyet
 - Dữ liệu được lưu tại primary node (ví dụ node 1) và sao lưu sang 2 node replica (node 0 và node 2).
 - Tắt primary node
 - Dừng node 1 bằng Ctrl + C.
 - Đọc dữ liệu khi primary đã chết
 - Thực hiện: get b từ client.
 - Client kết nối tới một node còn sống (node 0 hoặc node 2).
 - Các node này sẽ forward yêu cầu về owner (node 1). Vì node 1 đã chết, yêu cầu thất bại.
→ Kết luận: Khi owner node bị hỏng, dữ liệu tạm thời không khả dụng cho đến khi node được khởi động lại và khôi phục.

Trường hợp 2: Một replica node bị tắt
 - Ghi dữ liệu
 - Thực hiện: put a 123.
 - Tắt một node replica (ví dụ node 2).
 - Node 2 ngừng hoạt động.
 - Đọc dữ liệu
 - Thực hiện: get a.
 - Primary node hoặc replica còn lại vẫn forward về owner (còn sống), nên dữ liệu vẫn đọc được.
→ Kết luận: Hệ thống vẫn hoạt động khi mất một replica.

Trường hợp 3: Tắt nhiều node
 - Ghi dữ liệu
 - Thực hiện: put c 456.
 - Tắt tất cả các node trong cluster.
 - Node 0, node 1 và node 2 đều dừng.
 - Đọc dữ liệu
 - Thực hiện: get c.
 - Client không thể kết nối tới bất kỳ node nào.
→ Kết luận: Khi toàn bộ cluster ngừng hoạt động, dữ liệu không khả dụng.

Trường hợp 4: Khôi phục node
 - Tắt một node (ví dụ node 1).
 - Node 1 mất dữ liệu cục bộ.
 - Khởi động lại node 1.
 - Chạy lại: python node.py, nhập Node ID = 1.
 - Node 1 gửi RPC Recover đến các node còn sống.
 - Nhận snapshot dữ liệu và đồng bộ lại local store.
 - Đọc dữ liệu sau khi khôi phục
 - Thực hiện: get b.
 - Node 1 đã có lại dữ liệu và trả kết quả thành công.
→ Kết luận: Node có thể khôi phục trạng thái dữ liệu sau khi khởi động lại.

## Ghi chú
Giao thức: TCP với gRPC.
Tuần tự hóa: Protocol Buffers.
Replication: mỗi key có ít nhất 3 bản sao (owner + 2 replica).
Heartbeat: mỗi node gửi Ping định kỳ để phát hiện node chết.
Recover: node khởi động lại yêu cầu snapshot từ node khác để khôi phục dữ liệu phân vùng.

## Hạn chế
+ Chưa sử dụng consistent hashing
+ Chưa xử lý network partition phức tạp
+ Chưa có consensus (Raft/Paxos)
+ Dữ liệu chỉ lưu trong RAM

## Hướng cải tiến
+ Áp dụng consistent hashing
+ Tăng số replica
+ Lưu dữ liệu xuống disk
+ Thêm cơ chế đồng thuận Raft
+ Hỗ trợ scale động số node


