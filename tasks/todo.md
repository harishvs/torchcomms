# EFA Support for ctran

## Why

AWS EC2 GPU instances (p4d, p5, p5en, p6) ship with EFA (Elastic Fabric Adapter) NICs instead of InfiniBand. Today, ctran only supports IB for RDMA data transfer, which means torchcomms users on AWS must fall back to slower Socket or TCPDM backends. Adding EFA as a first-class ctran backend enables zero-copy GPU-to-GPU RDMA on AWS infrastructure, matching the performance characteristics of IB on on-prem clusters.

EFA uses AWS's SRD (Scalable Reliable Datagram) protocol over libfabric — connectionless, reliable, and OS-bypass capable. The existing aws-ofi-nccl plugin proves this stack works for GPU collectives; we're bringing the same capability into ctran's one-sided put/get model.

## Overview

Add AWS EFA as a new ctran backend transport using libfabric (OFI) API with SRD protocol. Follows the existing IB backend pattern and TCPDM conditional compilation model.

---

## Phase 1: Scaffold (no libfabric dependency) ✅

**Goal**: Wire EFA into every layer of the ctran stack so the codebase compiles and routes correctly, without any actual libfabric calls. Mock stubs stand in for the real backend. This lets us land the integration plumbing without introducing a new build dependency.

- [x] Add `EFA=5` to `CommBackend` enum in `comms/utils/commSpecs.h`, bump `NUM_BACKENDS=6`
  > The enum is how ctran identifies backends everywhere. Without this, no code can reference EFA as a backend type.

- [x] Add `efa` to `NCCL_CTRAN_BACKENDS` cvar choices in `comms/utils/cvars/nccl_cvars.yaml`
  > Users select backends via `NCCL_CTRAN_BACKENDS=efa` env var. The cvar system needs to parse and validate "efa" as a legal value, otherwise it's rejected at startup.

- [x] Create `comms/ctran/backends/efa/CtranEfaBase.h` — request, remote access key, config types
  > Defines `CtranEfaRequest` (tracks async operation completion), `CtranEfaRemoteAccessKey` (holds per-rail remote MR keys for RDMA), and `CtranEfaConfig`. These types are used by the mapper and RegCache layers — they must exist even when the real backend is disabled.

- [x] Create mock files `comms/ctran/backends/mock/CtranEfaMock.h` and `CtranEfaBaseMock.h`
  > When `CTRAN_DISABLE_EFA` is defined (the default), these mocks provide the same class/struct interfaces but all methods return `commInvalidUsage`. This is exactly how TCPDM works — the mock path lets the rest of the code compile and link without libfabric.

- [x] Add `EFA_EXPORT_MEM` to `ControlMsgType` enum and `EfaDesc` to `ControlMsg` union in `CtranCtrl.h`
  > Control messages carry buffer metadata between ranks during the handshake phase. `EFA_EXPORT_MEM` is the new message type, and `EfaDesc` carries the remote address + per-rail MR keys. Without this, the sender can't tell the receiver where to RDMA write.

- [x] Update `CtranMapperTypes.h` — add EFA fields to `CtranMapperRequest`, `CtranMapperRemoteAccessKey`, `CtranMapperNotify`
  > The mapper layer is backend-agnostic — it holds request/key objects that internally contain backend-specific fields. We add `efaReq`, `efaKey`, `EFA_PUT`/`EFA_GET` request types so the mapper can track EFA operations alongside IB/NVL/TCPDM ones.

- [x] Update `CtranMapper.h` — conditional include, `ctranEfa` ptr, update all routing
  > The mapper is the central routing layer: `iput`, `iget`, `progress`, `exportMem`, `importMem`, `checkNotify`, `waitNotify`, etc. Each of these has a backend dispatch chain (`if ctranIb ... else if ctranEfa ... else if ctranSock ...`). We add EFA to every dispatch point so operations flow through to the EFA backend when active.

