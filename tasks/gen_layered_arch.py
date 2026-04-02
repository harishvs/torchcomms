#!/usr/bin/env python3
"""Generate EFA Backend Layered Architecture diagram as PNG using matplotlib."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

fig, ax = plt.subplots(1, 1, figsize=(20, 28))
ax.set_xlim(0, 20)
ax.set_ylim(0, 28)
ax.axis("off")
fig.patch.set_facecolor("white")

# Colors
C_ALGO = "#4A90D9"
C_MAPPER = "#7B68EE"
C_BACKEND_EXISTING = "#A0A0A0"
C_EFA_MAIN = "#E8833A"
C_EFA_DETAIL = "#F5C242"
C_LIBFABRIC = "#50C878"
C_PROVIDER = "#20B2AA"
C_HW = "#CD5C5C"
C_TEXT = "white"
C_TEXT_DARK = "#1a1a1a"

def draw_box(x, y, w, h, color, label, fontsize=11, text_color=C_TEXT, style="round,pad=0.02", alpha=0.95, bold=False):
    box = mpatches.FancyBboxPatch((x, y), w, h, boxstyle=style, facecolor=color, edgecolor="#333", linewidth=1.5, alpha=alpha)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x + w/2, y + h/2, label, ha="center", va="center", fontsize=fontsize, color=text_color, fontweight=weight, wrap=True)

def draw_arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color="#555", lw=2))

# === Layer 1: Collective Algorithms ===
draw_box(1, 26.5, 18, 1.0, C_ALGO, "Collective Algorithms\n(AllReduce, AllGather, ReduceScatter, Broadcast, ...)", fontsize=13, bold=True)
draw_arrow(10, 26.5, 10, 26.0)

# === Layer 2: Ctran Mapper ===
draw_box(1, 23.2, 18, 2.7, C_MAPPER, "", fontsize=10, alpha=0.15)
ax.text(10, 25.65, "CTRAN MAPPER (CtranMapper)", ha="center", va="center", fontsize=13, color=C_MAPPER, fontweight="bold")

# Mapper sub-boxes
draw_box(1.3, 24.5, 5.5, 0.8, C_MAPPER, "Control Path\nisendCtrl / irecvCtrl\nexportMem / importMem", fontsize=8, alpha=0.85)
draw_box(7.2, 24.5, 5.5, 0.8, C_MAPPER, "Data Path\niput / iget / iputBatch\natomicSet / iflush", fontsize=8, alpha=0.85)
draw_box(13.1, 24.5, 5.6, 0.8, C_MAPPER, "Notification Path\nnotify / checkNotify\nwaitNotify / progress", fontsize=8, alpha=0.85)

draw_box(1.3, 23.5, 8.5, 0.7, C_MAPPER, "Backend Router:  queryPeerBackend(rank) --> IB | NVL | SOCKET | TCPDM | EFA", fontsize=8, alpha=0.85)
draw_box(10.2, 23.5, 4.2, 0.7, C_MAPPER, "RegCache\n(mem registration cache)", fontsize=8, alpha=0.85)
draw_box(14.8, 23.5, 4.0, 0.7, C_MAPPER, "CtranCtrlManager\n(callback dispatch)", fontsize=8, alpha=0.85)

# === Layer 3: Backend Selection (5 backends) ===
draw_box(1.0, 21.7, 3.2, 1.0, C_BACKEND_EXISTING, "CtranIb\n(IB/RoCE)", fontsize=9)
draw_box(4.5, 21.7, 3.0, 1.0, C_BACKEND_EXISTING, "CtranNvl\n(NVLink)", fontsize=9)
draw_box(7.8, 21.7, 3.0, 1.0, C_BACKEND_EXISTING, "CtranSocket\n(TCP)", fontsize=9)
draw_box(11.1, 21.7, 3.2, 1.0, C_BACKEND_EXISTING, "CtranTcpDm\n(TCP DMA)", fontsize=9)
draw_box(14.8, 21.7, 4.2, 1.0, C_EFA_MAIN, "CtranEfa\n(NEW - EFA)", fontsize=10, bold=True)

for x in [2.6, 6.0, 9.3, 12.7, 16.9]:
    draw_arrow(x, 23.2, x, 22.7)

draw_arrow(16.9, 21.7, 16.9, 21.0)

# === Layer 4: EFA Backend Detail ===
draw_box(1.0, 13.5, 18, 7.3, C_EFA_MAIN, "", fontsize=10, alpha=0.08)
ax.text(10, 20.5, "EFA BACKEND  (comms/ctran/backends/efa/)", ha="center", va="center", fontsize=13, color=C_EFA_MAIN, fontweight="bold")

# CtranEfa public API
draw_box(1.3, 17.8, 7.0, 2.4, C_EFA_MAIN, "CtranEfa  (Public API)\n\niput / iget\nisendCtrlMsg / irecvCtrlMsg\nregMem / deregMem\nexportMem / importMem\nnotify / checkNotify / waitNotify\npreConnect / progress", fontsize=8, alpha=0.9)

# Singleton
draw_box(9.0, 17.8, 5.2, 2.4, C_EFA_MAIN, "CtranEfaSingleton\n(folly::Singleton)\n\nfi_fabric / fi_domain\nMulti-NIC discovery\nGPU-NIC affinity map\nRDMA capability detection\nGDR detection (FI_OPT_CUDA_API)", fontsize=8, alpha=0.9)

# Request
draw_box(14.8, 17.8, 4.0, 2.4, C_EFA_MAIN, "CtranEfaRequest\n\nstate: INCOMPLETE\n       / COMPLETE\nrefCount\n(multi-rail stripe)\nnotify flag", fontsize=8, alpha=0.9)

# Per-rail state
draw_box(1.3, 15.5, 8.5, 1.9, C_EFA_DETAIL, "Per-Rail State (x N rails)\n\nRail 0:  fi_endpoint  |  fi_cq  |  fi_av  |  fi_mr[]\nRail 1:  fi_endpoint  |  fi_cq  |  fi_av  |  fi_mr[]\n  ...         ...            ...         ...          ...\nRail N:  fi_endpoint  |  fi_cq  |  fi_av  |  fi_mr[]", fontsize=8, text_color=C_TEXT_DARK)

# Stripe scheduler
draw_box(10.2, 15.5, 8.5, 1.9, C_EFA_DETAIL, "Stripe Scheduler\n\nSmall msg (< threshold)\n  --> single rail, round-robin\n\nLarge msg (> threshold)\n  --> stripe across N rails, 128B aligned", fontsize=8, text_color=C_TEXT_DARK)

# Notification paths
draw_box(1.3, 13.8, 8.5, 1.3, C_EFA_DETAIL, "Notification Strategy\n\nRDMA Write supported (p5+):  fi_writedata() with 32-bit immediate\nRDMA Write unsupported (p4d):  fi_send/fi_recv fallback", fontsize=8, text_color=C_TEXT_DARK)

draw_box(10.2, 13.8, 8.5, 1.3, C_EFA_DETAIL, "Progress Engine\n\nfi_cq_read() per rail (manual poll, batch reads)\nDispatch: FI_SEND | FI_RECV | FI_WRITE | FI_READ | FI_REMOTE_WRITE\nFI_EAGAIN --> pending ops retry queue", fontsize=8, text_color=C_TEXT_DARK)

draw_arrow(10, 13.5, 10, 12.9)

# === Layer 5: Libfabric API ===
draw_box(1.0, 10.3, 18, 2.4, C_LIBFABRIC, "", fontsize=10, alpha=0.15)
ax.text(10, 12.45, "LIBFABRIC (OFI) API  (>= 1.22.0)", ha="center", va="center", fontsize=13, color="#2E8B57", fontweight="bold")

draw_box(1.3, 10.5, 4.0, 1.5, C_LIBFABRIC, "Endpoints\nfi_endpoint(FI_EP_RDM)\nfi_ep_bind(cq, av)\nfi_enable(ep)", fontsize=8)
draw_box(5.7, 10.5, 4.0, 1.5, C_LIBFABRIC, "Memory Reg\nfi_mr_regattr()\nFI_HMEM_CUDA\nFI_MR_VIRT_ADDR", fontsize=8)
draw_box(10.1, 10.5, 4.0, 1.5, C_LIBFABRIC, "Data Transfer\nfi_write / fi_writedata\nfi_read\nfi_send / fi_recv", fontsize=8)
draw_box(14.5, 10.5, 4.2, 1.5, C_LIBFABRIC, "Completions\nfi_cq_read (manual)\nFI_CQ_FORMAT_DATA\nfi_av_open(TABLE)", fontsize=8)

draw_arrow(10, 10.3, 10, 9.7)

# === Layer 6: EFA Provider ===
draw_box(1.0, 7.5, 18, 2.0, C_PROVIDER, "", fontsize=10, alpha=0.15)
ax.text(10, 9.2, "EFA PROVIDER  (libfabric EFA plugin)", ha="center", va="center", fontsize=12, color="#178B8B", fontweight="bold")

draw_box(1.3, 7.7, 4.0, 1.1, C_PROVIDER, "SRD Protocol\nReliable, Out-of-order\nConnectionless, OS-bypass", fontsize=8)
draw_box(5.7, 7.7, 4.0, 1.1, C_PROVIDER, "RDMA Ops\nRead: all instances\nWrite: p5+ only\nNo atomics", fontsize=8)
draw_box(10.1, 7.7, 4.0, 1.1, C_PROVIDER, "GPU Direct\nFI_HMEM + CUDA DMA\nGDRCopy required\nP2P must be enabled", fontsize=8)
draw_box(14.5, 7.7, 4.2, 1.1, C_PROVIDER, "Constraints\nFI_PROGRESS_MANUAL\nFI_AV_TABLE only\nIOV limit = 1", fontsize=8)

draw_arrow(10, 7.5, 10, 6.9)

# === Layer 7: Hardware ===
draw_box(1.0, 4.5, 18, 2.2, C_HW, "", fontsize=10, alpha=0.15)
ax.text(10, 6.4, "EFA HARDWARE", ha="center", va="center", fontsize=13, color=C_HW, fontweight="bold")

draw_box(1.5, 4.7, 4.5, 1.3, C_HW, "EFA NIC 0\n(PCIe attached)\nSRD QP", fontsize=9)
draw_box(7.0, 4.7, 4.5, 1.3, C_HW, "EFA NIC 1\n(PCIe attached)\nSRD QP", fontsize=9)
draw_box(12.5, 4.7, 4.5, 1.3, C_HW, "EFA NIC N\n(PCIe attached)\nSRD QP", fontsize=9)

ax.text(11.0, 5.35, "...", ha="center", va="center", fontsize=20, color="#555")

# Network bar
draw_box(1.0, 3.2, 18, 0.9, "#8B4513", "AWS Nitro Network  (SRD wire protocol)", fontsize=12, bold=True)

for x in [3.75, 9.25, 14.75]:
    draw_arrow(x, 4.7, x, 4.1)
draw_arrow(10, 4.1, 10, 4.1)

# Legend
ax.text(1.0, 2.5, "Legend:", fontsize=10, fontweight="bold", color="#333")
legend_items = [
    (C_ALGO, "Collective Algorithms"),
    (C_MAPPER, "Ctran Mapper (routing layer)"),
    (C_BACKEND_EXISTING, "Existing Backends"),
    (C_EFA_MAIN, "New EFA Backend"),
    (C_EFA_DETAIL, "EFA Internal Components"),
    (C_LIBFABRIC, "Libfabric API"),
    (C_PROVIDER, "EFA Provider"),
    (C_HW, "Hardware"),
]
for i, (color, label) in enumerate(legend_items):
    col = i // 4
    row = i % 4
    bx = 1.0 + col * 9.5
    by = 2.0 - row * 0.45
    box = mpatches.FancyBboxPatch((bx, by), 0.5, 0.3, boxstyle="round,pad=0.02", facecolor=color, edgecolor="#333", linewidth=1)
    ax.add_patch(box)
    ax.text(bx + 0.7, by + 0.15, label, fontsize=9, va="center", color="#333")

plt.tight_layout()
plt.savefig("/home/ubuntu/torchcomms/tasks/efa_layered_architecture.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved efa_layered_architecture.png")
