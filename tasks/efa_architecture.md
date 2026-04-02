# EFA Backend Architecture Diagrams

## 1. Layered Architecture

```
+============================================================================+
|                        COLLECTIVE ALGORITHMS                               |
|                  (AllReduce, AllGather, ReduceScatter, ...)                 |
+============================================================================+
                                    |
                                    v
+============================================================================+
|                           CTRAN MAPPER                                     |
|  CtranMapper                                                               |
|  +----------------------------------------------------------------------+  |
|  |  isendCtrl / irecvCtrl    |  iput / iget       |  notify / waitNotify|  |
|  |  isendCtrlMsg / irecvCtrlMsg | iputBatch       |  checkNotify        |  |
|  |  exportMem / importMem    |  atomicSet / iflush |  progress          |  |
|  +----------------------------------------------------------------------+  |
|  |                     BACKEND ROUTER                                   |  |
|  |  queryPeerBackend(rank) --> IB | NVL | SOCKET | TCPDM | EFA         |  |
|  +----------------------------------------------------------------------+  |
|  |  RegCache          |  CtranCtrlManager      |  enableBackends_[]    |  |
|  +----------------------------------------------------------------------+  |
+============================================================================+
         |              |             |              |              |
         v              v             v              v              v
+----------+  +----------+  +-----------+  +-----------+  +================+
| CtranIb  |  | CtranNvl |  |CtranSocket|  | CtranTcpDm|  ||  CtranEfa    ||
| (IB/RoCE)|  | (NVLink) |  | (TCP)     |  | (TCP DMA) |  ||  (NEW)      ||
+----------+  +----------+  +-----------+  +-----------+  +================+
                                                                   |
                              +====================================+
                              |
                              v
+============================================================================+
|                         CTRAN EFA BACKEND                                  |
|                                                                            |
|  +----------------------------------+  +-------------------------------+   |
|  |        CtranEfa (Public API)     |  |    CtranEfaSingleton          |   |
|  |                                  |  |    (folly::Singleton)         |   |
|  |  iput / iget                     |  |                               |   |
|  |  isendCtrlMsg / irecvCtrlMsg     |  |  fi_fabric / fi_domain        |   |
|  |  regMem / deregMem               |  |  Multi-NIC discovery          |   |
|  |  exportMem / importMem           |  |  GPU-NIC affinity map         |   |
|  |  notify / checkNotify / waitNotify|  |  RDMA cap detection          |   |
|  |  preConnect / progress           |  |  GDR detection                |   |
|  +----------------------------------+  +-------------------------------+   |
|                    |                                                       |
|  +----------------------------------+  +-------------------------------+   |
|  |     Per-Rail State               |  |    CtranEfaRequest            |   |
|  |                                  |  |                               |   |
|  |  Rail 0: ep, cq, av, mr[]       |  |  state: INCOMPLETE/COMPLETE   |   |
|  |  Rail 1: ep, cq, av, mr[]       |  |  refCount (multi-rail stripe) |   |
|  |  ...                             |  |  notify flag                  |   |
|  |  Rail N: ep, cq, av, mr[]       |  +-------------------------------+   |
|  +----------------------------------+                                      |
|                    |                                                       |
|  +----------------------------------------------------------------------+  |
|  |                    STRIPE SCHEDULER                                  |  |
|  |  Small msg (<threshold) --> single rail (round-robin)                |  |
|  |  Large msg (>threshold) --> stripe across N rails (128B aligned)     |  |
|  +----------------------------------------------------------------------+  |
+============================================================================+
                              |
                              v
+============================================================================+
|                       LIBFABRIC (OFI) API                                  |
|                                                                            |
|  Endpoints        Memory Reg       Data Transfer      Completions          |
|  +-----------+    +-----------+    +-------------+    +-------------+      |
|  |FI_EP_RDM  |    |fi_mr_reg  |    |fi_write     |    |fi_cq_read   |      |
|  |fi_endpoint|    |fi_mr_reg  |    |fi_writedata |    |(manual poll)|      |
|  |fi_ep_bind |    |  attr     |    |fi_read      |    |FI_CQ_FORMAT |      |
|  +-----------+    |FI_HMEM    |    |fi_send/recv |    |  _DATA      |      |
|                   |  _CUDA    |    +-------------+    +-------------+      |
|  Address Vec      +-----------+                                            |
|  +-----------+                     Immediate Data                          |
|  |FI_AV_TABLE|                     +-------------+                         |
|  |fi_av_insert|                    |fi_writedata |                         |
|  +-----------+                     |32-bit imm:  |                         |
|                                    | comm_id +   |                         |
|                                    | seq_num     |                         |
|                                    +-------------+                         |
+============================================================================+
                              |
                              v
+============================================================================+
|                     EFA PROVIDER (libfabric)                               |
|                                                                            |
|  SRD Protocol    |  RDMA Ops      |  GPU Direct    |  Progress             |
|  - Reliable      |  - Read  (all) |  - FI_HMEM     |  - FI_PROGRESS_MANUAL |
|  - Out-of-order  |  - Write (p5+) |  - CUDA DMA    |  - Explicit fi_cq_read|
|  - Connectionless|  - No atomics  |  - GDRCopy     |  - No AUTO support    |
|  - OS-bypass     |                |  - P2P required |                       |
+============================================================================+
                              |
                              v
+============================================================================+
|                        EFA HARDWARE (NIC)                                  |
|                                                                            |
|  +------------------+  +------------------+  +------------------+          |
|  | EFA Device 0     |  | EFA Device 1     |  | EFA Device N     |          |
|  | (NIC on PCIe)    |  | (NIC on PCIe)    |  | (NIC on PCIe)    |          |
|  |                  |  |                  |  |                  |          |
|  | SRD QP           |  | SRD QP           |  | SRD QP           |          |
|  | UD QP (fallback) |  | UD QP (fallback) |  | UD QP (fallback) |          |
|  +------------------+  +------------------+  +------------------+          |
|         |                      |                      |                    |
|         +----------------------+----------------------+                    |
|                                |                                           |
|                    AWS Nitro Network (SRD wire protocol)                    |
+============================================================================+
```