- [x] Update `CtranMapper.cc` — add EFA to `getToEnableBackends()`, constructor init block, logging
  > `getToEnableBackends()` maps the cvar enum to `CtranMapperBackend` — EFA needs an entry here. The constructor init block creates the `CtranEfa` instance (or skips if IB is already enabled, since they're mutually exclusive). Also updates `getBackend()`, `hasBackend()`, `preConnect()` to recognize EFA.

- [x] Add `efaRegElem` field to `RegElem` in `RegCache.h`, add EFA reg/dereg in `RegCache.cc`
  > RegCache is the global memory registration cache. Each `RegElem` holds per-backend registration handles (`ibRegElem`, `tcpRegElem`, now `efaRegElem`). `doRegister()` calls `CtranEfa::regMem()` and `doDeregister()` calls `CtranEfa::deregMem()` — both route to mocks when disabled.

- [x] Update `comms/ctran/CMakeLists.txt` — conditional `CTRAN_DISABLE_EFA` / `ENABLE_EFA` gating
  > Follows the TCPDM pattern: when `ENABLE_EFA` is OFF (default), the build defines `CTRAN_DISABLE_EFA` and excludes `backends/efa/` source files. This ensures zero build impact when EFA is not needed, and the mock headers provide type compatibility.

- [ ] Verify build compiles with `CTRAN_DISABLE_EFA` (mock path, no regressions)
  > Final validation: build the full project with EFA disabled to confirm the scaffold doesn't break anything. Requires CUDA toolkit (not available on current dev machine).

## Phase 2: Core EFA Backend

**Goal**: Implement the real EFA backend that talks to libfabric. This is where actual `fi_*` calls happen — fabric init, endpoint creation, memory registration, RDMA writes/reads, and CQ polling. Each subsection below maps to a distinct responsibility in the EFA data path.

### Singleton & Initialization
- [ ] Create `comms/ctran/backends/efa/CtranEfaSingleton.h/.cc` — fabric/domain singleton via `folly::Singleton`
  > Like `CtranIbSingleton` holds global IB resources (devices, PDs), this singleton holds the libfabric `fi_fabric` and `fi_domain` objects shared across all communicators. It also does one-time discovery: enumerate EFA NICs via `fi_getinfo()`, map GPU-to-NIC affinity for topology-aware rail assignment, check libfabric version (>= 1.22.0), and probe each device for RDMA read/write capability (`EFADV_DEVICE_ATTR_CAPS`). GDR (GPU Direct RDMA) support is detected by attempting to disable `FI_OPT_CUDA_API_PERMITTED` — if it succeeds, the provider handles GPU memory natively.

### Endpoint & Connection
- [ ] Create `comms/ctran/backends/efa/CtranEfa.h` — main backend class API
  > Public interface matching what `CtranMapper` calls: `iput`, `iget`, `regMem`, `deregMem`, `exportMem`, `importMem`, `isendCtrlMsg`, `irecvCtrlMsg`, `notify`, `checkNotify`, `waitNotify`, `preConnect`, `progress`. Mirrors `CtranIb.h` structure.

- [ ] Implement `CtranEfa.cc` constructor — per-rail endpoint, CQ, AV creation
  > For each rail (NIC): create an `FI_EP_RDM` endpoint (reliable datagram — the only production endpoint on EFA), a completion queue (`FI_CQ_FORMAT_DATA`), and an address vector (`FI_AV_TABLE` — the only supported type). `FI_PROGRESS_MANUAL` is required because AUTO is broken on EFA. IOV limit is 1, so no scatter/gather.

- [ ] Implement address exchange — bootstrap allgather + `fi_av_insert` per rail
  > Each rank gets its local endpoint address via `fi_getname()`, then all ranks exchange addresses through the existing bootstrap allgather. Each rank then inserts peer addresses into its AV via `fi_av_insert()`. This is the connectionless equivalent of IB's QP connection.

- [ ] Implement `preConnect` — trigger eager handshakes
  > Libfabric's EFA provider has an internal handshake protocol — the first 16 operations to a new peer may be queued while it completes. `preConnect` triggers these handshakes eagerly so the first real operation doesn't pay the latency.

### Memory Registration
- [ ] Implement `regMem`/`deregMem` — `fi_mr_regattr`/`fi_close` per rail
  > GPU buffers must be registered with the NIC before RDMA. We call `fi_mr_regattr()` with `FI_HMEM_CUDA` for GPU memory and `FI_HMEM_SYSTEM` for host memory, per rail. Access flags include all directions (`FI_SEND|FI_RECV|FI_READ|FI_WRITE|FI_REMOTE_READ|FI_REMOTE_WRITE`). The CUDA device ID is passed for HMEM so the provider can set up the correct GPU-NIC DMA path.

- [ ] Implement `exportMem`/`importMem` — remote key exchange via control messages
  > After registration, the local rank packs its buffer address and per-rail MR keys into an `EfaDesc` control message. The remote rank unpacks this to get the `CtranEfaRemoteAccessKey` needed for RDMA. Must handle `FI_MR_VIRT_ADDR` mode where the remote address is the virtual address (base_addr=0), vs offset mode.

### Data Transfer
- [ ] Implement `iput` — `fi_write` (RDMA write), striped across rails for large messages
  > The core data path. Posts `fi_write()` to push data from local GPU buffer to remote GPU buffer. For large messages, the stripe scheduler splits the transfer across multiple rails (128-byte aligned chunks) to maximize NIC bandwidth. P5 instances have 32 EFA NICs — using all of them is critical for performance.

- [ ] Implement `iget` — `fi_read` (RDMA read), with fallback if RDMA write unsupported on instance
  > RDMA read pulls data from a remote buffer to the local buffer. Available on ALL EFA instances (including p4d which lacks RDMA write). Used as the fallback data transfer method on older instance types.

- [ ] Implement `isendCtrlMsg`/`irecvCtrlMsg` — via `fi_send`/`fi_recv` (or `fi_tsend`/`fi_trecv` tagged)
  > Control messages (buffer metadata exchange, sync) use the messaging API rather than RDMA. These are small payloads exchanged during the handshake phase before RDMA operations can begin.

### Notifications
- [ ] Implement `notify`/`checkNotify`/`waitNotify` — via `fi_writedata()` (RDMA write with immediate)
  > After all `fi_write` completions, the sender signals the receiver by posting `fi_writedata()` — a zero-byte RDMA write carrying a 32-bit immediate value (encoding comm_id + seq_num). The receiver detects this via `FI_REMOTE_WRITE` CQ completion with immediate data. This is strictly sequential: the notification fires ONLY after all data writes complete. On p4d/p4de (no RDMA write), falls back to explicit `fi_send`/`fi_recv`.

### Progress
- [ ] Implement `progress()` — `fi_cq_read` polling loop across all rails
  > Drives all completion processing. For each rail, batch-reads CQ entries via `fi_cq_read()`. Dispatches based on `comp_flags`: `FI_SEND` (ctrl msg sent), `FI_RECV` (ctrl msg received), `FI_WRITE` (local RDMA write done), `FI_READ` (local RDMA read done), `FI_REMOTE_WRITE` (remote wrote data + notification). Handles `FI_EAGAIN` by queueing to a pending ops retry list.

### Atomics (not supported)
- [ ] Stub out `ifetchAndAdd`/`iatomicSet` — return `commNotSupported`
  > EFA hardware has no RDMA atomic operations (unlike IB which supports fetch-and-add and CAS). The IB backend uses these for distributed synchronization in some algorithms. We stub them out cleanly so algorithms that need atomics can detect the limitation and use alternative approaches.

### Multi-Rail
- [ ] Implement rail discovery — enumerate EFA NICs, respect Nitro card topology on P5+
  > P5 instances have 32 EFA devices grouped by Nitro card. The rail discovery must enumerate all devices and sort them to match GPU-NIC affinity for optimal PCIe topology. On P5en/P6, a `max:1` NIC distribution policy optimizes across PCIe switches.

- [ ] Implement stripe scheduler — round-robin single rail for small msgs, stripe across rails for large msgs (128-byte alignment)
  > Small messages go to a single rail (round-robin for load balance). Large messages are split into 128-byte-aligned chunks distributed across all available rails. The stripe count is chosen as the largest factor of total rails that fits the message size (same approach as aws-ofi-nccl).

- [ ] Per-rail state: endpoint, CQ, AV, MR handles
  > Each rail maintains its own `fi_endpoint`, `fi_cq`, `fi_av`, and per-buffer `fi_mr` handles. These are independent — operations on different rails can proceed in parallel without locking.

## Phase 3: Integration and Testing

**Goal**: Connect the real backend to the mapper, verify it compiles with libfabric, and validate correctness on actual EFA hardware.

- [ ] Wire up mapper constructor to instantiate `CtranEfa`
  > Replace the mock `CtranEfa` with the real implementation when `ENABLE_EFA=ON`. The mapper constructor creates the backend, calls `regCtrlCb`, and the full data path is live.

- [ ] Build with `ENABLE_EFA=ON` + libfabric >= 1.22.0 — verify compilation
  > First compilation gate. Requires libfabric headers and libraries. Tests that all `fi_*` calls are correct, types match, and linking succeeds.

- [ ] Write unit tests under `comms/ctran/backends/efa/tests/`
  > Unit tests for the backend in isolation: mock the libfabric layer, verify request tracking, MR key serialization, stripe scheduling logic, CQ dispatch, etc.

- [ ] Run existing collectives integration tests with `NCCL_CTRAN_BACKENDS=efa`
  > Run the standard ctran integration test suite (AllReduce, AllGather, etc.) with `NCCL_CTRAN_BACKENDS=efa` to verify the full path works end-to-end. Requires multi-GPU EFA instances.

- [ ] Test on EFA-equipped AWS instance (p5 preferred for RDMA write; p4d for read-only fallback path)
  > P5 exercises the full RDMA write + fi_writedata notification path. P4d exercises the RDMA read + fi_send notification fallback. Both must pass for the backend to be production-ready.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| EFA and IB are mutually exclusive | AWS has EFA, on-prem has IB. No benefit to both. |
| Notifications via `fi_writedata()` (write with immediate) | EFA libfabric provider supports `FI_REMOTE_WRITE` completions with 32-bit immediate data. Proven pattern in aws-ofi-nccl. Fallback to explicit fi_send for p4d/p4de (no RDMA write). |
| `FI_EP_RDM` endpoints | Reliable datagram — the only production-quality endpoint type on EFA. Connectionless, scales with AV. |
| `FI_AV_TABLE` only | `FI_AV_MAP` silently converts to TABLE with warnings on EFA. Use TABLE directly. |
| `FI_PROGRESS_MANUAL` | `FI_PROGRESS_AUTO` advertised but broken on EFA. Must poll explicitly. |
| GPU memory via `FI_HMEM_CUDA` | Requires libfabric >= 1.22.0. Detect GDR at init via `FI_OPT_CUDA_API_PERMITTED`. |
| Multi-rail support | P5 has 32 EFA NICs. Stripe large messages across rails for bandwidth. |
| No atomics | EFA lacks RDMA atomic ops. Stub returns `commNotSupported`. |
| IOV limit = 1 | EFA only supports single-segment MR. No scatter/gather. |
| Runtime RDMA capability detection | p4d = read only, p5+ = read + write. Probe at init, adapt code paths. |
| Build gated by `ENABLE_EFA` | Default OFF. `CTRAN_DISABLE_EFA` define for mock path. |
| Libfabric >= 1.22.0 required | EFA provider requirement. Check at init, fail with clear error. |

## Review

_To be filled after implementation is complete._
