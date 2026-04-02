# EFA Support for ctran

## Overview
Add AWS EFA (Elastic Fabric Adapter) as a new ctran backend transport using libfabric (OFI) API with SRD protocol. Follows the existing IB backend pattern and TCPDM conditional compilation model.

---

## Phase 1: Scaffold (no libfabric dependency)

- [ ] Add `EFA=5` to `CommBackend` enum in `comms/utils/commSpecs.h`, bump `NUM_BACKENDS=6`
- [ ] Add `efa` to `NCCL_CTRAN_BACKENDS` cvar choices in `comms/utils/cvars/nccl_cvars.yaml`
- [ ] Create `comms/ctran/backends/efa/CtranEfaBase.h` — request, remote access key, config types
- [ ] Create mock files `comms/ctran/backends/mock/CtranEfaMock.h` and `CtranEfaBaseMock.h`
- [ ] Add `EFA_EXPORT_MEM` to `ControlMsgType` enum and `EfaDesc` to `ControlMsg` union in `CtranCtrl.h`
- [ ] Update `CtranMapperTypes.h` — add EFA fields to `CtranMapperRequest`, `CtranMapperRemoteAccessKey`, `CtranMapperNotify`
- [ ] Update `CtranMapper.h` — conditional include, `ctranEfa` ptr, update all routing (queryPeerBackend, getCtrlBackend, exportMem, importMem, iputImpl, igetImpl, progress, checkComplete, waitNotify, checkNotify, backendToStr)
- [ ] Update `CtranMapper.cc` — add EFA to `getToEnableBackends()`, constructor init block, logging
- [ ] Add `efaRegElem` field to `RegElem` in `RegCache.h`, add EFA reg/dereg in `RegCache.cc`
- [ ] Update `comms/ctran/CMakeLists.txt` — conditional `CTRAN_DISABLE_EFA` / `ENABLE_EFA` gating
- [ ] Verify build compiles with `CTRAN_DISABLE_EFA` (mock path, no regressions)

## Phase 2: Core EFA Backend

### Singleton & Initialization
- [ ] Create `comms/ctran/backends/efa/CtranEfaSingleton.h/.cc` — fabric/domain singleton via `folly::Singleton`
  - Multi-NIC discovery: enumerate all EFA devices via `fi_getinfo()`
  - GPU-NIC affinity mapping (topology-aware rail assignment)
  - Libfabric version check: require >= 1.22.0, fail gracefully if older
  - RDMA capability detection: probe `EFADV_DEVICE_ATTR_CAPS_RDMA_READ` / `RDMA_WRITE` per device
  - GDR detection: disable `FI_OPT_CUDA_API_PERMITTED` to test GPU Direct support

### Endpoint & Connection
- [ ] Create `comms/ctran/backends/efa/CtranEfa.h` — main backend class API
- [ ] Implement `CtranEfa.cc` constructor — per-rail endpoint, CQ, AV creation
  - Use `FI_EP_RDM` endpoints exclusively (reliable datagram)
  - Use `FI_AV_TABLE` (only supported AV type on EFA)
  - Use `FI_PROGRESS_MANUAL` (AUTO is broken on EFA)
  - Use `FI_CQ_FORMAT_DATA` for completions (context + flags + length + 4B CQ data)
  - IOV limit = 1: all operations must use single contiguous buffers
- [ ] Implement address exchange — bootstrap allgather + `fi_av_insert` per rail
- [ ] Implement `preConnect` — trigger eager handshakes (first 16 ops to new peer are queued during libfabric handshake)

### Memory Registration
- [ ] Implement `regMem`/`deregMem` — `fi_mr_regattr`/`fi_close` per rail
  - `FI_HMEM_CUDA` for GPU buffers, `FI_HMEM_SYSTEM` for host
  - Device ID lookup via CUDA API for HMEM registration
  - Access flags: `FI_SEND | FI_RECV | FI_READ | FI_WRITE | FI_REMOTE_READ | FI_REMOTE_WRITE`
- [ ] Implement `exportMem`/`importMem` — remote key exchange via control messages
  - Handle `FI_MR_VIRT_ADDR` vs offset-based MR mode (base_addr tracking)

### Data Transfer
- [ ] Implement `iput` — `fi_write` (RDMA write), striped across rails for large messages
- [ ] Implement `iget` — `fi_read` (RDMA read), with fallback if RDMA write unsupported on instance
- [ ] Implement `isendCtrlMsg`/`irecvCtrlMsg` — via `fi_send`/`fi_recv` (or `fi_tsend`/`fi_trecv` tagged)

### Notifications
- [ ] Implement `notify`/`checkNotify`/`waitNotify` — via `fi_writedata()` (RDMA write with immediate)
  - Encode comm_id + seq_num in 32-bit immediate field
  - Receiver detects via `FI_REMOTE_WRITE` CQ completion with immediate data
  - Fallback: explicit `fi_send`/`fi_recv` on instances without RDMA write support (p4d/p4de)

### Progress
- [ ] Implement `progress()` — `fi_cq_read` polling loop across all rails
  - Batch CQ reads for efficiency
  - `FI_EAGAIN` retry queue for flow control (pending ops pattern from IB backend)
  - Dispatch completions by `comp_flags`: FI_SEND, FI_RECV, FI_WRITE, FI_READ, FI_REMOTE_WRITE

### Atomics (not supported)
- [ ] Stub out `ifetchAndAdd`/`iatomicSet` — return `commNotSupported` (EFA has no RDMA atomics)

### Multi-Rail
- [ ] Implement rail discovery — enumerate EFA NICs, respect Nitro card topology on P5+
- [ ] Implement stripe scheduler — round-robin single rail for small msgs, stripe across rails for large msgs (128-byte alignment)
- [ ] Per-rail state: endpoint, CQ, AV, MR handles

## Phase 3: Integration and Testing

- [ ] Wire up mapper constructor to instantiate `CtranEfa`
- [ ] Build with `ENABLE_EFA=ON` + libfabric >= 1.22.0 — verify compilation
- [ ] Write unit tests under `comms/ctran/backends/efa/tests/`
- [ ] Run existing collectives integration tests with `NCCL_CTRAN_BACKENDS=efa`
- [ ] Test on EFA-equipped AWS instance (p5 preferred for RDMA write; p4d for read-only fallback path)

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