## 2. Sequence Diagram: RDMA Put with Notification

```
Rank 0 (Sender)                                              Rank 1 (Receiver)
   |                                                              |
   |  =================== BOOTSTRAP (one-time) ================  |
   |                                                              |
   |  [CtranEfaSingleton::getInstance()]                          |  [CtranEfaSingleton::getInstance()]
   |  fi_getinfo() -> discover EFA devices                        |  fi_getinfo() -> discover EFA devices
   |  fi_fabric() / fi_domain()                                   |  fi_fabric() / fi_domain()
   |  Detect RDMA caps, GDR support                               |  Detect RDMA caps, GDR support
   |                                                              |
   |  [CtranEfa constructor - per rail]                           |  [CtranEfa constructor - per rail]
   |  fi_endpoint(FI_EP_RDM)                                      |  fi_endpoint(FI_EP_RDM)
   |  fi_cq_open(FI_CQ_FORMAT_DATA)                               |  fi_cq_open(FI_CQ_FORMAT_DATA)
   |  fi_av_open(FI_AV_TABLE)                                     |  fi_av_open(FI_AV_TABLE)
   |  fi_ep_bind(cq, av)                                          |  fi_ep_bind(cq, av)
   |  fi_enable(ep)                                               |  fi_enable(ep)
   |                                                              |
   |  [preConnect - address exchange via bootstrap allgather]      |
   |  fi_getname(ep) --> local_addr                               |  fi_getname(ep) --> local_addr
   |                                                              |
   |  <------------- allgather(local_addrs) ---------------------->
   |                                                              |
   |  fi_av_insert(peer_addrs)                                    |  fi_av_insert(peer_addrs)
   |                                                              |
   |  =================== MEMORY REGISTRATION ==================  |
   |                                                              |
   |  [mapper->regMem(sendbuf)]                                   |  [mapper->regMem(recvbuf)]
   |  ctranEfa->regMem(buf, len, cudaDev)                         |  ctranEfa->regMem(buf, len, cudaDev)
   |    per rail:                                                 |    per rail:
   |    fi_mr_regattr(                                            |    fi_mr_regattr(
   |      iface=FI_HMEM_CUDA,                                    |      iface=FI_HMEM_CUDA,
   |      access=FI_SEND|FI_RECV|                                 |      access=FI_SEND|FI_RECV|
   |             FI_READ|FI_WRITE|                                |             FI_READ|FI_WRITE|
   |             FI_REMOTE_READ|                                  |             FI_REMOTE_READ|
   |             FI_REMOTE_WRITE)                                 |             FI_REMOTE_WRITE)
   |    --> mr_handle, rkey                                       |    --> mr_handle, rkey
   |                                                              |
   |  =============== CONTROL EXCHANGE (handshake) ==============  |
   |                                                              |
   |  [mapper->isendCtrl(sendbuf, hdl, peer=1)]                   |  [mapper->irecvCtrl(recvbuf, &key, peer=0)]
   |    exportMem(buf, regElem) --> ControlMsg{                   |    irecvCtrlMsg(payload, size, peer=0, req)
   |      type: EFA_EXPORT_MEM,                                   |      fi_recv(ep, payload, size)
   |      EfaDesc: {addr, rkeys[], nKeys}                         |        |
   |    }                                                         |        |
   |    isendCtrlMsg(msg, peer=1)                                 |        |
   |      fi_send(ep, &msg, sizeof(msg), peer_fi_addr)            |        |
   |        |                                                     |        |
   |        +---------------------------------------------------->+        |
   |                                                              |    importMem(msg) --> remoteAccessKey{
   |                                                              |      addr, rkeys[]
   |                                                              |    }
   |                                                              |
   |  (Receiver also sends its buf info back)                     |
   |        <----------------------------------------------------+|
   |  importMem(msg) --> remoteAccessKey                          |
   |                                                              |
   |  ================= DATA TRANSFER (iput) ====================  |
   |                                                              |
   |  [mapper->iput(sbuf, dbuf, len, peer=1, notify=true)]        |
   |    ctranEfa->iput(sbuf, dbuf, len, ...)                      |
   |                                                              |
   |    [Stripe Scheduler decides rail assignment]                |
   |    if len < threshold:                                       |
   |      single rail (round-robin)                               |
   |    else:                                                     |
   |      stripe across N rails, 128B aligned chunks              |
   |                                                              |
   |    Per rail chunk:                                           |
   |    fi_write(ep,                                              |
   |      local_buf + offset,   // source                        |
   |      chunk_len,                                              |
   |      local_mr_desc,        // local MR                      |
   |      peer_fi_addr,         // AV table index                |
   |      remote_addr + offset, // dest                          |
   |      remote_rkey)          // from importMem                |
   |        |                                                     |
   |        |  [RDMA WRITE over SRD - zero copy, OS bypass]       |
   |        +====================================================>|
   |        |                                                     |  (data lands directly in
   |        |                                                     |   GPU recvbuf via GDR)
   |                                                              |
   |  [Sender CQ: FI_WRITE completion per rail chunk]             |
   |  fi_cq_read(cq) --> comp_flags & FI_WRITE                   |
   |  req->refCount-- per chunk                                   |
   |                                                              |
   |  ================== NOTIFICATION ===========================  |
   |                                                              |
   |  [After all WRITE completions, notify=true triggers:]        |
   |                                                              |
   |  ctranEfa->notify(peer=1, req)                               |  [Receiver polls for notification]
   |    fi_writedata(ep,                                          |  ctranEfa->checkNotify(peer=0)
   |      NULL, 0,              // zero-byte write               |    fi_cq_read(cq) -->
   |      imm_data=encode(                                       |      comp_flags & FI_REMOTE_WRITE
   |        comm_id, seq_num),                                    |      imm_data present
   |      peer_fi_addr,                                           |    decode(imm_data) -->
   |      remote_addr,                                            |      comm_id, seq_num
   |      remote_rkey)                                            |    match seq_num --> notify=true
   |        |                                                     |
   |        +====================================================>|
   |                                                              |
   |  ===================== PROGRESS ============================  |
   |                                                              |
   |  [Both ranks poll in progress loop]                          |
   |                                                              |
   |  ctranEfa->progress()                                        |  ctranEfa->progress()
   |    for each rail:                                            |    for each rail:
   |      fi_cq_read(cq, &cqe, batch_size)                       |      fi_cq_read(cq, &cqe, batch_size)
   |      switch(cqe.flags):                                     |      switch(cqe.flags):
   |        FI_SEND  -> ctrl msg sent                             |        FI_RECV   -> ctrl msg arrived
   |        FI_WRITE -> RDMA write done                           |        FI_REMOTE_WRITE -> data+notify
   |        FI_READ  -> RDMA read done                            |        FI_REMOTE_WRITE w/ imm -> notify
   |      if -FI_EAGAIN: retry pending ops                        |      if -FI_EAGAIN: retry pending ops
   |                                                              |
   |  ==================== CLEANUP ==============================  |
   |                                                              |
   |  [mapper->deregMem(hdl)]                                     |  [mapper->deregMem(hdl)]
   |  ctranEfa->deregMem(efaRegElem)                              |  ctranEfa->deregMem(efaRegElem)
   |    per rail: fi_close(mr)                                    |    per rail: fi_close(mr)
   |                                                              |
```

## 3. Sequence Diagram: Fallback Path (p4d - No RDMA Write)

```
Rank 0 (Sender)                                              Rank 1 (Receiver)
   |                                                              |
   |  [Singleton detects: RDMA Write NOT supported (p4d)]         |
   |  [Falls back to tagged send/recv for notifications]          |
   |                                                              |
   |  ================= DATA TRANSFER ==========================  |
   |                                                              |
   |  ctranEfa->iput(sbuf, dbuf, len, ...)                        |
   |    fi_read on RECEIVER side pulls data:                      |
   |    (sender exports, receiver does fi_read)                   |
   |                                                              |
   |  -- OR --                                                    |
   |  ctranEfa->iget(sbuf, dbuf, len, ...)                        |
   |    fi_read(ep, local_buf, len,                               |
   |      local_mr_desc, peer_fi_addr,                            |
   |      remote_addr, remote_rkey)                               |
   |        |                                                     |
   |        +====================================================>|
   |        |  [RDMA READ - supported on all EFA instances]       |
   |        |<====================================================+
   |        |  (data copied to local GPU buf)                     |
   |                                                              |
   |  ================== NOTIFICATION ==========================  |
   |                                                              |
   |  [No fi_writedata available, use explicit send/recv]         |
   |                                                              |
   |  ctranEfa->notify(peer=1, req)                               |  ctranEfa->checkNotify(peer=0)
   |    fi_send(ep, &notify_msg, size,                            |    fi_recv(ep, &notify_msg, size)
   |      NULL, peer_fi_addr)                                     |      --> on CQ: FI_RECV completion
   |        |                                                     |      decode notify_msg
   |        +---------------------------------------------------->+      --> notify=true
   |                                                              |
```

## 4. Component Dependency Graph

```
                    +-------------------+
                    |  nccl_cvars.yaml  |
                    | (NCCL_CTRAN_      |
                    |  BACKENDS += efa) |
                    +-------------------+
                             |
                    +-------------------+
                    |  commSpecs.h      |
                    | (CommBackend::EFA)|
                    +-------------------+
                             |
              +--------------+--------------+
              |                             |
   +--------------------+       +------------------------+
   | CtranMapperTypes.h |       |     CtranCtrl.h        |
   | EFA_PUT/EFA_GET    |       | EFA_EXPORT_MEM         |
   | CtranEfaRequest    |       | EfaDesc in ControlMsg  |
   | CtranEfaRemoteKey  |       +------------------------+
   +--------------------+                  |
              |                            |
   +--------------------+                  |
   |  CtranMapper.h/.cc |------------------+
   |  ctranEfa ptr      |
   |  routing logic     |
   +--------------------+
              |
   +--------------------+       +------------------------+
   |  RegCache.h/.cc    |       |   CMakeLists.txt       |
   |  efaRegElem field  |       | ENABLE_EFA /           |
   +--------------------+       | CTRAN_DISABLE_EFA      |
                                +------------------------+
              |
   +=========================================================+
   |                   EFA BACKEND FILES                      |
   |                                                          |
   |  comms/ctran/backends/efa/                               |
   |  +-------------------+  +----------------------------+   |
   |  | CtranEfaBase.h    |  | CtranEfaSingleton.h/.cc    |   |
   |  | - Request type    |  | - folly::Singleton         |   |
   |  | - RemoteAccessKey |  | - fi_fabric/fi_domain      |   |
   |  | - Config          |  | - NIC discovery            |   |
   |  +-------------------+  | - RDMA cap detection       |   |
   |           |              | - GDR detection            |   |
   |           v              +----------------------------+   |
   |  +-------------------+               |                    |
   |  | CtranEfa.h/.cc    |<--------------+                    |
   |  | - Public API      |                                    |
   |  | - Per-rail state  |  +----------------------------+    |
   |  | - Stripe sched    |  | comms/ctran/backends/mock/ |    |
   |  | - Progress loop   |  | CtranEfaMock.h             |    |
   |  +-------------------+  | CtranEfaBaseMock.h         |    |
   |           |              +----------------------------+    |
   +=========================================================+
              |
              v
   +-------------------+
   |  libfabric >= 1.22|
   |  EFA provider     |
   |  FI_EP_RDM        |
   +-------------------+
              |
              v
   +-------------------+
   |  EFA Hardware      |
   |  (SRD protocol)   |
   +-------------------+
```
